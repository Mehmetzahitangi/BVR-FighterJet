"""
IHLALIN KAYNAGI: ruzgar darbesi mi, ic dongunun kendi dinamik asimi mi?

Neden ayirmak zorundayiz: ic dongu, n_cmd'yi yapisi geregi -2.0 g'nin
altina indiremez (gamma_dot limiti yatisa gore turetiliyor, sonra
kinematik ters cevriliyor). Yani olculen -4.58 g'nin TAMAMI asimdir.
Asimin kaynagi iki farkli cozum gerektirir:

  ruzgar darbesi  -> komut kisitlamak ISE YARAMAZ; pay birakmak veya
                     daha hizli bir filtre gerekir
  dinamik asim    -> n dongusunun PI ayari / ileri-besleme kazanci
                     duzeltilebilir; ucuz ve hedefli

Yontem: her bolumde turbulans acik mi kapali mi kaydedilir (ortam %30
olasilikla aciyor), ihlal oranlari iki grupta ayri olculur. Ayrica ihlal
aninda KOMUT EDILEN n ile GERCEKLESEN n arasindaki fark (asim) olculur.
"""
import sys
import os
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv
from bvr.config import load_experiment
from bvr.sim import aircraft as ac


def collect(policy, cfg, n_ep, seed0):
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    rows = []          # (turb_acik, adim, ihlal, en_kotu_nz)
    overshoot = []     # ihlal aninda: (n_cmd, gerceklesen_nz)
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        # Turbulans ortam tarafindan reset'te ayarlandi; JSBSim'den okuyoruz
        turb = float(env.sim["atmosphere/wind-mag-fps"]) > 1.0
        n_steps = n_viol = 0
        worst = 0.0
        done = False
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, _, term, trunc, info = env.step(a)
            n_steps += 1
            v = env._intra["nz_lo"]
            worst = min(worst, v) if worst else v
            if v < ac.NZ_MIN:
                n_viol += 1
                # Ic dongunun son komut ettigi n (tanilama alanindan)
                overshoot.append((float(env.inner.last_n_cmd)
                                  if hasattr(env.inner, "last_n_cmd") else np.nan, v))
            done = term or trunc
        rows.append((turb, n_steps, n_viol, worst))
    env.close()
    return rows, overshoot


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
    rows, ov = collect(pol, cfg, a.n, a.seed0)

    T = [r for r in rows if r[0]]
    C = [r for r in rows if not r[0]]
    print(f"model: {a.model}")
    print(f"{a.n} bolum -> turbulansli {len(T)}, sakin {len(C)}\n")
    print(f"{'grup':<14} {'bolum':>7} {'ihlal orani':>13} {'ihlalli bolum':>15} {'en kotu nz':>12}")
    for nm, G in (("TURBULANSLI", T), ("SAKIN", C)):
        if not G:
            print(f"{nm:<14} {'--':>7}"); continue
        rate = np.mean([r[2] / max(r[1], 1) for r in G])
        nviol = sum(1 for r in G if r[2] > 0)
        worst = min(r[3] for r in G)
        print(f"{nm:<14} {len(G):>7} {rate:13.5f} {nviol:>10}/{len(G):<4} {worst:12.3f}")

    rt = np.mean([r[2]/max(r[1],1) for r in T]) if T else 0.0
    rc = np.mean([r[2]/max(r[1],1) for r in C]) if C else 0.0
    print()
    if rc > 0:
        print(f"-> turbulansli/sakin ihlal orani: {rt/rc:.1f} kat")
    elif rt > 0:
        print("-> SAKIN havada HIC ihlal yok: kaynak TAMAMEN atmosferik")
    print()
    print("YORUM ANAHTARI")
    print("  oran turbulansli grupta cok yuksekse -> ruzgar darbesi baskin;")
    print("     komut kisitlamak ise yaramaz, pay/hizli filtre gerekir.")
    print("  iki grup benzerse -> ic dongu dinamik asimi baskin;")
    print("     n dongusunun PI/ileri-besleme ayari hedefli duzeltilebilir.")
