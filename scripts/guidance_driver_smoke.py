"""
GuidanceDriver duman testi: GuidanceEnv'in fizik davranisiyla BIREBIR AYNI
sonucu urettigini kanitlar.

Yontem: GuidanceEnv ve GuidanceDriver'i AYNI baslangic kosuluna (elle, trim
ile) kur, AYNI (sabit tohumlu rastgele) aksiyon dizisini ikisine de ver,
her adimda ortaya cikan FlightState'i alan alan karsilastir.

Kullanim:
    python -m scripts.guidance_driver_smoke
"""
from __future__ import annotations

import numpy as np

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.envs.guidance_driver import GuidanceDriver

ALT0, MACH0, HDG0 = 20000.0, 0.80, 45.0
N_STEPS = 200
FIELDS = ["t", "alt_ft", "north_ft", "east_ft", "phi_rad", "theta_rad", "psi_rad",
          "gamma_rad", "mach", "vt_fps", "alpha_rad", "beta_rad", "nz", "fuel_frac"]


def main() -> None:
    cfg = GuidanceConfig(use_shield=False)

    env = GuidanceEnv(cfg=cfg, seed=1)
    env.reset(seed=1)
    env._st = env.sim.reset(alt_ft=ALT0, mach=MACH0, heading_deg=HDG0,
                             trim=True, fuel_frac=0.65)
    env.inner.reset(trim_throttle=env.sim["fcs/throttle-cmd-norm"])
    env._last_applied = np.zeros(3)
    # step()'in kullandigi ama _obs disinda gerekli olmayan hedef alanlarini
    # gecerli tut (waypoint mantigi tetiklenmesin diye cok uzak bir hedef).
    env.tgt_n = env._st.north_ft + 10 * 6076.0
    env.tgt_e = env._st.east_ft
    env.tgt_alt, env.tgt_mach = ALT0, MACH0
    env._prev_range = env._range_to_target()
    env._prev_alt_err = 0.0
    env._prev_mach_err = 0.0

    driver = GuidanceDriver(cfg=cfg, seed=1)
    driver.reset(alt_ft=ALT0, mach=MACH0, heading_deg=HDG0, fuel_frac=0.65)

    rng = np.random.default_rng(42)
    max_abs_diff = {f: 0.0 for f in FIELDS}
    first_mismatch_step = None

    for k in range(N_STEPS):
        action = rng.uniform(-0.3, 0.3, size=3).astype(np.float32)

        obs, r, term, trunc, info = env.step(action)
        st_driver = driver.tick(action)
        st_env = env._st

        for f in FIELDS:
            d = abs(getattr(st_env, f) - getattr(st_driver, f))
            if d > max_abs_diff[f]:
                max_abs_diff[f] = d
            if d > 1e-6 and first_mismatch_step is None:
                first_mismatch_step = (k, f, getattr(st_env, f), getattr(st_driver, f))

        if term:
            print(f"UYARI: env {k}. adimda sonlandi (beklenmiyordu), test kisaltildi.")
            break

    print(f"{N_STEPS} adim, alan basina en buyuk mutlak fark (env vs driver):")
    for f in FIELDS:
        print(f"  {f:<10} {max_abs_diff[f]:.3e}")

    if first_mismatch_step is None:
        print("\nSONUC: GuidanceEnv ve GuidanceDriver TUM adimlarda (1e-6 toleransla) "
              "BIREBIR AYNI fizigi uretti.")
    else:
        k, f, ev, dv = first_mismatch_step
        print(f"\nSONUC: FARK VAR -- ilk sapma adim {k}, alan '{f}': env={ev} driver={dv}")


if __name__ == "__main__":
    main()
