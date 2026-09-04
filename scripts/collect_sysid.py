"""
Sistem tanimlama veri seti topla + KAPSAMA RAPORU uret.

Kapsama raporu neden onemli:
Bir Koopman/DMD modeli, ancak VERININ GECTIGI bolgede gecerlidir. Model
hicbir zaman gormedigi bir ucus rejiminde saglam tahmin yapamaz -- ve
CBF o tahmine guvenerek "guvenli" diyorsa, guvenlik yanilsamadir.
Bu yuzden modeli fit etmeden ONCE verinin durum uzayini ne kadar
kapladigini gormek gerekir.

Ayrica raporda KALICI UYARIM (persistent excitation) tanisi var:
regresyon matrisi [X; U]'nun tekil degerleri ve kosul sayisi. Kosul sayisi
cok buyukse veri bazi yonlerde bilgi tasimiyordur -- model o yonlerde
gurultu uydurur.

Kullanim:
  python scripts/collect_sysid.py --episodes 600 --workers 8
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bvr.sysid.collect import collect, CollectConfig
from bvr.models.state_def import X_NAMES, U_NAMES, normalize_x, normalize_u


def coverage_report(X, U, Xn, out_png):
    print()
    print("=" * 74)
    print("KAPSAMA RAPORU")
    print("=" * 74)
    print(f"{'durum':>12} {'min':>10} {'p5':>10} {'ortanca':>10} {'p95':>10} {'max':>10}")
    for i, name in enumerate(X_NAMES):
        c = X[:, i]
        print(f"{name:>12} {c.min():10.3f} {np.percentile(c,5):10.3f} "
              f"{np.median(c):10.3f} {np.percentile(c,95):10.3f} {c.max():10.3f}")
    print()
    print(f"{'girdi':>14} {'min':>10} {'ortanca':>10} {'max':>10}")
    for i, name in enumerate(U_NAMES):
        c = U[:, i]
        print(f"{name:>14} {c.min():10.3f} {np.median(c):10.3f} {c.max():10.3f}")

    # --- Kalici uyarim tanisi ---
    Z = normalize_x(X)
    W = normalize_u(U)
    Om = np.hstack([Z, W])
    Om = Om - Om.mean(axis=0, keepdims=True)
    s = np.linalg.svd(Om, compute_uv=False)
    print()
    print("KALICI UYARIM (persistent excitation) TANISI")
    print(f"  [X|U] tekil degerleri: {np.array2string(s, precision=2, max_line_width=200)}")
    print(f"  kosul sayisi (cond)  : {s[0]/s[-1]:.1f}")
    if s[0] / s[-1] > 1e3:
        print("  UYARI: kosul sayisi yuksek -- bazi yonlerde veri bilgi tasimiyor.")
    else:
        print("  Kosul sayisi makul; regresyon iyi kosullanmis.")

    # --- Grafik ---
    fig = plt.figure(figsize=(14, 9))
    for i, name in enumerate(X_NAMES):
        ax = fig.add_subplot(3, 4, i + 1)
        ax.hist(X[:, i], bins=60, color="steelblue")
        ax.set_title(name, fontsize=9)
        ax.tick_params(labelsize=7)
    ax = fig.add_subplot(3, 4, 11)
    ax.hexbin(X[:, 3], X[:, 2], gridsize=45, cmap="viridis", bins="log")
    ax.set_xlabel("alt_ft", fontsize=8); ax.set_ylabel("mach", fontsize=8)
    ax.set_title("isletme zarfi kapsamasi", fontsize=9); ax.tick_params(labelsize=7)
    ax = fig.add_subplot(3, 4, 12)
    ax.semilogy(s, "o-", ms=3)
    ax.set_title("[X|U] tekil degerleri", fontsize=9)
    ax.grid(alpha=.3); ax.tick_params(labelsize=7)
    fig.suptitle("Sistem tanimlama veri seti - kapsama", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    print(f"\nKapsama grafigi: {out_png}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=600)
    ap.add_argument("--episode-sec", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", type=str, default="data/sysid_train.npz")
    ap.add_argument("--seed0", type=int, default=0)
    args = ap.parse_args()

    cfg = CollectConfig(episode_s=args.episode_sec)
    print(f"Toplaniyor: {args.episodes} bolum x {args.episode_sec:.0f} s, "
          f"{args.workers} isci")
    t0 = time.time()
    res = collect(args.episodes, args.out, cfg, seed0=args.seed0,
                  n_workers=args.workers)
    dt = time.time() - t0

    print()
    print(f"Kaydedildi     : {res['path']}")
    print(f"Gecis sayisi   : {res['n_transitions']:,}")
    print(f"Basarili bolum : {res['n_episodes']}/{args.episodes}")
    print(f"Bitis sebepleri: {res['reasons']}")
    print(f"Sure           : {dt:.1f} s "
          f"({args.episodes*args.episode_sec/dt:.0f}x gercek zaman)")

    coverage_report(res["X"], res["U"], res["Xn"],
                    args.out.replace(".npz", "_coverage.png"))
