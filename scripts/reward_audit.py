"""
ODUL DENETIMI: adim odulunun teorik araligi + politikanin FIILEN nereden
odul topladigi + ulasilabilir tavan.

Neden gerekli: "bolum odulu 2390" tek basina hicbir sey ifade etmez.
Anlamli olmasi icin uc sey bilinmeli:
  1. Adim odulunun teorik alt/ust siniri
  2. FIZIKSEL olarak ulasilabilir tavan (butun terimler ayni anda maksimum
     olamaz -- menzili kapatirken irtifayi da kapatmak birbiriyle yarisir)
  3. Politikanin her terimden ne kadar aldigi -> masada ne kaldigi
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.config import load_experiment


def theoretical_range(c: GuidanceConfig):
    pos = dict(
        ilerleme=c.w_progress * 1.0,
        irtifa_ilerleme=c.w_alt_prog * 1.0,
        mach_ilerleme=c.w_mach_prog * 1.0,
        irtifa_hassasiyet=c.w_alt_prec * 1.0,
        mach_hassasiyet=c.w_mach_prec * 1.0,
    )
    neg = dict(
        ilerleme=-c.w_progress,
        irtifa_ilerleme=-c.w_alt_prog,
        mach_ilerleme=-c.w_mach_prog,
        komut_cezasi=-c.w_action_rate * 3 * (2 * c.action_rate_limit) ** 2,
    )
    return pos, neg


def decompose(policy, cfg, n_ep=20, seed0=10_000):
    """Bolum boyunca her odul terimini AYRI topla (ortami degistirmeden yeniden hesapla)."""
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    acc = {k: [] for k in ("ilerleme", "irtifa_ilerleme", "mach_ilerleme",
                           "irtifa_hassasiyet", "mach_hassasiyet",
                           "komut_cezasi", "hedef_bonusu", "carpma")}
    totals, wpts = [], []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done, tot = False, 0.0
        ep_acc = {k: 0.0 for k in acc}
        pr, pa, pm = env._prev_range, env._prev_alt_err, env._prev_mach_err
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            a = np.clip(np.asarray(a, float), -1, 1)
            prev_applied = env._last_applied.copy()
            obs, r, term, trunc, info = env.step(a)
            st = env._st
            c = cfg
            dt = 1.0 / c.outer_hz
            rng = env._range_to_target()
            # env icindeki formullerin aynisi (env DEGISTIRILMEDEN yeniden hesap)
            closure = (pr - rng) / max(st.vt_fps * dt, 1.0)
            ep_acc["ilerleme"] += c.w_progress * float(np.clip(closure, -1, 1))
            da, dm = abs(env.tgt_alt - st.alt_ft), abs(env.tgt_mach - st.mach)
            ep_acc["irtifa_ilerleme"] += c.w_alt_prog * float(
                np.clip((pa - da) / c.alt_prog_scale_ft, -1, 1))
            ep_acc["mach_ilerleme"] += c.w_mach_prog * float(
                np.clip((pm - dm) / c.mach_prog_scale, -1, 1))
            ep_acc["irtifa_hassasiyet"] += c.w_alt_prec * math.exp(
                -((env.tgt_alt - st.alt_ft) / c.alt_prec_ft) ** 2)
            ep_acc["mach_hassasiyet"] += c.w_mach_prec * math.exp(
                -((env.tgt_mach - st.mach) / c.mach_prec) ** 2)
            ep_acc["komut_cezasi"] -= c.w_action_rate * float(
                np.sum((a - prev_applied) ** 2))
            if "waypoint" in info:
                w = info["waypoint"]
                ep_acc["hedef_bonusu"] += c.r_waypoint * (
                    0.4 + 0.4 * w["alt_ok"] + 0.2 * w["mach_ok"])
            if term:
                ep_acc["carpma"] += c.r_crash
            pr, pa, pm = rng, da, dm
            tot += r
            done = term or trunc
        for k in acc:
            acc[k].append(ep_acc[k])
        totals.append(tot)
        wpts.append(info.get("episode_waypoints", 0))
    return acc, totals, wpts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args()

    rd = os.path.dirname(a.model)
    y = os.path.join(rd, "config.resolved.yaml")
    cfg = load_experiment(y).env if os.path.exists(y) else GuidanceConfig()
    n_steps = int(cfg.episode_s * cfg.outer_hz)

    pos, neg = theoretical_range(cfg)
    print("=" * 70)
    print("1) ADIM ODULUNUN TEORIK ARALIGI")
    print("=" * 70)
    print(f"  {'terim':<22} {'max':>7} {'min':>7}")
    for k in pos:
        print(f"  {k:<22} {pos[k]:7.2f} {neg.get(k, 0.0):7.2f}")
    print(f"  {'komut_cezasi':<22} {0.0:7.2f} {neg['komut_cezasi']:7.2f}")
    print(f"  {'TOPLAM / adim':<22} {sum(pos.values()):7.2f} "
          f"{sum(neg.values()):7.2f}")
    print(f"  olay bazli: hedef bonusu +{cfg.r_waypoint*0.4:.0f}..+{cfg.r_waypoint:.0f}"
          f"   carpma {cfg.r_crash:+.0f}")
    print()
    print(f"  Bolum = {n_steps} adim ({cfg.episode_s:.0f} s @ {cfg.outer_hz:.0f} Hz)")
    print(f"  Kaba ust sinir  : {sum(pos.values())*n_steps:8.0f}  (ULASILAMAZ:")
    print( "                     terimler birbiriyle yarisir -- menzili kapatirken")
    print( "                     irtifa/Mach ilerlemesi ayni anda maks olamaz)")
    print()
    print("=" * 70)
    print("2) FIZIKSEL OLARAK ULASILABILIR TAVAN (kararli izleme)")
    print("=" * 70)
    ceil_step = cfg.w_progress + cfg.w_alt_prec + cfg.w_mach_prec
    print(f"  Hedefe DOGRUDAN ucan + irtifa/Mach TOLERANSTA olan ucak:")
    print(f"    ilerleme {cfg.w_progress:.1f} + irtifa_hassasiyet {cfg.w_alt_prec:.1f}"
          f" + mach_hassasiyet {cfg.w_mach_prec:.1f} = {ceil_step:.1f}/adim")
    print(f"  -> {ceil_step*n_steps:.0f} + hedef bonuslari (~{cfg.r_waypoint*2:.0f})"
          f"  ~= {ceil_step*n_steps + cfg.r_waypoint*2:.0f}")
    print()
    print("=" * 70)
    print(f"3) POLITIKANIN FIILI DAGILIMI  ({a.n} bolum)")
    print("=" * 70)
    acc, totals, wpts = decompose(SAC.load(a.model, device="cpu"), cfg, a.n)
    tm = float(np.mean(totals))
    print(f"  {'terim':<22} {'bolum basi':>11} {'% (pozitif icinde)':>20}")
    tot_pos = sum(np.mean(v) for v in acc.values() if np.mean(v) > 0)
    for k, v in acc.items():
        m = float(np.mean(v))
        pct = 100 * m / tot_pos if m > 0 else 0.0
        print(f"  {k:<22} {m:11.1f} {pct:19.1f}%")
    print(f"  {'TOPLAM':<22} {tm:11.1f}")
    print()
    print(f"  hedef/bolum {np.mean(wpts):.2f}   "
          f"tavana oran %{100*tm/(ceil_step*n_steps + cfg.r_waypoint*2):.0f}")
