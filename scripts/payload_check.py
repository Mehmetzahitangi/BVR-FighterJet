"""
MUHIMMAT KUTLESI KONTROLU: dondurulmus guidance katmani, fuze agirligi
eklenince SOZLESMESINI (GUI-11) hala tutuyor mu?

=============================================================================
NEDEN GEREKLI
=============================================================================
Guidance katmani yakit %30-100 araliginda egitildi. JSBSim'den olculen
gercek agirliklar:

    bos + pilot            17.630 lb
    yakit %30              19.722 lb   <- egitim alt siniri
    yakit %100             24.602 lb   <- egitim ust siniri

4 AMRAAM = +1.340 lb. Tam yakit + tam muhimmat = 25.942 lb, yani egitim ust
sinirinin %5.5 USTUNDE. Bu, dondurulmus bir katmani egitim dagiliminin
disina cikarmaktir -- bu projede uc kez tuzaga dusulen tam olarak bu sey
(bkz. TAC-08, HANDOFF tuzak 31).

Onemli nuans: ortusme buyuk. Yakit %30 + 4 fuze = 21.062 lb ve bu araligin
TAM ICINDE. Dagilim disi bolge yalnizca AGIR kosede (yuksek yakit + tam
muhimmat).

=============================================================================
JSBSIM TUZAGI: NOKTA KUTLE RESET ARASINDA KALICIDIR
=============================================================================
Turbulans gibi, `inertia/pointmass-weight-lbs[0]` da reset ile temizlenmez.
Bu hem TUZAK hem KOLAYLIK: bir kez yazilirsa sonraki reset'lerin trim'i
onu dikkate alir. Ama olcum yaparken referans kosuya gecerken ACIKCA geri
yazilmazsa, "yuksuz" olcum aslinda yuklu cikar (bu betik yazilirken tam
olarak bu hata yapildi ve yakalandi).

F-16 modelinde yalnizca [0] yuvasi tanimli (pilot, 230 lb @ X=-336.2).
[1] yazilabiliyor ama kutle dengesine GIRMIYOR. Bu yuzden muhimmat
kutlesi [0] yuvasina eklenir ve konumu, birlesik momenti koruyacak sekilde
secilir -- yoksa CG 8 inc geriye kayar ve gevsek kararli bir ucakta bu
olcumu yanli hale getirir.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv
from bvr.config import load_experiment
from bvr.sim import aircraft as ac
from scripts.command_hold_test import CASES, hold_test

PILOT_W, PILOT_X = 230.0, -336.2
AMRAAM_LB = 335.0          # AIM-120C, yaklasik
STATION_X = -191.0         # ucagin CG'sine yakin (gercekte de oyle asilir)


def set_payload(env, n_missiles: int) -> None:
    """Muhimmat kutlesini nokta kutle [0] uzerinden ekler.

    HER kosudan once cagrilmalidir -- 0 icin de. Kalici oldugu icin
    atlanirsa onceki kosunun yuku tasinir.
    """
    f = env.sim.fdm
    extra = n_missiles * AMRAAM_LB
    w = PILOT_W + extra
    x = PILOT_X if extra == 0 else (PILOT_W * PILOT_X + extra * STATION_X) / w
    f.set_property_value("inertia/pointmass-weight-lbs[0]", w)
    f.set_property_value("inertia/pointmass-location-X-inches[0]", x)


def run_config(pol, cfg, n_msl, fuel, verbose=True):
    env = GuidanceEnv(cfg=cfg, seed=7)
    set_payload(env, n_msl)                 # trim'den ONCE, kalici oldugu icin gecerli
    ok_a = ok_m = tot = 0
    worst_a = worst_m = 0.0
    for a0, m0, ac_, mc, kind in CASES:
        env.close()
        env = GuidanceEnv(cfg=cfg, seed=7)
        set_payload(env, n_msl)
        r = _hold(env, pol, cfg, ac_, mc, a0, m0, fuel)
        if r is None:
            continue
        tot += 1
        ok_a += abs(r["alt_ss"]) <= cfg.alt_tol_ft
        ok_m += abs(r["mach_ss"]) <= cfg.mach_tol
        worst_a = max(worst_a, abs(r["alt_ss"]))
        worst_m = max(worst_m, abs(r["mach_ss"]))
    env.close()
    return ok_a, ok_m, tot, worst_a, worst_m


def _hold(env, policy, cfg, alt_cmd, mach_cmd, alt0, mach0, fuel, hold_s=90.0):
    obs, _ = env.reset(seed=7)
    env._st = env.sim.reset(alt_ft=alt0, mach=mach0, heading_deg=0.0,
                            trim=True, fuel_frac=fuel)
    env.inner.reset(trim_throttle=env.sim["fcs/throttle-cmd-norm"])
    if env.shield is not None:
        env.shield.reset_state()
    env.tgt_n = env._st.north_ft + 30 * 6076.0
    env.tgt_e = env._st.east_ft
    env.tgt_alt, env.tgt_mach = alt_cmd, mach_cmd
    env._prev_range = env._range_to_target()
    env._prev_alt_err = abs(alt_cmd - env._st.alt_ft)
    env._prev_mach_err = abs(mach_cmd - env._st.mach)
    obs = env._obs()
    ae, me = [], []
    for k in range(int(hold_s * cfg.outer_hz)):
        a, _ = policy.predict(obs, deterministic=True)
        obs, _, term, trunc, _ = env.step(a)
        env.tgt_alt, env.tgt_mach = alt_cmd, mach_cmd
        ae.append(env._st.alt_ft - alt_cmd)
        me.append(env._st.mach - mach_cmd)
        if term:
            return None
    w = int(30.0 * cfg.outer_hz)
    return dict(alt_ss=float(np.mean(ae[-w:])), mach_ss=float(np.mean(me[-w:])))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    a = ap.parse_args()
    rd = os.path.dirname(a.model)
    cfg = load_experiment(os.path.join(rd, "config.resolved.yaml")).env
    cfg.episode_s = 600.0
    pol = SAC.load(a.model, device="cpu")

    #  (etiket, fuze sayisi, yakit orani)
    CONFIGS = [
        ("referans: 0 fuze, yakit %60", 0, 0.60),
        ("0 fuze, yakit %100",          0, 1.00),
        ("4 fuze, yakit %30",           4, 0.30),
        ("4 fuze, yakit %60",           4, 0.60),
        ("4 fuze, yakit %100 (EN AGIR)",4, 1.00),
    ]
    print(f"model: {a.model}")
    print(f"AMRAAM {AMRAAM_LB:.0f} lb/adet, istasyon X={STATION_X:.0f} in\n")
    print(f"{'konfigurasyon':<32} {'irtifa':>8} {'mach':>8} {'en kotu irt':>12} {'en kotu M':>10}")
    for lbl, nm, fu in CONFIGS:
        oa, om, tot, wa, wm = run_config(pol, cfg, nm, fu)
        print(f"{lbl:<32} {oa:>4}/{tot:<3} {om:>4}/{tot:<3} "
              f"{wa:>10.0f}ft {wm:>10.4f}", flush=True)
