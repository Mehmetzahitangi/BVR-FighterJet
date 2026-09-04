"""
ELLE MODEL TESTI: bir modeli calistir, HER ADIMDA hedefi ve ucagin o hedefe
gore ANLIK degerini yaz.

=============================================================================
NEDEN AYRI BIR ARAC
=============================================================================
`mission_eval` ve `safety_eval` TOPLU sayilar uretir (ortalama, guven
araligi). Bunlar karar vermek icin dogru araclardir ama "ucak SU AN ne
yapiyor" sorusuna cevap vermezler. Bir politikayi gozle anlamak icin
zaman serisi gerekir: hedef ne, ucak nerede, aradaki fark kapaniyor mu,
hangi komut veriliyor, kalkan mudahale ediyor mu.

KULLANIM

  # Ortamin kendi urettigi hedeflerle serbest ucus
  python scripts/test_model.py runs/reward_r3_both/sac_1999968_steps.zip

  # SABIT komut ver ve oturmasini izle (komut tutma davranisi)
  python scripts/test_model.py <model> --hold 25000 0.90 --from 30000 0.80

  # DEGISEN komutlar: 3 asamali senaryo
  python scripts/test_model.py <model> --schedule 0:25000:0.90       60:30000:0.80 120:20000:1.00

  # Hedef menzilini gercekci yap (salinim teshisi icin)
  python scripts/test_model.py <model> --hold 25000 0.90 --target-range 30

  # Daha seyrek log + Tacview kaydi
  python scripts/test_model.py <model> --every 20 --acmi runs/test.acmi

  # Kalkani kapatip farki gor
  python scripts/test_model.py <model> --no-shield

SUTUNLAR

  t        : bolum zamani [s]
  menzil   : hedefe kalan mesafe [deniz mili]
  IRTIFA   : hedef / anlik / hata   (hata = anlik - hedef; + ise yuksekteyiz)
  MACH     : hedef / anlik / hata
  kerteriz : hedefe gore yon hatasi [derece]  (0 = burun hedefte)
  komut    : ic donguye UYGULANAN komut (kalkandan gectikten SONRA)
             phi = yatis [deg], gam = ucus yolu acisi [deg], M = mach
  zarf     : alpha [deg] / nz [g]  -- adim-ici (60 Hz) tepe degerler
  K        : ajanin ISTEDIGI komut ile UYGULANAN komut farkliysa *
             (kalkan mudahalesi VEYA slew sinirlayicisi -- ikisi de
             komutu degistirir; ayirmak icin --no-shield ile kiyasla)
"""
import sys
import os
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv
from bvr.config import load_experiment
from bvr.sim import aircraft as ac

NM = 6076.0


def _bearing_err_deg(env) -> float:
    """Ucagin burnu ile hedef yonu arasindaki aci [-180, 180]."""
    st = env._st
    dn, de = env.tgt_n - st.north_ft, env.tgt_e - st.east_ft
    tgt_brg = math.atan2(de, dn)
    err = math.degrees(tgt_brg - st.psi_rad)
    return (err + 180.0) % 360.0 - 180.0


def parse_schedule(items):
    """'t:irtifa:mach[:kerteriz]' listesini ayristirir.

    Ornek:  --schedule 0:25000:0.90  60:30000:0.80  120:20000:1.00
    Dorduncu alan verilirse o anda hedef kerterizi de DEGISIR (derece,
    ucagin o anki burnuna GORE degil, mutlak yon).
    """
    out = []
    for it in items:
        f = it.split(":")
        if len(f) not in (3, 4):
            sys.exit(f"gecersiz senaryo adimi: {it}  (t:irtifa:mach[:kerteriz])")
        out.append((float(f[0]), float(f[1]), float(f[2]),
                    float(f[3]) if len(f) == 4 else None))
    return sorted(out, key=lambda x: x[0])


def run(model_path, seed, episode_s, every, hold, start, acmi, no_shield,
        schedule=None, tgt_range_nm=200.0):
    rd = os.path.dirname(model_path)
    y = os.path.join(rd, "config.resolved.yaml")
    if not os.path.exists(y):
        sys.exit(f"config bulunamadi: {y}")
    cfg = load_experiment(y).env
    cfg.episode_s = episode_s
    if no_shield:
        cfg.use_shield = False

    pol = SAC.load(model_path, device="cpu")
    env = GuidanceEnv(cfg=cfg, seed=seed)
    obs, _ = env.reset(seed=seed)

    if start is not None:
        env._st = env.sim.reset(alt_ft=start[0], mach=start[1], heading_deg=0.0,
                                trim=True, fuel_frac=0.6)
        env.inner.reset(trim_throttle=env.sim["fcs/throttle-cmd-norm"])
        if env.shield is not None:
            env.shield.reset_state()

    # HEDEF MENZILI ONEMLIDIR. Egitimde hedefler 3.3-14.8 nmi araligindaydi.
    # Cok uzak bir hedef (200 nmi) kerterizi ucagin yonune neredeyse
    # duyarsiz kilar; kurs takip dongusunun dogal sonumlemesi kaybolur ve
    # politika egitim dagiliminin DISINDA calisir. Salinim gorurseniz once
    # --target-range ile menzili gercekci bir degere cekip tekrar bakin.
    def _place(brg_deg, rng_nm):
        b = math.radians(brg_deg)
        env.tgt_n = env._st.north_ft + rng_nm * NM * math.cos(b)
        env.tgt_e = env._st.east_ft + rng_nm * NM * math.sin(b)

    cur_brg = 0.0
    if hold is not None:
        _place(cur_brg, tgt_range_nm)
        env.tgt_alt, env.tgt_mach = hold[0], hold[1]
    elif schedule:
        t0, a0, m0, b0 = schedule[0]
        cur_brg = b0 if b0 is not None else 0.0
        _place(cur_brg, tgt_range_nm)
        env.tgt_alt, env.tgt_mach = a0, m0

    env._prev_range = env._range_to_target()
    env._prev_alt_err = abs(env.tgt_alt - env._st.alt_ft)
    env._prev_mach_err = abs(env.tgt_mach - env._st.mach)
    obs = env._obs()

    rec = None
    if acmi:
        from bvr.sim.acmi import ACMIRecorder
        rec = ACMIRecorder(acmi, title=f"test: {os.path.basename(model_path)}")
        rec.open()

    print(f"model  : {model_path}")
    print(f"kalkan : {cfg.use_shield}   tohum: {seed}   sure: {episode_s:.0f} s")
    if hold:
        print(f"MOD    : SABIT KOMUT  irtifa {hold[0]:.0f} ft, Mach {hold[1]:.2f}"
              f"   (hedef {tgt_range_nm:.0f} nmi)")
    elif schedule:
        print(f"MOD    : SENARYO  {len(schedule)} asama   (hedef {tgt_range_nm:.0f} nmi,"
              f" her komut degisiminde yeniden konumlanir)")
        for t, al, mc, br in schedule:
            print(f"         t={t:6.0f} s -> irtifa {al:6.0f} ft, Mach {mc:4.2f}"
                  + (f", kerteriz {br:+.0f} deg" if br is not None else ""))
    else:
        print(f"MOD    : serbest ucus (ortam hedef uretir)")
    print()
    hdr = (f"{'t':>6} {'menzil':>7} | {'IRTIFA hedef':>12} {'anlik':>8} {'hata':>7} "
           f"| {'MACH h':>6} {'anlik':>6} {'hata':>7} | {'kert':>6} "
           f"| {'phi':>6} {'gam':>6} {'M':>5} | {'alpha':>6} {'nz':>6} K")
    print(hdr)
    print("-" * len(hdr))

    n = int(episode_s * cfg.outer_hz)
    n_wpt, worst_nz, term_reason = 0, 0.0, "timeout"
    alt_errs, mach_errs = [], []

    for k in range(n):
        a, _ = pol.predict(obs, deterministic=True)
        obs, r, term, trunc, info = env.step(a)
        if hold is not None:                      # hedefi SABIT tut
            env.tgt_alt, env.tgt_mach = hold[0], hold[1]
        elif schedule:
            t_now = k / cfg.outer_hz
            seg = [x for x in schedule if x[0] <= t_now]
            if seg:
                _, sa, sm, sb = seg[-1]
                if (sa, sm) != (env.tgt_alt, env.tgt_mach) or sb is not None:
                    if sb is not None and abs(sb - cur_brg) > 1e-9:
                        cur_brg = sb
                    _place(cur_brg, tgt_range_nm)
                if (sa, sm) != (env.tgt_alt, env.tgt_mach):
                    print(f"{'':>6} {'':>7} | >>> YENI KOMUT @ {t_now:.0f} s: "
                          f"irtifa {sa:.0f} ft, Mach {sm:.2f}"
                          + (f", kerteriz {cur_brg:.0f} deg" if sb is not None else ""))
                env.tgt_alt, env.tgt_mach = sa, sm

        st = env._st
        alt_err = st.alt_ft - env.tgt_alt
        mach_err = st.mach - env.tgt_mach
        alt_errs.append(alt_err); mach_errs.append(mach_err)
        pk = env._intra
        worst_nz = min(worst_nz, pk["nz_lo"]) if worst_nz else pk["nz_lo"]

        if rec:
            rec.record(st, extra={"TgtAlt": env.tgt_alt, "TgtMach": env.tgt_mach,
                                  "AltErr": alt_err, "MachErr": mach_err})

        if "waypoint" in info:
            n_wpt += 1
            w = info["waypoint"]
            print(f"{'':>6} {'':>7} | >>> HEDEFE VARILDI  irtifa "
                  f"{'TAM' if w['alt_ok'] else 'ISKA'}  mach "
                  f"{'TAM' if w['mach_ok'] else 'ISKA'}   (toplam {n_wpt})")

        if k % every == 0:
            cmd = np.asarray(env._last_applied, dtype=float)  # kalkandan GECMIS
            phi_d = math.degrees(cmd[0] * math.radians(ac.BANK_MAX_DEG))
            gam_d = math.degrees(cmd[1] * math.radians(ac.GAMMA_MAX_DEG))
            m_cmd = cfg.mach_lo + (cmd[2] + 1.0) * 0.5 * (cfg.mach_hi - cfg.mach_lo)
            dev = float(np.max(np.abs(np.asarray(a, dtype=float) - cmd)))
            shielded = "*" if dev > 0.01 else "."
            print(f"{k/cfg.outer_hz:6.1f} {env._range_to_target()/NM:7.2f} "
                  f"| {env.tgt_alt:12.0f} {st.alt_ft:8.0f} {alt_err:+7.0f} "
                  f"| {env.tgt_mach:6.3f} {st.mach:6.3f} {mach_err:+7.3f} "
                  f"| {_bearing_err_deg(env):+6.1f} "
                  f"| {phi_d:+6.1f} {gam_d:+6.1f} {m_cmd:5.2f} "
                  f"| {math.degrees(st.alpha_rad):6.1f} {pk['nz_lo']:+6.2f} {shielded}")

        if term or trunc:
            term_reason = info.get("termination", "timeout")
            break

    if rec:
        rec.close()
        print(f"\nTacview kaydi: {acmi}")

    w = int(min(len(alt_errs), 30 * cfg.outer_hz))     # son 30 s
    print()
    print("=" * 64)
    print(f"sonlanma        : {term_reason}   ({k+1} adim, {(k+1)/cfg.outer_hz:.1f} s)")
    print(f"ulasilan hedef  : {n_wpt}")
    print(f"son 30 s irtifa : ort {np.mean(alt_errs[-w:]):+.0f} ft   "
          f"sapma {np.std(alt_errs[-w:]):.0f} ft   "
          f"(tolerans +-{cfg.alt_tol_ft:.0f})")
    print(f"son 30 s Mach   : ort {np.mean(mach_errs[-w:]):+.4f}   "
          f"sapma {np.std(mach_errs[-w:]):.4f}   "
          f"(tolerans +-{cfg.mach_tol:.2f})")
    print(f"en dusuk nz     : {worst_nz:+.2f} g   "
          f"(bariyer {ac.NZ_MIN:.1f}, sonlandirma {ac.NZ_MIN-0.5:.1f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    ap.add_argument("model", help="sac_*.zip yolu")
    ap.add_argument("--seed", type=int, default=50_000)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    ap.add_argument("--every", type=int, default=10,
                    help="kac dis dongu adiminda bir satir yaz (10 = 1 s)")
    ap.add_argument("--hold", nargs=2, type=float, metavar=("IRTIFA", "MACH"),
                    help="SABIT komut ver ve oturmasini izle")
    ap.add_argument("--from", dest="start", nargs=2, type=float,
                    metavar=("IRTIFA", "MACH"), help="baslangic durumunu zorla")
    ap.add_argument("--schedule", nargs="+", metavar="t:IRTIFA:MACH[:KERTERIZ]",
                    help="zaman icinde DEGISEN komut dizisi, orn: "
                         "0:25000:0.90 60:30000:0.80 120:20000:1.00")
    ap.add_argument("--target-range", type=float, default=200.0, metavar="NMI",
                    help="sanal hedefin menzili (varsayilan 200; egitim araligi "
                         "3.3-14.8 nmi -- salinim gorurseniz 20-40 deneyin)")
    ap.add_argument("--acmi", default=None, help="Tacview kaydi yolu")
    ap.add_argument("--no-shield", action="store_true")
    a = ap.parse_args()
    sch = parse_schedule(a.schedule) if a.schedule else None
    if a.hold and sch:
        sys.exit("--hold ile --schedule birlikte kullanilamaz")
    run(a.model, a.seed, a.episode_sec, a.every, a.hold, a.start,
        a.acmi, a.no_shield, schedule=sch, tgt_range_nm=a.target_range)
