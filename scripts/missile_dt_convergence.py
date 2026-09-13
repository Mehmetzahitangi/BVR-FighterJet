"""
Fuze gudum donguesu dt-yakinsama olcumu (Faz 1.4/1.5 tasarim karari).

Soru: Engagement muhasebe katmani 10 Hz'de (dt=0.1) calisirken, fuze fizigini
de disaridaki AYNI dt ile mi guncellemeli, yoksa kendi icinde daha ince
alt-adimlarla mi kosturmali?

Yontem: bvr.combat.missile.Missile'i (GERCEK kod, port degil) uc senaryoda --
manevrasiz hedef, 3g surekli yanal manevra, 6g surekli yanal manevra -- farkli
dt degerleriyle kosturup sonucu (isabet/iska) ve ulasilan en yakin mesafeyi
karsilastirir. dt=0.002 referans (pratikte surekli-zaman) kabul edilir.

Kullanim:
    python scripts/missile_dt_convergence.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from bvr.combat.missile import Missile, MissileConfig

G0 = 32.174049


def run_scenario(dt: float, max_time_s: float, maneuver_g: float) -> dict:
    cfg = MissileConfig()
    launch = type("Launch", (), {"pos_ft": np.array([0.0, 0.0, 30000.0]), "vel_fps": np.array([900.0, 0.0, 0.0])})()
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([30000.0, 0.0, 30000.0])
    target_vel = np.array([0.0, 800.0, 0.0])

    n_steps = int(np.ceil(max_time_s / dt))
    state = None
    for _ in range(n_steps):
        if maneuver_g:
            target_vel = target_vel + np.array([0.0, maneuver_g * G0 * dt, 0.0])
        target_pos = target_pos + target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        if not state.alive:
            break

    return {
        "dt": dt,
        "hz": 1.0 / dt,
        "result": state.result,
        "min_range_ft": missile._min_range_ft,
        "t_final": state.t_since_launch,
    }


def print_table(title: str, maneuver_g: float, dts: list[float]) -> None:
    print(f"\n=== {title} ===")
    print(f"{'dt (s)':>8} | {'Hz':>7} | {'sonuc':<7} | {'min_menzil_ft':>14} | {'t_final':>8}")
    for dt in dts:
        r = run_scenario(dt, max_time_s=40.0, maneuver_g=maneuver_g)
        print(f"{r['dt']:>8.3f} | {r['hz']:>7.1f} | {r['result']:<7} | {r['min_range_ft']:>14.4f} | {r['t_final']:>8.3f}")


if __name__ == "__main__":
    dts = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1]
    print_table("Senaryo A: sabit hizli hedef (kriter 4, manevrasiz)", 0.0, dts)
    print_table("Senaryo B: 3g surekli yanal manevra", 3.0, dts)
    print_table("Senaryo C: 6g surekli yanal manevra (sert/marjinal)", 6.0, dts)

    print("\nNot: bu script bvr/combat/engagement.py'nin alt-adim (missile_substeps)")
    print("mantigini KULLANMAZ -- Missile.update()'i dogrudan, tek katmanda cagirir.")
    print("Amac, disaridaki muhasebe adiminin (10 Hz) fuze fizigi icin tek basina")
    print("yeterli olup olmadigini olcmekti; sonuc: degildi (bkz. REQUIREMENTS.md ENG-10).")
