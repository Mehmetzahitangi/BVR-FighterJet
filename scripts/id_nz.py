"""
ADIM 1b: Nz (g yuku) isaret/ofset konvansiyonunu ve yatis telafisini olc.

NEDEN:
Pitch dongusunu g uzerinden kapatacagiz. Bunun icin "duz ucusta olcum kac?"
ve "isaret hangi yonde?" sorularinin kesin cevabi lazim. JSBSim'de
accelerations/n-pilot-z-norm govde z ekseninde olculur ve isaret sezgisel
degildir; tahminle degil olcumle sabitliyoruz.

Ayrica YATIS TELAFISINI dogruluyoruz: phi bankinda duz ucus icin gereken
yuk n = 1/cos(phi). 60 derece bank -> 2.0 g. Bu, koordineli donuste irtifa
kaybetmemenin anahtaridir ve gamma dongusune ileri-besleme olarak girer.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from bvr.sim.jsbsim_bridge import F16Sim


def probe(alt_ft=20000.0, mach=0.8):
    sim = F16Sim()
    sim.reset(alt_ft=alt_ft, mach=mach, trim=True)
    thr = sim["fcs/throttle-cmd-norm"]
    for _ in range(int(2 * sim.fdm_hz)):
        sim.send_fcs(0.0, 0.0, thr)
        st = sim.run(1)
    return sim, thr, st


if __name__ == "__main__":
    sim, thr, st = probe()
    print("--- DUZ TRIMLI UCUS ---")
    print(f"  n-pilot-z-norm      = {st.nz:+.4f}")
    print(f"  theta               = {np.degrees(st.theta_rad):+.2f} deg")
    print(f"  gamma               = {np.degrees(st.gamma_rad):+.2f} deg")
    print(f"  alpha               = {np.degrees(st.alpha_rad):+.2f} deg")
    print(f"  fcs/g-load-corrected= {sim['fcs/g-load-corrected']:+.4f}")
    print(f"  fcs/pitch-trim      = {sim['fcs/pitch-trim-cmd-norm']:+.4f}")
    print()
    print("YORUM: n_eff = -n-pilot-z-norm alirsak duz ucusta ~+1.0 g bekleriz.")
    print(f"  n_eff = {-st.nz:+.4f}")

    # --- Elevator komutu -> kalici Nz egrisi (lineerlik ve kazanc) ---
    print()
    print("--- elevator-cmd -> kalici n_eff (20 kft / M0.8) ---")
    print(f"{'cmd':>7} {'n_eff':>8} {'d_n':>8} {'dn/dcmd':>9}")
    n_level = None
    for cmd in (0.3, 0.15, 0.0, -0.1, -0.2, -0.35, -0.5, -0.75, -1.0):
        s2, t2, _ = probe()
        vals = []
        for k in range(int(3.0 * s2.fdm_hz)):
            s2.send_fcs(cmd, 0.0, t2)
            stt = s2.run(1)
            if k > int(1.8 * s2.fdm_hz):
                vals.append(-stt.nz)
        n_eff = float(np.mean(vals))
        if cmd == 0.0:
            n_level = n_eff
        dn = n_eff - (n_level if n_level is not None else 1.0)
        slope = dn / (-cmd) if abs(cmd) > 1e-6 else float("nan")
        print(f"{cmd:7.2f} {n_eff:8.3f} {dn:8.3f} {slope:9.2f}")

    # --- Yatis telafisi dogrulamasi: n = 1/cos(phi) ---
    print()
    print("--- YATIS TELAFISI: phi bankinda duz ucus icin gereken n ---")
    print(f"{'phi':>5} {'1/cos(phi)':>11} {'olculen n_eff':>14} {'dAlt/10s ft':>12}")
    for phi_t in (0.0, 30.0, 45.0, 60.0):
        s3 = F16Sim()
        s3.reset(alt_ft=20000.0, mach=0.8, trim=True)
        t3 = s3["fcs/throttle-cmd-norm"]
        # 1) Istenen bank acisina P kontrolu ile yatir
        for _ in range(int(6 * s3.fdm_hz)):
            stt = s3.state()
            phi_err = np.radians(phi_t) - stt.phi_rad
            p_cmd_degs = np.clip(np.degrees(phi_err) * 2.0, -90, 90)
            s3.send_fcs(0.0, p_cmd_degs / 180.0, t3)
            s3.run(1)
        # 2) Bank sabit tutulurken n = 1/cos(phi) ileri-beslemesi ile duz ucus
        alt0 = s3.state().alt_ft
        ns = []
        for _ in range(int(10 * s3.fdm_hz)):
            stt = s3.state()
            phi_err = np.radians(phi_t) - stt.phi_rad
            p_cmd_degs = np.clip(np.degrees(phi_err) * 2.0, -90, 90)
            # gamma=0 tutmak icin basit oransal g komutu (dogrulama amacli)
            n_req = 1.0 / max(0.2, np.cos(stt.phi_rad))
            n_now = -stt.nz
            el = -(n_req - n_now) * 0.12 - np.degrees(stt.gamma_rad) * 0.02
            s3.send_fcs(np.clip(el, -1, 0.44), p_cmd_degs / 180.0, t3)
            s3.run(1)
            ns.append(-s3.state().nz)
        alt1 = s3.state().alt_ft
        print(f"{phi_t:5.0f} {1/np.cos(np.radians(phi_t)):11.3f} "
              f"{np.mean(ns):14.3f} {alt1-alt0:12.0f}")
