"""
IC DONGU: klasik, sabit yapili tutus kontrolcusu (60 Hz).

=============================================================================
TASARIM GEREKCESI  (tez metnine dogrudan girebilecek ozet)
=============================================================================
JSBSim F-16 modeli CIPLAK bir ucak degildir; icinde gercek bir fly-by-wire
FLCS vardir (f16.xml):
  - roll  : fcs/aileron-cmd-norm  = normalize YATIS HIZI komutu (cmd 1 ~ 180 d/s)
  - pitch : fcs/elevator-cmd-norm = G-YUKU + pitch-rate karisim komutu,
            icinde alpha limiter (28-30 derecede komutu kesiyor)
  - yaw   : yaw damper + yanal ivme geri beslemesi

Dolayisiyla burada YENIDEN bir rate-CAS yazmak yanlis olurdu. Gercek F-16
otopilotu da FLCS'i by-pass etmez, ona komut verir. Bu modul de aynisini
yapar: FLCS'in USTUNE tutus/ucus-yolu tutucu bir katman koyar.

Kaskad yapisi (disaridan ice):
    gamma_cmd --> gamma_dot_cmd --> n_cmd (g yuku) --> elevator-cmd  [FLCS]
    phi_cmd   --> p_cmd                             --> aileron-cmd  [FLCS]
    mach_cmd  -->                                       throttle-cmd

NEDEN GAMMA (ucus yolu acisi), PITCH (theta) DEGIL?
theta = gamma + alpha. Ayni theta, farkli hizlarda farkli tirmanis hizi
demektir (alpha hiza gore degisir). Guidance katmani "ne kadar tirmanayim"
sorusunu sorar; bunun dogru degiskeni gamma'dir. Klasik havacilik kaskadi
zaten irtifa -> gamma -> theta -> q -> elevator seklindedir; RL'i gamma
katmanina koyariz.

NEDEN PITCH DONGUSU G UZERINDEN KAPANIR?
Olcumle dogrulanan kinematik bagintiya dayanir (scripts/id_fcs.py):

        gamma_dot = g * (n * cos(phi) - cos(gamma)) / V

Bunu n icin tersine cevirince istenen gamma_dot'u dogrudan bir g komutuna
ceviririz. Uc kazanci var:
  1. Alttaki FLCS zaten bir g-komut sistemi -> arayuz birebir uyusur.
  2. Nz zarfi (+9 / -3 g) DOGRUDAN bu komutta kirpilir; ayrica limiter
     yazmaya gerek kalmaz, guvenlik kisiti dogal yerinde uygulanir.
  3. 1/cos(phi) terimi YATIS TELAFISIDIR: 60 derece bankta duz ucus icin
     2.0 g gerekir. Bu terim olmazsa her donuste irtifa kaybedilir --
     koordineli donusun temel formulu budur.

NEDEN INTEGRAL SART?
Olcum (scripts/id_nz.py): elevator komutu basina elde edilen g,
komut buyuklugune gore 11.2 -> 4.7 araliginda degisiyor (alpha limiti
ve qbar yuzunden). Sabit bir ileri-besleme bu degisimi karsilayamaz;
kalici hatayi sifirlayan sey integral terimdir. Integral windup'a karsi
komut doygunlugunda integratoru dondururuz (conditional integration).

NEDEN SABIT KAZANC (ogrenilen degil)?
Ustteki RL ajaninin ogrenebilmesi icin ortamin DURAGAN (stationary) olmasi
gerekir: ayni komut her zaman ayni tepkiyi vermelidir. Kazanclarin online
degismesi ortami duragan olmaktan cikarir. Kazanclar qbar'a gore
CIZELGELENIR (gain scheduling) -- bu duraganligi bozmaz, cunku cizelge
durumun deterministik ve sabit bir fonksiyonudur.
=============================================================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..sim import aircraft as ac
from ..sim.jsbsim_bridge import FlightState


def wrap_pi(x: float) -> float:
    """Aciyi (-pi, pi] araligina sar."""
    return (x + math.pi) % (2.0 * math.pi) - math.pi


@dataclass
class PIController:
    """Kosullu integrasyonlu (anti-windup) PI kontrolcu.

    Anti-windup neden: komut doygunluga girdiginde (orn. throttle 1.0'a
    dayandi) hata integrali buyumeye devam ederse, kosul duzeldiginde
    kontrolcu uzun sure ters yonde asirilik yapar. Cozum: cikti doygunken
    ve integral doygunlugu DERINLESTIRIYORSA integratoru dondur.
    """
    kp: float
    ki: float
    lo: float = -1.0
    hi: float = 1.0
    i: float = 0.0

    def reset(self, i0: float = 0.0) -> None:
        self.i = i0

    def __call__(self, err: float, dt: float, ff: float = 0.0) -> float:
        raw = ff + self.kp * err + self.ki * self.i
        sat = float(np.clip(raw, self.lo, self.hi))
        # Kosullu integrasyon
        if (sat >= self.hi - 1e-9 and err > 0.0) or (sat <= self.lo + 1e-9 and err < 0.0):
            pass                      # doygunlugu derinlestirecek yonde birikme yok
        else:
            self.i += err * dt
        return sat


@dataclass
class InnerLoopCommand:
    """Dis dongunun (RL) ic dongyue verdigi komut. Faz-4 arayuzu de budur."""
    phi_cmd_rad: float = 0.0      # istenen yatis acisi
    gamma_cmd_rad: float = 0.0    # istenen ucus yolu acisi
    mach_cmd: float = 0.8         # istenen Mach

    def clipped(self) -> "InnerLoopCommand":
        return InnerLoopCommand(
            phi_cmd_rad=float(np.clip(self.phi_cmd_rad,
                                      -math.radians(ac.BANK_MAX_DEG),
                                      math.radians(ac.BANK_MAX_DEG))),
            gamma_cmd_rad=float(np.clip(self.gamma_cmd_rad,
                                        math.radians(ac.GAMMA_MIN_DEG),
                                        math.radians(ac.GAMMA_MAX_DEG))),
            mach_cmd=float(np.clip(self.mach_cmd, ac.MACH_MIN, ac.MACH_MAX)),
        )


@dataclass
class InnerLoopGains:
    """Elle kalibre edilmis sabit kazanclar (scripts/tune_inner_loop.py ile dogrulanir)."""
    # --- Roll: phi -> p_cmd ---
    k_phi: float = 2.5            # 1/s. phi hatasi -> istenen yatis hizi
    p_cmd_max_degs: float = 120.0 # otopilot calisma limiti (ucak 180 yapabilir)
    k_p_damp: float = 0.15        # p hatasi uzerinde kucuk oransal duzeltme
    # Sinirli yetkili integrator: bankta yanal kayma (beta) dihedral etkisiyle
    # surekli bir yuvarlanma momenti uretir; saf oransal donguyle bu ancak
    # kalici hata birakilarak dengelenir (olcum: 45 deg bankta 3.1 deg hata).
    # Yetki kasitli olarak KUCUK tutulur: buyuk integrator, hizli manevrada
    # gecikme ve asim yaratir. Trim gorevi gorur, kontrol gorevi degil.
    ki_phi: float = 0.004         # aileron birimi / (deg * s)
    i_phi_authority: float = 0.15 # integratorun uretebilecegi max aileron
    # Integrator YALNIZCA hata kucukken calisir ("integral near null").
    # Sebep: buyuk hatada integrator, manevra boyunca dolar; komut geri
    # alindiginda bosalmasi zaman alir ve ASIM yaratir (olcum: 60 deg bank
    # tutusundan cikista +14 deg asim). Integratorun isi trim, manevra degil.
    i_phi_enable_deg: float = 10.0

    # --- Pitch: gamma -> gamma_dot -> n -> elevator ---
    k_gamma: float = 1.2          # 1/s. gamma hatasi -> istenen gamma_dot
    # gamma_dot limiti SABIT DEGIL, g zarfindan turetilir (asagiya bak).
    # Bu iki degeri ic dongunun kendine tanidigi calisma yetkisidir; ucagin
    # yapisal limiti (NZ_MAX=9 / NZ_MIN=-3) degildir. Aradaki fark, ustteki
    # guvenlik katmanina (CBF) birakilan paydir.
    n_cmd_max: float = 7.0
    n_cmd_min: float = -2.0
    gamma_dot_max_degs: float = 25.0   # mutlak ust sinir (yumusaklik icin)
    k_dn_nominal: float = 8.0     # birim (-)elevator komutu basina delta-g (olculdu)
    kp_n: float = 0.060
    ki_n: float = 0.150
    k_q_damp: float = 0.020       # pitch hizi sonumleme (PIO onleyici)

    # --- Autothrottle: mach -> throttle ---
    # Tesis bir INTEGRATORDUR (fazla itki -> ivme -> hiz). PI ile kapali
    # cevrim ikinci mertebe olur:  s^2 + k*kp*s + k*ki = 0
    #   wn = sqrt(k*ki),   zeta = kp*sqrt(k) / (2*sqrt(ki))
    # k = dMach/dt birim gaz basina; olcum (scripts/id_fcs.py):
    #   ~0.030 (15 kft)  ...  ~0.012 (40 kft)
    # kp=10, ki=0.5 -> zeta 0.8 (yuksek irtifa) ... 1.2 (alcak irtifa)
    # Onceki kp=4, ki=0.3 -> zeta 0.40, olculen asim %30 ile birebir uyusuyordu.
    kp_m: float = 10.0
    ki_m: float = 0.50

    # --- Yaw: koordinasyon ---
    k_beta: float = 0.8           # yanal kayma -> rudder (FLCS damperinin ustune)


class InnerLoop:
    """FLCS uzerine oturan tutus / ucus-yolu / hiz tutucu.

    Kullanim:
        il = InnerLoop(dt=1/60)
        il.reset(trim_throttle=sim["fcs/throttle-cmd-norm"])
        el, ail, thr, rud = il.update(state, InnerLoopCommand(...))
    """

    def __init__(self, dt: float = 1.0 / 60.0, gains: Optional[InnerLoopGains] = None):
        self.dt = dt
        self.g = gains or InnerLoopGains()
        self.pi_n = PIController(self.g.kp_n, self.g.ki_n,
                                 lo=ac.ELEVATOR_CMD_MIN, hi=ac.ELEVATOR_CMD_MAX)
        self.pi_m = PIController(self.g.kp_m, self.g.ki_m, lo=0.0, hi=1.0)
        self._i_phi = 0.0
        self._last = {}

    def reset(self, trim_throttle: float = ac.THROTTLE_MIL) -> None:
        """Integratorleri sifirla; throttle integratorunu TRIM degerine tohumla.

        Tohumlama neden: Mach dongusu cok yavas (olcum: tam gazda bile
        ~0.01-0.02 Mach/s). Integratoru sifirdan baslatmak, ucagin bolum
        basinda gereksizce yavaslamasina/hizlanmasina yol acar. Trim degeri
        zaten "bu kosulda duz ucus icin gereken gaz"tir; dogru baslangictir.
        """
        self.pi_n.reset(0.0)
        # PI ciktisi = kp*err + ki*i  oldugundan, i0 = thr_trim / ki
        self.pi_m.reset(trim_throttle / max(self.g.ki_m, 1e-6))
        self._i_phi = 0.0
        self._last = {}

    # ------------------------------------------------------------------
    def update(self, st: FlightState, cmd: InnerLoopCommand):
        """Bir kontrol adimi. Donen: (elevator, aileron, throttle, rudder)."""
        g = self.g
        c = cmd.clipped()
        dt = self.dt

        # =============== ROLL KANALI ===============
        # phi hatasi -> istenen yatis hizi -> FLCS'in hiz komutuna normalize
        phi_err = wrap_pi(c.phi_cmd_rad - st.phi_rad)
        p_cmd_degs = float(np.clip(math.degrees(phi_err) * g.k_phi,
                                   -g.p_cmd_max_degs, g.p_cmd_max_degs))
        p_now_degs = math.degrees(st.p_rads)
        # Ileri-besleme (FLCS zaten hiz dongusunu kapatiyor) + kucuk duzeltme
        aileron_pd = (p_cmd_degs / ac.P_CMD_MAX_DEGS
                      + g.k_p_damp * (p_cmd_degs - p_now_degs) / ac.P_CMD_MAX_DEGS)
        # Sinirli yetkili integrator (aileron trimi)
        i_term = float(np.clip(g.ki_phi * self._i_phi,
                               -g.i_phi_authority, g.i_phi_authority))
        aileron_raw = aileron_pd + i_term
        aileron = float(np.clip(aileron_raw, -1.0, 1.0))
        # Kosullu integrasyon: ne aileron doygunken ne de integrator kendi
        # yetki sinirindayken, hatayi derinlestirecek yonde birikme yapma.
        phi_err_deg = math.degrees(phi_err)
        at_auth = abs(i_term) >= g.i_phi_authority - 1e-9
        saturating = (aileron_raw > 1.0 and phi_err_deg > 0) or \
                     (aileron_raw < -1.0 and phi_err_deg < 0) or \
                     (at_auth and math.copysign(1.0, i_term) == math.copysign(1.0, phi_err_deg))
        near_null = abs(phi_err_deg) <= g.i_phi_enable_deg
        if near_null and not saturating:
            self._i_phi += phi_err_deg * dt
        elif not near_null:
            # Buyuk hatada integratoru yavasca sifira sizdir (leaky integrator):
            # manevra sirasinda birikmesin, ama tutus sirasinda bulduğu trimi
            # de aniden kaybetmesin.
            self._i_phi *= math.exp(-dt / 1.5)

        # =============== PITCH KANALI ===============
        gamma_err = wrap_pi(c.gamma_cmd_rad - st.gamma_rad)

        # cos(phi) 0'a giderken patlamasin diye 75 dereceden kirpilir.
        cos_phi = max(math.cos(st.phi_rad), math.cos(math.radians(75.0)))
        v = max(st.vt_fps, 100.0)

        # --- gamma_dot limitini G ZARFINDAN TURET ---
        # Kinematik:  gamma_dot = g*(n*cos(phi) - cos(gamma))/V
        # Sabit bir gamma_dot limiti hiza gore anlamsizdir: M1.1'de 15 deg/s
        # ~9 g ister, M0.5'te ~4 g. Limiti dogrudan izin verilen g'den
        # hesaplarsak komut hicbir zaman ulasilamaz olmaz; boylece PI
        # doygunluga girmez ve (ileride) Koopman veri seti temiz kalir.
        cos_gam = math.cos(st.gamma_rad)
        gd_up = ac.G_FPS2 * (g.n_cmd_max * cos_phi - cos_gam) / v      # rad/s
        gd_dn = ac.G_FPS2 * (g.n_cmd_min * cos_phi - cos_gam) / v      # rad/s (negatif)
        gd_max = math.radians(g.gamma_dot_max_degs)
        gamma_dot_cmd_rads = float(np.clip(
            math.radians(math.degrees(gamma_err) * g.k_gamma),
            max(gd_dn, -gd_max), min(gd_up, gd_max)))

        # Kinematigi n icin ters cevir
        n_cmd = (v * gamma_dot_cmd_rads / ac.G_FPS2 + cos_gam) / cos_phi
        n_cmd = float(np.clip(n_cmd, ac.NZ_MIN, ac.NZ_MAX))
        gamma_dot_cmd = math.degrees(gamma_dot_cmd_rads)

        # Olculen etkin g (isaret konvansiyonu id_nz.py ile dogrulandi:
        # JSBSim n-pilot-z-norm duz ucusta -1.0 okur)
        n_eff = -st.nz
        n_err = n_cmd - n_eff

        # Ileri-besleme: duz ucus (n=1) icin elevator=0 oldugundan,
        # gereken fazla g'yi olculen dn/dcmd egimiyle komuta cevir.
        # NEGATIF elevator = burun yukari oldugu icin isaret ters.
        k_dn = self._k_dn_scheduled(st)
        el_ff = -(n_cmd - 1.0) / k_dn
        # PI duzeltme. Hata isareti ters cevrilir cunku NEGATIF elevator
        # komutu POZITIF g uretir (bkz. aircraft.ELEVATOR_CMD_MIN yorumu).
        elevator = self.pi_n(-n_err, dt, ff=el_ff)
        elevator = float(np.clip(elevator, ac.ELEVATOR_CMD_MIN, ac.ELEVATOR_CMD_MAX))

        # =============== THROTTLE KANALI ===============
        mach_err = c.mach_cmd - st.mach
        throttle = self.pi_m(mach_err, dt)

        # =============== YAW KANALI ===============
        # FLCS'in kendi yaw damperi var; buradaki terim yalnizca kalici
        # yanal kaymayi (beta) sifira ceken ince bir koordinasyon duzeltmesi.
        rudder = float(np.clip(-g.k_beta * st.beta_rad, -0.3, 0.3))

        self._last = dict(p_cmd_degs=p_cmd_degs, i_phi=self._i_phi, n_cmd=n_cmd, n_eff=n_eff,
                          gamma_dot_cmd=gamma_dot_cmd, k_dn=k_dn,
                          phi_err_deg=math.degrees(phi_err),
                          gamma_err_deg=math.degrees(gamma_err),
                          mach_err=mach_err)
        return elevator, aileron, throttle, rudder

    # ------------------------------------------------------------------
    def _k_dn_scheduled(self, st: FlightState) -> float:
        """Birim elevator komutu basina delta-g (qbar'a gore cizelgelenmis).

        Olculen (scripts/id_nz.py, 20 kft / M0.8, qbar ~535 psf):
            kucuk cekis  -> ~9.2
            orta cekis   -> ~7.0
            tam cekis    -> ~4.7   (alpha limiti devrede)
        Aerodinamik moment ~ qbar ile olcekledigi icin kazanci qbar ile
        oranlariz. Kalan hatayi PI'nin integrali kapatir; bu yuzden
        cizelgenin cok hassas olmasi gerekmez -- amaci sadece PI'ye
        makul bir baslangic vermek ve zarf ucunda salinimi onlemek.
        """
        qbar_ref = 535.0
        qbar = max(st.qbar_psf, 50.0)
        scale = float(np.clip((qbar / qbar_ref) ** 0.5, 0.45, 1.6))
        return self.g.k_dn_nominal * scale

    @property
    def debug(self) -> dict:
        return dict(self._last)
