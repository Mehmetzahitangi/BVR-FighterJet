"""
POLITIKA DAVRANIS TANILAMASI.

Tacview'de gozle gorulen sikayetleri SAYIYA cevirir:
  1. "Ucak asagi gitme egiliminde mi?"     -> irtifa surukleni, gamma ortalamasi
  2. "Titreyerek sag-sola gidiyor mu?"     -> aksiyon isaret degistirme orani,
                                              baskin salinim frekansi
  3. "Ara ara sert hareket yapiyor mu?"    -> aksiyon sicramalarinin dagilimi

Neden sayiya cevirmek gerekli: gorsel izlenim yon verir ama olcumsuz
duzeltme yapilmaz. "Titriyor" -> hangi kanalda, kac Hz'de, ne genlikte?
Bunlar bilinmeden dogru duzeltmenin (odul cezasi mi, komut filtresi mi,
kalkan mi) hangisi oldugu secilemez.
"""
import sys
import os
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig


def collect(model, use_shield, n_ep=6, episode_s=180.0, seed0=10_000):
    cfg = GuidanceConfig(episode_s=episode_s, turbulence_prob=0.3,
                         use_shield=use_shield)
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    eps = []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        rows = []
        done = False
        while not done:
            a, _ = model.predict(obs, deterministic=True)
            a = np.asarray(a, dtype=np.float64)
            obs, r, term, trunc, info = env.step(a)
            st = env._st
            rows.append([st.alt_ft, math.degrees(st.gamma_rad),
                         math.degrees(st.phi_rad), st.mach,
                         a[0], a[1], a[2],
                         env._last_applied[0], env._last_applied[1],
                         env._last_applied[2],
                         env.tgt_alt])
            done = term or trunc
        eps.append(np.array(rows))
    return eps, env


def chatter(a: np.ndarray, dt: float = 0.1):
    """Titreme metrikleri: isaret degistirme orani ve baskin frekans."""
    d = np.diff(a)
    if len(d) < 4:
        return dict(sign_rate=np.nan, f_peak=np.nan, rms_rate=np.nan)
    # Kac adimda bir komut YON degistiriyor? 0.5 = her iki adimda bir
    # (yani 5 Hz salinim) -> agir titreme.
    sign_rate = float(np.mean(np.sign(d[1:]) != np.sign(d[:-1])))
    # Baskin salinim frekansi (DC cikarilmis guc spektrumu)
    x = a - a.mean()
    P = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), dt)
    P[0] = 0.0
    return dict(sign_rate=sign_rate, f_peak=float(f[np.argmax(P)]),
                rms_rate=float(np.sqrt(np.mean(d ** 2))))


def report(tag, eps):
    A = np.concatenate(eps)
    names = ["phi_cmd", "gamma_cmd", "mach_cmd"]
    print(f"--- {tag} ---")
    # 1) Irtifa egilimi
    drift = [e[-1, 0] - e[0, 0] for e in eps]
    gam_mean = [e[:, 1].mean() for e in eps]
    # Hedefe gore: ajan hedef irtifanin altinda mi kaliyor?
    alt_bias = [np.mean(e[:, 0] - e[:, 10]) for e in eps]
    print(f"  irtifa suruklenisi (bolum sonu - basi) : "
          f"{np.mean(drift):+8.0f} ft  (bolum bazinda "
          f"{np.array2string(np.array(drift), precision=0, max_line_width=200)})")
    print(f"  ortalama gamma                          : {np.mean(gam_mean):+7.2f} deg")
    print(f"  HEDEFE gore irtifa yanliligi            : {np.mean(alt_bias):+8.0f} ft "
          f"(negatif = surekli hedefin ALTINDA)")
    # 2) Titreme
    print("  titreme (aksiyon kanallari):")
    for i, nm in enumerate(names):
        m = chatter(A[:, 4 + i])
        ma = chatter(A[:, 7 + i])
        print(f"    {nm:<10} istenen: yon-degisim %{100*m['sign_rate']:4.1f} "
              f"f_tepe {m['f_peak']:.2f} Hz  rms_hiz {m['rms_rate']:.3f}   |  "
              f"uygulanan: %{100*ma['sign_rate']:4.1f} rms {ma['rms_rate']:.3f}")
    # 3) Sert hareketler
    d = np.abs(np.diff(A[:, 4:7], axis=0)).max(axis=1)
    print(f"  aksiyon sicramasi: p95={np.percentile(d,95):.3f} "
          f"p99={np.percentile(d,99):.3f} max={d.max():.3f} "
          f"(|da|>0.5 olan adim orani %{100*np.mean(d>0.5):.2f})")
    print()


def plot(eps_ns, eps_sh, path):
    fig, ax = plt.subplots(4, 2, figsize=(15, 11), sharex="col")
    for col, (eps, ttl) in enumerate([(eps_ns, "KALKAN KAPALI"),
                                      (eps_sh, "KALKAN ACIK")]):
        e = eps[0]
        t = np.arange(len(e)) * 0.1
        ax[0, col].plot(t, e[:, 0], label="irtifa")
        ax[0, col].plot(t, e[:, 10], "k--", lw=1, label="hedef irtifa")
        ax[0, col].set_ylabel("irtifa [ft]"); ax[0, col].legend(fontsize=7)
        ax[0, col].set_title(ttl, fontsize=11)
        ax[1, col].plot(t, e[:, 1], lw=0.8)
        ax[1, col].axhline(0, color="k", lw=0.5)
        ax[1, col].set_ylabel("gamma [deg]")
        ax[2, col].plot(t, e[:, 4], lw=0.8, label="phi_cmd istenen")
        ax[2, col].plot(t, e[:, 7], lw=0.8, label="phi_cmd uygulanan")
        ax[2, col].set_ylabel("phi komutu [-1,1]"); ax[2, col].legend(fontsize=7)
        ax[3, col].plot(t, e[:, 5], lw=0.8, label="gamma_cmd istenen")
        ax[3, col].plot(t, e[:, 8], lw=0.8, label="gamma_cmd uygulanan")
        ax[3, col].set_ylabel("gamma komutu"); ax[3, col].set_xlabel("zaman [s]")
        ax[3, col].legend(fontsize=7)
        for a in ax[:, col]:
            a.grid(alpha=.3)
    fig.suptitle("Politika davranisi: irtifa egilimi ve komut titremesi", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(f"Grafik: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/guidance_v2/sac_final.zip")
    ap.add_argument("-n", type=int, default=6)
    args = ap.parse_args()

    model = SAC.load(args.model, device="cpu")
    eps_ns, _ = collect(model, False, args.n)
    report("KALKAN KAPALI", eps_ns)
    eps_sh, env = collect(model, True, args.n)
    report("KALKAN ACIK", eps_sh)
    os.makedirs("runs", exist_ok=True)
    plot(eps_ns, eps_sh, "runs/policy_diagnosis.png")
