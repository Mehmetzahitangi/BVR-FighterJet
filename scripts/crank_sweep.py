"""
Faz 2.0 duman testi: crank acisi -> tepe ATA egrisi.

SORU: komutan en fazla kac derece kirabilir ki kendi radari hedefi
kaybetmesin? Tek nokta olculmustu (50 deg komut -> 65.5 deg ATA); bu
betik butun egriyi (0-90 deg, 3 irtifa, 2 Mach, iki yon) cikarir.

NEDEN IZOLE (tam 1v1 degil): 1v1'de dusman da manevra yapar, fuze atis
zamanlamasi degisir, sonuc tek bit ("isabet var/yok") olur. Burada SAF
bir fizik egrisi istiyoruz -- tek GuidanceDriver + KINEMATIK bir hedef
(sabit hizla M0.9'da bize dogru gelen bir nokta, JSBSim'i yok). ATA ve
elevation SADECE hedefin KONUMUNA ve bizim yonumuze baglidir
(geometry.py:62,73 -- relative_geometry() hic red.psi_rad/vt_fps
kullanmadan ATA/elevation'i hesaplar), bu yuzden hedefin gercek bir
FlightState olmasi GEREKMEZ -- sadece pozisyonu ilerleyen bir nokta
yeterli, relative_geometry() icin dataclasses.replace() ile sarilir.

KRITIK: komut, bvr_1v1_smoke.py'deki pick_target() ile AYNI fonksiyon --
kopyalanmadi, DOGRUDAN import edildi. Aksi halde olculen sey smoke'taki
komutanin fizigi degil, bu betigin kendi yorumu olurdu.

Kullanim:
    python -m scripts.crank_sweep <model.zip>
    python -m scripts.crank_sweep <model.zip> --quick   # hizli dogrulama (3 kosu)
    python -m scripts.crank_sweep <model.zip> --csv runs/crank_sweep.csv
"""
from __future__ import annotations

import sys
import os
import csv
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
INTERCEPT_S = 20.0          # 0-20s: hedefe don, ATA ~0'a otursun (taban cizgi)
EVADE_S = 60.0               # 20-80s: crank_rad ile kir
DURATION_S = INTERCEPT_S + EVADE_S
SS_WINDOW_S = 20.0           # ATA_ss icin son 20s

TARGET_RANGE_NM = 30.0       # hedef baslangicta bu kadar kuzeyde
TARGET_MACH = 0.9            # hedef sabit hizla (duz ucus) bize geliyor
TARGET_HEADING_RAD = math.radians(180.0)   # "sicak" -- guneye, bize dogru

MISSILE_MASS_LB = MissileConfig().mass_lb
PAYLOAD_MISSILES = 3         # "crank ilk atistan sonra baslar" -- 4-1=3 fuze kalmis

THETAS_DEG = [0.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 90.0]
ALTS_FT = [15000.0, 25000.0, 35000.0]
MACHES = [0.8, 0.9]
DIR_CHECK_THETA_DEG = 35.0   # yon simetrisi bu acida her irtifa x Mach'ta tekrarlanir

GIMBAL_AZ_DEG = 60.0         # RadarConfig.gimbal_az_deg ile AYNI (bkz. radar.py)
SETTLE_BAND_DEG = 3.0


def run_one(model, cfg, theta_deg: float, alt_ft: float, mach: float,
            sign: float = 1.0, seed: int = 1) -> dict:
    """Tek bir crank kosusu. 0-INTERCEPT_S: mode='intercept' (ATA tabani),
    INTERCEPT_S-DURATION_S: mode='evade', crank_rad=sign*theta_deg.
    Donen log, her tik icin (t, ata_deg, elevation_deg, bank_deg, range_nm)."""
    crank_rad = sign * math.radians(theta_deg)

    driver = GuidanceDriver(cfg=cfg, seed=seed)
    driver.set_payload(PAYLOAD_MISSILES * MISSILE_MASS_LB)
    driver.reset(alt_ft=alt_ft, mach=mach, heading_deg=0.0, fuel_frac=0.75)

    _, sos_fps = atmosphere(alt_ft)
    v_target_fps = TARGET_MACH * sos_fps
    tgt_n = driver.st.north_ft + TARGET_RANGE_NM * NM_TO_FT
    tgt_e = driver.st.east_ft
    tgt_alt = alt_ft

    n_steps = int(round(DURATION_S / DT))
    log = {"t": np.zeros(n_steps), "ata_deg": np.zeros(n_steps),
           "elevation_deg": np.zeros(n_steps), "bank_deg": np.zeros(n_steps),
           "range_nm": np.zeros(n_steps)}

    for k in range(n_steps):
        t = k * DT
        own = driver.st
        mode = "intercept" if t < INTERCEPT_S else "evade"
        tgt_n_cmd, tgt_e_cmd, tgt_alt_cmd, tgt_mach_cmd = pick_target(
            own.north_ft, own.east_ft, tgt_n, tgt_e, tgt_alt, mode, crank_rad)

        obs = gs.build_obs(own, tgt_n_cmd, tgt_e_cmd, tgt_alt_cmd, tgt_mach_cmd,
                            driver.last_applied)
        action, _ = model.predict(obs, deterministic=True)
        driver.tick(action)

        # Hedef kinematigi -- bu tikte KULLANILAN pozisyondan SONRA ilerletilir
        # (aynen 1v1_smoke.py'deki aircraft/target guncelleme sirasi gibi).
        tgt_n += v_target_fps * math.cos(TARGET_HEADING_RAD) * DT
        tgt_e += v_target_fps * math.sin(TARGET_HEADING_RAD) * DT

        st = driver.st
        fake_red = dataclasses.replace(st, north_ft=tgt_n, east_ft=tgt_e, alt_ft=tgt_alt)
        geom = relative_geometry(st, fake_red)

        log["t"][k] = t
        log["ata_deg"][k] = geom.ata_deg
        log["elevation_deg"][k] = geom.elevation_deg
        log["bank_deg"][k] = math.degrees(st.phi_rad)
        log["range_nm"][k] = geom.range_nm

    return log


def metrics(log: dict, theta_deg: float) -> dict:
    """SIM2/RAD dogrulama araclarinin ayni desenini izler: ham log ->
    tek satirlik ozet. Tum ATA hesaplari EVADE penceresi (t>=INTERCEPT_S)
    uzerinden -- intercept penceresi sadece taban cizgi icindir."""
    t = log["t"]
    evade = t >= INTERCEPT_S
    ata = log["ata_deg"][evade]
    t_e = t[evade]
    bank = log["bank_deg"][evade]

    idx_peak = int(np.argmax(np.abs(ata)))
    ata_peak = float(ata[idx_peak])          # ISARETLI -- yon kontrolu icin
    t_peak = float(t_e[idx_peak])
    overshoot = abs(ata_peak) - theta_deg

    ss_mask = t >= (DURATION_S - SS_WINDOW_S)
    ata_ss = float(np.mean(log["ata_deg"][ss_mask]))
    ss_error = abs(ata_ss) - theta_deg

    # Oturma zamani: ATA ne zamandan itibaren |theta|+-3 bandinda KALICI kaliyor.
    # Sondan geriye tara: bandi son ihlal eden ornekten SONRAKI ilk ornek.
    band_ok = np.abs(np.abs(ata) - theta_deg) <= SETTLE_BAND_DEG
    if not band_ok[-1]:
        t_settle = float("nan")            # hicbir zaman oturmadi
    else:
        i = len(band_ok) - 1
        while i > 0 and band_ok[i - 1]:
            i -= 1
        t_settle = float(t_e[i])

    gimbal_margin = GIMBAL_AZ_DEG - abs(ata_peak)
    t_over_60 = float(np.sum(np.abs(ata) > GIMBAL_AZ_DEG) * DT)
    bank_peak = float(np.max(np.abs(bank)))

    return dict(ata_peak=ata_peak, t_peak=t_peak, overshoot=overshoot,
                ata_ss=ata_ss, ss_error=ss_error, t_settle=t_settle,
                gimbal_margin=gimbal_margin, t_over_60=t_over_60,
                bank_peak=bank_peak)


ROW_FMT = ("{theta:>5.0f} {sign:>3.0f} {alt:>7.0f} {mach:>5.2f} | "
           "{ata_peak:>8.1f} {t_peak:>6.1f} {overshoot:>+9.1f} | "
           "{ata_ss:>8.1f} {ss_error:>+8.1f} {t_settle:>8s} | "
           "{gimbal_margin:>+8.1f} {t_over_60:>7.1f} {bank_peak:>7.1f}")
HEADER = ("theta sgn     alt  mach |  ATApeak  tpeak  asim(pk) |"
          "    ATAss  hata(ss)  t_otur |  gimbalpay t>60deg  bankpk")


def _fmt_row(theta, sign, alt, mach, m: dict) -> str:
    t_settle_s = "nan" if math.isnan(m["t_settle"]) else f"{m['t_settle']:.1f}"
    fields = {k: v for k, v in m.items() if k != "t_settle"}
    return ROW_FMT.format(theta=theta, sign=sign, alt=alt, mach=mach,
                           t_settle=t_settle_s, **fields)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--quick", action="store_true",
                     help="Hizli dogrulama: theta=[0,50,90], alt=[25000], mach=[0.9]")
    ap.add_argument("--csv", type=str, default=None, help="Sonuc tablosunu CSV'ye de yaz")
    args = ap.parse_args()

    thetas = [0.0, 50.0, 90.0] if args.quick else THETAS_DEG
    alts = [25000.0] if args.quick else ALTS_FT
    machs = [0.9] if args.quick else MACHES

    rd = os.path.dirname(args.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    model = SAC.load(args.model, device="cpu")

    rows = []   # (theta, sign, alt, mach, metrics dict)

    print(f"model: {args.model}")
    print(f"kosu sayisi: {len(thetas) * len(alts) * len(machs)} "
          f"(+ yon kontrolu icin {0 if args.quick else len(ALTS_FT) * len(MACHES)})")
    print(HEADER)

    for alt in alts:
        for mach in machs:
            for theta in thetas:
                log = run_one(model, cfg, theta, alt, mach, sign=1.0)
                m = metrics(log, theta)
                rows.append((theta, 1.0, alt, mach, m))
                print(_fmt_row(theta, 1.0, alt, mach, m))

    if not args.quick:
        print(f"\n-- yon simetrisi kontrolu (theta={DIR_CHECK_THETA_DEG:.0f}, sign=-1) --")
        for alt in ALTS_FT:
            for mach in MACHES:
                log = run_one(model, cfg, DIR_CHECK_THETA_DEG, alt, mach, sign=-1.0)
                m = metrics(log, DIR_CHECK_THETA_DEG)
                rows.append((DIR_CHECK_THETA_DEG, -1.0, alt, mach, m))
                print(_fmt_row(DIR_CHECK_THETA_DEG, -1.0, alt, mach, m))

    if args.csv:
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["theta_deg", "sign", "alt_ft", "mach", "ata_peak", "t_peak",
                        "overshoot", "ata_ss", "ss_error", "t_settle", "gimbal_margin",
                        "t_over_60", "bank_peak"])
            for theta, sign, alt, mach, m in rows:
                w.writerow([theta, sign, alt, mach, m["ata_peak"], m["t_peak"],
                            m["overshoot"], m["ata_ss"], m["ss_error"], m["t_settle"],
                            m["gimbal_margin"], m["t_over_60"], m["bank_peak"]])
        print(f"\nCSV yazildi: {args.csv}")

    # -- OZ-DENETIM (bkz. dosya basligindaki "tuzak 46" notu) -------------
    print("\n== OZ-DENETIM ==")
    ok_all = True

    zero_runs = [(a, mc, m) for th, sg, a, mc, m in rows if th == 0.0 and sg == 1.0]
    zero_bad = [(a, mc, m) for a, mc, m in zero_runs if abs(m["ata_peak"]) >= 5.0]
    if zero_runs:
        status = "PASS" if not zero_bad else "FAIL"
        ok_all &= not zero_bad
        print(f"[{status}] theta=0 kontrolu: tum {len(zero_runs)} kosuda |ATApeak| < 5 deg olmali "
              f"(en kotu: {max((abs(m['ata_peak']) for _, _, m in zero_runs), default=0):.2f} deg)")
        if zero_bad:
            print("        -> olcum araci supheli: sifir komutta ATA sifira oturmuyor.")

    ninety_runs = [(a, mc, m) for th, sg, a, mc, m in rows if th == 90.0 and sg == 1.0]
    ninety_bad = [(a, mc, m) for a, mc, m in ninety_runs if m["t_over_60"] <= 0.0]
    if ninety_runs:
        status = "PASS" if not ninety_bad else "FAIL"
        ok_all &= not ninety_bad
        print(f"[{status}] theta=90 kontrolu: tum {len(ninety_runs)} kosuda t_over_60 > 0 olmali")
        if ninety_bad:
            print("        -> olcum araci supheli: tam beam bile gimbal asimini yakalamiyor.")

    smoke_ref = [m for th, sg, a, mc, m in rows
                 if th == 50.0 and sg == 1.0 and a == 25000.0 and mc == 0.9]
    if smoke_ref:
        m = smoke_ref[0]
        diff = abs(abs(m["ata_peak"]) - 65.5)
        status = "PASS" if diff <= 10.0 else "UYARI"
        print(f"[{status}] smoke capraz-dogrulama: theta=50, 25kft, M0.9 -> "
              f"ATApeak={m['ata_peak']:.1f} deg (smoke gozlemi: 65.5 deg, fark {diff:.1f})")
        if diff > 10.0:
            print("        -> izole kurulum, bvr_1v1_smoke.py'nin fizigini TEMSIL ETMIYOR olabilir.")

    print("SONUC:", "TUM OZ-DENETIMLER GECTI" if ok_all else "EN AZ BIR OZ-DENETIM BASARISIZ -- once bunu incele.")


if __name__ == "__main__":
    main()
