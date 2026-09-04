"""
GUVENLIK DEGERLENDIRMESI: bariyer bazinda IHLAL ORANI.

=============================================================================
NEDEN TEPE DEGERI DEGIL, IHLAL ORANI
=============================================================================
Onceki degerlendirmede zarf metrigi "en kotu tek ornek" (max/min) idi.
Bu yaniltici: 18.000 adimlik bir kosuda TEK bir -3.37 g anlik degeri,
"g bariyeri tutmuyor" gibi gorunur; oysa olcum, n < -3 olan adim oraninin
%0.01 (yani ~2 adim) oldugunu gosterdi. Guvenli-RL literaturunde
raporlanan buyukluk IHLAL ORANI ve IHLAL SIDDETIDIR:

  - ihlal orani   : kac adim zarfin disindaydi (%)
  - ihlal siddeti : disarida kalinan miktarin ortalamasi/maksimumu
  - ihlal suresi  : ust uste kac adim disarida kalindi

Ayrica olcum ADIM-ICI tepe degerlerle yapilir (60 Hz ic dongu alt
adimlari), yalnizca 10 Hz karar sinirinda degil -- aksi halde iki karar
arasindaki asimlar gorunmez kalir.
"""
import sys
import os
import math
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from stable_baselines3 import SAC

from bvr.envs.guidance_env import GuidanceEnv, GuidanceConfig
from bvr.sim import aircraft as ac

# (isim, adim-ici anahtar, limit, yon)  yon=+1 -> deger limitten BUYUKSE ihlal
BARRIERS = [
    ("alpha_max", "alpha", ac.ALPHA_MAX_DEG, +1),
    ("beta_max", "beta", ac.BETA_MAX_DEG, +1),
    ("nz_max", "nz_hi", ac.NZ_MAX, +1),
    ("nz_min", "nz_lo", ac.NZ_MIN, -1),
    # Mach tabani IRTIFAYA BAGLI oldugu icin sabit esikle degil, ortamin
    # hesapladigi PAY (mach_marg) ile olculur: pay < 0 ise ihlal.
    # GERCEK agirlikla stall payi (bariyerin muhafazakar payi degil)
    ("stall_marj", "stall_marg", 0.0, -1),
]


def _boot_ci(x, n_boot=4000, alpha=0.05, seed=0):
    """Bolum-basi degerlerin ortalamasi icin bootstrap %95 guven araligi.

    NEDEN BOOTSTRAP VE NEDEN BOLUM BASINA:
    Zarf ihlalleri ADIM seviyesinde BAGIMSIZ DEGILDIR -- ucak bir bolumde
    yavas bir duruma girer ve 200-900 adim orada kalir. Adimlari bagimsiz
    sayip "%ihlal" hesaplamak, etkin orneklem sayisini yuzlerce kat abartir.
    Olcum: ayni konfigurasyon, farkli tohum bloklariyla %0.048 ile %1.742
    arasinda degisti (36 kat). Dogru birim BOLUMDUR; belirsizlik de
    bolumler uzerinden bootstrap ile verilmelidir.
    """
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), \
        float(np.quantile(means, 1 - alpha / 2))


def run(policy, use_shield, n_ep, episode_s, seed0=10_000, margin_path=None,
        model_path="data/models/edmd_physics.pkl"):
    cfg = GuidanceConfig(episode_s=episode_s, use_shield=use_shield,
                         turbulence_prob=0.3, shield_margin_path=margin_path,
                         shield_model_path=model_path)
    env = GuidanceEnv(cfg=cfg, seed=seed0)
    # Bolum BASINA ihlal orani tutulur (adim yigmak degil) -- belirsizlik
    # bolumler uzerinden hesaplanacak.
    per_ep = {b[0]: [] for b in BARRIERS}
    rewards, wpts, terms = [], [], []
    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        done, R = False, 0.0
        cnt = {b[0]: 0 for b in BARRIERS}
        nstep = 0
        while not done:
            a, _ = policy.predict(obs, deterministic=True)
            obs, r, t, tr, info = env.step(a)
            R += r
            nstep += 1
            p = env._intra
            for name, key, lim, sgn in BARRIERS:
                if (p[key] - lim if sgn > 0 else lim - p[key]) > 0:
                    cnt[name] += 1
            done = t or tr
        for name in cnt:
            per_ep[name].append(100.0 * cnt[name] / max(nstep, 1))
        rewards.append(R)
        wpts.append(info.get("episode_waypoints", 0))
        terms.append(info.get("termination", "timeout"))
    shield = env.shield.stats.summary() if env.shield else None
    return per_ep, rewards, wpts, terms, shield


def summarize(tag, per_ep, rewards, wpts, terms, shield):
    n = len(rewards)
    rm, rlo, rhi = _boot_ci(rewards)
    print(f"--- {tag}  ({n} bolum) ---")
    print(f"  odul {rm:7.1f}  [{rlo:.0f}, {rhi:.0f}]   "
          f"hedef/bolum {np.mean(wpts):5.2f}   "
          f"erken sonlanma {sum(1 for t in terms if t != 'timeout')}/{n}")
    print(f"  {'bariyer':<11} {'ihlal %':>9} {'%95 GA':>18} {'ihlalli bolum':>14}")
    tot = np.zeros(n)
    for name, *_ in BARRIERS:
        v = np.asarray(per_ep[name])
        tot += v
        m, lo, hi = _boot_ci(v)
        n_bad = int((v > 0).sum())
        print(f"  {name:<11} {m:9.3f} [{lo:7.3f}, {hi:7.3f}] {n_bad:8d}/{n}")
    m, lo, hi = _boot_ci(tot)
    n_bad = int((tot > 0).sum())
    print(f"  {'TOPLAM':<11} {m:9.3f} [{lo:7.3f}, {hi:7.3f}] {n_bad:8d}/{n}")
    if shield:
        print(f"  kalkan: mudahale %{100*shield['mudahale_orani']:.1f}  "
              f"slack %{100*shield['slack_orani']:.1f}  "
              f"ort sapma {shield['ort_sapma']:.4f}  "
              f"cozucu hatasi {shield['cozucu_hata']}")
    print()
    return (m, lo, hi, rm, rlo, rhi)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    ap.add_argument("--configs", type=str, default="")
    # TEK MODEL MODU: sabit karsilastirma listesi ESKI kosulara (guidance_shield,
    # physics+poly2) sabitlenmistir; nihai/aday modeller icin guvenlik olcumu
    # bu bayrakla yapilir. Kalkan modeli acikca verilir -- varsayilana
    # guvenmek bu projede iki kez sessiz hataya yol acti.
    ap.add_argument("--model", type=str, default=None,
                    help="tek bir SAC .zip olc (sabit listeyi atla)")
    ap.add_argument("--shield-model", type=str,
                    default="data/models/edmd_physics.pkl")
    ap.add_argument("--no-shield", action="store_true")
    ap.add_argument("--seed0", type=int, default=10_000)
    args = ap.parse_args()

    if args.model:
        pol = SAC.load(args.model, device="cpu")
        use_sh = not args.no_shield
        print("=" * 74)
        print(f"GUVENLIK DEGERLENDIRMESI -- TEK MODEL ({args.n} bolum x "
              f"{args.episode_sec:.0f} s, adim-ici 60 Hz olcum)")
        print(f"  model  : {args.model}")
        print(f"  kalkan : {use_sh}  ({args.shield_model})")
        print(f"  tohum blogu: {args.seed0}")
        print("=" * 74)
        logs, R, W, T, S = run(pol, use_sh, args.n, args.episode_sec,
                               seed0=args.seed0, model_path=args.shield_model)
        summarize(os.path.basename(args.model), logs, R, W, T, S)
        sys.exit(0)

    from bvr.agents.scripted_guidance import ScriptedGuidance
    cfg0 = GuidanceConfig()
    CONFIGS = [
        ("klasik gudum",
         ScriptedGuidance(mach_lo=cfg0.mach_lo, mach_hi=cfg0.mach_hi), False, None,
         "data/models/edmd_physics_poly2.pkl"),
        ("SAC kalkansiz",
         SAC.load("runs/guidance_noshield/sac_final.zip", device="cpu"), False,
         None, "data/models/edmd_physics_poly2.pkl"),
        ("SAC + CBF (enerji ufuklari AKTIF)",
         SAC.load("runs/guidance_shield/sac_final.zip", device="cpu"), True,
         None, "data/models/edmd_physics_poly2.pkl"),
    ]
    print("=" * 74)
    print(f"GUVENLIK DEGERLENDIRMESI ({args.n} bolum x {args.episode_sec:.0f} s, "
          f"adim-ici 60 Hz olcum)")
    print("=" * 74)
    out = {}
    for tag, pol, sh, mp, mdl in CONFIGS:
        logs, R, W, T, S = run(pol, sh, args.n, args.episode_sec, margin_path=mp,
                               model_path=mdl)
        out[tag] = summarize(tag, logs, R, W, T, S)
    print("=" * 88)
    print("OZET  (bolum-basi ortalama, %95 bootstrap guven araligi)")
    print("=" * 88)
    print(f"{'konfigurasyon':<28} {'ihlal %':>9} {'%95 GA':>18}   {'odul':>7} {'%95 GA':>16}")
    for k, (m, lo, hi, rm, rlo, rhi) in out.items():
        print(f"{k:<28} {m:9.3f} [{lo:7.3f}, {hi:7.3f}]   {rm:7.0f} [{rlo:5.0f}, {rhi:5.0f}]")
