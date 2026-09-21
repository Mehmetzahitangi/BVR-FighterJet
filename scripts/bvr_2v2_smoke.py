"""
Faz 1.5e duman testi: 2v2 angajman -- DORT GuidanceDriver (2 mavi + 2
kirmizi), dort radar, coklu fuze, TEK Engagement muhasebesi, Tacview kaydi.

1v1'den (bvr_1v1_smoke.py) FARK: her ucagin artik BIRDEN FAZLA olasi
dusmani var. Bu betik iki yeni karar noktasi ekliyor (1v1'de yoktu):
  1. HEDEF SECIMI: her tikte, her ucak KENDI takimindaki digerinden
     BAGIMSIZ olarak en yakin CANLI dusmani secer (nearest_alive_enemy).
     Guidance/pick_target mantigi (TAC-08, --crank-deg kirma) DEGISMEDI --
     sadece "dusman" artik sabit degil, tikten tike degisebilir.

NEDEN --crank-deg VARSAYILANI 30 (1v1_smoke.py ile AYNI gerekce): ilk
surumde 90 derece (tam beam) sabitti ve 16/16 fuze "kor" (datalink kaybi)
oluyordu. `crank_sweep.py`'nin TAM taramasi crank'in SONSUZA KADAR degil
tehdit gecene kadar tutuldugunu ve |ATA|'nin menzil kapandikca BUYUMEYE
devam ettigini gosterdi -- dogru soru "hangi aci guvenli" degil "hangi aci
HANGI MENZILE kadar guvenli": 30 derece ~6 nmi'ye, 35 derece ~9 nmi'ye kadar
|ATA|<55 derecede kaliyor. 30 SEÇILDI cunku tam olcumde biraz daha genis
pay biraktigi ve karsilikli imha ile dogrulandigi icin, "sonsuza dek
asilmaz" oldugu icin DEGIL. Tarama ayrica saga/sola crank'in SIMETRIK
OLMADIGINI buldu (guidance'in be=0'daki dogal saga-yatik onyargisi, bkz.
SIM2-08); 30 derece daha kotu (sag) yone gore secildi. Faz 2.3'un davranis
agaci crank'i SABIT aciyla degil GERI BESLEMEYLE (|ATA| esigi asinca kis)
surmeli. Ayrinti: REQUIREMENTS.md SIM2-09.
  2. ATES DONGUSU: 1v1'de tek (shooter,target) cifti vardi; burada
     TAKIM ICI CARPRAZ tum (shooter,target) ciftleri (4 kombinasyon)
     her tikte ayri ayri can_fire ile kontrol edilir -- Engagement zaten
     N-ucakli/N-fuzeli tasarlandigi icin (bkz. engagement.py) BURADA
     hicbir degisiklik gerekmedi.

Radar (bvr/combat/radar.py) zaten "target_id sozlugu" ile CESITLI hedefi
ayni anda izleyecek sekilde tasarlanmisti (kendi docstring'i: "Ileride kol
ucusu 2v2 gibi senaryolar icin") -- bu betik o tasarimin ilk gercek testi.
Bilinen sadelestirme (degistirilmedi): Engagement.update() radari SADECE
dusmanlara degil, takim arkadasina karsi da calistirir (gercek bir radar
dost/dusman ayrimi -- IFF -- yapar, burada yapilmiyor); bu zararsiz çünkü
her hedef KENDI target_id'siyle ayri izleniyor, kilitlenme durumu
birbirine karismiyor -- sadece bosuna "izlenen" bir kontak var.

Kullanim:
    python -m scripts.bvr_2v2_smoke <model.zip> [--acmi <path>]
"""
from __future__ import annotations

import sys
import os
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import SAC

from bvr.combat.geometry import relative_geometry
from bvr.combat.missile import MissileConfig
from bvr.combat.engagement import Engagement, LaunchRules
from bvr.config import load_experiment
from bvr.sim.acmi import ACMIRecorder
# Faz 2.2: pick_target / Aircraft / sabitler artik TEK kaynaktan (duel.py)
# geliyor -- daha once burada birebir KOPYALARI vardi ve komutan/crank
# mantigi degisince 2v2 sessizce geride kalabilirdi (bkz. duel.py basligi,
# HANDOFF tuzak 47/51'in "iki kopya" dersi). 1v1'e ozgu run_duel()'u
# kullanmiyoruz (2 ucaga sabit) -- sadece paylasilan parcalari import ediyoruz.
from bvr.combat.duel import (
    Aircraft, pick_target, NM_TO_FT, DT, DURATION_S, CRANK_DEG_DEFAULT,
)

SEP_NM = 30.0           # iki takim arasi baslangic mesafesi (1v1 ile ayni)
WING_NM = 3.0           # kanat ucagi araligi (duvar formasyonu)


def nearest_alive_enemy(name, team_of, states, eng):
    """`name`'in takiminda OLMAYAN, HALA CANLI ucaklar arasindan menzilce
    en yakinini dondurur -- yoksa None (takim tamamen imha edilmis demektir,
    bu betikte dongu bundan once zaten sonlanir, ama savunmaci kontrol)."""
    own_team = team_of[name]
    candidates = [n for n in states if team_of[n] != own_team and eng.aircraft[n].alive]
    if not candidates:
        return None
    return min(candidates, key=lambda n: relative_geometry(states[name], states[n]).range_nm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--duration", type=float, default=DURATION_S)
    ap.add_argument("--acmi", type=str, default=None,
                     help="Tacview ACMI kayit yolu (verilmezse kayit yapilmaz)")
    ap.add_argument("--crank-deg", type=float, default=CRANK_DEG_DEFAULT,
                     help="Kacis (evade) kirma acisi -- bkz. dosya basligindaki SIM2-07 notu")
    ap.add_argument("--warning", choices=("truth", "rwr"), default="rwr",
                     help="'truth' = kacis karari gercek fuze listesinden (eski, "
                          "omniscient davranis, sadece REGRESYON referansi icin kalir); "
                          "'rwr' = RWR modelinden (gercekci, varsayilan). bvr_1v1_smoke.py "
                          "ile AYNI bayrak/gerekce.")
    args = ap.parse_args()
    crank_rad = math.radians(args.crank_deg)

    rd = os.path.dirname(args.model)
    cfg = load_experiment(f"{rd}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    model = SAC.load(args.model, device="cpu")

    # Roster: (isim, takim, baslangic yonelimi, kuzey ofseti, dogu ofseti)
    roster = [
        ("blue1", "blue", 0.0, 0.0, 0.0),
        ("blue2", "blue", 0.0, 0.0, WING_NM * NM_TO_FT),
        ("red1", "red", 180.0, SEP_NM * NM_TO_FT, 0.0),
        ("red2", "red", 180.0, SEP_NM * NM_TO_FT, WING_NM * NM_TO_FT),
    ]
    team_of = {name: team for name, team, *_ in roster}
    aircraft: dict[str, Aircraft] = {}
    for i, (name, team, hdg, on_ft, oe_ft) in enumerate(roster):
        # seed acikca veriliyor (eskiden hash(name)%1000 -- surecler arasi
        # rastgele, "tekrar uretilebilir" iddiasi kagit ustundeydi).
        aircraft[name] = Aircraft(name, cfg, model, alt_ft=25000, mach=0.9,
                                   heading_deg=hdg, origin_n_ft=on_ft, origin_e_ft=oe_ft,
                                   seed=i)

    eng = Engagement(rules=LaunchRules(), missile_cfg=MissileConfig())
    for name in team_of:
        ac = aircraft[name]
        eng.add_aircraft(name, ac.combat_state, ac.radar, ac.loadout)

    obj_id_of = {"blue1": 1, "blue2": 2, "red1": 3, "red2": 4}
    callsign_of = {"blue1": "Blue1", "blue2": "Blue2", "red1": "Red1", "red2": "Red2"}
    color_of_team = {"blue": "Blue", "red": "Red"}

    rec = ACMIRecorder(args.acmi, ref_lat=39.0, ref_lon=32.8,
                        title="BVR 2v2 angajman") if args.acmi else None
    if rec is not None:
        rec.open()
    missile_obj_ids: dict[str, int] = {}
    next_missile_obj_id = 100

    n_steps = int(args.duration / DT)
    fired = {name: 0 for name in team_of}
    crashed = False

    try:
        for k in range(n_steps):
            t = k * DT
            pre_states = {name: aircraft[name].combat_state for name in team_of}

            for name in team_of:
                enemy_name = nearest_alive_enemy(name, team_of, pre_states, eng)
                if enemy_name is None:
                    continue  # takim tamamen imha edildi -- asagida zaten donguden cikilacak
                if args.warning == "truth":
                    # ESKI (omniscient) davranis -- SADECE regresyon referansi
                    # icin, bkz. bvr_1v1_smoke.py'deki AYNI gerekce.
                    evading = any(m.target_id == name and m.missile.alive for m in eng.missiles)
                else:
                    worst = eng.aircraft[name].rwr.get_worst_threat()
                    evading = worst is not None and worst.kind in ("kilit", "fuze")
                aircraft[name].step(pre_states[enemy_name],
                                     "evade" if evading else "intercept", crank_rad)

            post_states = {name: aircraft[name].combat_state for name in team_of}

            crashed = False
            for name, st in post_states.items():
                if not (math.isfinite(st.alt_ft) and math.isfinite(st.north_ft)
                        and math.isfinite(st.mach)):
                    print(f"t={t:.1f}s: {name} durumunda NaN/sonsuz deger -- COKME")
                    crashed = True
            if crashed:
                break

            events = eng.update(DT, post_states)
            for ev in events:
                print(f"t={ev.t:.1f}s  {ev.kind:<10} {ev.actor} -> {ev.target}  {ev.detail}")

            for shooter in team_of:
                if not eng.aircraft[shooter].alive:
                    continue
                for target in team_of:
                    if team_of[target] == team_of[shooter] or not eng.aircraft[target].alive:
                        continue
                    can, reason = eng.can_fire(shooter, target)
                    if can:
                        eng.fire(shooter, target)
                        fired[shooter] += 1
                        aircraft[shooter].drop_missile()
                        rng = relative_geometry(eng.aircraft[shooter].state,
                                                 eng.aircraft[target].state).range_nm
                        print(f"t={t:.1f}s  ATES      {shooter} -> {target} (menzil {rng:.1f} nmi)")

            if rec is not None:
                rec_t = next(iter(post_states.values())).t
                for name, st in post_states.items():
                    rec.record(st, obj_id=obj_id_of[name], name="F-16C",
                               color=color_of_team[team_of[name]], callsign=callsign_of[name])

                alive_ids = set()
                for m in eng.missiles:
                    if not m.missile.alive:
                        continue
                    alive_ids.add(m.id)
                    if m.id not in missile_obj_ids:
                        missile_obj_ids[m.id] = next_missile_obj_id
                        next_missile_obj_id += 1
                    color = color_of_team[team_of[m.shooter_id]]
                    rec.record_missile(rec_t, m.missile.pos, m.missile.vel,
                                        missile_obj_ids[m.id], color=color)

                for msl_id in list(missile_obj_ids):
                    if msl_id not in alive_ids:
                        rec.remove_object(rec_t, missile_obj_ids.pop(msl_id))

            blue_alive = any(eng.aircraft[n].alive for n in team_of if team_of[n] == "blue")
            red_alive = any(eng.aircraft[n].alive for n in team_of if team_of[n] == "red")
            if not blue_alive or not red_alive:
                print(f"t={t:.1f}s: bir takim tamamen imha oldu, angajman bitti.")
                break
    finally:
        if rec is not None:
            rec.close()

    print(f"\n{'COKTU' if crashed else 'TAMAMLANDI'} -- "
          f"toplam {len(eng.events)} olay.")
    for name in team_of:
        print(f"  {name} ({team_of[name]}): {fired[name]} atis, "
              f"muhimmat kalan {eng.aircraft[name].loadout.amraam}, "
              f"alive={eng.aircraft[name].alive}")


if __name__ == "__main__":
    main()
