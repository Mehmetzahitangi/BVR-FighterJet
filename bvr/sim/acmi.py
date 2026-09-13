"""
Tacview ACMI (metin, surum 2.2) telemetri kaydedici.

Neden gerekli: sayisal metrikler "kriter gecti mi" sorusunu cevaplar ama
"ucak gercekten mantikli mi uctu" sorusunu cevaplamaz. Salinim, ters yonde
donus, burun asagi kayma gibi hatalar tabloda gizlenebilir; Tacview'de
aninda gorunur. Her kontrol/RL degisikliginden sonra bir gorsel kosu
calistirmak, sessizce yanlis davranan bir sistemle aylarca ugrasmanin
en ucuz panzehiridir.

Format ozeti (ACMI 2.2 text):
    satir basi '#'  -> zaman damgasi (saniye)
    'ID,T=lon|lat|alt|roll|pitch|yaw,...' -> nesne guncellemesi
    '-ID' -> nesne kaldirilir (ornegin fuze isabet/iska sonrasi)
    T alanindaki aci birimi DERECE, irtifa birimi METREDIR.

COKLU NESNE (Faz 1.5d): pozisyon `st.lon_deg`/`st.lat_deg`'DEN DEGIL,
`st.north_ft`/`st.east_ft`'TEN (NEU, "muhasebe" cercevesi) hesaplanir --
her F16Sim/Missile kendi yerel (0,0) noktasini tutuyor olabilir (bkz.
bvr/combat/ FlightState/MissileState kullanimlari, "ortak cerceve ofseti"),
ama ayni sahnede iki nesneyi dogru yerlestirmek icin TEK bir referans
noktasindan (ref_lat/ref_lon) turetilen ortak bir donusum sarttir. Tek
ucakli kullanim icin bu MATEMATIKSEL OLARAK ESDEGERDIR (JSBSim IC'si daima
lat=lon=0'da baslar, yani north_ft = lat_deg*364000 tam olarak) -- eski
davranis degismez.
"""
from __future__ import annotations

import math
from typing import Optional, TextIO

FT_TO_M = 0.3048
MAX_FUEL_LBS = 6972.0    # f16.xml: 2 x 3486 lb dahili tank
FT_PER_DEG_LAT = 364000.0  # jsbsim_bridge.py::state() ile AYNI yaklasik sabit


class ACMIRecorder:
    """Cok nesneli ACMI kaydedici (ucaklar + fuzeler, PAYLASILAN NEU cercevesi)."""

    def __init__(
        self,
        path: str,
        callsign: str = "Blue1",
        aircraft: str = "F-16C",
        color: str = "Blue",
        ref_lat: float = 39.0,      # JSBSim 0,0'da baslar; kaydi tanidik bir
        ref_lon: float = 32.8,      # cografyaya kaydirmak icin referans nokta
        title: str = "BVR F-16 ic dongu dogrulamasi",
    ):
        self.path = path
        self.callsign = callsign
        self.aircraft = aircraft
        self.color = color
        self.ref_lat = ref_lat
        self.ref_lon = ref_lon
        self.title = title
        self._f: Optional[TextIO] = None
        self._header_written: set[int] = set()   # obj_id basina -- bkz. 1.5d notu
        self._last_t = -1.0

    # -- baglam yoneticisi ---------------------------------------------------
    def __enter__(self) -> "ACMIRecorder":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        self._f = open(self.path, "w", encoding="utf-8-sig", newline="\n")
        self._f.write("FileType=text/acmi/tacview\n")
        self._f.write("FileVersion=2.2\n")
        self._f.write("0,ReferenceTime=2026-01-01T00:00:00Z\n")
        self._f.write(f"0,Title={self.title}\n")
        self._f.write("0,DataSource=JSBSim 1.3.0 f16\n")
        self._f.write(f"0,ReferenceLongitude={self.ref_lon}\n")
        self._f.write(f"0,ReferenceLatitude={self.ref_lat}\n")

    def close(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None

    # -- ortak donusum ---------------------------------------------------------
    def _lonlat(self, north_ft: float, east_ft: float) -> tuple[float, float]:
        """NEU (north_ft, east_ft) -> (lon_deg, lat_deg). jsbsim_bridge.py::state()
        ile AYNI yaklasik sabit (364000 ft/derece enlem) kullanilir."""
        lat = self.ref_lat + north_ft / FT_PER_DEG_LAT
        lon = self.ref_lon + east_ft / (FT_PER_DEG_LAT * math.cos(math.radians(self.ref_lat)))
        return lon, lat

    def _write_timestamp(self, t: float) -> None:
        if t != self._last_t:
            self._f.write(f"#{t:.3f}\n")
            self._last_t = t

    # -- kayit: ucak -----------------------------------------------------------
    def record(self, st, extra: Optional[dict] = None, obj_id: int = 1,
               name: Optional[str] = None, color: Optional[str] = None,
               callsign: Optional[str] = None) -> None:
        """Bir FlightState anini yaz.

        `name`/`color`/`callsign` verilmezse kaydedicinin kendi varsayilanlari
        (tek-ucakli eski kullanimla AYNI) kullanilir -- coklu ucak icin obj_id
        basina farkli deger vermek icin bunlari acikca ver.

        `extra`: Tacview'de ayrica gorulecek skaler alanlar, orn.
                 {"GammaCmd": 8.0, "PhiCmd": 45.0}
        """
        if self._f is None:
            raise RuntimeError("ACMIRecorder acilmadi (open() cagrilmadi)")

        self._write_timestamp(st.t)

        lon, lat = self._lonlat(st.north_ft, st.east_ft)
        alt_m = st.alt_ft * FT_TO_M

        roll = math.degrees(st.phi_rad)
        pitch = math.degrees(st.theta_rad)
        yaw = math.degrees(st.psi_rad) % 360.0
        if yaw >= 359.9995:
            yaw = 0.0

        fields = [f"T={lon:.7f}|{lat:.7f}|{alt_m:.1f}|{roll:.2f}|{pitch:.2f}|{yaw:.2f}"]

        if obj_id not in self._header_written:
            fields += [
                f"Name={name or self.aircraft}",
                "Type=Air+FixedWing",
                f"Color={color or self.color}",
                f"Pilot={callsign or self.callsign}",
            ]
            self._header_written.add(obj_id)

        fields += [
            f"Mach={st.mach:.4f}",
            f"TAS={st.vt_fps * FT_TO_M:.1f}",
            f"AOA={math.degrees(st.alpha_rad):.2f}",
            f"AOS={math.degrees(st.beta_rad):.2f}",
            f"NormalGForce={-st.nz:.3f}",
            f"FuelWeight={st.fuel_frac * MAX_FUEL_LBS * 0.45359:.0f}",  # kg (Tacview birimi)
        ]
        if extra:
            for k, v in extra.items():
                fields.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")

        self._f.write(f"{obj_id:x}," + ",".join(fields) + "\n")

    # -- kayit: fuze -------------------------------------------------------
    def record_missile(self, t: float, pos_ft, vel_fps, obj_id: int,
                        name: str = "AIM-120", color: str = "Grey",
                        extra: Optional[dict] = None) -> None:
        """Bir MissileState anini yaz. `pos_ft`/`vel_fps`: NEU (north,east,alt)
        3-vektor -- Missile'in KENDI FlightState'i yok, bu yuzden ayri metod.

        `t`: MUTLAK sahne zamani (missile_state.t_since_launch DEGIL --
        atan uçakla AYNI saatte olmasi icin cagiran taraf bunu vermeli).
        """
        if self._f is None:
            raise RuntimeError("ACMIRecorder acilmadi (open() cagrilmadi)")

        self._write_timestamp(t)

        north_ft, east_ft, alt_ft = float(pos_ft[0]), float(pos_ft[1]), float(pos_ft[2])
        lon, lat = self._lonlat(north_ft, east_ft)
        alt_m = alt_ft * FT_TO_M

        vx, vy, vz = float(vel_fps[0]), float(vel_fps[1]), float(vel_fps[2])
        speed = math.hypot(vx, vy)
        yaw = math.degrees(math.atan2(vy, vx)) % 360.0
        pitch = math.degrees(math.atan2(vz, speed)) if speed > 1e-3 else 0.0

        fields = [f"T={lon:.7f}|{lat:.7f}|{alt_m:.1f}|0.00|{pitch:.2f}|{yaw:.2f}"]

        if obj_id not in self._header_written:
            fields += [f"Name={name}", "Type=Weapon+Missile", f"Color={color}"]
            self._header_written.add(obj_id)

        fields += [f"TAS={math.hypot(vx, vy, vz) * FT_TO_M:.1f}"]
        if extra:
            for k, v in extra.items():
                fields.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")

        self._f.write(f"{obj_id:x}," + ",".join(fields) + "\n")

    # -- nesne kaldirma ----------------------------------------------------
    def remove_object(self, t: float, obj_id: int) -> None:
        """Nesneyi sahneden kaldir (fuze isabet/iska/kor/tukenme sonrasi)."""
        if self._f is None:
            raise RuntimeError("ACMIRecorder acilmadi (open() cagrilmadi)")
        self._write_timestamp(t)
        self._f.write(f"-{obj_id:x}\n")
        self._header_written.discard(obj_id)
