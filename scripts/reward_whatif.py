"""
ODUL "NE OLURDU" ANALIZI: ayni yorungeler, farkli agirliklar.

Neden: bir odul degisikligini denemeden once, o degisikligin KABUL
KRITERINE bagli payi gercekten anlamli seviyeye cikarip cikarmadigini
bilmek isteriz. Politikanin davranisi sabit tutulup yalnizca agirliklar
degistirilir -- bu tam bir tahmin degildir (yeni odulle politika da
degisecek) ama DOGRU MERTEBEDE olup olmadigimizi soyler.

Olculen kilit sayi: getirinin yuzde kaci varis KALITESINE bagli?
Mevcut deger %0.26 idi ve SAC'in kritigi bunu cozemiyordu.
"""
import sys, os, math, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from stable_baselines3 import SAC
from bvr.envs.guidance_env import GuidanceEnv
from bvr.config import load_experiment


def rollout_terms(policy, cfg, n_ep, seed0=40_000):
    """Bolum basina HAM bilesenleri toplar (agirliktan bagimsiz)."""
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    rows = []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        acc = dict(prog=0.0, alt_prog=0.0, mach_prog=0.0,
                   alt_prec_raw=[], mach_prec_raw=[], dact=0.0,
                   n_wpt=0, n_alt_ok=0, n_mach_ok=0)
        prev_alt = abs(env.tgt_alt - env._st.alt_ft)
        prev_mach = abs(env.tgt_mach - env._st.mach)
        prev_rng = env._range_to_target()
        prev_applied = env._prev_applied.copy()
        done = False
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            a_raw = np.asarray(a, dtype=float)
            obs, r, term, trunc, info = env.step(a)
            st = env._st
            d_alt = abs(env.tgt_alt - st.alt_ft); d_mach = abs(env.tgt_mach - st.mach)
            rng = env._range_to_target()
            # Ortamla AYNI normalizasyon: menzil kapanmasi / ucagin kendi yolu
            acc["prog"] += float(np.clip(
                (prev_rng - rng) / max(st.vt_fps / cfg.outer_hz, 1.0), -1.0, 1.0))
            acc["alt_prog"] += float(np.clip((prev_alt - d_alt) / cfg.alt_prog_scale_ft, -1, 1))
            acc["mach_prog"] += float(np.clip((prev_mach - d_mach) / cfg.mach_prog_scale, -1, 1))
            # HAM hata: hassasiyet terimi cekirdek genisligine gore yeniden
            # hesaplanabilsin diye hatanin KENDISI saklanir
            acc["alt_prec_raw"].append(d_alt); acc["mach_prec_raw"].append(d_mach)
            acc["dact"] += float(np.sum((a_raw - prev_applied) ** 2))
            prev_alt, prev_mach, prev_rng = d_alt, d_mach, rng
            prev_applied = env._prev_applied.copy()
            if "waypoint" in info:
                acc["n_wpt"] += 1
                acc["n_alt_ok"] += int(info["waypoint"]["alt_ok"])
                acc["n_mach_ok"] += int(info["waypoint"]["mach_ok"])
                prev_rng = env._range_to_target()
            done = term or trunc
        rows.append(acc)
    env.close()
    return rows


def score(rows, c):
    """Verilen agirliklarla bolum getirisini ve kalite payini hesaplar."""
    out = []
    for a in rows:
        alt_prec = sum(math.exp(-(e / c.alt_prec_ft) ** 2) for e in a["alt_prec_raw"])
        mach_prec = sum(math.exp(-(e / c.mach_prec) ** 2) for e in a["mach_prec_raw"])
        pos = (c.w_progress * a["prog"] + c.w_alt_prog * a["alt_prog"]
               + c.w_mach_prog * a["mach_prog"]
               + c.w_alt_prec * alt_prec + c.w_mach_prec * mach_prec)
        uncond = c.r_waypoint * 0.4 * a["n_wpt"]
        qual = c.r_waypoint * (0.4 * a["n_alt_ok"] + 0.2 * a["n_mach_ok"])
        total = pos + uncond + qual - c.w_action_rate * a["dact"]
        # Kaliteye bagli BAND: ayni bolumu kusursuz vs kalitesiz bitirmenin farki
        band = c.r_waypoint * 0.6 * a["n_wpt"]
        out.append((total, qual, band))
    t = np.array([o[0] for o in out]); q = np.array([o[1] for o in out])
    b = np.array([o[2] for o in out])
    # HASSASIYET BLOGUNUN NEREYE GITTIGI: bu blok odulun ~%33'u. Eger buyuk
    # kismi TOLERANS DISINDAYKEN toplaniyorsa, blok "kabaca yakin ol" diyor
    # demektir -- yani en buyuk ikinci odul kalemi yanlis seyi odullendiriyor.
    ins = tot = 0.0
    for a in rows:
        for e in a["alt_prec_raw"]:
            v = c.w_alt_prec * math.exp(-(e / c.alt_prec_ft) ** 2)
            tot += v; ins += v if e <= c.alt_tol_ft else 0.0
        for e in a["mach_prec_raw"]:
            v = c.w_mach_prec * math.exp(-(e / c.mach_prec) ** 2)
            tot += v; ins += v if e <= c.mach_tol else 0.0
    return t.mean(), q.mean(), b.mean(), ins / max(tot, 1e-9)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--configs", nargs="+", required=True)
    a = ap.parse_args()

    base_cfg = load_experiment(os.path.join(os.path.dirname(a.model),
                                            "config.resolved.yaml")).env
    pol = SAC.load(a.model, device="cpu")
    rows = rollout_terms(pol, base_cfg, a.n)

    print(f"\nmodel: {a.model}   ({a.n} bolum, tohum blogu 40000)")
    print(f"{'config':<16} {'getiri':>9} {'kalite BANDI':>13} {'band %':>8} "
          f"{'hassasiyetin tolerans ICINDE toplanan payi':>44}")
    for cpath in a.configs:
        c = load_experiment(cpath).env if cpath != "MEVCUT" else base_cfg
        t, q, b, ins = score(rows, c)
        name = "MEVCUT" if cpath == "MEVCUT" else os.path.basename(cpath).replace(".yaml", "")
        print(f"{name:<16} {t:9.0f} {b:13.1f} {100*b/max(t,1e-9):7.2f}% "
              f"{100*ins:43.1f}%")
    print("\nkalite BANDI = ayni bolumu kusursuz bitirmekle konum-disi her seyi")
    print("kacirmak arasindaki odul farki. Kritigin cozmesi gereken sinyal budur.")
