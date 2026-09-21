"""
Fuzenin KINEMATIK ZARFI (EVAL-07, MSL-KAL): kilit/datalink KUSURSUZ, hedef SABIT dogrultuda
duz ucuyor. Soru: "35 nmi'de atilan fuze hedefe kinematik olarak yetisebilir mi, hedef donunce
(aspect) bu menzil nasil degisir, ve bu sonuc FUZE MODELININ HANGI PARAMETRELERINE bagli?"

NEDEN: 800+800 savasta fuzelerin ~%71'i 'tukenme' (enerji bitti) ile sonlaniyor. Tum taktik
manzara fuzenin enerji butcesine asili -- bu butce ise kismen FIZIK (itki, surukleme) kismen
bir KALIBRASYON DUGMESI (`MissileConfig.min_speed_mach`: burst sonrasi Mach bu esigin altina
inince fuze 'tukenme' ilan edilir, gercekte hala oldurucu olabilir). Komutani 'guclu' yazmadan
once bu dugmenin zarfi ne kadar oynattigini bilmek gerek: yoksa 'crank fuzeyi yener' bulgusu
BVR'nin degil modelin ozelligi olur.

Modlar (saniyeler surer, uzun kosu DEGIL):
    python -m scripts.missile_envelope             # eski tablo: menzil x hedef donusu (25 kft, 900 fps)
    python -m scripts.missile_envelope --sweep     # KALIBRASYON: irtifa x atici Mach x min_speed_mach
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from bvr.combat.missile import Missile, MissileConfig, atmosphere

NM = 6076.11549


class _Launch:
    def __init__(self, pos, vel):
        self.pos_ft = np.array(pos, float)
        self.vel_fps = np.array(vel, float)


def shoot(range_nm: float, phi_deg: float, tgt_speed: float = 800.0, dt: float = 0.05,
          t_max: float = 140.0, alt_ft: float = 25000.0, launch_fps: float = 900.0,
          min_speed_mach: float | None = None) -> tuple[str, float, float]:
    """Nokta kutle fuze, atici `launch_fps` hizla `alt_ft`'te. Donen: (sonuc, ucus_s, son_Mach)."""
    cfg = MissileConfig() if min_speed_mach is None else MissileConfig(min_speed_mach=min_speed_mach)
    m = Missile(cfg, _Launch([0, 0, alt_ft], [launch_fps, 0, 0]), target_id="red")
    tp = np.array([range_nm * NM, 0.0, alt_ft])
    ph = math.radians(phi_deg)
    tv = np.array([-tgt_speed * math.cos(ph), tgt_speed * math.sin(ph), 0.0])
    st = None
    for _ in range(int(t_max / dt)):
        tp = tp + tv * dt
        st = m.update(dt, tp, tv, datalink_ok=True)
        if not st.alive:
            break
    _, sos = atmosphere(float(st.pos_ft[2]))
    return st.result, st.t_since_launch, float(np.linalg.norm(st.vel_fps)) / sos


def rmax_nm(phi_deg: float, **kw) -> float:
    """Azami isabet menzili (nmi): isabet veren en buyuk menzil (5 nmi hassasiyette ikili arama +
    ince tarama). Hedef hizi atici hiziyla ayni Mach'ta (sos ile olceklenmis)."""
    lo, hi = 5.0, 90.0
    if shoot(lo, phi_deg, **kw)[0] != "isabet":
        return 0.0
    while hi - lo > 0.25:
        mid = 0.5 * (lo + hi)
        if shoot(mid, phi_deg, **kw)[0] == "isabet":
            lo = mid
        else:
            hi = mid
    return lo


def envelope_table() -> None:
    print("FUZE KINEMATIGI (kilit/datalink kusursuz; hedef duz ucuyor). Hucre: sonuc / ucus suresi")
    phis = (0, 30, 60, 90, 120)
    print("menzil  " + "".join(f"phi={p:<4d}        " for p in phis))
    for r in (15, 20, 25, 30, 35, 40):
        cells = []
        for p in phis:
            res, t, _ = shoot(r, p)
            cells.append(f"{res:8s} {t:5.1f}s ")
        print(f"{r:3d} nmi  " + " ".join(cells))


def sweep() -> None:
    print("KALIBRASYON: azami isabet menzili (nmi), kusursuz kilit, hedef duz ucuyor; atici ve hedef ayni Mach.")
    print("Ust satirlar: irtifa x atici Mach (MissileConfig varsayilani min_speed_mach=1.5).")
    print(f"{'irtifa':>8s} {'Mach':>5s} | {'kafa-kafaya':>11s} {'yan (90)':>9s} {'kacan (120)':>12s} | 25nmi kafa-kafaya: ucus_s / son_Mach")
    for alt in (15000.0, 25000.0, 35000.0):
        _, sos = atmosphere(alt)
        for mach in (0.75, 0.9, 1.05):
            v = mach * sos
            kw = dict(alt_ft=alt, launch_fps=v, tgt_speed=v)
            r0, r90, r120 = rmax_nm(0, **kw), rmax_nm(90, **kw), rmax_nm(120, **kw)
            res, t, mf = shoot(25.0, 0, **kw)
            print(f"{alt:8.0f} {mach:5.2f} | {r0:11.1f} {r90:9.1f} {r120:12.1f} | {res} {t:5.1f} s / M{mf:.2f}")
    print("\nDUGME DUYARLILIGI: `min_speed_mach` (25 kft, M0.9). Rmax (nmi) ve 25 nmi kafa-kafaya son Mach.")
    print(f"{'min_speed_mach':>15s} | {'kafa-kafaya':>11s} {'yan (90)':>9s} {'kacan (120)':>12s} | 25nmi: sonuc ucus_s / son_Mach")
    _, sos = atmosphere(25000.0)
    v = 0.9 * sos
    for msm in (0.8, 1.0, 1.2, 1.5, 1.8):
        kw = dict(alt_ft=25000.0, launch_fps=v, tgt_speed=v, min_speed_mach=msm)
        r0, r90, r120 = rmax_nm(0, **kw), rmax_nm(90, **kw), rmax_nm(120, **kw)
        res, t, mf = shoot(25.0, 0, **kw)
        print(f"{msm:15.1f} | {r0:11.1f} {r90:9.1f} {r120:12.1f} | {res} {t:5.1f} s / M{mf:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="kalibrasyon taramasi (irtifa x Mach x min_speed_mach)")
    args = ap.parse_args()
    if args.sweep:
        sweep()
    else:
        envelope_table()


if __name__ == "__main__":
    main()
