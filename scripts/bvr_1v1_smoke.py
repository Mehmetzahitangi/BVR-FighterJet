"""
Faz 1.5c duman testi: TAM 1v1 angajman -- iki GuidanceDriver (dondurulmus
guidance), radar, fuze, Engagement muhasebesi birlikte, ilk kez uctan uca.

Faz 2.2'de asil angajman mantigi `bvr/combat/duel.py::run_duel()`'e
TASINDI -- bu betik artik sadece SABIT bir senaryo (30 nmi, burun buruna,
25 kft, M0.9) kurup onu cagiran ince bir kabuk. Neden ayri bir modul:
`scripts/eval_commander.py` (Faz 2.2) AYNI angajman dongusunu rastgele
uretilmis yuzlerce senaryoyla kosturuyor -- iki KOPYA yerine TEK
kaynak (crank_sweep.py'nin pick_target'i import etme gerekcesiyle ayni).

Basit betikli komutan: birbirine don (TAC-08: sanal hedef ~12 nmi), kilit
gelince ates et, dusmanin aktif bir fuzesi varsa --crank-deg kadar kir
(crank/beam, varsayilan 30 derece). Crank sabitinin NEDEN 30 oldugunun
tam gerekcesi: `bvr/combat/duel.py` basligi ve REQUIREMENTS.md SIM2-09.

Kullanim:
    python -m scripts.bvr_1v1_smoke <model.zip>
"""
from __future__ import annotations

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import SAC

from bvr.combat.duel import DuelScenario, run_duel, CRANK_DEG_DEFAULT, DURATION_S
from bvr.config import load_experiment
from bvr.sim.acmi import ACMIRecorder

SEP_NM = 30.0  # bkz. eski dosya basligi -- sabit duman testi senaryosu


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--duration", type=float, default=DURATION_S)
    ap.add_argument("--acmi", type=str, default=None,
                     help="Tacview ACMI kayit yolu (verilmezse kayit yapilmaz)")
    ap.add_argument("--crank-deg", type=float, default=CRANK_DEG_DEFAULT,
                     help="Kacis (evade) kirma acisi -- bkz. REQUIREMENTS.md SIM2-09")
    ap.add_argument("--warning", choices=("truth", "rwr"), default="rwr",
                     help="'truth' = kacis karari gercek fuze listesinden (eski, "
                          "omniscient davranis, sadece REGRESYON referansi icin kalir); "
                          "'rwr' = RWR modelinden (gercekci, varsayilan).")
    ap.add_argument("--seed", type=int, default=0,
                     help="Sabit senaryonun JSBSim tohumu (tekrar uretilebilirlik icin)")
    args = ap.parse_args()

    rd = os.path.dirname(args.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 1e9  # kullanilmiyor -- run_duel kendi dongusunu yonetiyor
    model = SAC.load(args.model, device="cpu")

    scenario = DuelScenario(
        seed=args.seed, separation_nm=SEP_NM, aspect_deg=0.0, lateral_offset_nm=0.0,
        alt_blue_ft=25000.0, alt_red_ft=25000.0, mach_blue=0.9, mach_red=0.9,
        fuel_blue=0.75, fuel_red=0.75,
        turb_blue_fps=0.0, turb_red_fps=0.0, turb_blue_dir_deg=0.0, turb_red_dir_deg=0.0,
    )

    rec = ACMIRecorder(args.acmi, ref_lat=39.0, ref_lon=32.8,
                        title="BVR 1v1 angajman") if args.acmi else None
    if rec is not None:
        rec.open()
    try:
        result = run_duel(cfg, model, scenario, warning_mode=args.warning,
                           crank_deg=args.crank_deg, duration_s=args.duration,
                           acmi_recorder=rec, verbose=True)
    finally:
        if rec is not None:
            rec.close()

    print(f"\nSONUC: {result.outcome} -- blue {result.blue_fired} atis "
          f"({result.blue_hits} isabet), red {result.red_fired} atis ({result.red_hits} isabet)")
    print(f"blue alive={result.blue_alive}  red alive={result.red_alive}  "
          f"sure={result.duration_s:.1f}s  gercek_sure={result.wall_time_s:.2f}s")
    print(f"kor={result.kor_count} hedefsiz={result.hedefsiz_count} "
          f"iska={result.iska_count} tukenme={result.tukenme_count}  "
          f"en_yakin={result.closest_approach_nm:.1f} nmi  "
          f"nz_min(blue/red)={result.nz_min_blue:.2f}/{result.nz_min_red:.2f}  nz_max={result.nz_max_blue:.2f}/{result.nz_max_red:.2f}")


if __name__ == "__main__":
    main()
