"""
Faz 1.5b duman testi: IKI GuidanceDriver, AYNI 10 Hz tikte, FARKLI manevra
tipleriyle esanli surulur. Amac: RAD-08'de (radar) yasadigimiz "iki hedefi
tek nesneyle izlerken durum sizmasi" hatasinin GuidanceDriver/GuidanceEnv
tarafinda da olup olmadigini sinamak.

Yontem: 14 orijinal command_hold_test durumu 7 esanli CIFTE ayrilir
(0&7, 1&8, ...) -- bilerek AYNI degil FARKLI tipte manevralar eslenir
(orn. "tutma" ile "birlesik-alcalma"). Her cift 90 s esanli kosturulur,
her ucagin kalici hatasi, TEK-UCAKLI referansla (command_hold_test.py'nin
ayni modelle uzerinde uretilmis, asagida sabit yazili) birebir kiyaslanir.

Eger paylasilan bir durum (ornegin GuidanceDriver/InnerLoop/F16Sim
arasinda beklenmeyen bir global) varsa, esanli kosunun sonucu tek-ucakli
referanstan sapar -- kontaminasyonun somut kaniti budur.

Kullanim:
    python -m scripts.guidance_driver_dual_hold_test <model.zip>
"""
from __future__ import annotations

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_driver import GuidanceDriver
from bvr.envs import guidance_shared as gs
from bvr.config import load_experiment
from scripts.command_hold_test import CASES

# command_hold_test.py'nin AYNI modelle, TEK ucakli calistirilmis referans
# ciktisi (bu script yazilirken olculdu -- scripts/command_hold_test.py
# runs/reward_r3_both/sac_1999968_steps.zip). Format: (alt_ss, alt_sd, mach_ss, mach_sd)
SINGLE_AIRCRAFT_REF = [
    (-64, 2, -0.0108, 0.0002),
    (-37, 7, -0.0092, 0.0005),
    (-20, 3, -0.0180, 0.0012),
    (-146, 3, -0.0106, 0.0012),
    (-30, 8, -0.0083, 0.0015),
    (-68, 14, -0.0029, 0.0006),
    (-124, 6, -0.0097, 0.0007),
    (-59, 26, -0.0049, 0.0006),
    (-156, 5, -0.0111, 0.0009),
    (-56, 31, -0.0104, 0.0011),
    (-81, 23, -0.0060, 0.0003),
    (-72, 5, -0.0131, 0.0012),
    (-161, 6, -0.0099, 0.0009),
    (49, 5, -0.0170, 0.0026),
]

REF_ALT_TOL_FT = 1.5      # referans tabloda tam sayiya yuvarlanmis (goruntu), pay birakildi
REF_MACH_TOL = 0.00015    # referans tabloda 4 ondalik


def run_pair(policy, cfg, case_a, case_b, hold_s=90.0):
    a0_a, m0_a, ac_a, mc_a, kind_a = case_a
    a0_b, m0_b, ac_b, mc_b, kind_b = case_b

    drv_a = GuidanceDriver(cfg=cfg, seed=7)
    drv_a.reset(alt_ft=a0_a, mach=m0_a, heading_deg=0.0, fuel_frac=0.6)
    tgt_n_a, tgt_e_a = drv_a.st.north_ft + 30 * 6076.0, drv_a.st.east_ft

    drv_b = GuidanceDriver(cfg=cfg, seed=7)
    drv_b.reset(alt_ft=a0_b, mach=m0_b, heading_deg=0.0, fuel_frac=0.6)
    tgt_n_b, tgt_e_b = drv_b.st.north_ft + 30 * 6076.0, drv_b.st.east_ft

    n = int(hold_s * cfg.outer_hz)
    ae_a, me_a, ae_b, me_b = [], [], [], []
    for _ in range(n):
        obs_a = gs.build_obs(drv_a.st, tgt_n_a, tgt_e_a, ac_a, mc_a, drv_a.last_applied)
        obs_b = gs.build_obs(drv_b.st, tgt_n_b, tgt_e_b, ac_b, mc_b, drv_b.last_applied)
        act_a, _ = policy.predict(obs_a, deterministic=True)
        act_b, _ = policy.predict(obs_b, deterministic=True)
        drv_a.tick(act_a)
        drv_b.tick(act_b)
        ae_a.append(drv_a.st.alt_ft - ac_a); me_a.append(drv_a.st.mach - mc_a)
        ae_b.append(drv_b.st.alt_ft - ac_b); me_b.append(drv_b.st.mach - mc_b)

    w = int(30.0 * cfg.outer_hz)
    res_a = (float(np.mean(ae_a[-w:])), float(np.std(ae_a[-w:])),
              float(np.mean(me_a[-w:])), float(np.std(me_a[-w:])))
    res_b = (float(np.mean(ae_b[-w:])), float(np.std(ae_b[-w:])),
              float(np.mean(me_b[-w:])), float(np.std(me_b[-w:])))
    return res_a, res_b


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    a = ap.parse_args()
    rd = os.path.dirname(a.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 600.0
    pol = SAC.load(a.model, device="cpu")

    print(f"model: {a.model}")
    print(f"{'A (baslangic->komut,tip)':<38}{'B (baslangic->komut,tip)':<38}| "
          f"{'A sapma(alt,mach)':>20}  {'B sapma(alt,mach)':>20}")

    ok_alt = ok_mach = 0
    max_alt_dev = max_mach_dev = 0.0
    n_pairs = len(CASES) // 2
    for i in range(n_pairs):
        case_a, case_b = CASES[i], CASES[i + n_pairs]
        ref_a, ref_b = SINGLE_AIRCRAFT_REF[i], SINGLE_AIRCRAFT_REF[i + n_pairs]
        res_a, res_b = run_pair(pol, cfg, case_a, case_b)

        for res, ref, tag in ((res_a, ref_a, "A"), (res_b, ref_b, "B")):
            alt_ss, alt_sd, mach_ss, mach_sd = res
            ref_alt_ss, _, ref_mach_ss, _ = ref
            dev_alt = abs(alt_ss - ref_alt_ss)
            dev_mach = abs(mach_ss - ref_mach_ss)
            max_alt_dev = max(max_alt_dev, dev_alt)
            max_mach_dev = max(max_mach_dev, dev_mach)
            if abs(alt_ss) <= 500:
                ok_alt += 1
            if abs(mach_ss) <= 0.05:
                ok_mach += 1
            flag = "" if (dev_alt <= REF_ALT_TOL_FT and dev_mach <= REF_MACH_TOL) else "  <-- SAPMA (kontaminasyon supheli)"
            print(f"  [{tag}] {case_a if tag=='A' else case_b} -> alt_ss={alt_ss:+.2f} "
                  f"(ref {ref_alt_ss:+.0f}, fark {dev_alt:.3f}) "
                  f"mach_ss={mach_ss:+.5f} (ref {ref_mach_ss:+.4f}, fark {dev_mach:.5f}){flag}")

    print(f"\nkalici irtifa hatasi |e| <= 500 ft : {ok_alt}/{len(CASES)}")
    print(f"kalici Mach hatasi   |e| <= 0.05    : {ok_mach}/{len(CASES)}")
    print(f"\nTek-ucakli referansa gore en buyuk sapma: irtifa {max_alt_dev:.4f} ft, "
          f"mach {max_mach_dev:.6f}")
    if max_alt_dev <= REF_ALT_TOL_FT and max_mach_dev <= REF_MACH_TOL:
        print("SONUC: Esanli calisan iki GuidanceDriver, tek-ucakli referanstan "
              "SAPMADI -- kontaminasyon YOK.")
    else:
        print("SONUC: SAPMA VAR -- iki ornek arasinda paylasilan durum olabilir, incele.")
