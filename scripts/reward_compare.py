"""
ODUL DUZELTMESI KARSILASTIRMASI: dort config + taban, ayni olcutlerle.

Birincil olcut YAKALAMA KALITESI'dir -- kabul kriteriyle ayni (GUI-05).
Bu ders pahaliya ogrenildi: onceki tarama "hedef/bolum"e gore secmis ve
kabul olcutunde EN KOTU konfigurasyonu kazanan ilan etmisti.

Her kosunun BUTUN kontrol noktalari olculur, yalnizca son model degil.
Nihai 8M kosusunda son model, 2M'dekinin yarisi kadar iyiydi -- "son" ile
"en iyi" ayni sey degildir.

`sac_best.zip` KULLANILMAZ. Bu dort kosu, `BestByCaptureQuality`nin kucuk
payda hatasi olan surumuyle kosuldu: egitimin basinda cok az bacak
tamamlandigi icin oran 1/1 = 1.000 cikti ve secim orada dondu. Hata
duzeltildi (asgari bacak sarti) ama bu kosular icin secim BAGIMSIZ
yapilmalidir -- bu scriptteki n=200'luk olcum tam olarak odur.

Ikincil olcutler ZORUNLU olarak raporlanir:
  - seyrusefer verimi (GUI-02): r3/r4 ilerleme agirligini dusuruyor,
    bunun navigasyonu bozup bozmadigi gorulmeli
  - erken sonlanma (GUI-06)
"""
import sys
import os
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.config import load_experiment
from scripts.mission_eval import evaluate as mission_evaluate

#: Taban = mevcut en iyi model (odul duzeltmesi ONCESI). Karsilastirma
#: bunun uzerine ne kattigimizi gosterir; mutlak sayi tek basina anlamsiz.
BASELINE = ("TABAN (duzeltme yok)",
            "runs/guidance_final_s1/sac_1999968_steps.zip")


def row(tag, zip_path, n_ep, seed0):
    if not os.path.exists(zip_path):
        return None
    cfg_dir = os.path.dirname(zip_path)
    y = os.path.join(cfg_dir, "config.resolved.yaml")
    env_cfg = load_experiment(y).env
    env_cfg.episode_s = 180.0
    pol = SAC.load(zip_path, device="cpu")
    r = mission_evaluate(pol, env_cfg, n_ep=n_ep, seed0=seed0, verbose=False)
    return dict(
        tag=tag,
        quality=r["yakalama kalitesi (alt+mach)"],
        alt=r["  - irtifa toleransinda"],
        mach=r["  - mach toleransinda"],
        eff=r["seyrusefer verimi"],
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=200,
                    help="bolum sayisi (60 YETERSIZ -- bloklar arasi fark ~0.10)")
    ap.add_argument("--seed0", type=int, default=50_000)
    a = ap.parse_args()

    targets = [BASELINE]
    for c in sorted(glob.glob("configs/reward/*.yaml")):
        name = load_experiment(c).name
        d = os.path.join("runs", name)
        cks = sorted(glob.glob(os.path.join(d, "sac_*_steps.zip")),
                     key=lambda f: int(f.split("sac_")[-1].split("_")[0]))
        for f in cks:
            step = int(f.split("sac_")[-1].split("_")[0])
            targets.append((f"{name} @{step//1000}k", f))
        targets.append((f"{name} [son]", os.path.join(d, "sac_final.zip")))

    print(f"olcum: n={a.n} bolum, tohum blogu {a.seed0}")
    print("=" * 78)
    rows = []
    for tag, zp in targets:
        r = row(tag, zp, a.n, a.seed0)
        if r is None:
            print(f"{tag:<28} model yok, atlandi")
            continue
        rows.append(r)
        print(f"{r['tag']:<28} KALITE {r['quality'][0]:.3f} "
              f"[{r['quality'][1]:.3f}, {r['quality'][2]:.3f}]  "
              f"irt {r['alt'][0]:.3f}  mach {r['mach'][0]:.3f}  "
              f"verim {r['eff'][0]:.3f}", flush=True)

    if not rows:
        sys.exit("olculecek model yok")
    print()
    print("=" * 78)
    print("SIRALAMA  (birincil olcut: YAKALAMA KALITESI = GUI-05)")
    print("=" * 78)
    print(f"{'kosu':<28} {'KALITE':>7} {'%95 GA':>18} {'irtifa':>7} "
          f"{'mach':>6} {'verim':>7}")
    base = rows[0]
    for r in sorted(rows, key=lambda x: -x["quality"][0]):
        m, lo, hi = r["quality"]
        print(f"{r['tag']:<28} {m:7.3f} [{lo:6.3f}, {hi:6.3f}] "
              f"{r['alt'][0]:7.3f} {r['mach'][0]:6.3f} {r['eff'][0]:7.3f}")

    bm, blo, bhi = base["quality"]
    best = max(rows, key=lambda x: x["quality"][0])
    m, lo, hi = best["quality"]
    print(f"\nEn iyi: {best['tag']}  kalite {m:.3f} [{lo:.3f}, {hi:.3f}]")
    print(f"Taban : {base['tag']}  kalite {bm:.3f} [{blo:.3f}, {bhi:.3f}]")
    # GA ORTUSME KURALI: ortusuyorsa fark IDDIA EDILMEZ (bkz. HANDOFF tuzak 17)
    if lo > bhi:
        print(f"-> Iyilesme ISTATISTIKSEL OLARAK GOSTERILDI (GA'lar ortusmuyor).")
    elif best["tag"] == base["tag"]:
        print("-> Hicbir duzeltme tabani gecemedi.")
    else:
        print("-> Yon dogru olabilir ama GA'lar ORTUSUYOR: fark iddia EDILEMEZ. "
              "Daha buyuk ornek veya daha guclu bir degisiklik gerekir.")
    print(f"\nGUI-05 kabul esigi 0.70 -> "
          f"{'SAGLANDI' if lo >= 0.70 else 'saglanmadi (GA alt siniri 0.70 altinda)'}")
