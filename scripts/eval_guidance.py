"""
Egitilmis guidance politikasini degerlendir + Tacview kaydi uret.

Odul egrisine bakarak "iyi mi" karari VERILMEZ. Gorev metrikleri olculur:
  - bolum basina ulasilan hedef sayisi
  - basari orani (>=3 hedef ve erken sonlanma yok)
  - erken sonlanma sebeplerinin dagilimi
  - hedefe varista irtifa/Mach toleransi tutturma orani
  - ZARF ASIMLARI: alpha/beta/n/Mach sinirlarina ne kadar yaklasildi
    (kalkanin sonradan ne kadar isi kalacaginin olcusu -- P4 icin taban)
  - komut yumusakligi (aksiyon degisim RMS): PIO/titreme gostergesi

Kullanim:
  python scripts/eval_guidance.py --model runs/guidance_v1/sac_final.zip -n 30
"""
import sys
import os
import math
import argparse
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.sim.acmi import ACMIRecorder
from bvr.sim import aircraft as ac


def evaluate(model_path, n_episodes=30, episode_s=180.0, seed0=10_000,
             acmi_path=None, deterministic=True, use_shield=False):
    cfg = GuidanceConfig(episode_s=episode_s, turbulence_prob=0.3,
                         use_shield=use_shield)
    if model_path == "scripted":
        # Klasik gudum taban cizgisi: RL'in kendisiyle karsilastirilacagi
        # referans. Ayni tohumlar, ayni bolumler, ayni metrikler.
        from bvr.agents.scripted_guidance import ScriptedGuidance
        model = ScriptedGuidance(mach_lo=cfg.mach_lo, mach_hi=cfg.mach_hi)
    else:
        model = SAC.load(model_path, device="cpu")

    wpts, succ, terms = [], [], []
    alt_ok, mach_ok, wpt_total = 0, 0, 0
    peak = dict(alpha=0.0, beta=0.0, nz_hi=-9e9, nz_lo=9e9, mach_lo=9e9)
    act_rate = []
    ep_rewards = []

    # Ortam BIR KEZ yaratilir: her bolumde yeniden yaratmak hem yavas
    # (JSBSim kurulumu) hem de kalkan istatistiklerini sifirlar -- ozetde
    # yalnizca son bolum gorunurdu.
    env = GuidanceEnv(cfg=cfg, seed=seed0)

    for ep in range(n_episodes):
        rec = None
        if acmi_path and ep == 0:
            rec = ACMIRecorder(acmi_path, title="Guidance politikasi degerlendirme")
            rec.open()
        env.recorder = rec
        obs, _ = env.reset(seed=seed0 + ep)
        done = False
        R = 0.0
        prev_a = np.zeros(3)
        while not done:
            a, _ = model.predict(obs, deterministic=deterministic)
            obs, r, term, trunc, info = env.step(a)
            R += r
            act_rate.append(float(np.sum((a - prev_a) ** 2)))
            prev_a = np.asarray(a, dtype=np.float64)

            st = env._st
            peak["alpha"] = max(peak["alpha"], abs(math.degrees(st.alpha_rad)))
            peak["beta"] = max(peak["beta"], abs(math.degrees(st.beta_rad)))
            peak["nz_hi"] = max(peak["nz_hi"], -st.nz)
            peak["nz_lo"] = min(peak["nz_lo"], -st.nz)
            peak["mach_lo"] = min(peak["mach_lo"], st.mach)

            if "waypoint" in info:
                wpt_total += 1
                alt_ok += int(info["waypoint"]["alt_ok"])
                mach_ok += int(info["waypoint"]["mach_ok"])
            done = term or trunc
        if rec is not None:
            rec.close()
        wpts.append(info.get("episode_waypoints", 0))
        succ.append(info.get("is_success", 0.0))
        terms.append(info.get("termination", "timeout"))
        ep_rewards.append(R)

    n = len(terms)
    print("=" * 68)
    print(f"DEGERLENDIRME  ({n} bolum x {episode_s:.0f} s, "
          f"{'deterministik' if deterministic else 'stokastik'})")
    print("=" * 68)
    print(f"  bolum odulu (ort)      : {np.mean(ep_rewards):8.1f}  "
          f"+- {np.std(ep_rewards):.1f}")
    print(f"  hedef / bolum (ort)    : {np.mean(wpts):8.2f}  "
          f"(medyan {np.median(wpts):.0f}, max {max(wpts)})")
    print(f"  basari orani           : {100*np.mean(succ):8.1f} %")
    print(f"  toplam hedefe varis    : {wpt_total}")
    if wpt_total:
        print(f"    varista irtifa tol.  : {100*alt_ok/wpt_total:8.1f} % "
              f"(+-{cfg.alt_tol_ft:.0f} ft)")
        print(f"    varista Mach tol.    : {100*mach_ok/wpt_total:8.1f} % "
              f"(+-{cfg.mach_tol:.2f})")
    print()
    print("  erken sonlanma sebepleri:")
    for k, v in Counter(terms).most_common():
        print(f"    {k:<12} {v:4d}  ({100*v/n:5.1f} %)")
    print()
    print("  ZARF UC DEGERLERI (limit) -- kalkanin isi ne kadar kalacak?")
    print(f"    |alpha| max  {peak['alpha']:6.2f} deg   "
          f"(calisma {ac.ALPHA_MAX_DEG:.0f} / FLCS 30)")
    print(f"    |beta|  max  {peak['beta']:6.2f} deg   (limit {ac.BETA_MAX_DEG:.0f})")
    print(f"    n max/min    {peak['nz_hi']:6.2f} / {peak['nz_lo']:.2f} g  "
          f"(limit {ac.NZ_MAX:.0f} / {ac.NZ_MIN:.0f})")
    print(f"    Mach min     {peak['mach_lo']:6.3f}       (limit {ac.MACH_MIN:.2f})")
    print()
    print(f"  komut degisim RMS      : {np.sqrt(np.mean(act_rate)):8.4f}  "
          f"(kucuk = yumusak; buyuk = titreme/PIO)")
    if use_shield and env.shield is not None:
        s = env.shield.stats.summary()
        print()
        print("  KALKAN (CBF komut yoneticisi)")
        print(f"    mudahale orani       : {100*s['mudahale_orani']:8.2f} %")
        print(f"    slack (ihlal) orani  : {100*s['slack_orani']:8.2f} %")
        print(f"    ortalama sapma       : {s['ort_sapma']:8.4f}  (max {s['max_sapma']:.3f})")
        print(f"    cozucu hatasi        : {s['cozucu_hata']:8d}")
    if acmi_path:
        print(f"\n  Tacview kaydi: {acmi_path}")
    return dict(wpts=wpts, success=np.mean(succ), terms=Counter(terms))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/guidance_v1/sac_final.zip")
    ap.add_argument("-n", "--episodes", type=int, default=30)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    ap.add_argument("--acmi", default="runs/guidance_eval.acmi")
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--shield", action="store_true", help="CBF kalkanini ac")
    a = ap.parse_args()
    evaluate(a.model, a.episodes, a.episode_sec, acmi_path=a.acmi,
             deterministic=not a.stochastic, use_shield=a.shield)
