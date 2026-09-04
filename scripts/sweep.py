"""
Hiperparametre taramasi: configs/sweep/*.yaml -> sirayla egit -> karsilastir.

    python scripts/sweep.py                 # hepsini egit
    python scripts/sweep.py --eval-only     # egitilmis olanlari degerlendir

Tek faktor degisimi (one-factor-at-a-time) kullanilir: tam izgara 2^4 = 16
kosu ederdi, oysa amac hangi EKSENIN onemli oldugunu bulmak. Onemli eksenler
belirlendikten sonra nihai kosu en iyi kombinasyonla ve coklu tohumla yapilir.

SECIM OLCUTU KABUL KRITERIYLE AYNI OLMALIDIR.
Bu ders pahaliya ogrenildi: tarama once "hedef/bolum"e gore seciyordu ve
s2_smooth (w_action_rate 0.8) kazandi -- hedef 2.42, odul 2539, ihlal
%0.025 ile DORT metrikte birden onde. Ama KABUL KRITERI varis kalitesi
(irtifa+Mach toleransi) ve o olcutte s2_smooth 0.330, s0_base 0.589 idi.
Agir duzgunluk cezasi, ajani varistan hemen onceki keskin duzeltmelerden
caydiriyor: daha duzgun ve daha hizli uciyor, ama daha savruk variyor.
7.3 saatlik nihai egitim yanlis konfigurasyonla kosuldu.
Artik birincil olcut YAKALAMA KALITESI.
"""
import sys
import os
import glob
import time
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

PY = sys.executable


def train_all(cfgs, steps=None):
    for i, c in enumerate(cfgs, 1):
        name = os.path.splitext(os.path.basename(c))[0]
        run = os.path.join("runs", f"sweep_{name}", "sac_final.zip")
        if os.path.exists(run):
            print(f"[{i}/{len(cfgs)}] {name}: zaten egitilmis, atlaniyor")
            continue
        print(f"\n[{i}/{len(cfgs)}] EGITIM: {name}", flush=True)
        cmd = [PY, "scripts/train.py", c]
        if steps:
            cmd += ["--steps", str(steps)]
        t0 = time.time()
        log = os.path.join("runs", f"sweep_{name}.log")
        os.makedirs("runs", exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        print(f"    {'tamam' if r.returncode == 0 else 'HATA'} ({time.time()-t0:.0f} s)")


def evaluate_all(cfgs, n_ep, episode_s):
    from stable_baselines3 import SAC
    from bvr.config import load_experiment
    from scripts.safety_eval import run, BARRIERS, _boot_ci
    from bvr.envs.guidance_env import GuidanceConfig

    rows = []
    for c in cfgs:
        name = os.path.splitext(os.path.basename(c))[0]
        zip_path = os.path.join("runs", f"sweep_{name}", "sac_final.zip")
        if not os.path.exists(zip_path):
            print(f"{name}: model yok, atlaniyor")
            continue
        cfg = load_experiment(c)
        pol = SAC.load(zip_path, device="cpu")
        per, R, W, T, S = run(pol, cfg.env.use_shield, n_ep, episode_s,
                              model_path=cfg.env.shield_model_path)
        from scripts.mission_eval import evaluate as mission_evaluate
        q = mission_evaluate(pol, cfg.env, n_ep=n_ep, verbose=False)
        quality = q["yakalama kalitesi (alt+mach)"][0]
        alt_ok = q["  - irtifa toleransinda"][0]
        mach_ok = q["  - mach toleransinda"][0]
        viol = float(np.mean([sum(per[b[0]][i] for b in BARRIERS)
                              for i in range(len(R))]))
        rm, rlo, rhi = _boot_ci(R)
        rows.append(dict(name=name, reward=rm, rlo=rlo, rhi=rhi,
                         wpts=float(np.mean(W)), viol=viol, quality=quality,
                         alt_ok=alt_ok, mach_ok=mach_ok,
                         term=sum(1 for t in T if t != "timeout"),
                         shield=S))
        print(f"  {name:<14} KALITE {quality:.3f} (irt {alt_ok:.2f} mach {mach_ok:.2f})  "
              f"odul {rm:7.1f}  hedef {np.mean(W):5.2f}  ihlal %{viol:.3f}  "
              f"erken-son {rows[-1]['term']}/{n_ep}", flush=True)

    if not rows:
        return
    print()
    print("=" * 86)
    print("TARAMA SONUCU  (YAKALAMA KALITESI birincil olcut = kabul kriteri)")
    print("=" * 86)
    print(f"{'kosu':<14} {'KALITE':>7} {'irtifa':>7} {'mach':>6} "
          f"{'hedef':>6} {'odul':>7} {'ihlal %':>8} {'erken':>6}")
    for r in sorted(rows, key=lambda r: -r["quality"]):
        print(f"{r['name']:<14} {r['quality']:7.3f} {r['alt_ok']:7.3f} {r['mach_ok']:6.3f} "
              f"{r['wpts']:6.2f} {r['reward']:7.0f} {r['viol']:8.3f} {r['term']:6d}")
    best = max(rows, key=lambda r: r["quality"])
    print(f"\nEn iyi: {best['name']}  (yakalama kalitesi {best['quality']:.3f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("-n", type=int, default=40)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    a = ap.parse_args()

    cfgs = sorted(glob.glob("configs/sweep/*.yaml"))
    print(f"{len(cfgs)} konfigurasyon: {[os.path.basename(c) for c in cfgs]}")
    if not a.eval_only:
        train_all(cfgs, a.steps)
    print("\nDEGERLENDIRME")
    evaluate_all(cfgs, a.n, a.episode_sec)
