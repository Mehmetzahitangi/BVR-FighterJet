"""
Görüş Ötesi (BVR) Aktif Radar Güdümlü Füze Modeli (AMRAAM Tipi).
Adım 1: Atmosfer Yoğunluğu, Ses Hızı ve Mach'a Bağlı Cd(M) Tablosu.

Görüş Ötesi (BVR) Aktif Radar Güdümlü Füze Modeli (AMRAAM Tipi).
- Standart Atmosfer ve Mach'a Bağlı Cd(M) Tablosu
- Boost / Coast İtki ve Aerodinamik Sürükleme Kinematiği
- 3D Gerçek Oransal Seyrüsefer (True Proportional Navigation - TPN)
- Datalink / Pitbull Durum Makinesi
- İsabet / Iska / Tükenme / Kör Sonlanma Koşulları
"""

import math
import numpy as np
from dataclasses import dataclass

def atmosphere(alt_ft: float) -> tuple[float, float]:
    """
    ICAO Standart Atmosfer Modeli.
    Girdi: alt_ft: İrtifa (feet) [NEU kullanımında z]
    Çıktı: (density_slug_ft3, speed_of_sound_fps)
    """
    h = max(0.0, float(alt_ft))
    h_trop = 36089.0  # Troposfer tavanı (feet)
    
    t0 = 518.67       # Deniz seviyesi sıcaklığı (Rankine)
    rho0 = 0.0023769  # Deniz seviyesi yoğunluğu (slug/ft^3)
    a0 = 1116.45      # Deniz seviyesi ses hızı (ft/s)
    lapse = 0.00356616  # Sıcaklık gradyanı (R/ft)

    if h <= h_trop:
        temp = t0 - lapse * h
        theta = temp / t0
        rho = rho0 * (theta ** 4.25588)
        sos = a0 * math.sqrt(theta)
    else:
        # Tropopoz ve üzeri (izotermal katman)
        temp_trop = t0 - lapse * h_trop
        theta_trop = temp_trop / t0
        rho_trop = rho0 * (theta_trop ** 4.25588)
        sos = a0 * math.sqrt(theta_trop)
        
        # Üstel azalma
        delta_h = h - h_trop
        rho = rho_trop * math.exp(-delta_h / 20806.0)

    return rho, sos


# Çapa noktaları: (Mach, Cd)
_CD_POINTS = [
    (0.0, 0.25),
    (0.8, 0.25),
    (1.0, 0.55),
    (1.15, 0.72),
    (1.5, 0.58),
    (2.5, 0.40),
    (4.0, 0.32),
]

def drag_coefficient(mach: float) -> float:
    """
    Mach değerine bağlı aerodinamik sürükleme katsayısı (Cd).
    İnce gövdeli havadan havaya füze profiline göre doğrusal enterpolasyon.
    """
    m = max(0.0, float(mach))
    
    if m <= _CD_POINTS[0][0]:
        return _CD_POINTS[0][1]
    if m >= _CD_POINTS[-1][0]:
        return _CD_POINTS[-1][1]

    for i in range(len(_CD_POINTS) - 1):
        m0, cd0 = _CD_POINTS[i]
        m1, cd1 = _CD_POINTS[i + 1]
        if m0 <= m <= m1:
            fraction = (m - m0) / (m1 - m0)
            return cd0 + fraction * (cd1 - cd0)

    return _CD_POINTS[-1][1]


@dataclass
class MissileConfig:
    mass_lb: float = 335.0
    boost_s: float = 9.0
    boost_thrust_lbf: float = 3000.0     # Yaklaşık açık kaynak AIM-120 verisi
    ref_area_sqft: float = 0.268         # 7 inç gövde kesit alanı
    n_pro_nav: float = 4.0               # Seyrüsefer sabiti (N)
    max_g: float = 30.0                  # Yapısal azami g limiti
    pitbull_range_nm: float = 8.0        # Füzenin kendi radarını açtığı menzil
    lethal_radius_ft: float = 30.0       # Harp başlığı öldürücü yarıçapı
    min_speed_mach: float = 1.5          # Altında manevra kabiliyeti biter
    # DENGE PARAMETRESI (coast_s/lock_delay_s gibi) -- fiziksel sabit degil.
    # AMRAAM orta safhada ataletsel ucar; datalink guncellemesi tahminini
    # IYILESTIRIR, VARLIGI SART DEGILDIR. Bu yuzden datalink_ok=False aninda
    # "kor" degil -- son bilinen hedef durumundan ekstrapole ederek bu sure
    # kadar ucmaya devam eder, hata zamanla/hedef manevrasiyla buyur.
    # Bkz. REQUIREMENTS.md MSL bolumu. DENEME-GERI ALMA: 5.0->10.0 denendi
    # (MSL-09'un seeker sepetini canlandirmak icin), ama OLCULDU ki isabet
    # etmedi (en kotu durumda off-boresight 6.7 deg, sepet 30 deg) VE gercek
    # bir bedeli vardi (crank/notch cezasi yari yariya gevsedi). 5.0'a geri
    # alindi -- MSL-09 bilerek atil birakiliyor (bkz. asagidaki not).
    datalink_memory_s: float = 5.0       # guncelleme almadan ucabilecegi sure
    # Pitbull, OTOMATIK bagimsizlik demek DEGIL -- aktif radar hedefi kendi
    # sepetinde (FOV) ve kendi menzilinde GORMELI. Erken datalink kesintisi
    # inanci kaydirirsa, seeker sepet disinda kalip hicbir zaman yakalayamaz
    # (MSL-09). Bu da coast_s/lock_delay_s gibi bir denge parametresidir.
    seeker_fov_deg: float = 30.0         # aktif radarin arama sepeti (yari aci)
    seeker_range_nm: float = 10.0        # seeker'in kendi tespit menzili


@dataclass
class MissileState:
    pos_ft: np.ndarray      # NEU kartezyen koordinatları [x, y, z]
    vel_fps: np.ndarray     # Hız bileşenleri [vx, vy, vz]
    t_since_launch: float
    phase: str              # "boost" | "coast" | "pitbull"
    motor_phase: str        # "boost" | "coast" -- pitbull'da bile itki durumunu kaybetmez (Tacview icin)
    alive: bool
    result: str             # "" | "isabet" | "iska" | "tukenme" | "kor"
    los_rate_radps: float = 0.0
    applied_g: float = 0.0  # bu adimda uygulanan (clamp SONRASI) PN ivmesi buyuklugu, g cinsinden


class Missile:
    def __init__(self, cfg: MissileConfig, launch_state, target_id: str):
        self.cfg = cfg
        self.target_id = target_id

        if hasattr(launch_state, "pos_ft"):
            self.pos = np.array(launch_state.pos_ft, dtype=float).copy()
        else:
            self.pos = np.array([launch_state.north_ft, launch_state.east_ft, launch_state.alt_ft], dtype=float)

        if hasattr(launch_state, "vel_fps"):
            self.vel = np.array(launch_state.vel_fps, dtype=float).copy()
        else:
            # Gercek FlightState'te (bvr/sim/jsbsim_bridge.py) hazir bir hiz
            # vektoru yok -- vt_fps + yon acilarindan turetiliyor. Ayni formul
            # bvr/combat/geometry.py'deki hiz vektoru hesabiyla (Faz 1.1) birebir.
            psi = launch_state.psi_rad
            gamma = launch_state.gamma_rad
            beta = launch_state.beta_rad
            vt = launch_state.vt_fps
            self.vel = vt * np.array([
                math.cos(gamma) * math.cos(psi + beta),
                math.cos(gamma) * math.sin(psi + beta),
                math.sin(gamma),
            ])

        self.t_since_launch: float = 0.0
        self.alive: bool = True
        self.result: str = ""
        self.phase: str = "boost"
        self.motor_phase: str = "boost"
        self._prev_range_ft: float = float("inf")
        self._min_range_ft: float = float("inf")
        self._last_los_rate: float = 0.0
        self._last_applied_g: float = 0.0
        self._datalink_timer: float = self.cfg.datalink_memory_s
        self._last_known_target_pos: np.ndarray = None
        self._last_known_target_vel: np.ndarray = None
        self._time_since_update: float = 0.0
        self._seeker_locked: bool = False

    def update(
        self,
        dt: float,
        target_pos: np.ndarray,
        target_vel: np.ndarray,
        datalink_ok: bool
    ) -> MissileState:
        if not self.alive:
            return self._build_state()

        self.t_since_launch += dt
        g0 = 32.174049

        target_pos = np.array(target_pos, dtype=float)
        target_vel = np.array(target_vel, dtype=float)

        if self._last_known_target_pos is None:
            self._last_known_target_pos = target_pos.copy()
            self._last_known_target_vel = target_vel.copy()

        # 0. Datalink Hafızası -- "son bilinen" hedef durumunu güncelle/ekstrapole et.
        # datalink_ok=True: taze bilgi, sayaç tam dolar.
        # datalink_ok=False: son bilinen konumdan SABİT HIZLA ekstrapole ederek
        # (ataletsel) uçmaya devam eder, sayaç azalır. Radardaki ARAMA
        # ilerlemesiyle AYNI kalıp: sert kesinti yerine kademeli bozulma --
        # kırılgan bir eşik yaratmamak için (bkz REQUIREMENTS.md MSL bölümü).
        if datalink_ok:
            self._last_known_target_pos = target_pos.copy()
            self._last_known_target_vel = target_vel.copy()
            self._time_since_update = 0.0
            self._datalink_timer = self.cfg.datalink_memory_s
        else:
            self._time_since_update += dt

        # 1. On-kontrol: pitbull esigini (fuzenin kendi tahminiyle) test et.
        provisional_pos = self._last_known_target_pos + self._last_known_target_vel * self._time_since_update
        provisional_range_nm = float(np.linalg.norm(provisional_pos - self.pos)) / 6076.11549

        self.motor_phase = "boost" if self.t_since_launch <= self.cfg.boost_s else "coast"

        if provisional_range_nm <= self.cfg.pitbull_range_nm:
            self.phase = "pitbull"
            self._datalink_timer = self.cfg.datalink_memory_s  # artık anlamsız ama tutarlı kalsın

            # 1a. Seeker Yakalama Denemesi -- pitbull, OTOMATIK bağımsızlık
            # DEMEK DEĞİL. Aktif radar hedefi kendi sepetinde (FOV) VE kendi
            # menzilinde GÖRMELİ ki inancı gerçeğe tazeleyebilsin. Görmezse
            # (datalink erken kesilip inanç kaymışsa) kör ekstrapolasyona
            # devam eder, her adım tekrar dener (MSL-09).
            if not self._seeker_locked:
                true_r_vec = target_pos - self.pos
                true_r_ft = float(np.linalg.norm(true_r_vec))
                true_r_nm = true_r_ft / 6076.11549
                v_mag_now = float(np.linalg.norm(self.vel))
                if true_r_nm <= self.cfg.seeker_range_nm and true_r_ft > 1e-3 and v_mag_now > 1e-3:
                    boresight_angle = off_boresight_deg(self.vel, self.pos, target_pos)
                    if boresight_angle <= self.cfg.seeker_fov_deg:
                        self._seeker_locked = True


            if self._seeker_locked:
                # Aktif radar artik surekli izliyor -- her adim gercek hedefle tazelenir.
                self._last_known_target_pos = target_pos.copy()
                self._last_known_target_vel = target_vel.copy()
                self._time_since_update = 0.0
        else:
            self.phase = self.motor_phase
            if not datalink_ok:
                self._datalink_timer -= dt
                if self._datalink_timer <= 0.0:
                    self.alive = False
                    self.result = "kor"
                    return self._build_state()

        believed_pos = self._last_known_target_pos + self._last_known_target_vel * self._time_since_update
        believed_vel = self._last_known_target_vel

        # 2. Güdüm için Bağıl Geometri ve LOS -- füzenin (olası tazeleme
        # SONRASI) İNANDIĞI hedef durumuyla hesaplanır; gerçek hedef konumu
        # değil (CPA/sonlanma bunu ayrıca, gerçek target_pos ile kontrol eder).
        r_vec = believed_pos - self.pos
        range_ft = float(np.linalg.norm(r_vec))
        range_nm = range_ft / 6076.11549

        if range_ft < 1e-3:
            u_los = np.array([1.0, 0.0, 0.0])
        else:
            u_los = r_vec / range_ft

        v_rel = believed_vel - self.vel
        closure_fps = -float(np.dot(v_rel, u_los))

        # LOS Dönme Hızı Vektörü: omega = (r x v_bağıl) / R^2
        if range_ft > 1.0:
            omega = np.cross(r_vec, v_rel) / (range_ft ** 2)
        else:
            omega = np.array([0.0, 0.0, 0.0])

        los_rate = float(np.linalg.norm(omega))
        self._last_los_rate = los_rate

        # 3. İtki ve Sürükleme Kinematiği
        v_mag = float(np.linalg.norm(self.vel))
        v_hat = self.vel / v_mag if v_mag > 1e-3 else np.array([1.0, 0.0, 0.0])

        rho, sos = atmosphere(self.pos[2])
        mach = v_mag / max(sos, 1e-3)

        thrust_lbf = self.cfg.boost_thrust_lbf if self.t_since_launch <= self.cfg.boost_s else 0.0
        cd = drag_coefficient(mach)
        drag_lbf = 0.5 * rho * (v_mag ** 2) * cd * self.cfg.ref_area_sqft

        a_axial = ((thrust_lbf - drag_lbf) * g0) / self.cfg.mass_lb

        # 4. 3D PN Güdüm İvmesi + Yerçekimi Telafisi
        # Gercek bir fuzede otopilot, PN duzeltmesinden ONCE, duz ucusu
        # surdurmek icin yercekimini kaldirici (lift) kuvvetiyle dengeler --
        # bunu AYRI bir butceden degil, TOPLAM manevra butcesinden (max_g)
        # yapar. Telafiyi PN'den sonra ayri eklersek, yercekimi PN'in
        # dogrudan gormedigi surekli bir bozan haline gelir (olcduk: fuze
        # yavasladikca g/V terimi buyudugu icin lambda_dot azalacagina artar).
        gravity = np.array([0.0, 0.0, -g0])
        gravity_compensation = -gravity  # [0, 0, +g0]

        omega_cross_u = np.cross(omega, u_los)
        a_pn_cmd = self.cfg.n_pro_nav * closure_fps * omega_cross_u

        a_maneuver_cmd = a_pn_cmd + gravity_compensation

        # Yapısal G-Limiti (Clamping) -- TOPLAM manevra (PN + yercekimi telafisi)
        max_a_mag = self.cfg.max_g * g0
        maneuver_mag = float(np.linalg.norm(a_maneuver_cmd))
        if maneuver_mag > max_a_mag:
            a_maneuver = a_maneuver_cmd * (max_a_mag / maneuver_mag)
        else:
            a_maneuver = a_maneuver_cmd

        self._last_applied_g = float(np.linalg.norm(a_maneuver)) / g0

        # Toplam İvme: Eksenel + (PN + telafi, clamp'lenmis) + gercek yercekimi.
        # Clamp devrede degilken bu netlesir: a_maneuver + gravity = a_pn_cmd
        # (yercekimi tam iptal olur, PN hicbir zaman onunla "savasmaz").
        # Sadece max_g'ye yakin durumlarda telafi, PN'in kullanabilecegi
        # butceyi gercekci sekilde biraz azaltir.
        a_total = a_axial * v_hat + a_maneuver + gravity

        # Eski konumları sakla (Sürekli CPA enterpolasyonu için)
        old_pos = self.pos.copy()
        t_pos_curr = target_pos.copy()

        # Entegrasyon
        self.pos += self.vel * dt
        self.vel += a_total * dt

        # GERÇEK menzil -- güdümün kullandığı (inanılan) `range_ft`'ten FARKLI.
        # Sonlanma (isabet/ıska) her zaman gerçek hedef konumuna göre karar
        # verilir; füze "kör" uçarken bile fiilen çarpıp çarpmadığı gerçek
        # fizikle belirlenir, füzenin inancıyla değil.
        true_range_ft = float(np.linalg.norm(target_pos - self.pos))

        # 5. Sürekli En Yakın Yaklaşma (CPA) ve Sonlanma Koşulları
        # İki ayrık adım arasında füzenin hedefi atlamasını (tunneling) önleyen segment hesabı:
        r_start = t_pos_curr - old_pos
        r_end = (t_pos_curr + target_vel * dt) - self.pos
        delta_r = r_end - r_start
        dr_sq = float(np.dot(delta_r, delta_r))

        if dr_sq > 1e-6:
            tau = -float(np.dot(r_start, delta_r)) / dr_sq
            tau_clamped = max(0.0, min(1.0, tau))
            step_min_dist = float(np.linalg.norm(r_start + delta_r * tau_clamped))
        else:
            step_min_dist = true_range_ft

        self._min_range_ft = min(self._min_range_ft, step_min_dist)

        # A. Doğrudan veya Segment Üzerinde İsabet
        if step_min_dist <= self.cfg.lethal_radius_ft or true_range_ft <= self.cfg.lethal_radius_ft:
            self.alive = False
            self.result = "isabet"
            return self._build_state()

        # B. Iska / CPA (Menzil açılmaya başladığı an)
        if true_range_ft > self._prev_range_ft:
            self.alive = False
            self.result = "isabet" if self._min_range_ft <= self.cfg.lethal_radius_ft else "iska"
            return self._build_state()

        # C. Kinetik Enerji Tükenmesi (Sadece boost sonrasında)
        # DIKKAT: `mach` bu adimin BASINDAKI (entegrasyondan once) hizla
        # hesaplanmisti. Kontrolden once entegrasyon SONRASI hizla yeniden
        # hesapliyoruz, yoksa tukenme bir adim gecikmeli tespit edilir.
        if self.t_since_launch > self.cfg.boost_s:
            v_mag_new = float(np.linalg.norm(self.vel))
            mach_new = v_mag_new / max(sos, 1e-3)
            if mach_new < self.cfg.min_speed_mach:
                self.alive = False
                self.result = "tukenme"
                return self._build_state()

        self._prev_range_ft = true_range_ft
        return self._build_state()

    def _build_state(self) -> MissileState:
        return MissileState(
            pos_ft=self.pos.copy(),
            vel_fps=self.vel.copy(),
            t_since_launch=self.t_since_launch,
            phase=self.phase,
            motor_phase=self.motor_phase,
            alive=self.alive,
            result=self.result,
            los_rate_radps=self._last_los_rate,
            applied_g=self._last_applied_g
        )




def off_boresight_deg(vel: np.ndarray, from_pos: np.ndarray, to_pos: np.ndarray) -> float:
    """
        Serbest bir (module-level function)
        vel yönelimiyle, from_pos'tan to_pos'a çizilen görüş hattı (LOS) vektörü
    arasındaki açıyı derece cinsinden [0, 180] döner.
        Bağımsız olarak, füzenin kendi aktif radarının hedefi görebileceği (sepet içinde) bir ölçü verir. rwr.py'dan import edilirken boş yere bir füze örneği yaratmaya gerek yok, bu yüzden module-level function.
    """

    r_vec = to_pos - from_pos
    r_mag = float(np.linalg.norm(r_vec))
    v_mag = float(np.linalg.norm(vel))

    # Sıfıra bölme hatalarını önlemek için kontrol
    if r_mag < 1e-3 or v_mag < 1e-3:
        return 0.0
    
    cos_off = float(np.dot(vel / v_mag, r_vec / r_mag))

    # Floating point hassasiyetinden dolayı cosinus -1 ile 1 dışına çıkmasın diye clamp'liyoruz
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_off))))
