"""
GOREV METRIKLERI: "ajan verilen hedefi yapiyor mu?" sorusunun OLCULEBILIR hali.

=============================================================================
NEDEN YENI BIR OLCUM
=============================================================================
Ortamdaki `is_success` tanimi "bolumde >= 3 hedefe var" idi. Bu esik
FIZIKSEL TAVANIN USTUNDE:

    180 s x ~900 ft/s = 162.000 ft = 26.7 deniz mili menzil
    hedefler 3.3 - 14.8 nmi arasinda, ortalama ~9 nmi
    -> dumduz ucsa bile ~3 hedef; rastgele kerterizle donus kaybiyla ~2-2.5

Yani ulasilamayan bir esige gore "%15 basari" raporlaniyordu. Boyle bir
metrigi optimize etmek anlamsizdir; once metrik duzeltilir, sonra egitim.

Yerine gecen metrikler:
  1. BACAK YAKALAMA ORANI  : uretilen hedeflerin kaci yakalandi
  2. SEYRUSEFER VERIMI     : ideal sure / gercek sure  (1.0 = kusursuz)
                             ideal = baslangic menzili / ortalama yer hizi
  3. YAKALAMA KALITESI     : varista hem irtifa hem Mach toleransinda mi
  4. IZLEME HATASI         : bacak boyunca irtifa/Mach RMSE

Bu olcum ORTAMI DEGISTIRMEZ -- yalnizca disaridan gozlemler. Boylece
devam eden egitimler gecersiz olmaz.
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


def _boot_ci(x, n_boot=4000, alpha=0.05, seed=0):
    x = np.asarray(x, float)
    if len(x) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n_boot, len(x)))].mean(axis=1)
    return float(x.mean()), float(np.quantile(m, alpha/2)), float(np.quantile(m, 1-alpha/2))


def evaluate(policy, cfg, n_ep=60, seed0=10_000, verbose=True):
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    legs = []          # TAMAMLANAN hedef bacaklari
    truncated = []     # bolum sonunda yarim kalan bacaklar (basarisizlik DEGIL)
    ep_rows = []

    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done = False
        # Bacak takibi: hedef uretildiginde menzil ve zaman kaydedilir
        leg_r0 = env._range_to_target()
        leg_t0 = 0
        leg_v = []
        alt_err, mach_err = [], []
        k = 0
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, r, term, trunc, info = env.step(a)
            k += 1
            st = env._st
            leg_v.append(st.vt_fps)
            alt_err.append(env.tgt_alt - st.alt_ft)
            mach_err.append(env.tgt_mach - st.mach)

            if "waypoint" in info:                      # bacak yakalandi
                # PENCERE OLCUMU: varis ANI tek bir ornek; son W saniyenin
                # ne kadarinin toleransta gectigini de olceriz. Gercek bir
                # sistem de son yaklasma BANDINI degerlendirir, tek fotografi
                # degil. Ikisi de raporlanir -- hangisinin kullanilacagi
                # veriye bakilarak karara baglanir.
                dt = (k - leg_t0) / cfg.outer_hz
                v_avg = float(np.mean(leg_v)) if leg_v else 1.0
                t_ideal = leg_r0 / max(v_avg, 1.0)
                W = int(5.0 * cfg.outer_hz)          # son 5 saniye
                ae = np.abs(alt_err[-W:]); me = np.abs(mach_err[-W:])
                legs.append(dict(
                    captured=1.0,
                    win_alt=float(np.mean(ae <= cfg.alt_tol_ft)),
                    win_mach=float(np.mean(me <= cfg.mach_tol)),
                    win_both=float(np.mean((ae <= cfg.alt_tol_ft) &
                                           (me <= cfg.mach_tol))),
                    efficiency=float(np.clip(t_ideal / max(dt, 1e-6), 0.0, 1.5)),
                    quality=float(info["waypoint"]["alt_ok"] and info["waypoint"]["mach_ok"]),
                    alt_ok=float(info["waypoint"]["alt_ok"]),
                    mach_ok=float(info["waypoint"]["mach_ok"]),
                    alt_rmse=float(np.sqrt(np.mean(np.square(alt_err)))),
                    mach_rmse=float(np.sqrt(np.mean(np.square(mach_err)))),
                    range_nm=leg_r0 / 6076.0,
                ))
                leg_r0, leg_t0, leg_v = env._range_to_target(), k, []
                alt_err, mach_err = [], []
            done = term or trunc

        # Bolum bitiminde YARIM KALAN bacak.
        # Bu bir BASARISIZLIK DEGILDIR: bolum 180 s'de kesilir ve her bolumun
        # son bacagi tanim geregi yarim kalir. Onceki olcumde bunlar
        # "yakalanamadi" sayiliyordu ve yakalama orani %65 gorunuyordu --
        # oysa 86 bacagin 30'u tam olarak bolum basina 1 taneydi, yani
        # ZAMANI OLAN her bacak yakalanmisti. Ayri kategoride tutulur.
        if k > leg_t0 + 10:
            truncated.append(dict(
                range_nm=leg_r0 / 6076.0,
                progress=1.0 - self_range / leg_r0 if (self_range := env._range_to_target()) else 0.0,
            ))
        ep_rows.append(dict(term=info.get("termination", "timeout"),
                            wpts=info.get("episode_waypoints", 0)))

    if not legs:
        print("bacak yok"); return None
    L = {k: np.array([d[k] for d in legs], dtype=float) for k in legs[0]}
    cap = L["captured"] > 0
    res = {}

    def rep(label, arr, fmt="{:6.3f}"):
        m, lo, hi = _boot_ci(arr[np.isfinite(arr)])
        res[label] = (m, lo, hi)
        if verbose:
            print(f"  {label:<28} " + fmt.format(m) +
                  f"   [{fmt.format(lo)}, {fmt.format(hi)}]")

    if verbose:
        print(f"  {'metrik':<28} {'ortalama':>8}   {'%95 GA'}")
    rep("seyrusefer verimi", L["efficiency"][cap])
    rep("yakalama kalitesi (alt+mach)", L["quality"][cap])
    rep("  - irtifa toleransinda", L["alt_ok"][cap])
    rep("  - mach toleransinda", L["mach_ok"][cap])
    if verbose:
        print(f"  {'--- son 5 s PENCERESI ---':<28}")
    rep("pencere: ikisi birden", L["win_both"][cap])
    rep("  - irtifa toleransinda", L["win_alt"][cap])
    rep("  - mach toleransinda", L["win_mach"][cap])
    rep("irtifa RMSE [ft]", L["alt_rmse"], "{:6.0f}")
    rep("mach RMSE", L["mach_rmse"], "{:6.4f}")
    if verbose:
        nt = sum(1 for e in ep_rows if e["term"] != "timeout")
        n_tr = len(truncated)
        prog = float(np.mean([t["progress"] for t in truncated])) if truncated else 0.0
        print(f"  {'erken sonlanma':<28} {nt:6d}/{len(ep_rows)}")
        print(f"  {'tamamlanan bacak':<28} {len(legs):6d}  "
              f"(hepsi yakalandi)")
        print(f"  {'yarim kalan bacak':<28} {n_tr:6d}  "
              f"(bolum sonu; ortalama %{100*prog:.0f} yol alinmis)")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="sac_final.zip yolu VEYA config yaml")
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    # AYRI BOLUM BLOGU: aday secimi 10000 blogunda yapildiysa, secilen
    # modelin SAPMASIZ tahmini icin FARKLI bir blokta olculmelidir --
    # aksi halde 9 aday arasindan en iyiyi secmek, test kumesinde secim
    # yapmak demektir ve raporlanan deger yukari saplidir.
    ap.add_argument("--seed0", type=int, default=10_000)
    a = ap.parse_args()

    if a.model.endswith(".yaml"):
        cfg = load_experiment(a.model)
        env_cfg, zip_path = cfg.env, os.path.join(cfg.run_dir, "sac_final.zip")
    else:
        zip_path = a.model
        rd = os.path.dirname(zip_path)
        y = os.path.join(rd, "config.resolved.yaml")
        env_cfg = load_experiment(y).env if os.path.exists(y) else GuidanceConfig()
    env_cfg.episode_s = a.episode_sec
    print(f"model : {zip_path}")
    print(f"kalkan: {env_cfg.use_shield}\n")
    evaluate(SAC.load(zip_path, device="cpu"), env_cfg, a.n, seed0=a.seed0)
