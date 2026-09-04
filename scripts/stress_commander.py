"""
STRES TESTI: AGRESIF betikli komutan altinda zarf ihlali olcumu.

=============================================================================
NEDEN BU TEST, NEDEN SIMDI
=============================================================================
Guidance katmani donduruldu. Bir sonraki faz taktik komutandir ve o, ortamin
urettigi makul hedeflerden COK daha sert komutlar verecek: keskin donusler,
hizli alcalmalar, enerji sinirinda ucus.

Olculdu ki nz_min (negatif g) ihlali, komutan devreye girince ARTMASI
BEKLENEN tek boyut (bkz. SAF-10, REQUIREMENTS.md). Dondurma anindaki
referans: 0.042 [0.023, 0.062], 24/150 bolum.

Sorun su: bunu ancak komutani egittikten SONRA gorursek, duzeltme maliyeti
katlanir -- cunku ic donguye dokunmak guidance'i, guidance'i degistirmek de
(sozlesme bozulursa) komutani yeniden egitmeyi gerektirir. Komutani yeniden
egitmek guidance'i egitmekten kat kat pahalidir.

Bu yuzden komutanin KOMUT DAGILIMINI, komutani egitmeden taklit ederiz.
Betikli agresif bir komutan 2 Hz'de sert komutlar verir; nz_min orani
referansin 2 katini (0.085) asarsa, ic dongu karari BVR'a yatirim yapmadan
ONCE verilir.

KULLANIM

  python scripts/stress_commander.py <model> -n 60
  python scripts/stress_commander.py <model> -n 60 --level nominal   # kiyas
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

#: Agresiflik seviyeleri. "nominal" ortamin kendi hedef uretimine yakindir
#: ve KIYAS icin vardir -- stres sonucunu tek basina okumak anlamsizdir,
#: referansa gore okunmalidir.
LEVELS = {
    "nominal":  dict(hdg=(10, 45),   d_alt=(1000, 5000),  d_mach=(0.05, 0.15),
                     hold_s=(12.0, 25.0)),
    "agresif":  dict(hdg=(60, 150),  d_alt=(5000, 12000), d_mach=(0.20, 0.40),
                     hold_s=(5.0, 15.0)),
    "asiri":    dict(hdg=(120, 180), d_alt=(8000, 18000), d_mach=(0.30, 0.55),
                     hold_s=(3.0, 8.0)),
}


def _new_command(rng, st, cfg, lv):
    """2 Hz'lik komutanin urettigi yeni komut: (kerteriz, irtifa, mach)."""
    sgn = rng.choice([-1.0, 1.0])
    d_hdg = sgn * rng.uniform(*lv["hdg"])
    brg = st.psi_rad + math.radians(d_hdg)

    d_alt = rng.choice([-1.0, 1.0]) * rng.uniform(*lv["d_alt"])
    alt = float(np.clip(st.alt_ft + d_alt, cfg.alt_lo, cfg.alt_hi))

    d_m = rng.choice([-1.0, 1.0]) * rng.uniform(*lv["d_mach"])
    # FIZIKSEL GECERLILIK: irtifaya bagli Mach tabaninin altina komut verilmez.
    # Ulasilamaz komut vermek "ajan basarisiz" gibi gorunur ama aslinda
    # olcumu gecersiz kilar -- bu tuzaga daha once hedef uretiminde dusulmustu.
    floor = ac.mach_floor(alt) * 1.02
    mach = float(np.clip(st.mach + d_m, max(cfg.mach_lo, floor), cfg.mach_hi))
    return brg, alt, mach


def run(model_path, n_ep, episode_s, level, seed0, verbose):
    rd = os.path.dirname(model_path)
    cfg = load_experiment(os.path.join(rd, "config.resolved.yaml")).env
    cfg.episode_s = episode_s
    pol = SAC.load(model_path, device="cpu")
    lv = LEVELS[level]

    env = GuidanceEnv(cfg=cfg, seed=seed0)
    per_ep, peaks, runs_len = [], [], []
    n_cmds = 0
    cmd_every = int(cfg.outer_hz / 2.0)          # 2 Hz komutan

    for ep in range(n_ep):
        obs, _ = env.reset(seed=seed0 + ep)
        rng = np.random.default_rng(100 + ep)
        n = int(episode_s * cfg.outer_hz)
        next_cmd, cur_run, ep_viol = 0, 0, 0

        for k in range(n):
            if k >= next_cmd:
                brg, alt, mach = _new_command(rng, env._st, cfg, lv)
                # Yakalanamayacak kadar uzak sanal hedef -> kerteriz komutu
                env.tgt_n = env._st.north_ft + 200 * NM * math.cos(brg)
                env.tgt_e = env._st.east_ft + 200 * NM * math.sin(brg)
                env.tgt_alt, env.tgt_mach = alt, mach
                env._prev_range = env._range_to_target()
                env._prev_alt_err = abs(alt - env._st.alt_ft)
                env._prev_mach_err = abs(mach - env._st.mach)
                obs = env._obs()
                next_cmd = k + max(cmd_every,
                                   int(rng.uniform(*lv["hold_s"]) * cfg.outer_hz))
                n_cmds += 1

            a, _ = pol.predict(obs, deterministic=True)
            obs, _, term, trunc, info = env.step(a)
            v = env._intra["nz_lo"]
            if v < ac.NZ_MIN:
                ep_viol += 1; cur_run += 1; peaks.append(v)
            elif cur_run:
                runs_len.append(cur_run); cur_run = 0
            if term or trunc:
                break
        if cur_run:
            runs_len.append(cur_run)
        per_ep.append(ep_viol / max(k + 1, 1))
        if verbose and (ep + 1) % 10 == 0:
            print(f"  ... {ep+1}/{n_ep} bolum", flush=True)

    env.close()
    return np.array(per_ep), np.array(peaks), np.array(runs_len), n_cmds


def _boot(x, n_boot=4000, seed=0):
    x = np.asarray(x, float)
    if len(x) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n_boot, len(x)))].mean(axis=1)
    return float(x.mean()), float(np.quantile(m, .025)), float(np.quantile(m, .975))


#: Dondurma anindaki referans (REQUIREMENTS.md, SAF-10) ve DUR esigi.
REF, REF_LO, REF_HI = 0.042, 0.023, 0.062
STOP = 2 * REF

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("--episode-sec", type=float, default=180.0)
    ap.add_argument("--level", choices=list(LEVELS), default="agresif")
    ap.add_argument("--seed0", type=int, default=70_000)
    a = ap.parse_args()

    print(f"model : {a.model}")
    print(f"seviye: {a.level}  {LEVELS[a.level]}")
    print(f"{a.n} bolum x {a.episode_sec:.0f} s, 2 Hz betikli komutan\n")
    pe, pk, rn, nc = run(a.model, a.n, a.episode_sec, a.level, a.seed0, True)
    m, lo, hi = _boot(pe)

    print()
    print("=" * 68)
    print(f"uretilen komut sayisi : {nc}  (~{nc/a.n:.1f} komut/bolum)")
    print(f"ihlalli bolum         : {int((pe>0).sum())}/{a.n}")
    print(f"nz_min IHLAL ORANI    : {m:.3f} [{lo:.3f}, {hi:.3f}]")
    print(f"  referans (dondurma) : {REF:.3f} [{REF_LO:.3f}, {REF_HI:.3f}]")
    print(f"  DUR esigi           : {STOP:.3f}")
    if len(pk):
        print(f"ihlal derinligi medyan: {np.median(pk):+.3f} g")
        print(f"                en kotu: {pk.min():+.3f} g   "
              f"(referans -4.581)")
        print(f"kesintisiz sure medyan: {np.median(rn):.0f} adim   "
              f"en uzun: {rn.max():.0f} adim ({rn.max()/10:.1f} s)")
    print()
    # KARAR: alt sinir esigin uzerindeyse fark GOSTERILMIS demektir.
    # Sadece ortalamaya bakip karar vermek, bu projede tekrar tekrar
    # yanlis sonuca goturdu (bkz. HANDOFF tuzak 17).
    if lo > STOP:
        print("KARAR: esik ASILDI (GA alt siniri esigin uzerinde).")
        print("       -> BVR'a yatirim yapmadan ONCE ic dongu g sinirlamasi")
        print("          veya 60 Hz filtre degerlendirilmeli.")
    elif m > STOP:
        print("KARAR: ortalama esigi asiyor ama GA alt siniri altinda.")
        print("       -> orneklem buyutulmeli; tek basina karar verdirmez.")
    else:
        print("KARAR: esik asilmadi. BVR'a gecilebilir; metrik izlenmeye")
        print("       devam eder (SAF-10).")
