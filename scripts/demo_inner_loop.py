"""
IC DONGU GORSEL DOGRULAMASI -> Tacview (.acmi) + izleme grafigi (.png)

Senaryolu bir gorev ucar ve her kanali sirayla zorlar:
  1. duz ucus            (taban cizgisi)
  2. tirmanis            gamma = +10 deg
  3. seviyeye donus      gamma = 0
  4. sol koordineli donus phi = -60 deg  (yatis telafisi sinavi)
  5. kanatlar duz
  6. hizlanma            mach +0.30
  7. BILESIK manevra     alcalma -10 deg + sag 45 deg bank ayni anda
  8. toparlanma          duz ucus, baslangic Mach

Cikti:
  runs/demo_inner_loop.acmi  -> Tacview ile ac
  runs/demo_inner_loop.png   -> komut/gerceklesen izleme grafikleri
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bvr.sim.jsbsim_bridge import F16Sim
from bvr.sim.acmi import ACMIRecorder
from bvr.control.inner_loop import InnerLoop, InnerLoopCommand

CTRL_HZ = 60.0
ACMI_HZ = 20.0
ALT0, MACH0 = 25000.0, 0.80

# (bitis_zamani, phi_deg, gamma_deg, mach, etiket)
SCRIPT = [
    (15.0,   0.0,   0.0, MACH0,        "duz ucus"),
    (45.0,   0.0, +10.0, MACH0,        "tirmanis +10"),
    (60.0,   0.0,   0.0, MACH0,        "seviyeye don"),
    (90.0, -60.0,   0.0, MACH0,        "sol 60 bank"),
    (105.0,  0.0,   0.0, MACH0,        "kanatlar duz"),
    (140.0,  0.0,   0.0, MACH0 + 0.30, "hizlanma +0.30M"),
    (175.0, +45.0, -10.0, MACH0 + 0.30, "BILESIK: alcalma + sag bank"),
    (205.0,  0.0,   0.0, MACH0,        "toparlanma"),
]


def command_at(t):
    for t_end, phi, gam, mach, label in SCRIPT:
        if t < t_end:
            return InnerLoopCommand(np.radians(phi), np.radians(gam), mach), label
    last = SCRIPT[-1]
    return InnerLoopCommand(np.radians(last[1]), np.radians(last[2]), last[3]), last[4]


def main():
    os.makedirs("runs", exist_ok=True)
    acmi_path = os.path.join("runs", "demo_inner_loop.acmi")
    png_path = os.path.join("runs", "demo_inner_loop.png")

    sim = F16Sim()
    sim.reset(alt_ft=ALT0, mach=MACH0, heading_deg=0.0, trim=True)
    if not sim.trimmed:
        raise RuntimeError("Trim basarisiz")

    il = InnerLoop(dt=1.0 / CTRL_HZ)
    il.reset(trim_throttle=sim["fcs/throttle-cmd-norm"])

    sub = int(round(sim.fdm_hz / CTRL_HZ))
    acmi_every = int(round(CTRL_HZ / ACMI_HZ))
    t_end = SCRIPT[-1][0]
    n = int(t_end * CTRL_HZ)

    log = []
    st = sim.state()
    with ACMIRecorder(acmi_path, title="BVR F-16 ic dongu gorev dogrulamasi") as rec:
        for k in range(n):
            t = k / CTRL_HZ
            cmd, label = command_at(t)
            el, ail, thr, rud = il.update(st, cmd)
            sim.send_fcs(el, ail, thr, rud)
            st = sim.run(sub)

            if k % acmi_every == 0:
                rec.record(st, extra={
                    "PhiCmd": np.degrees(cmd.phi_cmd_rad),
                    "GammaCmd": np.degrees(cmd.gamma_cmd_rad),
                    "MachCmd": cmd.mach_cmd,
                    "Throttle": thr,
                })

            log.append((
                t, np.degrees(cmd.phi_cmd_rad), np.degrees(st.phi_rad),
                np.degrees(cmd.gamma_cmd_rad), np.degrees(st.gamma_rad),
                cmd.mach_cmd, st.mach, st.alt_ft,
                np.degrees(st.alpha_rad), np.degrees(st.beta_rad),
                -st.nz, el, ail, thr,
            ))

    L = np.array(log)
    t = L[:, 0]

    # ---- Ozet metrikler ----
    print(f"ACMI  : {acmi_path}")
    print(f"Sure  : {t[-1]:.0f} s   |   irtifa {L[0,7]:.0f} -> {L[-1,7]:.0f} ft")
    print()
    print("Kanal takip hatalari (komut degisim aninda ilk 3 s haric):")
    for name, ci, yi, unit in [("phi", 1, 2, "deg"), ("gamma", 3, 4, "deg"),
                               ("mach", 5, 6, "")]:
        err = L[:, yi] - L[:, ci]
        mask = np.ones_like(t, dtype=bool)
        for t_end_seg, *_ in SCRIPT:
            mask &= ~((t >= t_end_seg - 0.001) & (t < t_end_seg + 3.0))
        mask &= t > 3.0
        print(f"  {name:>6}: RMSE={np.sqrt((err[mask]**2).mean()):7.4f} {unit}"
              f"   |max|={np.abs(err[mask]).max():7.4f} {unit}")
    print()
    print(f"alpha max = {L[:,8].max():.2f} deg   (FLCS limiti 30)")
    print(f"|beta|max = {np.abs(L[:,9]).max():.2f} deg")
    print(f"n_eff araligi = [{L[:,10].min():.2f}, {L[:,10].max():.2f}] g")

    # ---- Grafik ----
    fig, ax = plt.subplots(5, 1, figsize=(12, 13), sharex=True)
    ax[0].plot(t, L[:, 1], "k--", lw=1.2, label="phi komut")
    ax[0].plot(t, L[:, 2], "b", lw=1.4, label="phi gercek")
    ax[0].set_ylabel("yatis [deg]"); ax[0].legend(loc="upper right"); ax[0].grid(alpha=.3)

    ax[1].plot(t, L[:, 3], "k--", lw=1.2, label="gamma komut")
    ax[1].plot(t, L[:, 4], "g", lw=1.4, label="gamma gercek")
    ax[1].set_ylabel("ucus yolu [deg]"); ax[1].legend(loc="upper right"); ax[1].grid(alpha=.3)

    ax[2].plot(t, L[:, 5], "k--", lw=1.2, label="Mach komut")
    ax[2].plot(t, L[:, 6], "r", lw=1.4, label="Mach gercek")
    ax[2].set_ylabel("Mach"); ax[2].legend(loc="upper right"); ax[2].grid(alpha=.3)

    ax[3].plot(t, L[:, 7], "m", lw=1.4)
    ax[3].set_ylabel("irtifa [ft]"); ax[3].grid(alpha=.3)

    ax[4].plot(t, L[:, 8], label="alpha [deg]")
    ax[4].plot(t, L[:, 9], label="beta [deg]")
    ax[4].plot(t, L[:, 10], label="n_eff [g]")
    ax[4].plot(t, L[:, 13], label="throttle")
    ax[4].set_ylabel("ic degiskenler"); ax[4].set_xlabel("zaman [s]")
    ax[4].legend(loc="upper right", ncol=4); ax[4].grid(alpha=.3)

    for a in ax:
        for t_end_seg, _, _, _, label in SCRIPT[:-1]:
            a.axvline(t_end_seg, color="gray", lw=0.6, alpha=0.5)
    for t_start, (t_end_seg, _, _, _, label) in zip(
            [0.0] + [s[0] for s in SCRIPT[:-1]], SCRIPT):
        ax[0].text((t_start + t_end_seg) / 2, ax[0].get_ylim()[1] * 0.92, label,
                   ha="center", fontsize=7, color="dimgray")

    fig.suptitle("Ic dongu gorev dogrulamasi - komut (siyah kesikli) vs gerceklesen",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    print(f"\nGrafik: {png_path}")


if __name__ == "__main__":
    main()
