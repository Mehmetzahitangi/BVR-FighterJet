"""
ADIM 1a: JSBSim F-16 FLCS'inin GERCEK basamak yanitini olc.

NEDEN:
Ic dongu kazanclarini tahminle secmek yerine, once alttaki sistemin ne
oldugunu olceriz. Klasik kontrol tasariminin ilk adimi budur: "tesisi tani"
(plant identification). Olcecegimiz uc sey:

  1. ROLL : aileron-cmd -> kalici yatis hizi p. Sozlesme cmd 1.0 <-> 180 deg/s
            olmali (f16.xml'den okuduk). Gercekten oyle mi? Zaman sabiti kac?
  2. PITCH: elevator-cmd -> kalici g yuku (Nz) ve gamma degisim hizi.
            Bu, gamma dongusunun kazancini belirler.
  3. THR  : throttle -> Mach degisim hizi. Art yakici esiginde (0.5) sicrama
            var mi?

Cikti: konsol tablosu. Bu tablo dogrudan inner_loop.py kazanclarini besler.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bvr.sim.jsbsim_bridge import F16Sim


def _prep(alt_ft, mach):
    sim = F16Sim()
    sim.reset(alt_ft=alt_ft, mach=mach, trim=True)
    trim_thr = sim["fcs/throttle-cmd-norm"]
    # Trim sonrasi 2 s yerlestir
    for _ in range(int(2 * sim.fdm_hz)):
        sim.send_fcs(0.0, 0.0, trim_thr)
        sim.run(1)
    return sim, trim_thr


def tau63(t, y, y_ss, y0):
    """%63 yukselme zamani = birinci mertebe zaman sabiti tahmini."""
    if abs(y_ss - y0) < 1e-9:
        return float("nan")
    target = y0 + 0.632 * (y_ss - y0)
    for i in range(len(y)):
        if (y_ss > y0 and y[i] >= target) or (y_ss < y0 and y[i] <= target):
            return t[i]
    return float("nan")


def roll_step(alt_ft, mach, cmd, dur=2.0):
    sim, thr = _prep(alt_ft, mach)
    n = int(dur * sim.fdm_hz)
    t, p, phi = [], [], []
    for k in range(n):
        sim.send_fcs(0.0, cmd, thr)
        st = sim.run(1)
        t.append(k / sim.fdm_hz)
        p.append(np.degrees(st.p_rads))
        phi.append(np.degrees(st.phi_rad))
    t, p = np.array(t), np.array(p)
    p_ss = p[int(0.7 * n):].mean()          # son %30'un ortalamasi
    return p_ss, tau63(t, p, p_ss, 0.0), phi[-1]


def pitch_step(alt_ft, mach, cmd, dur=3.0):
    sim, thr = _prep(alt_ft, mach)
    n = int(dur * sim.fdm_hz)
    t, nz, gam, q, alp = [], [], [], [], []
    for k in range(n):
        sim.send_fcs(cmd, 0.0, thr)
        st = sim.run(1)
        t.append(k / sim.fdm_hz)
        nz.append(st.nz)
        gam.append(np.degrees(st.gamma_rad))
        q.append(np.degrees(st.q_rads))
        alp.append(np.degrees(st.alpha_rad))
    t = np.array(t); nz = np.array(nz); gam = np.array(gam); q = np.array(q)
    seg = slice(int(0.6 * n), int(0.9 * n))
    nz_ss = nz[seg].mean()
    q_ss = q[seg].mean()
    gdot = np.gradient(gam, t)[seg].mean()   # gamma degisim hizi deg/s
    return nz_ss, q_ss, gdot, max(alp), tau63(t, nz, nz_ss, nz[0])


def throttle_step(alt_ft, mach, cmd, dur=15.0):
    sim, thr0 = _prep(alt_ft, mach)
    n = int(dur * sim.fdm_hz)
    t, m = [], []
    for k in range(n):
        sim.send_fcs(0.0, 0.0, cmd)
        st = sim.run(1)
        t.append(k / sim.fdm_hz)
        m.append(st.mach)
    t, m = np.array(t), np.array(m)
    mdot = np.gradient(m, t)[int(0.3 * n):].mean()   # kalici Mach ivmesi
    return thr0, mdot, m[-1] - m[0]


if __name__ == "__main__":
    COND = [(15000, 0.7), (30000, 0.9), (40000, 1.2)]

    print("=" * 78)
    print("1) ROLL EKSENI:  aileron-cmd -> kalici yatis hizi p")
    print("   Beklenti (f16.xml): cmd 1.0 <-> 180 deg/s")
    print("=" * 78)
    print(f"{'alt':>6} {'M':>4} {'cmd':>5} {'p_ss d/s':>9} {'tau63 s':>8} {'phi@2s':>7}")
    for alt, mch in COND:
        for c in (0.25, 0.5, 1.0):
            p_ss, tau, phi = roll_step(alt, mch, c)
            print(f"{alt:6d} {mch:4.2f} {c:5.2f} {p_ss:9.1f} {tau:8.3f} {phi:7.1f}")

    print()
    print("=" * 78)
    print("2) PITCH EKSENI: elevator-cmd -> kalici Nz, q ve gamma_dot")
    print("   Isaret: NEGATIF cmd = burun yukari = pozitif g")
    print("=" * 78)
    print(f"{'alt':>6} {'M':>4} {'cmd':>6} {'Nz_ss':>7} {'q d/s':>7} "
          f"{'gdot d/s':>9} {'a_max':>6} {'tau63':>7}")
    for alt, mch in COND:
        for c in (-0.1, -0.25, -0.5, 0.2):
            nz, q, gdot, amax, tau = pitch_step(alt, mch, c)
            print(f"{alt:6d} {mch:4.2f} {c:6.2f} {nz:7.2f} {q:7.2f} "
                  f"{gdot:9.2f} {amax:6.2f} {tau:7.3f}")

    print()
    print("=" * 78)
    print("3) THROTTLE:  kalici Mach ivmesi (art yakici esigi 0.5)")
    print("=" * 78)
    print(f"{'alt':>6} {'M':>4} {'thr_trim':>9} {'thr_cmd':>8} "
          f"{'dMach/dt':>10} {'dMach@15s':>10}")
    for alt, mch in COND:
        for c in (0.0, 0.35, 0.49, 0.55, 0.75, 1.0):
            t0, mdot, dm = throttle_step(alt, mch, c)
            print(f"{alt:6d} {mch:4.2f} {t0:9.3f} {c:8.2f} {mdot:10.5f} {dm:10.3f}")
