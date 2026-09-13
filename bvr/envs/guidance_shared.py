"""
GUIDANCE KATMANININ PAYLASILAN SAF MATEMATIGI

Bu dosya bvr/envs/guidance_env.py (RL egitimi) ile Faz 1.5'in
GuidanceDriver'i (canli/BVR kullanimi) arasinda TEK dogruluk kaynagidir.

NEDEN AYRI BIR MODUL: dondurulmuş guidance modeli (runs/reward_r3_both/
sac_1999968_steps.zip) bu formullerle uretilen gozlem vektorune gore
EGITILDI. Ayni formul iki yerde (egitim ortami + canli surucu) KOPYALANIRSA,
biri degisip digeri degismedigi an model, egitim aninda hic gormedigi bir
girdi formatiyla beslenir -- agirliklar ayni kalsa bile sozlesme sessizce
bozulur. Bkz. HANDOFF.md ilke #2 ("katmanlari asagidan yukari dondur").

Bu modul saf fonksiyonlardan olusur: hicbir sinif durumu (self) tutmaz,
sadece verilen degerlerden hesaplar. guidance_env.GuidanceEnv bu
fonksiyonlari kendi metodlarindan (ayni imzalarla, sadece self.* degerlerini
gecirerek) cagirir -- boylece mevcut cagri yerleri hic degismez.
"""
from __future__ import annotations

import math

import numpy as np

from ..sim import aircraft as ac
from ..control.inner_loop import InnerLoopCommand


def bearing_error(tgt_n: float, tgt_e: float, north_ft: float, east_ft: float, psi_rad: float) -> float:
    """Hedefe olan kerteriz ile mevcut yon (psi) arasindaki fark, [-pi, +pi]."""
    brg = math.atan2(tgt_e - east_ft, tgt_n - north_ft)
    e = brg - psi_rad
    return (e + math.pi) % (2 * math.pi) - math.pi


def range_to_target(tgt_n: float, tgt_e: float, north_ft: float, east_ft: float) -> float:
    """Hedefe yatay menzil (ft)."""
    return math.hypot(tgt_n - north_ft, tgt_e - east_ft)


def action_to_cmd(a: np.ndarray, mach_lo: float, mach_hi: float) -> InnerLoopCommand:
    """[-1,1]^3 -> fiziksel komut. Aralikllar aircraft.py'deki zarftan gelir."""
    a = np.clip(np.asarray(a, dtype=np.float64), -1.0, 1.0)
    phi = a[0] * math.radians(ac.BANK_MAX_DEG)
    gam = a[1] * math.radians(ac.GAMMA_MAX_DEG)
    mach = mach_lo + 0.5 * (a[2] + 1.0) * (mach_hi - mach_lo)
    return InnerLoopCommand(phi, gam, mach)


def cmd_to_action(cmd: InnerLoopCommand, mach_lo: float, mach_hi: float) -> np.ndarray:
    """action_to_cmd'in tersi. Kalkandan cikan komutu gozleme koymak icin."""
    span = max(mach_hi - mach_lo, 1e-9)
    return np.clip(np.array([
        cmd.phi_cmd_rad / math.radians(ac.BANK_MAX_DEG),
        cmd.gamma_cmd_rad / math.radians(ac.GAMMA_MAX_DEG),
        2.0 * (cmd.mach_cmd - mach_lo) / span - 1.0,
    ]), -1.0, 1.0)


def build_obs(st, tgt_n: float, tgt_e: float, tgt_alt: float, tgt_mach: float,
              last_applied: np.ndarray) -> np.ndarray:
    """19 boyutlu gozlem vektoru. Alan sirasi/olcekleri EGITIM ANINDAKIYLA
    birebir ayni olmak ZORUNDADIR -- degistirme, sadece bu dosyadan oku."""
    be = bearing_error(tgt_n, tgt_e, st.north_ft, st.east_ft, st.psi_rad)
    rng_ft = range_to_target(tgt_n, tgt_e, st.north_ft, st.east_ft)
    o = np.array([
        math.sin(be), math.cos(be),
        min(rng_ft / 50000.0, 3.0),
        (tgt_alt - st.alt_ft) / 5000.0,
        (tgt_mach - st.mach) / 0.30,
        st.phi_rad,
        st.gamma_rad / 0.40,
        st.alpha_rad / 0.20,
        st.beta_rad / 0.10,
        (-st.nz - 1.0) / 3.0,
        st.p_rads / 1.50,
        st.q_rads / 0.40,
        (st.mach - 0.90) / 0.40,
        (st.alt_ft - 25000.0) / 12000.0,
        st.h_dot_fps / 300.0,
        last_applied[0], last_applied[1], last_applied[2],
        (st.fuel_frac - 0.65) / 0.35,
    ], dtype=np.float32)
    return np.nan_to_num(o, nan=0.0, posinf=5.0, neginf=-5.0)
