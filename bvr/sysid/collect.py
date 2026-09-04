"""
OFFLINE SISTEM TANIMLAMA VERISI TOPLAMA.

Toplanan sey: kapali cevrimin (F-16 + FLCS + ic dongu) dis dongu adiminda
nasil evrildigi:

        x_k  --[ u_k ]-->  x_{k+1}          (dis dongu periyodu, 10 Hz)

NEDEN DIS DONGU PERIYODUNDA (0.1 s), 60 Hz'de DEGIL?
Guvenlik filtresi (CBF) dis dongu komutlarini kisitlayacak. Filtrenin
sormasi gereken soru "bu komutu bir dis dongu adimi boyunca uygularsam
zarftan cikar miyim?"dir. Model tam olarak bu soruya cevap verecek
zaman olceginde kurulmalidir.

NEDEN OFFLINE?
Kalici uyarim (persistent excitation) ancak TASARLANMIS bir uyarimla
saglanir; ajanin kendi urettigi veri politikaya gore daralir ve model
curur (bkz. excitation.py). Offline toplayip modeli DONDURMAK ayrica:
  - egitimi 10-50x hizlandirir (QP icin sabit matris, replay buffer'a
    model anlik goruntusu gommek yok),
  - model kalitesini RL'den BAGIMSIZ olcmeyi mumkun kilar (tez icin sart),
  - DMD/EDMD/Deep-Koopman'i BIREBIR ayni veri uzerinde karsilastirir.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np

from ..sim import aircraft as ac
from ..sim.jsbsim_bridge import F16Sim
from ..control.inner_loop import InnerLoop, InnerLoopCommand
from ..models.state_def import state_from_flight, cmd_to_u, X_DIM, U_DIM
from .excitation import MultiSine, RandomSteps, Multistep3211, Sum, Constant


@dataclass
class CollectConfig:
    ctrl_hz: float = 60.0
    outer_hz: float = 10.0
    episode_s: float = 120.0
    # Isletme noktasi ornekleme araligi (durum uzayi kapsamasi icin)
    alt_lo: float = 8000.0
    alt_hi: float = 45000.0
    # Uyarim genlikleri (zarfin biraz ICINDE tutulur; departure verisi
    # toplamak istemiyoruz -- model normal ucus bolgesinde dogru olmali)
    phi_amp_deg: float = 60.0
    gamma_amp_deg: float = 20.0
    mach_amp: float = 0.25
    turbulence_prob: float = 0.3
    fuel_lo: float = 0.30
    fuel_hi: float = 1.00
    # Guvenlik durdurma esikleri
    abort_alt_ft: float = 3000.0
    abort_mach_lo: float = 0.22
    abort_alpha_deg: float = 27.0


def _sample_operating_point(rng, cfg):
    """Isletme noktasi sec: irtifa ve o irtifada MAKUL bir Mach.

    Mach araligi irtifayla kayar (yuksekte stall Mach'i yukselir, ayrica
    yuksek irtifada dusuk Mach surdurulemez). Ulasilamaz noktalarda veri
    toplamak modeli bozar: orada zaten ucamayiz.
    """
    alt = rng.uniform(cfg.alt_lo, cfg.alt_hi)
    frac = (alt - cfg.alt_lo) / max(cfg.alt_hi - cfg.alt_lo, 1.0)
    m_lo = 0.40 + 0.30 * frac        # 8 kft: 0.40   45 kft: 0.70
    m_hi = 1.05 + 0.45 * frac        # 8 kft: 1.05   45 kft: 1.50
    mach = rng.uniform(m_lo, m_hi)
    return alt, mach, (m_lo, m_hi)


def _build_excitation(rng, cfg, mach0, mach_band):
    """Uc kanal icin uyarim sinyali kur.

    Her bolum bir "rejim" secer; boylece veri seti hem genis-bant
    (multisine), hem gecici (basamak), hem klasik ucus-testi (3-2-1-1)
    davranisi icerir. Tek tip sinyalle toplanan veri, o sinyalin
    goremedigi dinamigi modele hic ogretemez.
    """
    regime = rng.choice(["multisine", "steps", "mixed", "3211"],
                        p=[0.35, 0.30, 0.25, 0.10])
    phi_a = math.radians(cfg.phi_amp_deg) * rng.uniform(0.35, 1.0)
    gam_a = math.radians(cfg.gamma_amp_deg) * rng.uniform(0.35, 1.0)
    m_lo, m_hi = mach_band
    mach_a = min(cfg.mach_amp, 0.5 * (m_hi - m_lo)) * rng.uniform(0.3, 1.0)
    mach_c = float(np.clip(mach0, m_lo + mach_a, m_hi - mach_a))

    if regime == "multisine":
        phi = MultiSine(phi_a, 0.02, 0.60, 9, 0.0, rng)
        gam = MultiSine(gam_a, 0.02, 0.40, 9, 0.0, rng)
        mch = MultiSine(mach_a, 0.005, 0.06, 6, mach_c, rng)
    elif regime == "steps":
        phi = RandomSteps(-phi_a, phi_a, 2.0, 15.0, rng)
        gam = RandomSteps(-gam_a, gam_a, 3.0, 20.0, rng)
        mch = RandomSteps(mach_c - mach_a, mach_c + mach_a, 15.0, 45.0, rng)
    elif regime == "mixed":
        phi = Sum([RandomSteps(-phi_a * .7, phi_a * .7, 4.0, 20.0, rng),
                   MultiSine(phi_a * .4, 0.05, 0.60, 7, 0.0, rng)],
                  -math.radians(ac.BANK_MAX_DEG), math.radians(ac.BANK_MAX_DEG))
        gam = Sum([RandomSteps(-gam_a * .7, gam_a * .7, 5.0, 25.0, rng),
                   MultiSine(gam_a * .4, 0.05, 0.40, 7, 0.0, rng)],
                  math.radians(ac.GAMMA_MIN_DEG), math.radians(ac.GAMMA_MAX_DEG))
        mch = Sum([Constant(mach_c),
                   MultiSine(mach_a, 0.005, 0.05, 5, 0.0, rng)], m_lo, m_hi)
    else:  # 3-2-1-1 dizisi: kanallar sirayla, aralarda dinlenme
        T = float(rng.uniform(1.0, 3.0))
        phi = Sum([Multistep3211(phi_a, T, t0)
                   for t0 in np.arange(2.0, cfg.episode_s, 7 * T + 6.0)],
                  -math.radians(ac.BANK_MAX_DEG), math.radians(ac.BANK_MAX_DEG))
        gam = Sum([Multistep3211(gam_a, T * 1.5, t0)
                   for t0 in np.arange(2.0 + 3.5 * T, cfg.episode_s, 7 * T + 6.0)],
                  math.radians(ac.GAMMA_MIN_DEG), math.radians(ac.GAMMA_MAX_DEG))
        mch = Constant(mach_c)
    return phi, gam, mch, regime


def run_episode(seed: int, cfg: Optional[CollectConfig] = None) -> dict:
    """Tek bolum topla. Donen: X, U, Xn dizileri + ustveri."""
    cfg = cfg or CollectConfig()
    rng = np.random.default_rng(seed)

    alt0, mach0, mach_band = _sample_operating_point(rng, cfg)
    sim = F16Sim(seed=seed)
    try:
        sim.reset(alt_ft=alt0, mach=mach0,
                  heading_deg=float(rng.uniform(0, 360)), trim=True,
                  fuel_frac=float(rng.uniform(cfg.fuel_lo, cfg.fuel_hi)))
    except Exception as e:
        return dict(ok=False, reason=f"reset:{type(e).__name__}", n=0)
    if not sim.trimmed:
        return dict(ok=False, reason="trim_failed", n=0)

    if rng.random() < cfg.turbulence_prob:
        sim.set_turbulence(wind_fps=float(rng.uniform(0, 60)),
                           wind_dir_deg=float(rng.uniform(0, 360)),
                           turb_severity=int(rng.integers(0, 4)))

    il = InnerLoop(dt=1.0 / cfg.ctrl_hz)
    il.reset(trim_throttle=sim["fcs/throttle-cmd-norm"])

    phi_s, gam_s, mch_s, regime = _build_excitation(rng, cfg, mach0, mach_band)

    sub = int(round(sim.fdm_hz / cfg.ctrl_hz))          # FDM adim / kontrol adim
    inner_per_outer = int(round(cfg.ctrl_hz / cfg.outer_hz))
    n_outer = int(cfg.episode_s * cfg.outer_hz)

    X = np.zeros((n_outer, X_DIM))
    U = np.zeros((n_outer, U_DIM))
    Xn = np.zeros((n_outer, X_DIM))

    st = sim.state()
    t = 0.0
    k = 0
    reason = "ok"
    for k in range(n_outer):
        # Dis dongu adiminin BASINDA komut ornekle ve adim boyunca SABIT tut
        # (zero-order hold). Model de tam bu varsayimla fit edilecek.
        cmd = InnerLoopCommand(phi_s(t), gam_s(t), mch_s(t)).clipped()
        X[k] = state_from_flight(st)
        U[k] = cmd_to_u(cmd)

        for _ in range(inner_per_outer):
            el, ail, thr, rud = il.update(st, cmd)
            sim.send_fcs(el, ail, thr, rud)
            st = sim.run(sub)
            t += 1.0 / cfg.ctrl_hz

        Xn[k] = state_from_flight(st)

        # Guvenlik durdurma
        if not np.all(np.isfinite(Xn[k])):
            reason = "nan"; break
        if st.alt_ft < cfg.abort_alt_ft:
            reason = "low_alt"; break
        if st.mach < cfg.abort_mach_lo:
            reason = "low_mach"; break
        if abs(math.degrees(st.alpha_rad)) > cfg.abort_alpha_deg:
            reason = "alpha"; break

    n = k + 1 if reason != "ok" else n_outer
    n = max(n - 1, 0)      # durdurmaya sebep olan son gecisi atma
    return dict(ok=n > 0, reason=reason, n=n, regime=regime,
                alt0=alt0, mach0=mach0,
                X=X[:n], U=U[:n], Xn=Xn[:n])


def _worker(args):
    seed, cfg_dict = args
    return run_episode(seed, CollectConfig(**cfg_dict))


def collect(n_episodes: int, out_path: str, cfg: Optional[CollectConfig] = None,
            seed0: int = 0, n_workers: int = 1, verbose: bool = True) -> dict:
    """Bolumleri topla (istege bagli paralel) ve .npz olarak kaydet."""
    cfg = cfg or CollectConfig()
    cfg_dict = asdict(cfg)
    jobs = [(seed0 + i, cfg_dict) for i in range(n_episodes)]

    results = []
    if n_workers > 1:
        import multiprocessing as mp
        with mp.Pool(n_workers) as pool:
            for i, r in enumerate(pool.imap_unordered(_worker, jobs)):
                results.append(r)
                if verbose and (i + 1) % max(1, n_episodes // 20) == 0:
                    print(f"  {i+1}/{n_episodes} bolum", flush=True)
    else:
        for i, j in enumerate(jobs):
            results.append(_worker(j))
            if verbose and (i + 1) % max(1, n_episodes // 20) == 0:
                print(f"  {i+1}/{n_episodes} bolum", flush=True)

    good = [r for r in results if r["ok"]]
    if not good:
        raise RuntimeError("Hicbir bolum veri uretmedi")

    X = np.concatenate([r["X"] for r in good])
    U = np.concatenate([r["U"] for r in good])
    Xn = np.concatenate([r["Xn"] for r in good])
    ep_id = np.concatenate([np.full(r["n"], i) for i, r in enumerate(good)])

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    np.savez_compressed(out_path, X=X, U=U, Xn=Xn, ep_id=ep_id,
                        dt=1.0 / cfg.outer_hz,
                        regimes=np.array([r["regime"] for r in good]),
                        alt0=np.array([r["alt0"] for r in good]),
                        mach0=np.array([r["mach0"] for r in good]))

    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    return dict(path=out_path, n_transitions=len(X), n_episodes=len(good),
                reasons=reasons, X=X, U=U, Xn=Xn)
