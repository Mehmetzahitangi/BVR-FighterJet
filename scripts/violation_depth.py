"""
IHLAL DERINLIGI: bir zarf ihlali ne kadar CIDDI?

Neden gerekli: "ihlal orani %0.057" tek basina karar verdirmez. Bariyer
-3 g'de, sonlandirma -3.5 g'de. Ihlaller -3.05 civarinda geziniyorsa bu bir
MARJ meselesidir (bariyer zaten muhafazakar konmus); -3.45'e vuruyorsa
gercek bir emniyet payi kaybidir. Ikisi tamamen farkli mudahale gerektirir.

Ayrica ihlalin SURESI olculur: tek adimlik bir gecis mi, yoksa yuzlerce
adim suren bir oturma mi.
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


def collect(policy, cfg, n_ep, seed0):
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    peaks, runs, per_ep = [], [], []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done, worst, cur, ep_steps = False, 0.0, 0, 0
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, _, term, trunc, info = env.step(a)
            v = env._intra["nz_lo"]          # adim-ici (60 Hz) en dusuk g
            worst = min(worst, v) if worst else v
            if v < ac.NZ_MIN:
                cur += 1; ep_steps += 1
                peaks.append(v)
            elif cur:
                runs.append(cur); cur = 0
            done = term or trunc
        if cur:
            runs.append(cur)
        per_ep.append(ep_steps)
    env.close()
    return np.array(peaks), np.array(runs), np.array(per_ep)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("-n", type=int, default=150)
    ap.add_argument("--seed0", type=int, default=50_000)
    a = ap.parse_args()

    rd = os.path.dirname(a.model)
    cfg = load_experiment(os.path.join(rd, "config.resolved.yaml")).env
    cfg.episode_s = 180.0
    pol = SAC.load(a.model, device="cpu")
    pk, rn, pe = collect(pol, cfg, a.n, a.seed0)

    print(f"model: {a.model}")
    print(f"bariyer nz_min = {ac.NZ_MIN} g   sonlandirma = {ac.NZ_MIN - 0.5} g")
    print(f"{a.n} bolum, ihlalli bolum: {int((pe > 0).sum())}/{a.n}")
    if len(pk) == 0:
        print("hic ihlal yok"); sys.exit(0)
    print()
    print(f"ihlalli adim sayisi        : {len(pk)}")
    print(f"ihlal derinligi  medyan    : {np.median(pk):+.3f} g")
    print(f"                 %90       : {np.quantile(pk, 0.10):+.3f} g")
    print(f"                 EN KOTU   : {pk.min():+.3f} g")
    print(f"bariyeri asma miktari medyan: {ac.NZ_MIN - np.median(pk):.3f} g")
    print(f"                      en kotu: {ac.NZ_MIN - pk.min():.3f} g")
    print()
    print(f"kesintisiz ihlal suresi  medyan: {np.median(rn):.0f} adim "
          f"({np.median(rn)/10:.1f} s)")
    print(f"                         en uzun: {rn.max():.0f} adim "
          f"({rn.max()/10:.1f} s)")
    n_deep = int((pk < ac.NZ_MIN - 0.5).sum())
    print()
    print(f"SONLANDIRMA sinirini ({ac.NZ_MIN-0.5} g) asan adim: {n_deep}")
