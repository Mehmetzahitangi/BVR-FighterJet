"""
IHLAL NEREDE OLUYOR: nz_min ihlallerinin hedefe olan MENZILE gore dagilimi.

Neden: stres testi (hedef yakalanmayan kurulum) ile normal ortam arasinda
20 kat fark cikti ve buradan "ihlaller varis oncesi hassasiyet
duzeltmesinden geliyor" CIKARIMI yapildi. Cikarim, iki kurulum arasindaki
tek yapisal farkin varis asamasi olmasina dayaniyordu -- makul ama DOLAYLI.

Bu betik cikarimi dogrudan olcer: her ihlal aninda hedefe kalan menzil
kaydedilir. Ihlaller yakalama yaricapina (3000 ft) yakin bir yerde
yigiliyorsa cikarim dogrulanir; menzile duzgun yayilmissa YANLISTIR ve
"panik freni" aciklamasi belgelerden cikarilmalidir.
"""
import sys
import os
import argparse
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv
from bvr.config import load_experiment
from bvr.sim import aircraft as ac

NM = 6076.0


def collect(policy, cfg, n_ep, seed0):
    """Menzilin YANINDA yatis ve ucus yolu acisini da toplar.

    Ikinci hipotez: n_cmd = (V*gdot/g + cos gam) / cos(phi). Yatikken
    1/cos(phi) carpani ALCALMA komutunu daha negatif g'ye cevirir. Yani
    ihlaller "donerken ayni anda alcalma" durumundan geliyor olabilir.
    Bunu olcmeden iddia etmeyiz -- ilk hipotez (varis paniği) tam olarak
    boyle olcusuz kurulmustu ve YANLIS cikti.
    """
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    viol, allst = [], []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done = False
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, _, term, trunc, info = env.step(a)
            st = env._st
            row = (env._range_to_target(), abs(math.degrees(st.phi_rad)),
                   math.degrees(st.gamma_rad), env.tgt_alt - st.alt_ft)
            allst.append(row)
            if env._intra["nz_lo"] < ac.NZ_MIN:
                viol.append(row)
            done = term or trunc
    env.close()
    return np.array(viol), np.array(allst)


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
    V, A = collect(pol, cfg, a.n, a.seed0)
    v, allr = (V[:, 0] if len(V) else np.array([])), A[:, 0]

    cap = cfg.wpt_capture_ft
    print(f"model: {a.model}")
    print(f"yakalama yaricapi: {cap:.0f} ft ({cap/NM:.2f} nmi)")
    print(f"toplam adim: {len(allr)}   ihlalli adim: {len(v)}")
    if len(v) == 0:
        print("hic ihlal yok"); sys.exit(0)

    # BANT BANT KARSILASTIRMA: her menzil bandinda gecirilen ADIM sayisina
    # gore normalize edilmis ihlal orani. Ham sayim yaniltir -- ucak zaten
    # zamaninin cogunu uzak menzilde gecirir.
    edges = [0, cap, 2*cap, 5*cap, 10*cap, 20*cap, 1e12]
    names = [f"0 - {cap/1000:.0f}k ft (YAKALAMA)",
             f"{cap/1000:.0f}k - {2*cap/1000:.0f}k",
             f"{2*cap/1000:.0f}k - {5*cap/1000:.0f}k",
             f"{5*cap/1000:.0f}k - {10*cap/1000:.0f}k",
             f"{10*cap/1000:.0f}k - {20*cap/1000:.0f}k",
             f"{20*cap/1000:.0f}k+ ft"]
    print()
    print(f"{'menzil bandi':<26} {'adim':>9} {'ihlal':>7} {'ihlal orani':>13} {'kat':>6}")
    base = len(v) / len(allr)
    for i, nm in enumerate(names):
        lo, hi = edges[i], edges[i+1]
        na = int(((allr >= lo) & (allr < hi)).sum())
        nv = int(((v >= lo) & (v < hi)).sum())
        rate = nv / na if na else 0.0
        print(f"{nm:<26} {na:>9} {nv:>7} {rate:13.5f} {rate/base if base else 0:6.1f}x")
    print()
    print(f"genel ihlal orani: {base:.5f}")
    print(f"ihlallerin medyan menzili: {np.median(v)/1000:.1f}k ft "
          f"({np.median(v)/NM:.2f} nmi)")
    print(f"tum adimlarin medyan menzili: {np.median(allr)/1000:.1f}k ft "
          f"({np.median(allr)/NM:.2f} nmi)")
    near = float((v < 2*cap).mean())
    print()
    print(f"ihlallerin %{100*near:.0f}'i yakalama yaricapinin 2 katindan yakin")

    print()
    print("IKINCI HIPOTEZ: yatikken alcalma  (1/cos(phi) carpani)")
    print(f"{'':<22} {'ihlal aninda':>14} {'tum adimlar':>14}")
    for j, nm in ((1, "|yatis| [deg]"), (2, "ucus yolu acisi [deg]"),
                  (3, "irtifa hatasi [ft]")):
        print(f"{nm:<22} {np.median(V[:, j]):14.1f} {np.median(A[:, j]):14.1f}")
    hi_bank_v = float((V[:, 1] > 45).mean()); hi_bank_a = float((A[:, 1] > 45).mean())
    desc_v = float((V[:, 2] < -5).mean()); desc_a = float((A[:, 2] < -5).mean())
    both_v = float(((V[:, 1] > 45) & (V[:, 2] < -5)).mean())
    both_a = float(((A[:, 1] > 45) & (A[:, 2] < -5)).mean())
    print(f"{'yatis > 45 deg':<22} {100*hi_bank_v:13.1f}% {100*hi_bank_a:13.1f}%")
    print(f"{'alcalma (gam < -5)':<22} {100*desc_v:13.1f}% {100*desc_a:13.1f}%")
    print(f"{'IKISI BIRDEN':<22} {100*both_v:13.1f}% {100*both_a:13.1f}%")
    if both_a > 0:
        print()
        print(f"-> yatikken alcalma, ihlal aninda {both_v/both_a:.1f} kat daha sik")
