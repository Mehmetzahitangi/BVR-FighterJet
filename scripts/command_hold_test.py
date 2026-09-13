"""
KOMUT TUTMA TESTI: guidance katmaninin UST KATMANA verdigi arayuz sozlesmesi.

=============================================================================
NEDEN AYRI BIR TEST
=============================================================================
`mission_eval` "hedefe varis aninda uc ekseni ayni anda tutturdun mu?" diye
olcer. Ama TAKTIK KOMUTAN bunu hic kullanmaz: o 2 Hz'de surekli komut
yeniler ("su yone don, su irtifada kal, su hizda ol"). Onun bagli oldugu
sozlesme cok daha basittir:

    "Komutu SABIT tutarsam, kalici hata ne kadar?"

Yakalama hassasiyeti = navigasyon + eszamanli 3-eksen yakinsama + zamanlama,
hepsi birbirine karismis bir bilesik metrik. Komut tutma ise arayuzun
KENDISINI olcer -- ic dongudeki basamak yaniti testinin guidance
seviyesindeki karsiligi.

Yontem: cok uzak (yakalanamayacak) bir hedef konur, irtifa ve Mach hedefi
SABIT tutulur, 90 s ucurulur ve SON 30 SANIYENIN kalici hatasi olculur.
"""
import sys
import os
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.config import load_experiment
from bvr.sim import aircraft as ac


def hold_test(policy, cfg, alt_cmd, mach_cmd, alt0, mach0, hold_s=90.0, seed=7):
    env = GuidanceEnv(cfg=cfg, seed=seed)
    obs, _ = env.reset(seed=seed)
    # Baslangici istenen noktaya zorla
    env._st = env.sim.reset(alt_ft=alt0, mach=mach0, heading_deg=0.0,
                            trim=True, fuel_frac=0.6)
    env.inner.reset(trim_throttle=env.sim["fcs/throttle-cmd-norm"])
    if env.shield is not None:
        env.shield.reset_state()
    # Bacak bitmemeli ama hedef EGITIM DAGILIMINA yakin durmali.
    # Olculdu: hedef 40 nmi ve otesine konunca politika kurs takibinde bir
    # LIMIT CEVRIMINE giriyor (yatis std 30-37 deg, periyot ~12.7 s); 25 nmi
    # ve altinda salinim yok (std 6.4 deg). Sebep, uzak hedefte kerterizin
    # ucagin yonune neredeyse duyarsiz olmasi -- kurs dongusunun dogal
    # sonumlemesi kayboluyor ve politika egitim araligi (3.3-14.8 nmi)
    # DISINDA calisiyor. 30 nmi secildi: 90 s'lik testte ~900 fps ile
    # yakalanamaz (gerekli sure ~200 s) ama dagilima cok daha yakin.
    env.tgt_n = env._st.north_ft + 30 * 6076.0
    env.tgt_e = env._st.east_ft
    env.tgt_alt, env.tgt_mach = alt_cmd, mach_cmd
    env._prev_range = env._range_to_target()
    env._prev_alt_err = abs(alt_cmd - env._st.alt_ft)
    env._prev_mach_err = abs(mach_cmd - env._st.mach)
    obs = env._obs()

    n = int(hold_s * cfg.outer_hz)
    ae, me = [], []
    for k in range(n):
        a, _ = policy.predict(obs, deterministic=True)
        obs, r, term, trunc, info = env.step(a)
        # Hedefi SABIT tut (waypoint mantigi devreye girmesin)
        env.tgt_alt, env.tgt_mach = alt_cmd, mach_cmd
        ae.append(env._st.alt_ft - alt_cmd)
        me.append(env._st.mach - mach_cmd)
        if term:
            return None
    w = int(30.0 * cfg.outer_hz)            # son 30 s = kalici rejim
    return dict(alt_ss=float(np.mean(ae[-w:])), alt_sd=float(np.std(ae[-w:])),
                mach_ss=float(np.mean(me[-w:])), mach_sd=float(np.std(me[-w:])))


# (baslangic irtifa, baslangic Mach, KOMUT irtifa, KOMUT Mach, tip)
#
# SIMETRIK TASARIM: ilk surumde 2 tirmanis / 2 alcalma vardi ve r2
# konfigurasyonu alcalmalarin IKISINDE de batti (+1585, +4423 ft).
# Yon basina 2 ornekle "alcalamiyor" denemez; manevra tipi artik
# DENGELI ornekleniyor ve ozet tip bazinda da veriliyor.
CASES = [
    (20000, 0.80, 20000, 0.80, "tutma"),
    (30000, 0.90, 30000, 0.90, "tutma"),
    (20000, 0.80, 25000, 0.80, "tirmanis"),
    (15000, 0.85, 20000, 0.85, "tirmanis"),
    (25000, 0.90, 32000, 0.90, "tirmanis"),
    (30000, 0.95, 35000, 0.95, "tirmanis"),
    (30000, 0.90, 25000, 0.90, "alcalma"),
    (35000, 0.95, 30000, 0.95, "alcalma"),
    (25000, 0.85, 18000, 0.85, "alcalma"),
    (20000, 0.80, 15000, 0.80, "alcalma"),
    (25000, 0.75, 25000, 1.00, "hiz"),
    (25000, 1.10, 25000, 0.85, "hiz"),
    (15000, 0.70, 22000, 0.95, "birlesik-tirmanis"),
    (35000, 1.00, 30000, 0.80, "birlesik-alcalma"),
]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    a = ap.parse_args()
    rd = os.path.dirname(a.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 600.0
    pol = SAC.load(a.model, device="cpu")

    print(f"model: {a.model}")
    print(f"{'baslangic':>16} {'komut':>14} {'tip':<18}| "
          f"{'irtifa hatasi':>20} {'Mach hatasi':>18}")
    print(f"{'':>16} {'':>14} {'':<18}| "
          f"{'ort':>9} {'sapma':>9} {'ort':>9} {'sapma':>8}")
    ok_a = ok_m = tot = 0
    by_type = {}
    for a0, m0, ac_, mc, kind in CASES:
        r = hold_test(pol, cfg, ac_, mc, a0, m0)
        if r is None:
            print(f"{a0:>10}/{m0:<5.2f} {ac_:>8}/{mc:<5.2f} {kind:<18}|  BOLUM ERKEN SONLANDI")
            continue
        tot += 1
        ga = abs(r["alt_ss"]) <= cfg.alt_tol_ft
        gm = abs(r["mach_ss"]) <= cfg.mach_tol
        ok_a += ga; ok_m += gm
        t = by_type.setdefault(kind, [0, 0, 0])
        t[0] += 1; t[1] += ga; t[2] += gm
        print(f"{a0:>10}/{m0:<5.2f} {ac_:>8}/{mc:<5.2f} {kind:<18}| "
              f"{r['alt_ss']:+9.0f} {r['alt_sd']:9.0f} "
              f"{r['mach_ss']:+9.4f} {r['mach_sd']:8.4f}")
    print()
    print(f"kalici irtifa hatasi |e| <= {cfg.alt_tol_ft:.0f} ft : {ok_a}/{tot}")
    print(f"kalici Mach hatasi   |e| <= {cfg.mach_tol:.2f}    : {ok_m}/{tot}")
    print()
    print("MANEVRA TIPINE GORE  (irtifa / Mach)")
    for k in ("tutma", "tirmanis", "alcalma", "hiz",
              "birlesik-tirmanis", "birlesik-alcalma"):
        if k in by_type:
            n, a_, m_ = by_type[k]
            print(f"  {k:<20} {a_}/{n}   {m_}/{n}")
