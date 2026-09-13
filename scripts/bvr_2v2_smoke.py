"""
Faz 1.5e duman testi: 2v2 angajman -- DORT GuidanceDriver (2 mavi + 2
kirmizi), dort radar, coklu fuze, TEK Engagement muhasebesi, Tacview kaydi.

1v1'den (bvr_1v1_smoke.py) FARK: her ucagin artik BIRDEN FAZLA olasi
dusmani var. Bu betik iki yeni karar noktasi ekliyor (1v1'de yoktu):
  1. HEDEF SECIMI: her tikte, her ucak KENDI takimindaki digerinden
     BAGIMSIZ olarak en yakin CANLI dusmani secer (nearest_alive_enemy).
     Guidance/pick_target mantigi (TAC-08, --crank-deg kirma) DEGISMEDI --
     sadece "dusman" artik sabit degil, tikten tike degisebilir.

NEDEN --crank-deg VARSAYILANI 35 (1v1_smoke.py ile AYNI gerekce): ilk
surumde 90 derece (tam beam) sabitti ve 16/16 fuze "kor" (datalink kaybi)
oluyordu. Olculdu (REQUIREMENTS.md SIM2-07): 50 derecelik komut bile
gercek ATA'yi ~65 dereceye tasiyip radar gimbal sinirini (60 derece) asiyor
ve ATICI ucagin KENDI kilidini kirip fuzesini destesiz birakiyor. 35
derecede zincir uctan uca calisiyor (atis->pitbull->seeker->isabet).
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
import dataclasses

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import SAC

from bvr.envs.guidance_driver import GuidanceDriver
from bvr.envs import guidance_shared as gs
from bvr.combat.geometry import relative_geometry
from bvr.combat.radar import Radar
from bvr.combat.missile import MissileConfig
from bvr.combat.engagement import Engagement, Loadout, LaunchRules
from bvr.config import load_experiment
from bvr.sim.acmi import ACMIRecorder

NM_TO_FT = 6076.11549
DT = 0.1
DURATION_S = 180.0
CMD_RANGE_NM = 12.0     # TAC-08 (5-25 nmi) icinde, egitim dagilimina (3.3-14.8) yakin
CMD_MACH = 0.90
SEP_NM = 30.0           # iki takim arasi baslangic mesafesi (1v1 ile ayni)
WING_NM = 3.0           # kanat ucagi araligi (duvar formasyonu)
CRANK_DEG_DEFAULT = 35.0
MISSILE_MASS_LB = MissileConfig().mass_lb   # ENG'deki tek dogruluk kaynagi (335 lb)


def pick_target(own_north, own_east, enemy_north, enemy_east, enemy_alt, mode: str, crank_rad: float):
    """Basit betikli komutan: 'intercept' (dusmana don) ya da 'evade' (crank_rad kadar kir).
    1v1_smoke.py ile AYNI -- sadece 'dusman' artik sabit degil."""
    brg = math.atan2(enemy_east - own_east, enemy_north - own_north)
    if mode == "evade":
        brg += crank_rad
    tgt_n = own_north + CMD_RANGE_NM * NM_TO_FT * math.cos(brg)
    tgt_e = own_east + CMD_RANGE_NM * NM_TO_FT * math.sin(brg)
    return tgt_n, tgt_e, enemy_alt, CMD_MACH


class Aircraft:
    """1v1_smoke.py::Aircraft ile AYNI -- tek dusman degil, cagiran tarafin
    HER TIKTE sectigi dusmanin durumunu parametre olarak alir."""

    def __init__(self, name, cfg, model, alt_ft, mach, heading_deg, origin_n_ft, origin_e_ft):
        self.name = name
        self.model = model
        self.driver = GuidanceDriver(cfg=cfg, seed=abs(hash(name)) % 1000)
        self.origin_n_ft = origin_n_ft
        self.origin_e_ft = origin_e_ft
        self.radar = Radar()
        self.loadout = Loadout()
        # Tam muhimmatla trim -- bkz. bvr_1v1_smoke.py::Aircraft ve
        # GuidanceDriver.set_payload. reset()'TEN ONCE cagrilmali.
        self.driver.set_payload(self.loadout.amraam * MISSILE_MASS_LB)
        self.driver.reset(alt_ft=alt_ft, mach=mach, heading_deg=heading_deg, fuel_frac=0.75)

    @property
    def combat_state(self):
        st = self.driver.st
        return dataclasses.replace(st, north_ft=st.north_ft + self.origin_n_ft,
                                   east_ft=st.east_ft + self.origin_e_ft)

    def drop_missile(self):
        """Bir fuze atildiktan SONRA cagrilir -- kalan yuke gore JSBSim
        agirligini gunceller (yeniden trim GEREKMEZ)."""
        self.driver.set_payload(self.loadout.amraam * MISSILE_MASS_LB)

    def step(self, enemy_combat_state, mode: str, crank_rad: float):
        own = self.combat_state
        tgt_n, tgt_e, tgt_alt, tgt_mach = pick_target(
            own.north_ft, own.east_ft, enemy_combat_state.north_ft,
            enemy_combat_state.east_ft, enemy_combat_state.alt_ft, mode, crank_rad)
        obs = gs.build_obs(self.driver.st, tgt_n - self.origin_n_ft,
                           tgt_e - self.origin_e_ft, tgt_alt, tgt_mach,
                           self.driver.last_applied)
        action, _ = self.model.predict(obs, deterministic=True)
        return self.driver.tick(action)


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
    for name, team, hdg, on_ft, oe_ft in roster:
        aircraft[name] = Aircraft(name, cfg, model, alt_ft=25000, mach=0.9,
                                   heading_deg=hdg, origin_n_ft=on_ft, origin_e_ft=oe_ft)

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
                evading = any(m.target_id == name and m.missile.alive for m in eng.missiles)
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
