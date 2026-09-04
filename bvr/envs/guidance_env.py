"""
DIS DONGU (GUIDANCE) RL ORTAMI.

=============================================================================
AJANIN ISI NE?
=============================================================================
Ajan LEVYE KULLANMAZ. Ajanin isi, verilen hedefe (konum + irtifa + hiz)
ulasmak icin UCUS KOMUTU secmektir:

        aksiyon = [ phi_cmd, gamma_cmd, mach_cmd ]

Bu komutlari fiziksel yuzey hareketine ceviren sey klasik ic dongudur
(bvr/control/inner_loop.py). Yani ajan "pilot", ic dongu "otopilot",
JSBSim FLCS "uctagin refleksleri".

10 Hz'de karar verir; ic dongu 60 Hz, FDM 120 Hz calisir.

=============================================================================
GOZLEM TASARIMI: HAM DEGIL, HATA
=============================================================================
Ajana ham (X, Y, irtifa, Mach) vermek yerine HATA veriyoruz: yon hatasi,
menzil, irtifa hatasi, hiz hatasi. Sebep: ajanin ogrenmesi gereken sey
"hedefle aramdaki farki nasil kapatirim"dir; ham koordinat verirsek
once cikarma islemini ogrenmesi gerekir -- gereksiz yuk.

Yon hatasi SIN/COS olarak verilir. Ham aci verilseydi +179 ile -179
derece arasinda gozlemde SICRAMA olurdu; sinir ag bunu sureksizlik
olarak gorur. sin/cos gosterimi bu sureksizligi tamamen kaldirir.

=============================================================================
ODUL TASARIMI: SINIRLI VE POZITIF
=============================================================================
Adim odulu kabaca [-1, +2.5] araligindadir. Bu KASITLIDIR:
  - Odul normalizasyonuna (VecNormalize) hic ihtiyac kalmaz; eski
    mimaride -500000'lik carpma cezasi normalizasyon istatistigini
    sisirip butun izleme sinyalinin gradyanini eziyordu.
  - POZITIF terim vardir. Sadece cezadan olusan bir odul, ajana "ne
    yapmali"yi degil yalnizca "ne yapmamali"yi ogretir; kesif coker.
  - Carpma cezasi kucuktur (-10). Asil caydiricilik sayinin buyuklugu
    degil, BOLUMUN BITMESI ve gelecekteki tum odulun kaybidir.

Ana navigasyon sinyali ILERLEME (progress) odulu: menzilin kapanma hizi,
ucagin kendi hiziyla normalize edilir -> dogal olarak [-1, 1] araliginda
kalir ve hiza gore olcek degistirmez.
=============================================================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ..sim import aircraft as ac
from ..sim.jsbsim_bridge import F16Sim
from ..control.inner_loop import InnerLoop, InnerLoopCommand
from ..models.state_def import state_from_flight, cmd_to_u

OBS_DIM = 19
ACT_DIM = 3


@dataclass
class GuidanceConfig:
    ctrl_hz: float = 60.0
    outer_hz: float = 10.0
    episode_s: float = 180.0

    # Baslangic zarfi
    alt_lo: float = 10000.0
    alt_hi: float = 42000.0

    # Hedef uretimi
    wpt_range_lo_ft: float = 20000.0     # ~3.3 nmi
    wpt_range_hi_ft: float = 90000.0     # ~15 nmi
    wpt_capture_ft: float = 3000.0       # bu yaricapta "varildi" sayilir
    alt_delta_ft: float = 8000.0         # hedef irtifa sapmasi araligi
    mach_lo: float = 0.55
    mach_hi: float = 1.35

    # Tolerans (basari tanimi ve bonus icin)
    alt_tol_ft: float = 500.0
    mach_tol: float = 0.05

    # ---------------- Odul ----------------
    # reward_version:
    #   1 = SADECE Gauss "hassasiyet" terimi (ILK TASARIM -- KUSURLU)
    #   2 = ilerleme (progress) + hassasiyet  (varsayilan)
    #
    # v1'in kusuru: exp(-(dh/1000)^2) terimi 3000 ft hatada 1e-4'tur.
    # Hedefler +-8000 ft'e kadar uzakta uretildigi icin ajan irtifa
    # konusunda UZAKTAYKEN HIC GRADYAN GORMEZ; yogun sanilan odul aslinda
    # gizli bir SEYREK odul problemidir. Ayni kusur Mach'ta da vardir
    # (0.2 hatada terim 0.002, hedef araligi ise 0.55-1.35).
    #
    # v2 cozumu: her kanala, menzilde kullandigimizin aynisi olan
    # ILERLEME odulu eklenir -- "hata her adimda ne kadar kapandi",
    # kanalin FIZIKSEL max degisim hiziyla normalize edilir, [-1,1].
    # Bu her uzaklikta gradyan verir; Gauss terimi ise yalnizca son
    # hassasiyeti odullendirir. (Potansiyel-temelli odul sekillendirmenin
    # sinirlanmis, pratik bir bicimi.)
    reward_version: int = 2
    w_progress: float = 1.0
    # ODUL DENGESI (olcumle duzeltildi).
    # Onceki agirliklar: ilerleme 1.0, irtifa 1.0, Mach 0.5 -> ajan Mach'i
    # RASYONEL olarak onemsemedi. Olculen sonuc: irtifa toleransi %86,
    # Mach toleransi %30, Mach RMSE 0.20. Ajanin hatasi degil; ona oyle
    # soylemistik. Uc kanal artik dengeli:  ilerleme 1.0 | irtifa 0.9 | Mach 0.9
    w_alt_prog: float = 0.5
    w_alt_prec: float = 0.4
    w_mach_prog: float = 0.5
    w_mach_prec: float = 0.4
    # Hedef Mach'in bir onceki hedeften ne kadar sicrayabilecegi.
    # Onceden her bacakta [taban, 1.35] araligindan BAGIMSIZ cekiliyordu;
    # 0.8'lik sicramalar autothrottle icin (0.009-0.02 Mach/s) 40+ saniye
    # demekti -- yani fiziksel olarak ulasilamaz hedefler. Gercek bir
    # komutan da M0.6'dan M1.3'e sicramaz. Sinirli rastgele yuruyus hem
    # gercekci hem ulasilabilir.
    mach_step_max: float = 0.25
    # v1 uyumlulugu icin
    w_alt: float = 1.0
    w_mach: float = 0.5
    # Ilerleme normalizasyonu: adim basina FIZIKSEL olarak mumkun max degisim
    alt_prog_scale_ft: float = 25.0      # ~250 ft/s dikey hiz x 0.1 s
    mach_prog_scale: float = 0.004       # ~0.04 Mach/s (g cekerken frenleme dahil)
    alt_prec_ft: float = 1000.0
    mach_prec: float = 0.08

    # ---------------- Komut yumusakligi ----------------
    # Olcum (scripts/diagnose_policy.py): duzeltilmeden once ajan
    # komutunu her ~1.6 adimda bir TERS cevirivordu (yon degistirme
    # orani %63, ~3 Hz bang-bang), adimlarin %16'sinda komut tam
    # araligin dortte birinden fazla siciriyordu. Iki sebep:
    #   1. w_action_rate=0.05 cok kucuktu: adim basina ~0.012 ceza
    #      uretirken oduller ~1.3 mertebesindeydi (agirlik ~%1).
    #   2. Ortamda hicbir yapisal duzgunluk kisiti yoktu.
    #
    # Iki cozum birlikte uygulanir:
    #   - action_rate_limit: KOMUT SLEW SINIRI. Gercek bir gudum sistemi
    #     de komutu 10 Hz'de tam olcekte savurmaz; bu, klasik kontroldeki
    #     komut sekillendirme filtresinin karsiligidir. Duzgunlugu
    #     YAPISAL olarak garanti eder.
    #   - w_action_rate: ajanin sinira surekli dayanmasini caydirir.
    # Ceza, ajanin ham istegi ile bir onceki UYGULANAN komut arasindaki
    # farka verilir; boylece hem titreme hem de "kalkanla kavga etme"
    # cezalandirilmis olur.
    action_rate_limit: float = 0.25      # adim basina max |da| (None = kapali)
    w_action_rate: float = 0.30
    r_waypoint: float = 10.0
    r_crash: float = -10.0

    # Zarf ihlali sonlandirma (ic dongu zaten kirpiyor; bunlar SON siniir)
    term_alpha_deg: float = 26.0
    term_beta_deg: float = 15.0
    term_nz_hi: float = 9.5
    term_nz_lo: float = -3.5
    term_mach_lo: float = 0.30

    # ---------------- Alan rastgelelestirmesi (domain randomization) ----------------
    # Ruzgar/turbulans + YAKIT (dolayisiyla agirlik ve CG).
    # Yakit rastgelelestirmesi kritik: agirlik 19.500-24.600 lb arasinda
    # degisir, bu da stall hizini, donus oranini ve ivmelenmeyi degistirir.
    # Sabit yakitla egitilen politika agirlik degistiginde genellemez.
    turbulence_prob: float = 0.3
    wind_max_fps: float = 60.0
    fuel_lo: float = 0.30
    fuel_hi: float = 1.00

    # ---------------- Guvenlik kalkani (CBF) ----------------
    # Varsayilan KAPALI. Once kalkansiz taban cizgisi olculur; kalkanin
    # marjinal katkisi ancak o tabana gore anlamlidir. Ucunu ayni anda
    # devreye almak (RL + model + kalkan) eski projenin teshis edilemez
    # hale gelmesinin sebebiydi.
    use_shield: bool = False
    shield_model_path: str = "data/models/edmd_physics.pkl"
    shield_gamma: float = 0.1
    # None = CBFShield.DEFAULT_HORIZONS kullanilir. TEK DOGRULUK KAYNAGI
    # kalkanin kendisidir; burada bir kopya tutmak, kalkanin varsayilani
    # degistiginde SESSIZCE eski degeri dayatir -- olculdu: uzun ufuklar
    # eklendigi halde egitim hala 4 kisa ufukla kosuyordu.
    shield_horizons: Optional[tuple] = None
    shield_hard: bool = False
    # Robust CBF marji: bvr/safety/robust.py ile onceden hesaplanip
    # .npy olarak kaydedilir. None = sikilastirma yok (nominal CBF).
    shield_margin_path: Optional[str] = None


class GuidanceEnv(gym.Env):
    """Dis dongu guidance gorevi (kalkansiz taban surum)."""

    metadata = {"render_modes": []}

    def __init__(self, cfg: Optional[GuidanceConfig] = None,
                 seed: Optional[int] = None, recorder=None):
        super().__init__()
        self.cfg = cfg or GuidanceConfig()
        self.observation_space = spaces.Box(-np.inf, np.inf, (OBS_DIM,), np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, (ACT_DIM,), np.float32)

        self.sim = F16Sim(seed=seed)
        self.inner = InnerLoop(dt=1.0 / self.cfg.ctrl_hz)
        self._sub = int(round(self.sim.fdm_hz / self.cfg.ctrl_hz))
        self._inner_per_outer = int(round(self.cfg.ctrl_hz / self.cfg.outer_hz))
        self._max_steps = int(self.cfg.episode_s * self.cfg.outer_hz)

        self.recorder = recorder          # istege bagli ACMIRecorder
        self._rng = np.random.default_rng(seed)
        # _last_action  : ajanin KENDI komutu -> aksiyon degisim cezasi icin
        #                 (ajan yalnizca bundan sorumludur)
        # _last_applied : kalkandan CIKAN, fiilen uygulanan komut -> GOZLEME
        #                 bu girer. Kalkanin hiz sinirlayicisi statefuldir;
        #                 uygulanan komut gozlemde olmazsa ortam Markov
        #                 olmaktan cikar. Kalkan kapaliyken ikisi aynidir.
        self._last_action = np.zeros(ACT_DIM)
        self._last_applied = np.zeros(ACT_DIM)
        self._prev_applied = np.zeros(ACT_DIM)
        self._st = None

        self.shield = None
        if self.cfg.use_shield:
            from ..models.base import DynamicsModel
            from ..safety.cbf import CBFShield
            model = DynamicsModel.load(self.cfg.shield_model_path)
            margins = (np.load(self.cfg.shield_margin_path)
                       if self.cfg.shield_margin_path else None)
            self.shield = CBFShield(model, gamma=self.cfg.shield_gamma,
                                    horizons=(tuple(self.cfg.shield_horizons)
                                              if self.cfg.shield_horizons else None),
                                    hard=self.cfg.shield_hard, margins=margins)

    # ------------------------------------------------------------------
    # Aksiyon <-> fiziksel komut
    # ------------------------------------------------------------------
    def _action_to_cmd(self, a: np.ndarray) -> InnerLoopCommand:
        """[-1,1]^3 -> fiziksel komut. Aralikllar aircraft.py'deki zarftan gelir."""
        a = np.clip(np.asarray(a, dtype=np.float64), -1.0, 1.0)
        phi = a[0] * math.radians(ac.BANK_MAX_DEG)
        gam = a[1] * math.radians(ac.GAMMA_MAX_DEG)
        mach = self.cfg.mach_lo + 0.5 * (a[2] + 1.0) * (self.cfg.mach_hi - self.cfg.mach_lo)
        return InnerLoopCommand(phi, gam, mach)

    def _cmd_to_action(self, cmd: InnerLoopCommand) -> np.ndarray:
        """_action_to_cmd'in tersi. Kalkandan cikan komutu gozleme koymak icin."""
        span = max(self.cfg.mach_hi - self.cfg.mach_lo, 1e-9)
        return np.clip(np.array([
            cmd.phi_cmd_rad / math.radians(ac.BANK_MAX_DEG),
            cmd.gamma_cmd_rad / math.radians(ac.GAMMA_MAX_DEG),
            2.0 * (cmd.mach_cmd - self.cfg.mach_lo) / span - 1.0,
        ]), -1.0, 1.0)

    # ------------------------------------------------------------------
    def _new_waypoint(self) -> None:
        c, st = self.cfg, self._st
        brg = self._rng.uniform(0, 2 * math.pi)
        rng_ft = self._rng.uniform(c.wpt_range_lo_ft, c.wpt_range_hi_ft)
        self.tgt_n = st.north_ft + rng_ft * math.cos(brg)
        self.tgt_e = st.east_ft + rng_ft * math.sin(brg)
        self.tgt_alt = float(np.clip(
            st.alt_ft + self._rng.uniform(-c.alt_delta_ft, c.alt_delta_ft),
            c.alt_lo, c.alt_hi))
        # Hedef Mach, HEDEF IRTIFADAKI fiziksel tabanin uzerinde uretilir.
        # Onceki hali sabit [0.55, 1.35] idi; 42 kft'te taban 0.68 oldugu
        # icin ajana ULASILAMAZ hedefler veriliyordu -- ajan hedefi
        # tutturmak icin stall bolgesine iniyordu. Yani "mach_min ihlali"
        # nin bir kismi ajanin hatasi degil, GOREV URETIMININ hatasiydi.
        m_floor = ac.mach_floor(self.tgt_alt) + 0.05
        lo, hi = max(c.mach_lo, m_floor), c.mach_hi
        prev = getattr(self, "tgt_mach", None)
        if prev is None:
            self.tgt_mach = float(self._rng.uniform(lo, hi))
        else:
            # Sinirli rastgele yuruyus: bir onceki hedefin +-mach_step_max
            # komsulugundan sec, sonra fiziksel bandda kirp.
            d = c.mach_step_max
            self.tgt_mach = float(np.clip(
                self._rng.uniform(prev - d, prev + d), lo, hi))
        # Ilerleme referanslarini YENI hedefe gore sifirla. Aksi halde hedef
        # degistigi adimda hata birden siciriyor ve ajan hic yapmadigi bir
        # sey icin buyuk bir "gerileme" cezasi aliyor.
        self._prev_range = self._range_to_target()
        self._prev_alt_err = abs(self.tgt_alt - st.alt_ft)
        self._prev_mach_err = abs(self.tgt_mach - st.mach)

    def _range_to_target(self) -> float:
        st = self._st
        return math.hypot(self.tgt_n - st.north_ft, self.tgt_e - st.east_ft)

    def _bearing_error(self) -> float:
        st = self._st
        brg = math.atan2(self.tgt_e - st.east_ft, self.tgt_n - st.north_ft)
        e = brg - st.psi_rad
        return (e + math.pi) % (2 * math.pi) - math.pi

    # ------------------------------------------------------------------
    def _obs(self) -> np.ndarray:
        st = self._st
        be = self._bearing_error()
        rng_ft = self._range_to_target()
        o = np.array([
            math.sin(be), math.cos(be),
            min(rng_ft / 50000.0, 3.0),
            (self.tgt_alt - st.alt_ft) / 5000.0,
            (self.tgt_mach - st.mach) / 0.30,
            st.phi_rad,
            st.gamma_rad / 0.40,
            st.alpha_rad / 0.20,
            st.beta_rad / 0.10,
            (-st.nz - 1.0) / 3.0,
            st.p_rads / 1.50,
            st.q_rads / 0.40,
            (st.mach - 0.90) / 0.40,
            (st.alt_ft - 25000.0) / 12000.0,
            st.h_dot_fps / 300.0,
            # UYGULANAN komut (kalkan kapaliyken ajanin komutuyla ayni)
            self._last_applied[0], self._last_applied[1], self._last_applied[2],
            # YAKIT ORANI -> agirlik. Politikanin agirligi GORMESI gerekir:
            # ayni gamma komutu 19.900 lb ile 23.900 lb'de farkli tirmanis
            # hizi verir, stall payi da farklidir. Gercek otopilotlar da
            # agirliga gore kazanc cizelgeler. Ayrica BVR fazinda fuze
            # atisi ~350 lb agirlik dusurur; agirliga duyarli bir politika
            # bu gecisi puruzsuz karsilar.
            (st.fuel_frac - 0.65) / 0.35,
        ], dtype=np.float32)
        return np.nan_to_num(o, nan=0.0, posinf=5.0, neginf=-5.0)

    # ------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        c = self.cfg

        # Trim tekrar tekrar basarisiz olursa BOLUM COKMEMELIDIR: paralel
        # egitimde olen bir worker butun kosuyu dusurur (BrokenPipe).
        # Kademeli geri cekilme: rastgele nokta -> guvenli nokta -> yeni sim.
        ok = False
        for attempt in range(8):
            if attempt < 6:
                alt0 = float(self._rng.uniform(c.alt_lo, c.alt_hi))
                frac = (alt0 - c.alt_lo) / max(c.alt_hi - c.alt_lo, 1.0)
                m_lo = max(0.60 + 0.15 * frac, ac.mach_floor(alt0) + 0.08)
                m0 = float(self._rng.uniform(m_lo, 1.10 + 0.25 * frac))
            else:
                alt0, m0 = 20000.0, 0.80      # bilinen guvenli nokta
            if attempt == 7:
                self.sim = F16Sim(seed=int(self._rng.integers(1 << 30)))
            try:
                self._st = self.sim.reset(
                    alt_ft=alt0, mach=m0,
                    heading_deg=float(self._rng.uniform(0, 360)), trim=True,
                    fuel_frac=float(self._rng.uniform(c.fuel_lo, c.fuel_hi)))
                if self.sim.trimmed and np.isfinite(self._st.alt_ft):
                    ok = True
                    break
            except Exception:
                continue
        if not ok:
            raise RuntimeError("trim hicbir kosulda yakinsamadi")

        if self._rng.random() < c.turbulence_prob:
            self.sim.set_turbulence(
                wind_fps=float(self._rng.uniform(0, c.wind_max_fps)),
                wind_dir_deg=float(self._rng.uniform(0, 360)),
                turb_severity=int(self._rng.integers(0, 4)))

        self.inner.reset(trim_throttle=self.sim["fcs/throttle-cmd-norm"])
        if self.shield is not None:
            self.shield.reset_state()   # komut hiz sinirlayicinin hafizasi
        self._last_action = np.zeros(ACT_DIM)
        self._last_applied = np.zeros(ACT_DIM)
        self._prev_applied = np.zeros(ACT_DIM)
        self._k = 0
        self._n_waypoints = 0
        # Rastgele yuruyus bolum icinde gecerlidir; yeni bolum bagimsiz
        # bir Mach hedefiyle baslar (aksi halde onceki bolumun son hedefi
        # sizar ve baslangic dagilimi daralir).
        self.tgt_mach = None
        # Bolum sonunda TensorBoard'a yazilacak tanilar
        self._diag = dict(alt_err=[], mach_err=[], dact=[], alpha=[], nz_hi=[],
                          nz_lo=[], beta=[], mach_marg=[], stall_marg=[])
        self._new_waypoint()
        return self._obs(), {}

    # ------------------------------------------------------------------
    def step(self, action):
        c = self.cfg
        a_raw = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        self._prev_applied = self._last_applied.copy()   # ceza referansi

        # KOMUT SLEW SINIRI (bkz. GuidanceConfig.action_rate_limit).
        # Referans, bir onceki UYGULANAN komuttur ve o gozlemde bulundugu
        # icin ortam Markov kalir.
        if c.action_rate_limit is not None:
            lim = float(c.action_rate_limit)
            a = np.clip(a_raw, self._last_applied - lim, self._last_applied + lim)
        else:
            a = a_raw
        cmd = self._action_to_cmd(a)

        # ---------------- GUVENLIK KALKANI ----------------
        # Kalkan ORTAMIN parcasidir: ajan ne isterse istesin, uygulanan sey
        # projekte edilmis komuttur. Replay buffer'a ajanin KENDI aksiyonu
        # yazilir ("bunu istersem su olur" ogrenilir); bu, shielding
        # literaturundeki standart ve tutarli secimdir. Alternatif (uygulanan
        # aksiyonu yazmak) SAC'in entropi terimiyle tutarsizlik yaratir.
        shield_info = None
        if self.shield is not None:
            u_des = cmd_to_u(cmd)
            u_safe, shield_info = self.shield.filter(state_from_flight(self._st), u_des)
            cmd = InnerLoopCommand(float(u_safe[0]), float(u_safe[1]),
                                   float(u_safe[2])).clipped()
        self._last_applied = self._cmd_to_action(cmd)

        # Bir dis dongu adimi = inner_per_outer ic dongu adimi (ZOH komut)
        #
        # ADIM-ICI ZARF TAKIBI: zarf asimlarini yalnizca dis dongu
        # sinirinda (10 Hz) olcmek YANILTICIDIR -- iki karar arasindaki
        # 0.1 saniyede olusan tepe degerleri gorunmez kalir ve ihlaller
        # oldugundan AZ raporlanir. Alt adimlarin hepsinde tepe tutulur.
        # mach_marg: Mach ile IRTIFAYA BAGLI taban arasindaki en kucuk pay.
        # Taban irtifayla degistigi icin ham min-Mach yeterli degil.
        pk = dict(alpha=0.0, beta=0.0, nz_hi=-9e9, nz_lo=9e9, mach_lo=9e9,
                  mach_marg=9e9, stall_marg=9e9)
        for _ in range(self._inner_per_outer):
            el, ail, thr, rud = self.inner.update(self._st, cmd)
            self.sim.send_fcs(el, ail, thr, rud)
            self._st = self.sim.run(self._sub)
            s = self._st
            n_eff = -s.nz
            pk["alpha"] = max(pk["alpha"], abs(math.degrees(s.alpha_rad)))
            pk["beta"] = max(pk["beta"], abs(math.degrees(s.beta_rad)))
            pk["nz_hi"] = max(pk["nz_hi"], n_eff)
            pk["nz_lo"] = min(pk["nz_lo"], n_eff)
            pk["mach_lo"] = min(pk["mach_lo"], s.mach)
            # BARIYER payi: muhafazakar sabit agirlikla (CBF'in gordugu)
            pk["mach_marg"] = min(pk["mach_marg"],
                                  s.mach - float(ac.mach_floor(s.alt_ft)))
            # GERCEK stall payi: anlik agirlikla. IHLAL RAPORLAMASI bunu
            # kullanir. Bariyerin kasitli muhafazakarligini "ihlal" saymak,
            # metrigi sisirir ve filtreyi haksiz yere kotu gosterir.
            w = self.sim["inertia/weight-lbs"]
            pk["stall_marg"] = min(pk["stall_marg"], s.mach - ac.STALL_MARGIN_FACTOR
                                   * float(ac.true_stall_mach(s.alt_ft, w)))
        self._intra = pk
        st = self._st
        self._k += 1

        if self.recorder is not None:
            self.recorder.record(st, extra={
                "PhiCmd": math.degrees(cmd.phi_cmd_rad),
                "GammaCmd": math.degrees(cmd.gamma_cmd_rad),
                "MachCmd": cmd.mach_cmd,
                "TgtAlt": self.tgt_alt, "TgtMach": self.tgt_mach,
                "RangeNm": self._range_to_target() / 6076.0,
            })

        # ---------------- ODUL ----------------
        rng_ft = self._range_to_target()
        dt = 1.0 / c.outer_hz
        # Ilerleme: menzil kapanma hizi / ucagin kendi hizi -> [-1, 1]
        closure = (self._prev_range - rng_ft) / max(st.vt_fps * dt, 1.0)
        self._prev_range = rng_ft
        r = c.w_progress * float(np.clip(closure, -1.0, 1.0))

        alt_err = self.tgt_alt - st.alt_ft
        mach_err = self.tgt_mach - st.mach
        if c.reward_version == 1:
            # Eski (kusurlu) tasarim: uzaktayken gradyan yok. Ablasyon icin durur.
            r += c.w_alt * math.exp(-(alt_err / c.alt_prec_ft) ** 2)
            r += c.w_mach * math.exp(-(mach_err / c.mach_prec) ** 2)
        else:
            # Ilerleme: hata her adimda ne kadar kapandi (fiziksel max ile
            # normalize) -> her uzaklikta gradyan var.
            d_alt, d_mach = abs(alt_err), abs(mach_err)
            r += c.w_alt_prog * float(np.clip(
                (self._prev_alt_err - d_alt) / c.alt_prog_scale_ft, -1.0, 1.0))
            r += c.w_mach_prog * float(np.clip(
                (self._prev_mach_err - d_mach) / c.mach_prog_scale, -1.0, 1.0))
            # Hassasiyet: yalnizca hedefe yakinken odullendirir
            r += c.w_alt_prec * math.exp(-(alt_err / c.alt_prec_ft) ** 2)
            r += c.w_mach_prec * math.exp(-(mach_err / c.mach_prec) ** 2)
            self._prev_alt_err, self._prev_mach_err = d_alt, d_mach
        # Yumusaklik cezasi: ajanin HAM istegi ile bir onceki UYGULANAN
        # komut arasindaki fark. Boylece hem titreme, hem de slew sinirina
        # ya da kalkana surekli dayanma (kavga etme) cezalandirilir.
        r -= c.w_action_rate * float(np.sum((a_raw - self._prev_applied) ** 2))
        self._last_action = a

        # ---------------- TANI TOPLAMA (TensorBoard) ----------------
        d = self._diag
        d["alt_err"].append(abs(alt_err)); d["mach_err"].append(abs(mach_err))
        d["dact"].append(float(np.sum((a_raw - self._prev_applied) ** 2)))
        d["alpha"].append(pk["alpha"]); d["beta"].append(pk["beta"])
        d["nz_hi"].append(pk["nz_hi"]); d["nz_lo"].append(pk["nz_lo"])
        d["mach_marg"].append(pk["mach_marg"]); d["stall_marg"].append(pk["stall_marg"])

        info = {}
        # ---------------- HEDEFE VARIS ----------------
        in_alt = abs(alt_err) <= c.alt_tol_ft
        in_mach = abs(mach_err) <= c.mach_tol
        if rng_ft <= c.wpt_capture_ft:
            # Tam basari = konum + irtifa + hiz. Kismi varisa kismi odul.
            bonus = c.r_waypoint * (0.4 + 0.4 * in_alt + 0.2 * in_mach)
            r += bonus
            self._n_waypoints += 1
            info["waypoint"] = dict(alt_ok=bool(in_alt), mach_ok=bool(in_mach))
            self._new_waypoint()

        # ---------------- SONLANDIRMA ----------------
        terminated = False
        reason = ""
        alpha_deg = math.degrees(st.alpha_rad)
        beta_deg = math.degrees(st.beta_rad)
        n_eff = -st.nz
        if not np.isfinite(st.alt_ft) or not np.isfinite(st.mach):
            terminated, reason = True, "nan"
        elif st.alt_ft < ac.TERM_DECK_FT:
            terminated, reason = True, "hard_deck"
        elif st.alt_ft > ac.ALT_MAX_FT:
            terminated, reason = True, "ceiling"
        elif alpha_deg > c.term_alpha_deg or alpha_deg < -c.term_alpha_deg:
            terminated, reason = True, "alpha"
        elif abs(beta_deg) > c.term_beta_deg:
            terminated, reason = True, "beta"
        elif n_eff > c.term_nz_hi or n_eff < c.term_nz_lo:
            terminated, reason = True, "nz"
        elif st.mach < ac.stall_mach(st.alt_ft):
            # Sonlandirma esigi de irtifaya baglidir ve BARIYERIN ALTINDADIR:
            # bariyer 1.25x stall, sonlanma 1.0x stall. Boylece kalkanin
            # korumaya calistigi sinir, bolumun oldugu sinirdan icerdedir.
            terminated, reason = True, "low_mach"

        if terminated:
            r += c.r_crash
            info["termination"] = reason

        truncated = self._k >= self._max_steps
        if terminated or truncated:
            info["episode_waypoints"] = self._n_waypoints
            info["diag"] = dict(
                alt_err_mean=float(np.mean(d["alt_err"])),
                mach_err_mean=float(np.mean(d["mach_err"])),
                action_rate_rms=float(np.sqrt(np.mean(d["dact"]))),
                alpha_max=float(np.max(d["alpha"])),
                beta_max=float(np.max(d["beta"])),
                nz_max=float(np.max(d["nz_hi"])),
                nz_min=float(np.min(d["nz_lo"])),
                mach_margin_min=float(np.min(d["mach_marg"])),
                stall_margin_min=float(np.min(d["stall_marg"])),
            )
            if self.shield is not None:
                info["diag"].update(
                    {"shield_" + k: v for k, v in self.shield.stats.summary().items()
                     if isinstance(v, float)})
            if self.shield is not None:
                info["shield"] = self.shield.stats.summary()
            info["is_success"] = float(self._n_waypoints >= 3 and not terminated)

        return self._obs(), float(r), terminated, truncated, info

    def close(self):
        pass
