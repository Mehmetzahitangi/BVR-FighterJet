"""
ROBUST CBF ODUNLESIM EGRISI: guven seviyesi q -> (guvenlik, performans).

Robust CBF'te tek bir "dogru" ayar yoktur; secilen guven yuzdeligi q,
dogrudan bir GUVENLIK/PERFORMANS ODUNLESIMI belirler:

  q buyudukce  -> marj buyur -> ihlal azalir, gorev performansi duser
  q kucukse    -> marj kucuk -> performans korunur, ihlal kalir

Bu betik egriyi cikarir. Tezde tek bir tablo/grafik olarak sunulur ve
"hangi q secilmeli" sorusu, gorevin risk toleransina birakilir --
muhendislik acisindan dogru cerceve budur.

Marjlar ayrica UFUK bazinda uygulanabilir: kisa ufukta model dogru,
uzun ufukta degil. `--max-margin-horizon` ile yalnizca kisa ufuklara
marj uygulanabilir (uzun ufuklar yine de sezgisel ongoru saglar).
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from stable_baselines3 import SAC

from bvr.models.base import DynamicsModel
from bvr.safety.robust import compute_margins
from bvr.sysid.evaluate import load_dataset
from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.safety.cbf import CBFShield
from bvr.sim import aircraft as ac

BARRIERS = [
    ("alpha_max", "alpha", ac.ALPHA_MAX_DEG, +1),
    ("beta_max", "beta", ac.BETA_MAX_DEG, +1),
    ("nz_max", "nz_hi", ac.NZ_MAX, +1),
    ("nz_min", "nz_lo", ac.NZ_MIN, -1),
    ("mach_min", "mach_marg", 0.0, -1),
]


def evaluate(policy, margins, n_ep, episode_s, seed0=10_000):
    cfg = GuidanceConfig(episode_s=episode_s, use_shield=True, turbulence_prob=0.3)
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    if margins is not None:
        env.shield.margins = np.asarray(margins, float)
    R, W, T = [], [], []
    viol = {b[0]: 0 for b in BARRIERS}
    n = 0
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done, r_ = False, 0.0
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, r, t, tr, info = env.step(a)
            r_ += r
            n += 1
            p = env._intra
            for name, key, lim, sgn in BARRIERS:
                if (p[key] - lim if sgn > 0 else lim - p[key]) > 0:
                    viol[name] += 1
            done = t or tr
        R.append(r_)
        W.append(info.get("episode_waypoints", 0))
        T.append(info.get("termination", "timeout"))
    rate = 100.0 * sum(viol.values()) / max(n, 1)
    return dict(reward=float(np.mean(R)), wpts=float(np.mean(W)),
                term=sum(1 for t in T if t != "timeout"),
                viol_rate=rate, viol=viol,
                shield=env.shield.stats.summary())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/guidance_v5_smooth_shield/sac_final.zip")
    ap.add_argument("-n", type=int, default=16)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    ap.add_argument("--max-margin-horizon", type=int, default=None,
                    help="bu ufuktan uzun ufuklara marj uygulama")
    args = ap.parse_args()

    pol = SAC.load(args.model, device="cpu")
    model = DynamicsModel.load("data/models/edmd_physics.pkl")
    val = load_dataset("data/sysid_val.npz")
    H = CBFShield.DEFAULT_HORIZONS
    nb = 9   # envelope_constraints satir sayisi

    rows = []
    for q in [None, 0.80, 0.90, 0.95, 0.99]:
        if q is None:
            m, label = None, "marj yok"
        else:
            m = compute_margins(model, val, H, quantile=q)
            if args.max_margin_horizon is not None:
                for k, h in enumerate(sorted(H)):
                    if h > args.max_margin_horizon:
                        m[k * nb:(k + 1) * nb] = 0.0
            label = f"q={q}"
        r = evaluate(pol, m, args.n, args.episode_sec)
        r["label"] = label
        rows.append(r)
        print(f"{label:<10} odul {r['reward']:7.1f}  hedef {r['wpts']:5.2f}  "
              f"erken-son {r['term']}  ihlal %{r['viol_rate']:.4f}  "
              f"mudahale %{100*r['shield']['mudahale_orani']:.1f}  "
              f"slack %{100*r['shield']['slack_orani']:.1f}", flush=True)
        for k, v in r["viol"].items():
            if v:
                print(f"             {k}: {v}")

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    lbl = [r["label"] for r in rows]
    x = np.arange(len(rows))
    ax[0].bar(x, [r["viol_rate"] for r in rows], color="crimson")
    ax[0].set_xticks(x); ax[0].set_xticklabels(lbl)
    ax[0].set_ylabel("zarf ihlal orani [%]"); ax[0].grid(alpha=.3, axis="y")
    ax[0].set_title("Guvenlik", fontsize=10)
    ax[1].plot([r["viol_rate"] for r in rows], [r["reward"] for r in rows], "o-")
    for r in rows:
        ax[1].annotate(r["label"], (r["viol_rate"], r["reward"]), fontsize=8,
                       textcoords="offset points", xytext=(5, 5))
    ax[1].set_xlabel("zarf ihlal orani [%]"); ax[1].set_ylabel("bolum odulu")
    ax[1].set_title("Guvenlik / performans odunlesimi", fontsize=10)
    ax[1].grid(alpha=.3)
    fig.tight_layout()
    fig.savefig("runs/margin_sweep.png", dpi=110)
    print("\nruns/margin_sweep.png")
