"""
JSBSim F-16 koprusu.

Sorumlulugu SADECE simulatoru surmek:
  - modeli yukle, dt ayarla
  - baslangic kosulu kur ve TRIM et (dengeye getir)
  - FCS komutlarini yaz, bir adim ilerlet, durumu fiziksel birimlerde oku

Kontrol mantigi, odul, RL burada YOKTUR. Boylece ayni kopru hem egitimde,
hem sysid veri toplamada, hem degerlendirmede degismeden kullanilir.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

import jsbsim
import numpy as np

from . import aircraft as ac


@dataclass
class FlightState:
    """Fiziksel birimlerde ucus durumu (normalize DEGIL)."""
    t: float            # sim zamani (s)
    alt_ft: float
    lat_deg: float
    lon_deg: float
    # Yerel duzlem konumu (baslangic noktasina gore, ft) - guidance icin
    north_ft: float
    east_ft: float
    # Tutum
    phi_rad: float      # yatis (roll)
    theta_rad: float    # yunuslama (pitch)
    psi_rad: float      # yon (heading, 0 = kuzey)
    gamma_rad: float    # ucus yolu acisi
    # Hizlar
    mach: float
    vt_fps: float
    h_dot_fps: float
    p_rads: float
    q_rads: float
    r_rads: float
    # Aerodinamik
    alpha_rad: float
    beta_rad: float
    qbar_psf: float
    nz: float           # pilot z ekseni g yuku (duz ucusta ~1.0)
    # Diger
    fuel_frac: float

    def as_array(self) -> np.ndarray:
        return np.array(list(asdict(self).values()), dtype=np.float64)


class F16Sim:
    """JSBSim F-16 sarmalayicisi."""

    #: FDM cozucusunun calisma frekansi. JSBSim F-16 FCS'i icinde PID'ler ve
    #: kinematik aktuator modelleri var; 120 Hz bunlarin sayisal olarak
    #: stabil kalmasi icin guvenli taban. Kontrol dongusu bunun altinda
    #: (60 Hz) calisir, RL ise 10 Hz.
    FDM_HZ = 120.0

    def __init__(self, fdm_hz: float = FDM_HZ, seed: Optional[int] = None):
        self.fdm_hz = fdm_hz
        self.dt = 1.0 / fdm_hz
        self.rng = np.random.default_rng(seed)

        self.fdm = jsbsim.FGFDMExec(None)
        self.fdm.set_debug_level(0)
        if not self.fdm.load_model("f16"):
            raise RuntimeError("JSBSim f16 modeli yuklenemedi")
        self.fdm.set_dt(self.dt)

        self._origin_lat = 0.0
        self._origin_lon = 0.0
        self._trimmed = False

    # -- ozellik erisimi -----------------------------------------------------
    def __getitem__(self, prop: str) -> float:
        return self.fdm.get_property_value(prop)

    def __setitem__(self, prop: str, value: float) -> None:
        self.fdm.set_property_value(prop, float(value))

    # -- baslatma ------------------------------------------------------------
    def reset(
        self,
        alt_ft: float = 20000.0,
        mach: float = 0.8,
        heading_deg: float = 0.0,
        gamma_deg: float = 0.0,
        trim: bool = True,
        fuel_frac: Optional[float] = None,
    ) -> FlightState:
        """Baslangic kosulunu kur ve uctagi dengeye (trim) getir.

        TRIM NEDEN SART?
        run_ic() sadece "su hizda, su irtifada, su tutumda basla" der; kumanda
        yuzeyleri ve itki dengede DEGILDIR. Trim etmeden baslarsan ucak ilk
        saniyelerde kendiliginden salinir. Bu hem basamak-yanit olcumlerini
        hem de sistem tanimlama (Koopman) verisini bozar: olctugun sey
        kontrolcunun degil, baslangic gecicisinin davranisi olur.
        """
        f = self.fdm
        # DURGUN HAVADA TRIM: ruzgar/turbulans ozellikleri JSBSim'de KALICIDIR,
        # reset ile temizlenmez. Onceki bolumun turbulansi acikken trim
        # yapilmaya calisilirsa cozucu yakinsamaz ("udot doesn't appear to be
        # trimmable") ve bolum comer. Bu yuzden once havayi durultup trim
        # ediyoruz; bozucu etki trimden SONRA uygulanir (set_turbulence).
        self.set_turbulence(0.0, 0.0, 0)
        # Motorlari calisir durumda baslat
        f.set_property_value("propulsion/set-running", -1)

        f.set_property_value("ic/h-sl-ft", alt_ft)
        f.set_property_value("ic/mach", mach)
        f.set_property_value("ic/psi-true-deg", heading_deg)
        f.set_property_value("ic/gamma-deg", gamma_deg)
        f.set_property_value("ic/lat-gc-deg", 0.0)
        f.set_property_value("ic/long-gc-deg", 0.0)
        f.set_property_value("ic/phi-deg", 0.0)
        f.set_property_value("ic/beta-deg", 0.0)

        # Inis takimi yukari, hava frenleri kapali (BVR ucusu)
        f.set_property_value("gear/gear-cmd-norm", 0.0)
        f.set_property_value("fcs/speedbrake-cmd-norm", 0.0)
        f.set_property_value("fcs/fbw-override", 0.0)   # FLCS AKTIF kalsin

        # Baslangic kumanda tahmini: askeri guc, notr levye
        f.set_property_value("fcs/throttle-cmd-norm", ac.THROTTLE_MIL)
        f.set_property_value("fcs/elevator-cmd-norm", 0.0)
        f.set_property_value("fcs/aileron-cmd-norm", 0.0)
        f.set_property_value("fcs/rudder-cmd-norm", 0.0)

        if fuel_frac is not None:
            self.set_fuel(fuel_frac)      # TRIM'den ONCE: agirlik trimi belirler

        if not f.run_ic():
            raise RuntimeError("run_ic() basarisiz")

        self._trimmed = False
        if trim:
            self._trimmed = self._do_trim()

        self._origin_lat = f.get_property_value("position/lat-gc-deg")
        self._origin_lon = f.get_property_value("position/long-gc-deg")
        return self.state()

    def _do_trim(self, mode: int = 1) -> bool:
        """JSBSim trim rutinini calistir.

        mode 1 = duz ucus trimi (uzunlamasina denge + itki dengesi).
        Yakinsamazsa JSBSim istisna firlatir; sessizce dengesiz ucmaktansa
        False donup cagiran tarafin bolumu reddetmesini saglariz.
        """
        try:
            self.fdm.set_property_value("simulation/do_simple_trim", mode)
            return True
        except Exception:
            return False

    # -- komut ---------------------------------------------------------------
    def send_fcs(
        self,
        elevator_cmd: float,
        aileron_cmd: float,
        throttle_cmd: float,
        rudder_cmd: float = 0.0,
    ) -> None:
        """FLCS'e komut yaz (normalize, ham yuzey acisi DEGIL).

        Isaret ve aralik sozlesmesi icin bvr/sim/aircraft.py'ye bak:
          elevator: [-1, +0.44], NEGATIF = burun yukari = pozitif G
          aileron : [-1, +1],    cmd 1.0 ~ +180 deg/s yatis hizi
          throttle: [0, 1],      0.5 = askeri guc, >0.5 art yakici
        """
        f = self.fdm
        f.set_property_value(
            "fcs/elevator-cmd-norm",
            float(np.clip(elevator_cmd, ac.ELEVATOR_CMD_MIN, ac.ELEVATOR_CMD_MAX)),
        )
        f.set_property_value("fcs/aileron-cmd-norm", float(np.clip(aileron_cmd, -1.0, 1.0)))
        f.set_property_value("fcs/rudder-cmd-norm", float(np.clip(rudder_cmd, -1.0, 1.0)))
        f.set_property_value("fcs/throttle-cmd-norm", float(np.clip(throttle_cmd, 0.0, 1.0)))

    def run(self, n: int = 1) -> FlightState:
        for _ in range(n):
            if not self.fdm.run():
                raise RuntimeError("JSBSim run() basarisiz")
        return self.state()

    # -- durum ---------------------------------------------------------------
    def state(self) -> FlightState:
        f = self.fdm
        lat = f.get_property_value("position/lat-gc-deg")
        lon = f.get_property_value("position/long-gc-deg")
        # Duz-dunya yaklasimi (BVR olceginde <100 nm, hata ihmal edilebilir)
        north_ft = (lat - self._origin_lat) * 364000.0
        east_ft = (lon - self._origin_lon) * 364000.0 * math.cos(math.radians(lat))

        tank0 = f.get_property_value("propulsion/tank[0]/contents-lbs")
        tank1 = f.get_property_value("propulsion/tank[1]/contents-lbs")

        return FlightState(
            t=f.get_property_value("simulation/sim-time-sec"),
            alt_ft=f.get_property_value("position/h-sl-ft"),
            lat_deg=lat,
            lon_deg=lon,
            north_ft=north_ft,
            east_ft=east_ft,
            phi_rad=f.get_property_value("attitude/phi-rad"),
            theta_rad=f.get_property_value("attitude/theta-rad"),
            psi_rad=f.get_property_value("attitude/psi-rad"),
            gamma_rad=f.get_property_value("flight-path/gamma-rad"),
            mach=f.get_property_value("velocities/mach"),
            vt_fps=f.get_property_value("velocities/vt-fps"),
            h_dot_fps=f.get_property_value("velocities/h-dot-fps"),
            p_rads=f.get_property_value("velocities/p-rad_sec"),
            q_rads=f.get_property_value("velocities/q-rad_sec"),
            r_rads=f.get_property_value("velocities/r-rad_sec"),
            alpha_rad=f.get_property_value("aero/alpha-rad"),
            beta_rad=f.get_property_value("aero/beta-rad"),
            qbar_psf=f.get_property_value("aero/qbar-psf"),
            nz=f.get_property_value("accelerations/n-pilot-z-norm"),
            fuel_frac=(tank0 + tank1) / ac.MAX_FUEL_LBS,
        )

    # -- yardimci ------------------------------------------------------------
    @property
    def trimmed(self) -> bool:
        return self._trimmed

    def set_fuel(self, fraction: float) -> None:
        """Dahili tanklari doldur (0..1). TRIM'DEN ONCE cagrilmalidir.

        Agirlik dinamigi kokten etkiler: stall hizi, donus orani, ivmelenme,
        tirmanis performansi. Sabit yakitla egitilen bir politika agirlik
        degistiginde genellemez. Trim de agirliga bagli oldugu icin yakit
        mutlaka trimden ONCE ayarlanmalidir.

        Olcum (25 kft, M0.85, 180 s): askeri gucte agirlik %2.1, tam art
        yakicida %7.7 duser; CG 1.5 inc kayar. Yani kutle bolum ICINDE de
        anlamli sekilde degisir -- JSBSim bunu zaten modelliyor.
        """
        f = self.fdm
        per_tank = 0.5 * ac.MAX_FUEL_LBS * float(np.clip(fraction, 0.0, 1.0))
        f.set_property_value("propulsion/tank[0]/contents-lbs", per_tank)
        f.set_property_value("propulsion/tank[1]/contents-lbs", per_tank)

    def set_turbulence(self, wind_fps: float = 0.0, wind_dir_deg: float = 0.0,
                       turb_severity: int = 0) -> None:
        """Alan rastgelelestirmesi (domain randomization) icin ruzgar/turbulans."""
        f = self.fdm
        f.set_property_value("atmosphere/wind-mag-fps", wind_fps)
        f.set_property_value("atmosphere/wind-heading-deg", wind_dir_deg)
        f.set_property_value("atmosphere/turb-type", int(turb_severity))
