"""
Faz 2.2 -- paylasilan 1v1 angajman dongusu.

NEDEN AYRI BIR MODUL: `bvr_1v1_smoke.py` (duman testi/gorsel inceleme) ve
`scripts/eval_commander.py` (istatistiksel degerlendirme) AYNI fiziksel/
taktik mantigi kullanmali -- `crank_sweep.py`'nin `pick_target`'i
KOPYALAMAYIP IMPORT ETME gerekcesiyle birebir ayni: iki kopya olursa biri
duzelir digeri unutulur. Bu projede bu FIILEN iki kez oldu (füze kütlesi,
RWR kablolaması -- bkz. HANDOFF.md tuzak 47/51). Bu modul tek sorumluluk
tasir: bir `DuelScenario`'yu (baslangic kosullari) alip TAM bir 1v1
angajmani kosturup zengin bir `DuelResult` dondurur. Yazdirma/Tacview/CLI
arayuzu BURADA YOK -- cagiran taraf kendi ihtiyacina gore ekler.

RASTGELE SENARYO URETIMI (Faz 2.2): tek bir tam sayi tohumdan (`seed`)
TUM baslangic kosullari (mesafe, acili yaklasim, yanal ofset, irtifa, Mach,
yakit, turbulans) `numpy.random.default_rng` ile SIRALI olarak turetilir --
ayni tohum HER ZAMAN ayni senaryoyu (ve JSBSim seed'leri sabit oldugu icin
ayni sonucu) uretir. `generate_scenario()`'nun cizim SIRASI degistirilirse
eski tohumlarin urettigi senaryolar SESSIZCE degisir -- bu fonksiyona yeni
bir parametre eklerken en SONA ekle.

AYNALAMA (mirroring): SIM2-08'de olculen "guidance be=0'da bile saga yatik"
onyargisi, rastgele uretilen senaryolarda sonuca sistematik olarak
karisabilir. `mirror_scenario()` dogu-bati'yi (lateral_offset, aspect,
turbulans yonu) ters cevirir -- ayni cift uzerinden kazanma orani ~%50
olmalidir (bkz. eval_commander.py'nin oz-denetimi).
"""
from __future__ import annotations

import dataclasses
import math
import time
from dataclasses import dataclass

import numpy as np

from ..envs.guidance_driver import GuidanceDriver
from ..envs import guidance_shared as gs
from .geometry import relative_geometry
from .radar import Radar
from .missile import MissileConfig
from .engagement import Engagement, Loadout, LaunchRules
from .rwr import RWR

NM_TO_FT = 6076.11549
DT = 0.1
DURATION_S = 180.0
CMD_RANGE_NM = 12.0     # TAC-08 (5-25 nmi) icinde, egitim dagilimina (3.3-14.8) yakin
CMD_MACH = 0.90
CRANK_DEG_DEFAULT = 30.0   # bkz. bvr_1v1_smoke.py dosya basligi / REQUIREMENTS.md SIM2-09
MISSILE_MASS_LB = MissileConfig().mass_lb   # ENG'deki tek dogruluk kaynagi (335 lb)

# Faz 2.2 rastgele senaryo araliklari -- bunlar da FIZIKSEL SABIT DEGIL,
# degerlendirme tasariminin kendi denge parametreleri (bkz. RWR-01/SIM2-09'daki
# "denge parametresi" disiplini). Ayrintili gerekce REQUIREMENTS.md'ye
# eval-01 olarak islenecek.
SEPARATION_NM_RANGE = (25.0, 40.0)     # LaunchRules.max_launch_nm=35 -- hem icinde hem disinda basla
ASPECT_DEG_RANGE = (-60.0, 60.0)        # kirmizinin burun-buruna'dan sapmasi
# KOLTUK SIMETRISI (Faz 2.2 bulgusu): ilk surumde SADECE kirmizinin yonu
# rastgeleydi, mavi hep burnu rakibe donuk basliyordu (ort. sapma 8.6 derece
# vs kirmizi 30.3) -- ayni modelin kendisine karsi oldugu halde mavi karar
# verilen angajmanlarin %70'ini kazandi. Mavinin yonu de KIRMIZIYLA AYNI
# dagilimdan cekilir, boylece iki koltuk istatistiksel olarak ozdes.
BLUE_OFFSET_DEG_RANGE = ASPECT_DEG_RANGE
LATERAL_OFFSET_NM_RANGE = (-10.0, 10.0)
ALT_FT_RANGE = (15000.0, 35000.0)       # her iki taraf BAGIMSIZ
MACH_RANGE = (0.75, 0.95)
FUEL_FRAC_RANGE = (0.50, 1.00)
TURBULENCE_PROB = 0.30
TURBULENCE_FPS_RANGE = (0.0, 60.0)


@dataclass(frozen=True)
class DuelScenario:
    """Bir 1v1 angajmanin TUM baslangic kosullari. Degismez (frozen) --
    `mirror_scenario()` YENI bir kopya dondurur, mevcut olani degistirmez."""
    seed: int
    separation_nm: float
    aspect_deg: float            # kirmizinin yonelimi: heading = 180 + aspect_deg
    lateral_offset_nm: float     # kirmizinin dogu ofseti (maviye gore)
    alt_blue_ft: float
    alt_red_ft: float
    mach_blue: float
    mach_red: float
    fuel_blue: float
    fuel_red: float
    turb_blue_fps: float
    turb_red_fps: float
    turb_blue_dir_deg: float
    turb_red_dir_deg: float
    mirrored: bool = False
    blue_offset_deg: float = 0.0    # mavinin yonelimi: heading = blue_offset_deg (0 = kuzey)


def generate_scenario(seed: int) -> DuelScenario:
    """Tek bir tam sayi tohumdan TAM bir senaryo uretir -- deterministik,
    tekrar uretilebilir (bkz. dosya basligindaki uyari: cizim SIRASINI
    degistirme)."""
    rng = np.random.default_rng(seed)
    separation_nm = float(rng.uniform(*SEPARATION_NM_RANGE))
    aspect_deg = float(rng.uniform(*ASPECT_DEG_RANGE))
    lateral_offset_nm = float(rng.uniform(*LATERAL_OFFSET_NM_RANGE))
    alt_blue_ft = float(rng.uniform(*ALT_FT_RANGE))
    alt_red_ft = float(rng.uniform(*ALT_FT_RANGE))
    mach_blue = float(rng.uniform(*MACH_RANGE))
    mach_red = float(rng.uniform(*MACH_RANGE))
    fuel_blue = float(rng.uniform(*FUEL_FRAC_RANGE))
    fuel_red = float(rng.uniform(*FUEL_FRAC_RANGE))
    turb_on = bool(rng.random() < TURBULENCE_PROB)
    turb_blue_fps = float(rng.uniform(*TURBULENCE_FPS_RANGE)) if turb_on else 0.0
    turb_red_fps = float(rng.uniform(*TURBULENCE_FPS_RANGE)) if turb_on else 0.0
    turb_blue_dir_deg = float(rng.uniform(0.0, 360.0))
    turb_red_dir_deg = float(rng.uniform(0.0, 360.0))
    blue_offset_deg = float(rng.uniform(*BLUE_OFFSET_DEG_RANGE))   # HER ZAMAN en sonda
    return DuelScenario(
        seed=seed, separation_nm=separation_nm, aspect_deg=aspect_deg,
        lateral_offset_nm=lateral_offset_nm, alt_blue_ft=alt_blue_ft, alt_red_ft=alt_red_ft,
        mach_blue=mach_blue, mach_red=mach_red, fuel_blue=fuel_blue, fuel_red=fuel_red,
        turb_blue_fps=turb_blue_fps, turb_red_fps=turb_red_fps,
        turb_blue_dir_deg=turb_blue_dir_deg, turb_red_dir_deg=turb_red_dir_deg,
        blue_offset_deg=blue_offset_deg,
    )


def mirror_scenario(scenario: DuelScenario) -> DuelScenario:
    """Dogu-bati ayna goruntusu: yanal ofset, acili yaklasim ve turbulans
    yonu isaret degistirir; geri kalan (mesafe, irtifa, Mach, yakit,
    turbulans SIDDETI) AYNI kalir -- bunlar yon-bagimsiz buyukluler."""
    return dataclasses.replace(
        scenario,
        aspect_deg=-scenario.aspect_deg,
        blue_offset_deg=-scenario.blue_offset_deg,
        lateral_offset_nm=-scenario.lateral_offset_nm,
        turb_blue_dir_deg=(360.0 - scenario.turb_blue_dir_deg) % 360.0,
        turb_red_dir_deg=(360.0 - scenario.turb_red_dir_deg) % 360.0,
        mirrored=not scenario.mirrored,
    )


def initial_ata_deg(scenario: DuelScenario) -> tuple[float, float]:
    """Iki tarafin BASLANGIC anindaki |ATA|'si (derece): kendi burnuna gore
    rakibin sapmasi. Koltuk simetrisinin (mavi/kirmizi istatistiksel olarak
    ozdes mi) SIMULASYONSUZ, aninda kontrolu icin -- bkz. test_duel.py."""
    from .geometry import wrap_to_180
    brg_blue_to_red = math.degrees(math.atan2(scenario.lateral_offset_nm, scenario.separation_nm))
    blue_ata = abs(wrap_to_180(brg_blue_to_red - scenario.blue_offset_deg))
    red_heading = 180.0 + scenario.aspect_deg
    red_ata = abs(wrap_to_180(brg_blue_to_red + 180.0 - red_heading))
    return blue_ata, red_ata


def pick_target(own_north, own_east, enemy_north, enemy_east, enemy_alt, mode: str, crank_rad: float):
    """Basit betikli komutan: 'intercept' (dusmana don) ya da 'evade' (crank_rad kadar kir)."""
    brg = math.atan2(enemy_east - own_east, enemy_north - own_north)
    if mode == "evade":
        brg += crank_rad
    tgt_n = own_north + CMD_RANGE_NM * NM_TO_FT * math.cos(brg)
    tgt_e = own_east + CMD_RANGE_NM * NM_TO_FT * math.sin(brg)
    return tgt_n, tgt_e, enemy_alt, CMD_MACH


class Aircraft:
    def __init__(self, name, cfg, model, alt_ft, mach, heading_deg, origin_n_ft, origin_e_ft,
                 fuel_frac=0.75, seed=1, turb_fps=0.0, turb_dir_deg=0.0):
        self.name = name
        self.model = model
        self.driver = GuidanceDriver(cfg=cfg, seed=seed)
        self.origin_n_ft = origin_n_ft
        self.origin_e_ft = origin_e_ft
        self.radar = Radar()
        self.loadout = Loadout()
        # Tam muhimmatla trim -- gercek kalkis agirligi budur (payload_check.py
        # ile en agir konfigurasyonda GUI-11 sozlesmesinin hala tuttugu
        # olculmustu). reset()'TEN ONCE cagrilmali ki trim bunu hesaba katsin.
        self.driver.set_payload(self.loadout.amraam * MISSILE_MASS_LB)
        self.driver.reset(alt_ft=alt_ft, mach=mach, heading_deg=heading_deg, fuel_frac=fuel_frac)
        if turb_fps > 0.0:
            # set_turbulence() reset'TEN SONRA cagrilmali -- F16Sim.reset()
            # basinda turbulansi ZATEN sifirliyor (HANDOFF tuzak 2).
            self.driver.sim.set_turbulence(wind_fps=turb_fps, wind_dir_deg=turb_dir_deg, turb_severity=1)

    @property
    def combat_state(self):
        """Muhasebe/radar/fuze/RWR'nin gordugu, PAYLASILAN cercevedeki durum."""
        st = self.driver.st
        return dataclasses.replace(st, north_ft=st.north_ft + self.origin_n_ft,
                                   east_ft=st.east_ft + self.origin_e_ft)

    def drop_missile(self):
        """Bir fuze atildiktan SONRA cagrilir -- kalan yuke gore JSBSim
        agirligini gunceller (yeniden trim GEREKMEZ, bkz. GuidanceDriver.set_payload)."""
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


@dataclass
class DuelResult:
    scenario_seed: int
    mirrored: bool
    warning_mode: str
    outcome: str          # "galibiyet"|"maglubiyet"|"karsilikli_imha"|"zaman_asimi"|"muhimmatsiz"|"cokme"
    blue_alive: bool
    red_alive: bool
    blue_fired: int
    red_fired: int
    blue_hits: int
    red_hits: int
    kor_count: int
    hedefsiz_count: int
    iska_count: int
    tukenme_count: int
    first_hit_t: float | None
    closest_approach_nm: float
    max_missile_flight_s: float
    nz_min_blue: float      # negatif-g yonu (izleme listesi: esik -4.8 g); duz ucus = +1
    nz_min_red: float
    nz_max_blue: float      # tepe +g cekisi
    nz_max_red: float
    duration_s: float
    wall_time_s: float
    # Faz 2.3 (atis kapisi deneyi): kapi degerleri + ILK atisin menzili. Ilk atis
    # menzili mekanizma analizi icin (isabet, atis menziline gore nasil degisiyor?).
    fire_gate_blue_nm: float | None = None
    fire_gate_red_nm: float | None = None
    first_shot_range_blue_nm: float | None = None
    first_shot_range_red_nm: float | None = None
    # Kapinin KAC TIKTE atisi tuttugu: yetki (can_fire) VAR ama komutan bekledi. >0 ise
    # kapi bu savasta BAGLADI; 0 ise kapi bu senaryoda hicbir sey yapmadi (seyreltme olcusu).
    gate_blocked_ticks_blue: int = 0
    gate_blocked_ticks_red: int = 0
    # FUZE SONLANMA NEDENLERI, ATAN TARAFA gore (EVAL-05: 'kaciş rakibin fuzesini korletiyor mu?'
    # hipotezini ayirt etmek icin). Toplamlari kor_count/hedefsiz_count/iska_count/tukenme_count'a
    # esittir. 'isabet' zaten blue_hits/red_hits'te.
    blue_kor_count: int = 0
    blue_hedefsiz_count: int = 0
    blue_iska_count: int = 0
    blue_tukenme_count: int = 0
    red_kor_count: int = 0
    red_hedefsiz_count: int = 0
    red_iska_count: int = 0
    red_tukenme_count: int = 0
    # Kac tik (0.1 s) EVADE modunda gecti (EVAL-09 tani kolu: 'kacis fuzeyi tuketiyor mu?').
    evade_ticks_blue: int = 0
    evade_ticks_red: int = 0
    # Kacis tetikleyici gecikmesi (s), EVAL-11: 0.0 = eski (kilitte kac); inf = yalniz fuzede kac.
    evade_delay_blue_s: float = 0.0
    evade_delay_red_s: float = 0.0


_TERMINAL_KINDS = {"isabet", "iska", "kor", "tukenme", "hedefsiz"}
WARNING_MODES = ("rwr", "truth", "none")


def should_evade(threat, delay_s: float = 0.0) -> bool:
    """RWR-tabanli kacis karari (EVAL-11). `threat` = en kotu RWR temasi (None olabilir).
    - 'fuze' (aktif arayici gorundu): HER ZAMAN kac (gecikme uygulanmaz).
    - 'kilit' (radar kilidi): temas `delay_s` saniyeden ESKIYSE kac. `age_s` yayincinin ILK
      TESPITINDEN beri gecen suredir (arama seviyesinden baslar -- kilidin kendi yasi DEGIL, ama
      "temas ne kadardir suruyor" icin makul vekil).
    - baska her sey (arama/None): kacma.
    delay_s=0.0 -> eski davranis (kilit veya fuze) BIREBIR; delay_s=inf -> yalniz fuzede kac.
    """
    if threat is None:
        return False
    if threat.kind == "fuze":
        return True
    if threat.kind == "kilit":
        return threat.age_s >= delay_s
    return False


def tally_missile_end(kind: str, shooter: str, kind_counts: dict, side_counts: dict) -> bool:
    """Bir olayin fuze sonlanma turu (kor/hedefsiz/iska/tukenme) ise HEM toplam HEM ATAN
    tarafin sayacina isler; baska tur (ates, pitbull, isabet...) ise dokunmaz. Saf fonksiyon
    -- taraf atfi (kimin fuzesi korlendi?) simulasyon kosturmadan test edilebilsin diye
    run_duel'dan ayrildi. `shooter` = CombatEvent.actor (fuzeyi ATAN taraf)."""
    if kind not in kind_counts:
        return False
    kind_counts[kind] += 1
    side_counts[shooter][kind] += 1
    return True


def run_duel(cfg, model, scenario: DuelScenario, warning_mode: str = "rwr",
             crank_deg: float = CRANK_DEG_DEFAULT, duration_s: float = DURATION_S,
             dt: float = DT, acmi_recorder=None, verbose: bool = False,
             fire_gate_nm_blue: float | None = None,
             fire_gate_nm_red: float | None = None,
             evade_delay_s_blue: float = 0.0,
             evade_delay_s_red: float = 0.0) -> DuelResult:
    """Bir `DuelScenario`'yu TAM olarak kosturur, zengin bir `DuelResult`
    dondurur.

    `warning_mode`: 'rwr' (varsayilan, gercekci: kacis RWR kilit/fuze uyarisindan),
    'truth' (omniscient, eski regresyon referansi) veya 'none' (EVAL-09 TANI kolu:
    IKI taraf da HIC kacmaz -- gercekci bir politika DEGIL, 'kacis fuzelerin enerjisini
    tuketiyor mu?' sorusunu ayirmak icin). Bilinmeyen deger ValueError (eskiden yazim
    hatasi sessizce 'rwr' olarak kosuyordu).

    `evade_delay_s_*` (EVAL-11): RWR kacisinin 'kilit' tetikleyicisi bu kadar saniye GECIKIR
    (bkz. `should_evade`); yalniz `warning_mode='rwr'`da anlamli (baska modda sifirdan farkli
    deger ValueError -- sessizce yok sayilmasin). Varsayilan 0.0 = eski davranis BIREBIR.

    `fire_gate_nm_*` (Faz 2.3): KOMUTANIN ek atis disiplini -- `Engagement.can_fire`
    (yetki: 35 nmi Rmax, kilit, muhimmat) izin verse BILE menzil bu degerden buyukse
    ATESLEME. None = ek kapi yok (eski davranis, BIREBIR). Bilerek Engagement/
    LaunchRules'ta DEGIL burada: LaunchRules atis YETKISIDIR, 'ne zaman atarim'
    ise komutanin kararidir (Faz 3'te PPO'nun 'ates' aksiyonu da can_fire yetkisinin
    USTUNDE oturacak). Kapi Rmax'tan buyukse etkisizdir (yetki zaten keser).
 `acmi_recorder` verilirse (acilmis bir `ACMIRecorder`) kayit
    da yapilir -- cagiran taraf acip kapatmaktan sorumlu (bu fonksiyon
    SADECE `record()` cagirir, `open()`/`close()` cagirmaz)."""
    if warning_mode not in WARNING_MODES:
        raise ValueError(f"bilinmeyen warning_mode={warning_mode!r}; gecerli: {WARNING_MODES}")
    if warning_mode != "rwr" and (evade_delay_s_blue != 0.0 or evade_delay_s_red != 0.0):
        raise ValueError("evade_delay_s_* yalniz warning_mode='rwr' ile anlamli "
                         f"(warning_mode={warning_mode!r}); sessizce yok sayilmaz")
    t_wall0 = time.perf_counter()
    crank_rad = math.radians(crank_deg)

    blue = Aircraft("blue", cfg, model, alt_ft=scenario.alt_blue_ft, mach=scenario.mach_blue,
                     heading_deg=scenario.blue_offset_deg % 360.0,
                     origin_n_ft=0.0, origin_e_ft=0.0,
                     fuel_frac=scenario.fuel_blue, seed=scenario.seed * 2,
                     turb_fps=scenario.turb_blue_fps, turb_dir_deg=scenario.turb_blue_dir_deg)
    red = Aircraft("red", cfg, model, alt_ft=scenario.alt_red_ft, mach=scenario.mach_red,
                    heading_deg=180.0 + scenario.aspect_deg,
                    origin_n_ft=scenario.separation_nm * NM_TO_FT,
                    origin_e_ft=scenario.lateral_offset_nm * NM_TO_FT,
                    fuel_frac=scenario.fuel_red, seed=scenario.seed * 2 + 1,
                    turb_fps=scenario.turb_red_fps, turb_dir_deg=scenario.turb_red_dir_deg)

    eng = Engagement(rules=LaunchRules(), missile_cfg=MissileConfig())
    eng.add_aircraft("blue", blue.combat_state, blue.radar, blue.loadout)
    eng.add_aircraft("red", red.combat_state, red.radar, red.loadout)

    n_steps = int(duration_s / dt)
    fired = {"blue": 0, "red": 0}
    fire_gate = {"blue": fire_gate_nm_blue, "red": fire_gate_nm_red}
    first_shot_range: dict[str, float | None] = {"blue": None, "red": None}
    gate_blocked = {"blue": 0, "red": 0}
    evade_ticks = {"blue": 0, "red": 0}
    hits = {"blue": 0, "red": 0}
    kind_counts = {"kor": 0, "hedefsiz": 0, "iska": 0, "tukenme": 0}
    side_kind_counts = {"blue": dict.fromkeys(kind_counts, 0), "red": dict.fromkeys(kind_counts, 0)}
    first_hit_t = None
    closest_approach_ft = float("inf")
    max_missile_flight_s = 0.0
    # nz PROJE SOZLESMESINDE duz ucus = +1 (state_def.state_from_flight st.nz'yi
    # cevirir; HANDOFF tuzak 5). Ham st.nz duz ucusta ~ -1 -- ilk surumde ham
    # degerin minimumu alinmisti, bu aslinda +g CEKISIYDI (negatif-g degil).
    nz_min = {"blue": float("inf"), "red": float("inf")}
    nz_max = {"blue": float("-inf"), "red": float("-inf")}
    crashed = False
    t_final = 0.0
    missile_obj_ids: dict[str, int] = {}
    next_missile_obj_id = 100

    for k in range(n_steps):
        t = k * dt
        t_final = t
        st_blue_combat = blue.combat_state
        st_red_combat = red.combat_state

        if warning_mode == "none":
            # TANI (EVAL-09): hic kacis yok -- iki taraf da tum savas boyunca 'intercept'.
            blue_evading = False
            red_evading = False
        elif warning_mode == "truth":
            # ESKI (omniscient) davranis -- SADECE regresyon referansi icin.
            blue_evading = any(m.target_id == "blue" and m.missile.alive for m in eng.missiles)
            red_evading = any(m.target_id == "red" and m.missile.alive for m in eng.missiles)
        else:
            blue_threat = eng.aircraft["blue"].rwr.get_worst_threat()
            blue_evading = should_evade(blue_threat, evade_delay_s_blue)
            red_threat = eng.aircraft["red"].rwr.get_worst_threat()
            red_evading = should_evade(red_threat, evade_delay_s_red)

        evade_ticks["blue"] += int(blue_evading)
        evade_ticks["red"] += int(red_evading)
        blue.step(st_red_combat, "evade" if blue_evading else "intercept", crank_rad)
        red.step(st_blue_combat, "evade" if red_evading else "intercept", crank_rad)

        st_blue_combat = blue.combat_state
        st_red_combat = red.combat_state

        for label, st in (("blue", st_blue_combat), ("red", st_red_combat)):
            if not (math.isfinite(st.alt_ft) and math.isfinite(st.north_ft) and math.isfinite(st.mach)):
                crashed = True
            g = -st.nz
            nz_min[label] = min(nz_min[label], g)
            nz_max[label] = max(nz_max[label], g)
        if crashed:
            if verbose:
                print(f"t={t:.1f}s: NaN/sonsuz deger -- COKME")
            break

        geom_now = relative_geometry(st_blue_combat, st_red_combat)
        closest_approach_ft = min(closest_approach_ft, geom_now.range_ft)

        events = eng.update(dt, {"blue": st_blue_combat, "red": st_red_combat})
        for ev in events:
            if verbose:
                print(f"t={ev.t:.1f}s  {ev.kind:<10} {ev.actor} -> {ev.target}  {ev.detail}")
            if ev.kind == "isabet":
                hits[ev.actor] += 1
                if first_hit_t is None:
                    first_hit_t = ev.t
            else:
                tally_missile_end(ev.kind, ev.actor, kind_counts, side_kind_counts)
            if ev.kind in _TERMINAL_KINDS and "time_of_flight" in ev.detail:
                max_missile_flight_s = max(max_missile_flight_s, ev.detail["time_of_flight"])

        for shooter, target in (("blue", "red"), ("red", "blue")):
            can, _ = eng.can_fire(shooter, target)
            rng_nm = relative_geometry(eng.aircraft[shooter].state, eng.aircraft[target].state).range_nm
            if can and fire_gate[shooter] is not None and rng_nm > fire_gate[shooter]:
                can = False   # yetki var ama komutan bu menzilde ATMIYOR (atis disiplini)
                gate_blocked[shooter] += 1
            if can:
                eng.fire(shooter, target)
                fired[shooter] += 1
                if first_shot_range[shooter] is None:
                    first_shot_range[shooter] = rng_nm
                (blue if shooter == "blue" else red).drop_missile()
                if verbose:
                    print(f"t={t:.1f}s  ATES      {shooter} -> {target} (menzil {rng_nm:.1f} nmi)")

        if acmi_recorder is not None:
            rec_t = st_blue_combat.t
            acmi_recorder.record(st_blue_combat, obj_id=1, name="F-16C", color="Blue", callsign="Blue1")
            acmi_recorder.record(st_red_combat, obj_id=2, name="F-16C", color="Red", callsign="Red1")
            alive_ids = set()
            for m in eng.missiles:
                if not m.missile.alive:
                    continue
                alive_ids.add(m.id)
                if m.id not in missile_obj_ids:
                    missile_obj_ids[m.id] = next_missile_obj_id
                    next_missile_obj_id += 1
                color = "Blue" if m.shooter_id == "blue" else "Red"
                acmi_recorder.record_missile(rec_t, m.missile.pos, m.missile.vel,
                                              missile_obj_ids[m.id], color=color)
            for msl_id in list(missile_obj_ids):
                if msl_id not in alive_ids:
                    acmi_recorder.remove_object(rec_t, missile_obj_ids.pop(msl_id))

        if not eng.aircraft["blue"].alive or not eng.aircraft["red"].alive:
            if verbose:
                print(f"t={t:.1f}s: bir taraf imha oldu, angajman bitti.")
            break

        # Erken cikis: iki tarafin da mühimmati VE havada füzesi kalmadiysa
        # kalan sureyi bos yere koşturmanin anlami yok (sonuc zaten belli).
        no_ammo_left = eng.aircraft["blue"].loadout.amraam == 0 and eng.aircraft["red"].loadout.amraam == 0
        no_missiles_flying = not any(m.missile.alive for m in eng.missiles)
        if no_ammo_left and no_missiles_flying:
            if verbose:
                print(f"t={t:.1f}s: iki taraf da muhimmatsiz, aktif fuze yok -- erken bitiriliyor.")
            break

    blue_alive = eng.aircraft["blue"].alive
    red_alive = eng.aircraft["red"].alive

    if crashed:
        outcome = "cokme"
    elif blue_alive and not red_alive:
        outcome = "galibiyet"
    elif red_alive and not blue_alive:
        outcome = "maglubiyet"
    elif not blue_alive and not red_alive:
        outcome = "karsilikli_imha"
    else:
        no_ammo_left = eng.aircraft["blue"].loadout.amraam == 0 and eng.aircraft["red"].loadout.amraam == 0
        no_missiles_flying = not any(m.missile.alive for m in eng.missiles)
        outcome = "muhimmatsiz" if (no_ammo_left and no_missiles_flying) else "zaman_asimi"

    return DuelResult(
        scenario_seed=scenario.seed, mirrored=scenario.mirrored, warning_mode=warning_mode,
        outcome=outcome, blue_alive=blue_alive, red_alive=red_alive,
        blue_fired=fired["blue"], red_fired=fired["red"],
        blue_hits=hits["blue"], red_hits=hits["red"],
        kor_count=kind_counts["kor"], hedefsiz_count=kind_counts["hedefsiz"],
        iska_count=kind_counts["iska"], tukenme_count=kind_counts["tukenme"],
        first_hit_t=first_hit_t,
        closest_approach_nm=closest_approach_ft / NM_TO_FT if closest_approach_ft != float("inf") else -1.0,
        max_missile_flight_s=max_missile_flight_s,
        nz_min_blue=nz_min["blue"], nz_min_red=nz_min["red"],
        nz_max_blue=nz_max["blue"], nz_max_red=nz_max["red"],
        duration_s=t_final, wall_time_s=time.perf_counter() - t_wall0,
        fire_gate_blue_nm=fire_gate_nm_blue, fire_gate_red_nm=fire_gate_nm_red,
        first_shot_range_blue_nm=first_shot_range["blue"],
        first_shot_range_red_nm=first_shot_range["red"],
        gate_blocked_ticks_blue=gate_blocked["blue"], gate_blocked_ticks_red=gate_blocked["red"],
        blue_kor_count=side_kind_counts["blue"]["kor"], blue_hedefsiz_count=side_kind_counts["blue"]["hedefsiz"],
        blue_iska_count=side_kind_counts["blue"]["iska"], blue_tukenme_count=side_kind_counts["blue"]["tukenme"],
        red_kor_count=side_kind_counts["red"]["kor"], red_hedefsiz_count=side_kind_counts["red"]["hedefsiz"],
        red_iska_count=side_kind_counts["red"]["iska"], red_tukenme_count=side_kind_counts["red"]["tukenme"],
        evade_ticks_blue=evade_ticks["blue"], evade_ticks_red=evade_ticks["red"],
        evade_delay_blue_s=evade_delay_s_blue, evade_delay_red_s=evade_delay_s_red,
    )
