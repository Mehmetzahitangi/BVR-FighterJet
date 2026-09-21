"""
Faz 2 ek olcum: "cirkin donus"un (pure pursuit, be=0'da bile agresif yatis --
bkz. crank_sweep tartismasi/REQUIREMENTS.md SIM2-08) BEDELI ne?

SORU: guidance'in gereksiz erken donusu, GORCEK GOREV BASARISINI tehdit
edecek kadar mi kotu, yoksa "cirkin ama zararsiz" mi? Iki ayri cephe
olculuyor, cunku bu projenin ates kurallarinda (LaunchRules.max_launch_nm
=35 nmi, 1v1/2v2'de baslangic ayrimi 30 nmi) UCAK ZATEN t=0'da atis
menzilinin ICINDE -- "menzile ulasma suresi" darbogaz DEGIL. Asil darbogaz
RADAR KILIDIDIR (gimbal_az_deg=60, lock_delay_s=2.5): sürüklenme ATA'yi bu
sinira yaklastirirsa GERCEKTEN kilit/atisi tehdit eder.

  A) ISRAF (enerji/zaman): sadece 'intercept' modunda (hic crank yok),
     bir hedefe kapanirken katedilen GERCEK yol, DUZ CIZGI mesafesine
     kiyasla ne kadar uzun? Mach ortalama/en dusuk ne kadar sagiyor?
  B) TEHDIT (kilit riski): bu surukleme sirasinda |ATA| hic gimbal
     sinirina (60 derece) YAKLASIYOR mu? Yaklasmiyorsa, "cirkin ama
     zararsiz" -- kilit/atis hic risk altinda degil.

Kurulum crank_sweep.py ile AYNI (kinematik hedef, GuidanceDriver, gercek
pick_target) -- karsilastirilabilir olsun diye kopyalanmadi, import edildi.

Kullanim:
    python -m scripts.pursuit_cost <model.zip>
"""
from __future__ import annotations

import sys
import os
import math
import argparse
import dataclasses

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_driver import GuidanceDriver
from bvr.envs import guidance_shared as gs
from bvr.combat.geometry import relative_geometry
from bvr.combat.missile import MissileConfig, atmosphere
from bvr.config import load_experiment
from bvr.combat.duel import pick_target  # Faz 2.2: artik burada barinir, bkz. duel.py basligi

NM_TO_FT = 6076.11549
DT = 0.1
TARGET_RANGE_NM = 30.0
TARGET_MACH = 0.9
TARGET_HEADING_RAD = math.radians(180.0)
CAPTURE_RANGE_NM = 10.0      # "yeterince yakin" -- gercek atis zaten 30 nmi'de mumkun,
                              # bu sadece kapanma VERIMLILIGINI olcmek icin bir isaret cizgisi
MAX_DURATION_S = 180.0        # guvenlik tavani (hic capture olmazsa)
MISSILE_MASS_LB = MissileConfig().mass_lb
PAYLOAD_MISSILES = 4          # gercekci on-atis durumu (tam muhimmat)
GIMBAL_AZ_DEG = 60.0

ALTS_FT = [15000.0, 25000.0, 35000.0]
MACHES = [0.8, 0.9]


def run_intercept(model, cfg, alt_ft: float, mach: float, seed: int = 1) -> dict:
    driver = GuidanceDriver(cfg=cfg, seed=seed)
    driver.set_payload(PAYLOAD_MISSILES * MISSILE_MASS_LB)
    driver.reset(alt_ft=alt_ft, mach=mach, heading_deg=0.0, fuel_frac=0.75)

    _, sos_fps = atmosphere(alt_ft)
    v_target_fps = TARGET_MACH * sos_fps
    tgt_n = driver.st.north_ft + TARGET_RANGE_NM * NM_TO_FT
    tgt_e = driver.st.east_ft
    tgt_alt = alt_ft

    n0, e0 = driver.st.north_ft, driver.st.east_ft
    prev_n, prev_e = n0, e0
    path_ft = 0.0
    ata_abs_max = 0.0
    machs, t_capture = [], None

    n_steps = int(round(MAX_DURATION_S / DT))
    for k in range(n_steps):
        t = k * DT
        own = driver.st
        tgt_n_cmd, tgt_e_cmd, tgt_alt_cmd, tgt_mach_cmd = pick_target(
            own.north_ft, own.east_ft, tgt_n, tgt_e, tgt_alt, "intercept", 0.0)
        obs = gs.build_obs(own, tgt_n_cmd, tgt_e_cmd, tgt_alt_cmd, tgt_mach_cmd,
                            driver.last_applied)
        action, _ = model.predict(obs, deterministic=True)
        driver.tick(action)

        tgt_n += v_target_fps * math.cos(TARGET_HEADING_RAD) * DT
        tgt_e += v_target_fps * math.sin(TARGET_HEADING_RAD) * DT

        st = driver.st
        path_ft += math.hypot(st.north_ft - prev_n, st.east_ft - prev_e)
        prev_n, prev_e = st.north_ft, st.east_ft
        machs.append(st.mach)

        fake_red = dataclasses.replace(st, north_ft=tgt_n, east_ft=tgt_e, alt_ft=tgt_alt)
        geom = relative_geometry(st, fake_red)
        ata_abs_max = max(ata_abs_max, abs(geom.ata_deg))

        if t_capture is None and geom.range_nm <= CAPTURE_RANGE_NM:
            t_capture = t + DT
            n_final, e_final = st.north_ft, st.east_ft
            break

    if t_capture is None:
        # Yakalanmadi -- guvenlik tavaninda kes, mevcut degerlerle raporla.
        t_capture = MAX_DURATION_S
        n_final, e_final = driver.st.north_ft, driver.st.east_ft

    straight_ft = math.hypot(n_final - n0, e_final - e0)
    # NOT: pick_target() HER ZAMAN CMD_MACH=0.90'i hedefler (bvr_1v1_smoke.py),
    # baslangic 'mach' parametresi degil -- ideal kapanma hizi da BUNU kullanmali,
    # yoksa mach=0.8 baslangicli kosularda (hizlanma donemi oldugu icin) yanlis
    # kiyas cikar.
    from bvr.combat.duel import CMD_MACH
    v_own_fps = CMD_MACH * sos_fps
    closure_fps = v_own_fps + v_target_fps       # bas-basa yaklasim, sabit hiz varsayimiyla
    initial_range_ft = TARGET_RANGE_NM * NM_TO_FT
    capture_range_ft = CAPTURE_RANGE_NM * NM_TO_FT
    t_ideal = (initial_range_ft - capture_range_ft) / closure_fps

    return dict(
        alt_ft=alt_ft, mach=mach,
        t_actual=t_capture, t_ideal=t_ideal,
        time_penalty_s=t_capture - t_ideal,
        time_penalty_pct=100.0 * (t_capture - t_ideal) / t_ideal,
        path_ft=path_ft, straight_ft=straight_ft,
        path_penalty_pct=100.0 * (path_ft - straight_ft) / straight_ft,
        mach_mean=float(np.mean(machs)), mach_min=float(np.min(machs)),
        ata_abs_max=ata_abs_max, gimbal_margin=GIMBAL_AZ_DEG - ata_abs_max,
        captured=(t_capture < MAX_DURATION_S),
    )


ROW_FMT = ("{alt_ft:>7.0f} {mach:>5.2f} | {t_actual:>8.1f} {t_ideal:>8.1f} "
           "{time_penalty_pct:>+7.1f}% | {path_penalty_pct:>+7.1f}% | "
           "{mach_mean:>6.3f} {mach_min:>6.3f} | {ata_abs_max:>7.1f} {gimbal_margin:>+7.1f}")
HEADER = ("    alt  mach |  t_gercek  t_ideal   zaman-fark | yol-fark | "
          "M_ort  M_min |  |ATA|max gimbalpay")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    args = ap.parse_args()

    rd = os.path.dirname(args.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    model = SAC.load(args.model, device="cpu")

    print(f"model: {args.model}")
    print(f"yakalama esigi: {CAPTURE_RANGE_NM:.0f} nmi (baslangic {TARGET_RANGE_NM:.0f} nmi)")
    print(HEADER)

    rows = []
    for alt in ALTS_FT:
        for mach in MACHES:
            m = run_intercept(model, cfg, alt, mach)
            rows.append(m)
            print(ROW_FMT.format(**m))

    worst_time = max(r["time_penalty_pct"] for r in rows)
    worst_path = max(r["path_penalty_pct"] for r in rows)
    worst_gimbal_margin = min(r["gimbal_margin"] for r in rows)
    worst_mach_min = min(r["mach_min"] for r in rows)

    print("\n== DEGERLENDIRME ==")
    print(f"en kotu zaman farki : {worst_time:+.1f}%  (BVR olcegi: fuze ucus suresi "
          f"~10-60 s, kapanma ~100+ s -- birkaç yuzde 'gurultu', 2 katina cikmak 'sorun')")
    print(f"en kotu yol farki   : {worst_path:+.1f}%  (katedilen fazla yol = fazla yakit/enerji)")
    print(f"en dar gimbal payi  : {worst_gimbal_margin:+.1f} derece "
          f"(negatifse surukleme TEK BASINA kilidi kirar)")
    print(f"en dusuk Mach       : {worst_mach_min:.3f}  (komut 0.8-0.9, sapma enerji kaybi)")

    verdict = "ONEMSIZ (gurultu duzeyinde)"
    if worst_gimbal_margin < 10.0 or worst_time > 100.0 or worst_path > 50.0:
        verdict = "GERCEK SORUN -- crank_sweep/komutan tasarimindan once ele alinmali"
    elif worst_time > 20.0 or worst_path > 15.0:
        verdict = "IZLENMELI -- kucuk ama olculebilir bir maliyet var"

    print(f"\nSONUC: {verdict}")


if __name__ == "__main__":
    main()
