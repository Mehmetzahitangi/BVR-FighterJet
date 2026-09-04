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
    T alanindaki aci birimi DERECE, irtifa birimi METREDIR.
"""
from __future__ import annotations

import math
from typing import Optional, TextIO

FT_TO_M = 0.3048
MAX_FUEL_LBS = 6972.0    # f16.xml: 2 x 3486 lb dahili tank


class ACMIRecorder:
    """Tek ucaklik ACMI kaydedici (ileride coklu nesne icin genisletilebilir)."""

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
        self._header_written = False
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

    # -- kayit ---------------------------------------------------------------
    def record(self, st, extra: Optional[dict] = None, obj_id: int = 1) -> None:
        """Bir FlightState anini yaz.

        `extra`: Tacview'de ayrica gorulecek skaler alanlar, orn.
                 {"GammaCmd": 8.0, "PhiCmd": 45.0}
        """
        if self._f is None:
            raise RuntimeError("ACMIRecorder acilmadi (open() cagrilmadi)")

        # Zaman damgasi (yalnizca degistiginde yazilir)
        if st.t != self._last_t:
            self._f.write(f"#{st.t:.3f}\n")
            self._last_t = st.t

        lon = self.ref_lon + (st.lon_deg - 0.0)
        lat = self.ref_lat + (st.lat_deg - 0.0)
        alt_m = st.alt_ft * FT_TO_M

        roll = math.degrees(st.phi_rad)
        pitch = math.degrees(st.theta_rad)
        yaw = math.degrees(st.psi_rad) % 360.0
        if yaw >= 359.9995:
            yaw = 0.0

        fields = [f"T={lon:.7f}|{lat:.7f}|{alt_m:.1f}|{roll:.2f}|{pitch:.2f}|{yaw:.2f}"]

        if not self._header_written:
            fields += [
                f"Name={self.aircraft}",
                "Type=Air+FixedWing",
                f"Color={self.color}",
                f"Pilot={self.callsign}",
            ]
            self._header_written = True

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
