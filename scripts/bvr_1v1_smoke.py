"""
Faz 1.5c duman testi: TAM 1v1 angajman -- iki GuidanceDriver (dondurulmus
guidance), radar, fuze, Engagement muhasebesi birlikte, ilk kez uctan uca.

Basit betikli komutan: birbirine don (TAC-08: sanal hedef ~12 nmi), kilit
gelince ates et, dusmanin aktif bir fuzesi varsa --crank-deg kadar kir
(crank/beam, varsayilan 35 derece).

NEDEN 35 VE NEDEN PARAMETRE: ilk surumde bu 90 derece (tam beam) sabitti
ve TUM atislar "kor" (datalink kaybi) ile sonuclaniyordu. Olcum (bkz.
REQUIREMENTS.md SIM2-07) gosterdi ki 50 derecelik bir komut bile gercek
ATA'yi ~65 dereceye tasiyor (asim var) ve bu, radar gimbal sinirini
(60 derece, RadarConfig.gimbal_az_deg) asip ATICI ucagin KENDI kilidini
kirip fuzesini destesiz birakiyor. 35 derecede zincir ilk kez uctan uca
CALISIYOR: atis -> pitbull -> seeker -> isabet. Bu sayi FIZIKSEL SABIT
DEGIL, bir DENGE PARAMETRESI (crank ne kadar agresif olursa kacis o kadar
iyi ama kendi fuzeni o kadar cok riske atarsin) -- Faz 2'nin ogrenilmis
komutani bunu duruma gore ayarlayacak, betikli komutan sabit tutuyor.

Mimari not -- ORTAK COORDINAT CERCEVESI: her F16Sim kendi reset() anini
yerel (0,0) kabul eder (bkz. jsbsim_bridge.py::state(), origin_lat/lon
reset'te o anki konuma esitlenir). Iki ayri F16Sim'i ayni sahnede (ornegin
30 nmi ayri) baslatmak icin, her ucagin kendi north_ft/east_ft'ine bir
SABIT ofset eklenip PAYLASILAN bir cerceveye tasinmasi gerekir --
dataclasses.replace() ile FlightState'in bir kopyasi uretilip muhasebe/
radar/fuze katmanlarina O verilir; driver'in kendi ic durumu (ve JSBSim'in
gercek lat/lon'u) hic degismez, sadece "disariya sunulan" konum duzeltilir.

Kullanim:
    python -m scripts.bvr_1v1_smoke <model.zip>
"""
from __future__ import annotations

import sys
import os
import math
import argparse
import dataclasses

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
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
CRANK_DEG_DEFAULT = 35.0   # bkz. dosya basligindaki SIM2-07 notu
MISSILE_MASS_LB = MissileConfig().mass_lb   # ENG'deki tek dogruluk kaynagi (335 lb)


def pick_target(own_north, own_east, enemy_north, enemy_east, enemy_alt, mode: str, crank_rad: float):
    """Basit betikli komutan: 'intercept' (dusmana don) ya da 'evade' (crank_rad kadar kir)."""
    brg = math.atan2(enemy_east - own_east, enemy_north - own_north)
    if mode == "evade":
        brg += crank_rad
    tgt_n = own_north + CMD_RANGE_NM * NM_TO_FT * math.cos(brg)
    tgt_e = own_east + CMD_RANGE_NM * NM_TO_FT * math.sin(brg)
    return tgt_n, tgt_e, enemy_alt, CMD_MACH


class Aircraft:
    def __init__(self, name, cfg, model, alt_ft, mach, heading_deg, origin_n_ft, origin_e_ft):
        self.name = name
        self.model = model
        self.driver = GuidanceDriver(cfg=cfg, seed=abs(hash(name)) % 1000)
        self.origin_n_ft = origin_n_ft
        self.origin_e_ft = origin_e_ft
        self.radar = Radar()
        self.loadout = Loadout()
        # Tam muhimmatla trim -- gercek kalkis agirligi budur (payload_check.py
        # ile en agir konfigurasyonda (25.942 lb) GUI-11 sozlesmesinin hala
        # tuttugu olculmustu). reset()'TEN ONCE cagrilmali ki trim bunu hesaba
        # katsin. bkz. GuidanceDriver.set_payload.
        self.driver.set_payload(self.loadout.amraam * MISSILE_MASS_LB)
        self.driver.reset(alt_ft=alt_ft, mach=mach, heading_deg=heading_deg, fuel_frac=0.75)

    @property
    def combat_state(self):
        """Muhasebe/radar/fuze'nin gordugu, PAYLASILAN cercevedeki durum."""
        st = self.driver.st
        return dataclasses.replace(st, north_ft=st.north_ft + self.origin_n_ft,
                                   east_ft=st.east_ft + self.origin_e_ft)

    def drop_missile(self):
        """Bir fuze atildiktan SONRA cagrilir -- kalan yuke gore JSBSim
        agirligini gunceller (yeniden trim GEREKMEZ, bkz. set_payload)."""
        self.driver.set_payload(self.loadout.amraam * MISSILE_MASS_LB)

    def step(self, enemy_combat_state, mode: str, crank_rad: float):
        own = self.combat_state
        tgt_n, tgt_e, tgt_alt, tgt_mach = pick_target(
            own.north_ft, own.east_ft, enemy_combat_state.north_ft,
            enemy_combat_state.east_ft, enemy_combat_state.alt_ft, mode, crank_rad)
        # build_obs LOKAL (driver'in kendi cercevesindeki) pos/hedef bekler --
        # hedefi de ayni cerceveye (ofseti cikararak) cevirmemiz gerekiyor.
        obs = gs.build_obs(self.driver.st, tgt_n - self.origin_n_ft,
                           tgt_e - self.origin_e_ft, tgt_alt, tgt_mach,
                           self.driver.last_applied)
        action, _ = self.model.predict(obs, deterministic=True)
        return self.driver.tick(action)


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
    cfg.episode_s = 1e9  # kullanilmiyor -- bu betik kendi dongusunu yonetiyor
    model = SAC.load(args.model, device="cpu")

    SEP_NM = 30.0
    blue = Aircraft("blue", cfg, model, alt_ft=25000, mach=0.9, heading_deg=0.0,
                    origin_n_ft=0.0, origin_e_ft=0.0)
    red = Aircraft("red", cfg, model, alt_ft=25000, mach=0.9, heading_deg=180.0,
                   origin_n_ft=SEP_NM * NM_TO_FT, origin_e_ft=0.0)

    eng = Engagement(rules=LaunchRules(), missile_cfg=MissileConfig())
    eng.add_aircraft("blue", blue.combat_state, blue.radar, blue.loadout)
    eng.add_aircraft("red", red.combat_state, red.radar, red.loadout)

    n_steps = int(args.duration / DT)
    fired = {"blue": 0, "red": 0}
    crashed = False

    # Faz 1.5d: Tacview kaydi -- verilmezse rec=None, asagidaki tum "if rec"
    # bloklari atlanir (calisan davranis degismez).
    rec = ACMIRecorder(args.acmi, ref_lat=39.0, ref_lon=32.8,
                        title="BVR 1v1 angajman") if args.acmi else None
    if rec is not None:
        rec.open()
    missile_obj_ids: dict[str, int] = {}
    next_missile_obj_id = 100

    try:
        for k in range(n_steps):
            t = k * DT
            st_blue_combat = blue.combat_state
            st_red_combat = red.combat_state

            blue_evading = any(m.target_id == "blue" and m.missile.alive for m in eng.missiles)
            red_evading = any(m.target_id == "red" and m.missile.alive for m in eng.missiles)

            blue.step(st_red_combat, "evade" if blue_evading else "intercept", crank_rad)
            red.step(st_blue_combat, "evade" if red_evading else "intercept", crank_rad)

            st_blue_combat = blue.combat_state
            st_red_combat = red.combat_state

            for label, st in (("blue", st_blue_combat), ("red", st_red_combat)):
                if not (math.isfinite(st.alt_ft) and math.isfinite(st.north_ft)
                        and math.isfinite(st.mach)):
                    print(f"t={t:.1f}s: {label} durumunda NaN/sonsuz deger -- COKME")
                    crashed = True
            if crashed:
                break

            events = eng.update(DT, {"blue": st_blue_combat, "red": st_red_combat})
            for ev in events:
                print(f"t={ev.t:.1f}s  {ev.kind:<10} {ev.actor} -> {ev.target}  {ev.detail}")

            for shooter, target in (("blue", "red"), ("red", "blue")):
                can, reason = eng.can_fire(shooter, target)
                if can:
                    eng.fire(shooter, target)
                    fired[shooter] += 1
                    (blue if shooter == "blue" else red).drop_missile()
                    print(f"t={t:.1f}s  ATES      {shooter} -> {target} "
                          f"(menzil {relative_geometry(eng.aircraft[shooter].state, eng.aircraft[target].state).range_nm:.1f} nmi)")

            if rec is not None:
                # ONEMLI: rec.record() zaman damgasini kendi ic saatinden
                # (st.t, adim SONRASI -- (k+1)*DT) alir; script'in yerel `t`
                # degiskeni ise adim ONCESI (k*DT) -- ikisi 1 DT kayar. Fuze
                # ve ucak AYNI karede AYNI zaman damgasi altinda gorunsun diye
                # (yoksa fuze izi atan ucaktan "1 tik once/sonra" baslar gibi
                # gorunur) fuze/kaldirma icin de st.t kullanilir, yerel t degil.
                rec_t = st_blue_combat.t
                rec.record(st_blue_combat, obj_id=1, name="F-16C", color="Blue", callsign="Blue1")
                rec.record(st_red_combat, obj_id=2, name="F-16C", color="Red", callsign="Red1")

                # Fuzeler -- yeni atilan (bu tikte eng.missiles'a eklenen) bir
                # fuze, launch pozisyonuyla (atan ucagin O ANKI durumu) ilk kez
                # burada gorunur -- iz, atisin oldugu karede atan ucaktan baslar.
                alive_ids = set()
                for m in eng.missiles:
                    if not m.missile.alive:
                        continue
                    alive_ids.add(m.id)
                    if m.id not in missile_obj_ids:
                        missile_obj_ids[m.id] = next_missile_obj_id
                        next_missile_obj_id += 1
                    color = "Blue" if m.shooter_id == "blue" else "Red"
                    rec.record_missile(rec_t, m.missile.pos, m.missile.vel,
                                        missile_obj_ids[m.id], color=color)

                # Sonuclanan (isabet/iska/kor/tukenme/hedefsiz) fuzeleri
                # sahneden kaldir -- artik eng.missiles'ta "alive" degiller.
                for msl_id in list(missile_obj_ids):
                    if msl_id not in alive_ids:
                        rec.remove_object(rec_t, missile_obj_ids.pop(msl_id))

            if not eng.aircraft["blue"].alive or not eng.aircraft["red"].alive:
                print(f"t={t:.1f}s: bir taraf imha oldu, angajman bitti.")
                break
    finally:
        if rec is not None:
            rec.close()

    print(f"\n{'COKTU' if crashed else 'TAMAMLANDI'} -- "
          f"blue {fired['blue']} atis, red {fired['red']} atis, "
          f"toplam {len(eng.events)} olay.")
    print(f"blue alive={eng.aircraft['blue'].alive}  red alive={eng.aircraft['red'].alive}")


if __name__ == "__main__":
    main()
