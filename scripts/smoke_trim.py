"""
ADIM 0 DOGRULAMA: trim calisiyor mu, ucak elleri birakinca duz uctuyor mu?

Neden bu test ilk sirada:
Kontrolcu yazmadan once "hicbir sey yapmazsan ne oluyor" taban cizgisini
bilmek zorundayiz. Eger ucak trim sonrasi kendiliginden alcaliyor/salinyorsa,
sonradan yazacagimiz PID'in olctugu sey kontrolcu performansi degil, bu
gecici davranis olur.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bvr.sim.jsbsim_bridge import F16Sim
from bvr.sim import aircraft as ac


def run_case(alt_ft, mach, trim, hold_sec=60.0):
    sim = F16Sim()
    s0 = sim.reset(alt_ft=alt_ft, mach=mach, trim=trim)

    # Trim rutininin BULDUGU kumanda degerlerini oku (bunlari koruyacagiz)
    el = sim["fcs/elevator-cmd-norm"]
    ail = sim["fcs/aileron-cmd-norm"]
    thr = sim["fcs/throttle-cmd-norm"]
    ptrim = sim["fcs/pitch-trim-cmd-norm"]

    n = int(hold_sec * sim.fdm_hz)
    alts, machs, thetas, qs = [], [], [], []
    for _ in range(n):
        sim.send_fcs(el, ail, thr)
        sim["fcs/pitch-trim-cmd-norm"] = ptrim
        st = sim.run(1)
        alts.append(st.alt_ft)
        machs.append(st.mach)
        thetas.append(np.degrees(st.theta_rad))
        qs.append(np.degrees(st.q_rads))

    alts = np.array(alts); machs = np.array(machs)
    thetas = np.array(thetas); qs = np.array(qs)
    return dict(
        alt0=alt_ft, mach0=mach, trim=trim, ok=sim.trimmed,
        cmd=(el, ail, thr, ptrim),
        alpha0_deg=np.degrees(s0.alpha_rad),
        d_alt=alts[-1] - alt_ft,
        d_mach=machs[-1] - mach,
        theta_mean=thetas.mean(), theta_std=thetas.std(),
        q_absmax=np.abs(qs).max(),
    )


if __name__ == "__main__":
    cases = [(15000, 0.6), (20000, 0.8), (30000, 0.9), (40000, 1.2)]
    print(f"{'alt':>6} {'M':>4} {'trim':>5} {'elev':>7} {'thr':>6} {'ptrim':>7} "
          f"{'a0deg':>6} {'dAlt60s':>8} {'dMach':>7} {'th_std':>7} {'|q|max':>7}")
    print("-" * 88)
    for alt, m in cases:
        for trim in (False, True):
            try:
                r = run_case(alt, m, trim)
                el, ail, thr, pt = r["cmd"]
                print(f"{alt:6d} {m:4.2f} {str(trim):>5} {el:7.3f} {thr:6.3f} {pt:7.3f} "
                      f"{r['alpha0_deg']:6.2f} {r['d_alt']:8.0f} {r['d_mach']:7.3f} "
                      f"{r['theta_std']:7.3f} {r['q_absmax']:7.2f}")
            except Exception as e:
                print(f"{alt:6d} {m:4.2f} {str(trim):>5}   HATA: {type(e).__name__}: {e}")
