"""
Faz 1.5a duman testi: iki F16Sim ornegi yan yana.

Soru: JSBSim ornekleri arasinda paylasilan (sizan) durum var mi? Turbulans ve
nokta kutlenin bir ORNEK ICINDE reset() arasinda kalici oldugu biliniyor
(HANDOFF tuzak 2, 37) -- ama iki AYRI F16Sim nesnesi arasinda sizinti olup
olmadigi hic sinanmadi.

Yontem: iki F16Sim, ikisi de ayni kosulda (20 kft, M0.8, duz) trim edilir,
60 s duz ucus (phi=0, gamma=0, mach=trim mach) icin InnerLoop ile surulur.
Ikisinin de irtifa sapmasi olculur ve karsilastirilir.

Kullanim:
    python -m scripts.two_jsbsim_smoke
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bvr.sim.jsbsim_bridge import F16Sim
from bvr.control.inner_loop import InnerLoop, InnerLoopCommand

CTRL_HZ = 60.0
DURATION_S = 60.0


def fly_level(sim: F16Sim, label: str) -> dict:
    st = sim.reset(alt_ft=20000.0, mach=0.8, heading_deg=0.0, trim=True)
    if not sim.trimmed:
        raise RuntimeError(f"{label}: trim basarisiz")

    inner = InnerLoop(dt=1.0 / CTRL_HZ)
    inner.reset(trim_throttle=sim["fcs/throttle-cmd-norm"])

    alt0 = st.alt_ft
    mach0 = st.mach
    cmd = InnerLoopCommand(phi_cmd_rad=0.0, gamma_cmd_rad=0.0, mach_cmd=mach0)

    n_steps = int(DURATION_S * CTRL_HZ)
    alt_min, alt_max = alt0, alt0
    for _ in range(n_steps):
        el, ail, thr, rud = inner.update(st, cmd)
        sim.send_fcs(el, ail, thr, rud)
        st = sim.run(1)
        alt_min = min(alt_min, st.alt_ft)
        alt_max = max(alt_max, st.alt_ft)

    return {
        "label": label,
        "alt0": alt0,
        "alt_final": st.alt_ft,
        "drift_final_ft": st.alt_ft - alt0,
        "drift_peak_ft": max(abs(alt_max - alt0), abs(alt_min - alt0)),
        "mach_final": st.mach,
        "t_final": st.t,
    }


if __name__ == "__main__":
    sim_a = F16Sim(seed=1)
    sim_b = F16Sim(seed=2)

    # Once A'yi tek basina uc (referans), sonra B'yi A'nin fdm'i "kirletmis"
    # olabilecegi bir durumda uc -- eger sizinti varsa B'nin sonucu A'dan
    # (veya B'nin kendi tek-basina sonucundan) farkli cikar.
    result_a = fly_level(sim_a, "A (tek basina)")
    result_b = fly_level(sim_b, "B (A'dan SONRA, A hala bellekte acikken)")

    print(f"{'ornek':<32} | {'alt0':>10} | {'final':>10} | {'sapma(final)':>13} | {'sapma(tepe)':>12} | {'mach':>6}")
    for r in (result_a, result_b):
        print(f"{r['label']:<32} | {r['alt0']:>10.1f} | {r['alt_final']:>10.1f} | "
              f"{r['drift_final_ft']:>13.2f} | {r['drift_peak_ft']:>12.2f} | {r['mach_final']:>6.4f}")

    diff = abs(result_a["drift_final_ft"] - result_b["drift_final_ft"])
    print(f"\nA ve B final-sapma farki: {diff:.2f} ft")
    print("(Sizinti YOKSA bu fark, ayni sim'in iki farkli tohumla uretecegi")
    print(" normal koşu-farkindan buyuk olmamali -- yani kucuk ve rastgele.)")
