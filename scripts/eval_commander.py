"""
Faz 2.2 -- degerlendirme duzenegi: rastgele senaryolar + Wilson GA + McNemar,
ortak rastgele sayilarla (CRN) iki komutan/uyari modunu kiyaslar.

NEDEN GEREKLI: tek bir angajmanin sonucu ANEKDOT. `--warning truth` vs
`rwr` A/B'sinde bunu GORDUK -- 1.1 saniyelik bir gecikme farki sonucu
CEVIRDI (bkz. REQUIREMENTS.md RWR-03). Bu arac "hangisi daha iyi" sorusunu
GUVEN ARALIGIYLA cevaplar. Faz 4'un kabul olcutu ("RL, betikli tabani
gecsin, GA'lar ortusmesin") AYNEN bu araçla olculecek -- yani burada
yazilan sey iki faz sonra da kullanilacak.

MIMARI: angajman mantigini KOPYALAMAZ -- `bvr/combat/duel.py::run_duel()`
cagirir (crank_sweep.py'nin pick_target'i import etme gerekcesiyle ayni
disiplin). Bu dosyanin TEK isi: SENARYO URETIMI + ISTATISTIK + PARALEL
KOSTURMA.

ORTAK RASTGELE SAYILAR (CRN): her senaryo TEK bir tam sayi tohumdan
uretilir (bkz. duel.py::generate_scenario) ve HER IKI KOL (truth/rwr)
AYNI tohumla kosturulur -- ayni ruzgar, ayni geometri, tek fark komutan.
Boylece fark senaryo gurultusune KARISMAZ (guidance fazinin "blok etkisi"
dersinin dogrudan karsiligi).

AYNALAMA: SIM2-08'de olculen "guidance be=0'da bile saga yatik" onyargisi
rastgele senaryolara sistematik olarak karisabilir. Her senaryo NORMAL ve
DOGU-BATI AYNA goruntusuyle olmak uzere IKI kez kosturulur (bkz.
duel.py::mirror_scenario). Toplam kosu sayisi: n senaryo x 2 (ayna) x 2
(kol) = 4n.

KULLANIM:
    # HIZLI, HER ZAMAN GUVENLI -- ~40 kosu, birkaç dakika, kullanici onayi GEREKMEZ
    python -m scripts.eval_commander <model.zip> --self-check

    # TAM DEGERLENDIRME -- "UZUN KOSU" siniftinda, KULLANICI "baslat" DEMEDEN calistirilmaz
    python -m scripts.eval_commander <model.zip> --n 200 --workers 24
"""
from __future__ import annotations

import sys
import os
import argparse
import dataclasses
import multiprocessing as mp
import math
import time
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from scipy.stats import binomtest
from stable_baselines3 import SAC

from bvr.combat.duel import (DuelScenario, DuelResult, generate_scenario, mirror_scenario,
                              run_duel, initial_ata_deg)
from bvr.config import load_experiment

Z_95 = 1.959963984540054  # %95 iki-yonlu normal kritik deger


# ============================================================
# Istatistik -- bagimsiz, kucuk, dogrudan test edilebilir fonksiyonlar
# ============================================================

def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson skor araligi -- bir ORANIN (kazanma orani) GA'si. Wald
    (normal yaklasim) araliginin ucundaki (p yakin 0 ya da 1) bozulmayi
    duzeltir; bootstrap'tan hem daha dogru hem hesapsiz (kapali form)."""
    if n == 0:
        return (0.0, 1.0)
    phat = successes / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)
    return ((center - margin) / denom, (center + margin) / denom)


def mcnemar_p_value(b: int, c: int) -> float:
    """McNemar KESIN testi (binom tabanli) -- eslesmis ikili karsilastirma.
    SADECE uyumsuz ciftler (b: kol-A kazandi/kol-B kazanmadi, c: tersi)
    bilgi tasir -- ikisi de ayni sonucu verdigi ciftler H0 altinda da
    beklenen sey, hicbir sey soylemez. H0: b ve c esit olasilikli
    (Binomial(b+c, 0.5)). n=0 (hic uyumsuz cift yoksa) -> p=1.0 (fark
    goremedik, ki bu dogru: hicbir kanit yok)."""
    n = b + c
    if n == 0:
        return 1.0
    return float(binomtest(b, n, 0.5, alternative="two-sided").pvalue)


# ============================================================
# Senaryo/kol -> gorev listesi
# ============================================================

@dataclass(frozen=True)
class ArmSpec:
    """Bir deney kolu: uyari modu + (opsiyonel) TARAF-BAZLI atis kapisi.
    Donmus (frozen) + basit alanlar -> multiprocessing.Pool'a dogrudan gecer."""
    label: str
    warning_mode: str = "rwr"
    fire_gate_blue_nm: float | None = None
    fire_gate_red_nm: float | None = None
    evade_delay_blue_s: float = 0.0
    evade_delay_red_s: float = 0.0

    @property
    def symmetric(self) -> bool:
        """Iki taraf AYNI politikayi mi kullaniyor? Asimetrik kolda koltuk
        dengesi ~%50 BEKLENMEZ (mavi bilerek farkli oynuyor)."""
        return (self.fire_gate_blue_nm == self.fire_gate_red_nm
                and self.evade_delay_blue_s == self.evade_delay_red_s)


# Faz 2.3 atis-kapisi deneyinin ONCEDEN SABITLENMIS birincil degeri (REQUIREMENTS
# EVAL-04). Baska bir deger denenirse rapor bunu KESIF diye isaretler -- birden
# cok kapi degerini "en iyisini bul" diye denemek p-degerini sessizce sisirir.
PRIMARY_GATE_NM = 25.0
RWR_ARM = ArmSpec("rwr", "rwr")
# EVAL-11 kacis-gecikmesi ailesi: ONCEDEN SABITLENMIS iki varyant (15 s ve inf = yalniz fuze). Iki
# karsilastirma -> Bonferroni esigi 0.025. Baska deger KESIF sayilir.
PRIMARY_EVADE_DELAY_S = 15.0
PRE_REGISTERED_EVADE_DELAYS = (15.0, math.inf)
EVADE_ALPHA = 0.025


def experiment_arms(experiment: str, gate_nm: float = PRIMARY_GATE_NM,
                     evade_delay_s: float = PRIMARY_EVADE_DELAY_S) -> tuple[ArmSpec, ArmSpec]:
    """Deney adindan (kol_A, kol_B). `warning`: truth vs rwr (EVAL-03).
    `gate`: A = 35v35 referans, B = mavi gate_nm / kirmizi 35 (ASIMETRIK -- kapi
    IKI tarafa birden uygulanirsa iki komutan da ayni anda iyilesir, kazanma
    orani kapinin USTUNLUGUNU gostermez; bkz. EVAL-04)."""
    if experiment == "warning":
        return ArmSpec("truth", "truth"), ArmSpec("rwr", "rwr")
    if experiment == "gate":
        return ArmSpec("A_35v35", "rwr"), ArmSpec(f"B_{gate_nm:g}v35", "rwr", fire_gate_blue_nm=gate_nm)
    if experiment == "gate-sym":
        # SIMETRIK kapi (EVAL-06): iki taraf da gate_nm'de atar. Zamanlama asimetrisini kaldirir;
        # "menzil TEK BASINA isabeti artiriyor mu?" sorusunu temiz sorar.
        return (ArmSpec("A_35v35", "rwr"),
                ArmSpec(f"C_{gate_nm:g}v{gate_nm:g}", "rwr", fire_gate_blue_nm=gate_nm, fire_gate_red_nm=gate_nm))
    if experiment == "evade-diag":
        # TANI (EVAL-09): iki kol da SIMETRIK gate_nm (kinematik olarak ulasilabilir menzil); tek fark
        # kacis: C = RWR-tabanli kacis, N = HIC kacis yok. Gercekci bir politika degil, mekanizma ayirici.
        return (ArmSpec(f"C_{gate_nm:g}v{gate_nm:g}", "rwr", fire_gate_blue_nm=gate_nm, fire_gate_red_nm=gate_nm),
                ArmSpec(f"N_{gate_nm:g}v{gate_nm:g}", "none", fire_gate_blue_nm=gate_nm, fire_gate_red_nm=gate_nm))
    if experiment == "evade-delay":
        # EVAL-11: A = iki taraf da mevcut kacis (kilitte kac), B = MAVI kacisi evade_delay_s gecikmeli
        # (ASIMETRIK; kirmizi mevcut politika). Kapi YOK (gercek oyun, 35 nmi).
        lab = "fuzeOnly" if math.isinf(evade_delay_s) else f"{evade_delay_s:g}s"
        return (ArmSpec("A_evade0", "rwr"),
                ArmSpec(f"B_delay{lab}", "rwr", evade_delay_blue_s=evade_delay_s))
    raise ValueError(f"bilinmeyen deney: {experiment}")


# EVAL-05'te (ve oncesinde) GORULMUS senaryo tohumlari. Bu verilerden dogan YENI bir hipotez ayni
# senaryolarla test edilirse ayni veriye ikinci kez bakilmis (cift-dalis) olur -> taze tohum sart.
SEEN_SEEDS = (frozenset(range(1000, 1200)) | frozenset(range(2000, 2200))
              | frozenset(range(3000, 3200)) | frozenset(range(4000, 4200)))   # EVAL-05..10


def overlaps_seen_seeds(seeds) -> bool:
    return any(s in SEEN_SEEDS for s in seeds)


def build_tasks(seeds: list[int], arms: tuple[ArmSpec, ...] = (ArmSpec("truth", "truth"), RWR_ARM),
                 include_mirror: bool = True) -> list[tuple[int, bool, ArmSpec]]:
    """(seed, mirrored, arm) uclu gorev listesi. AYNI seed HER kol icin
    tekrar kullanilir (CRN) -- eslestirme buradan gelir."""
    tasks = []
    mirror_options = (False, True) if include_mirror else (False,)
    for seed in seeds:
        for mirrored in mirror_options:
            for arm in arms:
                tasks.append((seed, mirrored, arm))
    return tasks


# ============================================================
# Worker -- model HER GOREVDE DEGIL, worker sureci basina BIR KEZ yuklenir
# ============================================================

_WORKER_MODEL = None
_WORKER_CFG = None


def _worker_init(model_path: str) -> None:
    global _WORKER_MODEL, _WORKER_CFG
    rd = os.path.dirname(model_path)
    _WORKER_CFG = load_experiment(f"{rd}/config.resolved.yaml").env
    _WORKER_CFG.episode_s = 1e9
    _WORKER_MODEL = SAC.load(model_path, device="cpu")


def _run_task(task: tuple[int, bool, ArmSpec]) -> DuelResult:
    seed, mirrored, arm = task
    scenario = generate_scenario(seed)
    if mirrored:
        scenario = mirror_scenario(scenario)
    return run_duel(_WORKER_CFG, _WORKER_MODEL, scenario, warning_mode=arm.warning_mode,
                    fire_gate_nm_blue=arm.fire_gate_blue_nm, fire_gate_nm_red=arm.fire_gate_red_nm,
                    evade_delay_s_blue=arm.evade_delay_blue_s, evade_delay_s_red=arm.evade_delay_red_s)


def run_tasks(model_path: str, tasks: list[tuple[int, bool, ArmSpec]], workers: int) -> list[DuelResult]:
    """Gorevleri paralel kostur. workers<=1 ise TEK surecte (hata ayiklama
    icin) -- multiprocessing.Pool hata izlerini gizler, kucuk kosularda
    dogrudan calistirmak daha kolay teshis edilir."""
    if workers <= 1:
        _worker_init(model_path)
        return [_run_task(t) for t in tasks]

    with mp.Pool(processes=workers, initializer=_worker_init, initargs=(model_path,)) as pool:
        return pool.map(_run_task, tasks)


# ============================================================
# Sonuc ozetleme
# ============================================================

def _is_blue_win(r: DuelResult) -> bool:
    return r.outcome == "galibiyet"


def seat_balance(results: list[DuelResult]) -> dict:
    """KOLTUK DENGESI: ayni model iki tarafta da oynadigi icin, KARAR
    VERILEN (galibiyet+maglubiyet) angajmanlarda mavinin payi ~%50 olmali.
    Beraberlikler (muhimmatsiz/zaman asimi) HARIC tutulur -- tum kosularin
    kazanma orani %50'yi icermek ZORUNDA DEGIL (ilk oz-denetim kriteri bu
    yuzden kusurluydu). Sonuc %50'den anlamli saparsa OLCUM ARACI taraf
    tutuyor demektir (ilk tam kosuda tam bu cikti: senaryo uretecinde mavi
    hep burnu rakibe donuk basliyordu)."""
    w = sum(1 for r in results if r.outcome == "galibiyet")
    l = sum(1 for r in results if r.outcome == "maglubiyet")
    n = w + l
    lo, hi = wilson_interval(w, n)
    return dict(wins=w, losses=l, decisive=n, blue_share=(w / n if n else 0.5),
                ci95=(lo, hi), balanced=(lo <= 0.5 <= hi))


def gate_report(results: list[DuelResult]) -> dict:
    """KAPI RAPORU (EVAL-04 incelemesi): (1) kapi kac savasta BAGLADI -- 25 nmi
    kapisi ayrim 25-40 nmi'den cekildigi icin bazi senaryolarda hicbir sey
    yapmaz; N/n bilinmeden 200 senaryo uzerinden hesaplanan fark SEYRELMIS
    olabilir. (2) Kapinin asil riski: BEKLERKEN VURULMAK. 'Hic atamadan oldu'
    sayaci, kapi bagliyken (kapi yuzunden gec kalma ADAYI) ve kapidan bagimsiz
    (ornegin kilit hic kurulmadi) olarak ikiye ayrilir. Kirmizi icin de ayni
    sayac -- kapisiz taraf temel oran (baseline) olur."""
    out = {}
    for side in ("blue", "red"):
        def blocked(r, side=side):
            return getattr(r, f"gate_blocked_ticks_{side}") > 0
        died_unfired = [r for r in results
                        if not getattr(r, f"{side}_alive") and getattr(r, f"{side}_fired") == 0]
        out[side] = dict(
            n=len(results),
            bound=sum(1 for r in results if blocked(r)),
            died_unfired=len(died_unfired),
            died_unfired_gate_bound=sum(1 for r in died_unfired if blocked(r)),
        )
    return out


def gate_bound_seeds(results: list[DuelResult]) -> set[int]:
    """Kapinin (herhangi bir tarafta, herhangi bir aynada) bagladigi senaryo tohumlari."""
    return {r.scenario_seed for r in results
            if r.gate_blocked_ticks_blue > 0 or r.gate_blocked_ticks_red > 0}


def restrict_to_seeds(results: list[DuelResult], seeds: set[int]) -> list[DuelResult]:
    return [r for r in results if r.scenario_seed in seeds]


def side_missile_outcomes(results: list[DuelResult]) -> dict:
    """ATAN TARAF bazinda fuze sonlanma NEDENLERI (pooled). EVAL-05 hipotezi: rakibi erken
    kacisa zorlamak, rakibin KENDI fuzesinin kilidini sarsiyor (kor). Bunu ayirt eden sayilar:
    her tarafin fuzelerinin kacinin isabet/kor/hedefsiz/tukenme/iska ile bittigi. Atis - toplam
    sonlanan = kosu bittiginde HALA UCAN fuzeler (savas erken bittigi icin)."""
    out = {}
    for side in ("blue", "red"):
        fired = sum(getattr(r, f"{side}_fired") for r in results)
        d = dict(fired=fired, isabet=sum(getattr(r, f"{side}_hits") for r in results))
        for k in ("kor", "hedefsiz", "iska", "tukenme"):
            d[k] = sum(getattr(r, f"{side}_{k}_count") for r in results)
        d["havada"] = fired - d["isabet"] - d["kor"] - d["hedefsiz"] - d["iska"] - d["tukenme"]
        out[side] = d
    return out


def side_efficiency(results: list[DuelResult]) -> dict:
    """TARAF BAZLI atis verimi. Asimetrik kolda AYNI savaslar icinde mavi
    (kapili) ile kirmizi (35 nmi) karsilastirilir -- kapinin MEKANIZMASINI
    (atis basina isabet, ilk atis menzili) gosterir; kazanma orani ise
    kumelenmis eslesmis testte. Pooled oranlar (savas basina oran ortalamasi
    DEGIL -- summarize_arm'daki shots_per_hit dersi)."""
    out = {}
    for side in ("blue", "red"):
        fired = sum(getattr(r, f"{side}_fired") for r in results)
        hits = sum(getattr(r, f"{side}_hits") for r in results)
        ranges = [getattr(r, f"first_shot_range_{side}_nm") for r in results
                  if getattr(r, f"first_shot_range_{side}_nm") is not None]
        out[side] = dict(fired=fired, hits=hits, hit_per_shot=(hits / fired if fired else 0.0),
                         mean_first_shot_nm=(float(np.mean(ranges)) if ranges else float("nan")))
    return out


def summarize_arm(results: list[DuelResult]) -> dict:
    n = len(results)
    wins = sum(1 for r in results if _is_blue_win(r))
    lo, hi = wilson_interval(wins, n)
    outcome_counts = {}
    for r in results:
        outcome_counts[r.outcome] = outcome_counts.get(r.outcome, 0) + 1
    return dict(
        n=n, wins=wins, win_rate=wins / n if n else 0.0, ci95=(lo, hi),
        outcome_counts=outcome_counts,
        mean_kor=float(np.mean([r.kor_count for r in results])) if n else 0.0,
        mean_hedefsiz=float(np.mean([r.hedefsiz_count for r in results])) if n else 0.0,
        # POOLED oran: toplam atis / toplam isabet. (Ilk surumde her savasin
        # atis/max(isabet,1) orani ortalanmisti -- isabetsiz savaslar orani sisiriyordu.)
        shots_per_hit=(sum(r.blue_fired + r.red_fired for r in results)
                        / max(sum(r.blue_hits + r.red_hits for r in results), 1)) if n else 0.0,
        # nz: proje sozlesmesi duz ucus=+1. nz_min = negatif-g yonu (izleme
        # listesi esigi -4.8 g), nz_max = tepe +g cekisi.
        nz_min_worst=float(min([min(r.nz_min_blue, r.nz_min_red) for r in results])) if n else 0.0,
        nz_max_worst=float(max([max(r.nz_max_blue, r.nz_max_red) for r in results])) if n else 0.0,
        mean_wall_time_s=float(np.mean([r.wall_time_s for r in results])) if n else 0.0,
    )


def compare_arms(results_a: list[DuelResult], results_b: list[DuelResult],
                  label_a: str, label_b: str) -> dict:
    """McNemar -- results_a/results_b AYNI (seed, mirrored) sirasiyla
    ESLESMIS olmali (build_tasks + run_tasks bunu garanti eder, sirayi
    BOZMA)."""
    assert len(results_a) == len(results_b)
    b = sum(1 for ra, rb in zip(results_a, results_b) if _is_blue_win(ra) and not _is_blue_win(rb))
    c = sum(1 for ra, rb in zip(results_a, results_b) if _is_blue_win(rb) and not _is_blue_win(ra))
    p = mcnemar_p_value(b, c)
    return dict(label_a=label_a, label_b=label_b, discordant_a_only=b, discordant_b_only=c,
                concordant=len(results_a) - b - c, p_value=p)


def compare_arms_clustered(results_a: list[DuelResult], results_b: list[DuelResult],
                            label_a: str, label_b: str) -> dict:
    """SENARYO DUZEYINDE KUMELENMIS eslesmis test -- ASIL karar bu.

    NEDEN: bir senaryonun NORMAL ve AYNALI kosusu BAGIMSIZ DEGIL (ayni tohum:
    ayni yakit/irtifa/Mach/turbulans buyuklukleri, sadece yon isaretleri
    farkli). `compare_arms` (McNemar, kosu duzeyinde) 2n cifti bagimsiz sayar,
    oysa n senaryo var -- p-degeri iyimser cikar. Burada her senaryo TEK
    gozlem: senaryonun kollardaki galibiyet SAYISI (ayna dahil) kiyaslanir;
    hangi kol daha cok kazandiysa o senaryo o kolun lehine sayilir, esit
    olanlar (uyumlu) bilgi tasimaz. Sonra ayni kesin binom testi.
    (Ilk tam kosuda: kosu-duzeyi p=0.029, kumelenmis p=0.023 -- karar ayni
    kaldi, ama bunu bilmek icin hesaplamak gerekiyordu.)"""
    wins_a: dict[int, int] = {}
    wins_b: dict[int, int] = {}
    for r in results_a:
        wins_a[r.scenario_seed] = wins_a.get(r.scenario_seed, 0) + int(_is_blue_win(r))
    for r in results_b:
        wins_b[r.scenario_seed] = wins_b.get(r.scenario_seed, 0) + int(_is_blue_win(r))
    assert wins_a.keys() == wins_b.keys(), "iki kol ayni tohum kumesini kosturmus olmali"
    a_only = sum(1 for s in wins_a if wins_a[s] > wins_b[s])
    b_only = sum(1 for s in wins_a if wins_b[s] > wins_a[s])
    return dict(label_a=label_a, label_b=label_b, n_clusters=len(wins_a),
                discordant_a_only=a_only, discordant_b_only=b_only,
                concordant=len(wins_a) - a_only - b_only,
                p_value=mcnemar_p_value(a_only, b_only))


def compare_arms_clustered_metric(results_a: list[DuelResult], results_b: list[DuelResult],
                                   label_a: str, label_b: str, metric) -> dict:
    """Sayisal bir metrik icin SENARYO DUZEYINDE kumelenmis isaret testi. `metric(r)` -> sayi
    (ornegin r.blue_hits + r.red_hits). Her senaryo icin metrik ayna kopyalari uzerinden TOPLANIR;
    A'nin toplami B'ninkinden buyukse senaryo A lehine, kucukse B lehine sayilir, esitler bilgi
    tasimaz. Sonra ayni kesin binom testi (compare_arms_clustered ile ayni mantik, ikili kazanma
    yerine sayisal metrik -- galibiyet gibi ikili bir sonuc, 'isabet sayisi'ni yakalamaz)."""
    tot_a: dict[int, float] = {}
    tot_b: dict[int, float] = {}
    for r in results_a:
        tot_a[r.scenario_seed] = tot_a.get(r.scenario_seed, 0) + metric(r)
    for r in results_b:
        tot_b[r.scenario_seed] = tot_b.get(r.scenario_seed, 0) + metric(r)
    assert tot_a.keys() == tot_b.keys(), "iki kol ayni tohum kumesini kosturmus olmali"
    a_more = sum(1 for s in tot_a if tot_a[s] > tot_b[s])
    b_more = sum(1 for s in tot_a if tot_b[s] > tot_a[s])
    return dict(label_a=label_a, label_b=label_b, n_clusters=len(tot_a),
                total_a=sum(tot_a.values()), total_b=sum(tot_b.values()),
                a_more=a_more, b_more=b_more, tied=len(tot_a) - a_more - b_more,
                p_value=mcnemar_p_value(a_more, b_more))


def total_hits(r: DuelResult) -> int:
    """Bir savasta iki tarafin TOPLAM isabeti (gate-sym birincil olcutu, EVAL-06)."""
    return r.blue_hits + r.red_hits


def duel_net_score(r: DuelResult) -> int:
    """MAVI net skor (EVAL-11 birincili): galibiyet +1, magnubiyet -1, digerleri 0 (karsilikli imha,
    sonucsuz dahil). Hem kazanmayi hem HAYATTA KALMAYI tek olcutte yakalar -- kacis politikasi
    esas olarak hayatta kalmayi degistirir (EVAL-05: kazanma ~ayni, kayip +%30 idi)."""
    return 1 if r.outcome == "galibiyet" else (-1 if r.outcome == "maglubiyet" else 0)


def duel_had_kill(r: DuelResult) -> int:
    """Savas EN AZ BIR isabetle bitti mi (0/1)? SANSURE DUYARSIZ olcut (EVAL-09 birincili): kacis
    olmayinca duello erken biter ve kalan fuzeler sonuclanmadan kesilir -- 'tukenme payi' ya da
    isabet SAYISI bu yuzden yanilticidir; 'kill oldu mu' sorusu degil."""
    return int(r.blue_hits + r.red_hits > 0)


def scenario_csv_fields(seed: int, mirrored: bool) -> dict:
    """CSV'ye yazilacak senaryo parametreleri. Tohumdan TAM olarak yeniden
    uretilebiliyor, ama her analizde yeniden uretmek zorunda kalmamak icin
    (ve analizin sahte bir 'mesafe dilimi' hesabina dayanmamasi icin) hazir
    yaziyoruz. `scn_` oneki DuelResult sutunlariyla cakismayi onler."""
    scn = generate_scenario(seed)
    if mirrored:
        scn = mirror_scenario(scn)
    ata_blue, ata_red = initial_ata_deg(scn)
    fields = {f"scn_{k}": v for k, v in asdict(scn).items() if k not in ("seed", "mirrored")}
    fields["scn_initial_ata_blue_deg"] = ata_blue
    fields["scn_initial_ata_red_deg"] = ata_red
    return fields


# ============================================================
# Oz-denetim (HIZLI, --self-check ile kosar, kullanici onayi gerekmez)
# ============================================================

def self_check(model_path: str, workers: int, n_seeds: int = 10) -> bool:
    print(f"model: {model_path}")
    print(f"oz-denetim: {n_seeds} tohum x 2 (ayna) x 2 (kol) = {n_seeds * 4} kosu\n")
    ok = True

    # 1) Tekrar uretilebilirlik -- AYNI (seed, mirrored, mode) IKI KEZ.
    #    NOT: DuelResult.wall_time_s duvar-saati gercek suresidir, ASLA
    #    iki kosuda ayni cikmaz -- karsilastirmadan ONCE 0'a esitlenir,
    #    yoksa bu kontrol HER ZAMAN (yanlislikla) basarisiz olur.
    seeds = list(range(n_seeds))
    task0 = (seeds[0], False, RWR_ARM)
    r1 = run_tasks(model_path, [task0], workers=1)[0]
    r2 = run_tasks(model_path, [task0], workers=1)[0]
    r1z = dataclasses.replace(r1, wall_time_s=0.0)
    r2z = dataclasses.replace(r2, wall_time_s=0.0)
    reproducible = r1z == r2z
    ok &= reproducible
    print(f"[{'PASS' if reproducible else 'FAIL'}] tekrar uretilebilirlik: "
          f"ayni tohum iki kez -> {'birebir ayni' if reproducible else 'FARKLI (bkz. seed kaynaklari)'}")

    # 2) KOLTUK SIMETRISI -- GEOMETRI (simulasyonsuz, aninda, KESKIN): iki
    #    tarafin baslangic |ATA| dagilimi ozdes olmali. (Ilk surumde mavi
    #    ort. 8.6 derece, kirmizi 30.3 derece cikti -- bu kontrol o gun
    #    olsaydi hatayi simulasyon calistirmadan yakalardi.)
    geo = [initial_ata_deg(generate_scenario(sd)) for sd in range(5000)]
    mean_blue = float(np.mean([g[0] for g in geo]))
    mean_red = float(np.mean([g[1] for g in geo]))
    geo_ok = abs(mean_blue - mean_red) / max(mean_blue, mean_red) < 0.05
    ok &= geo_ok
    print(f"[{'PASS' if geo_ok else 'FAIL'}] koltuk simetrisi (geometri, 5000 tohum): "
          f"baslangic |ATA| mavi ort={mean_blue:.1f} deg, kirmizi ort={mean_red:.1f} deg "
          f"(fark <%5 olmali)")

    # 3) KOLTUK DENGESI -- SONUCLAR (simulasyonlu): karar verilenlerde mavi
    #    payi ~%50. Kucuk n'de GA genis, bu kontrol ANCAK buyuk n'de keskin --
    #    burada bilgi amacli; asil sinav tam kosunun raporunda.
    tasks_normal = [(s_, False, RWR_ARM) for s_ in seeds]
    tasks_mirror = [(s_, True, RWR_ARM) for s_ in seeds]
    res_normal = run_tasks(model_path, tasks_normal, workers=workers)
    res_mirror = run_tasks(model_path, tasks_mirror, workers=workers)
    sb = seat_balance(res_normal + res_mirror)
    print(f"[{'PASS' if sb['balanced'] else 'UYARI'}] koltuk dengesi (sonuc): karar verilen "
          f"{sb['decisive']} angajmanda mavi payi {sb['blue_share']:.2f} "
          f"(%95 GA [{sb['ci95'][0]:.2f}, {sb['ci95'][1]:.2f}], 0.5 icermeli)")
    print(f"      not: n={n_seeds} kucuk bir oz-denetim ornegi -- bu GA genis, sonuc-tabanli "
          f"kontrol ancak --n 200'de keskin.")

    # 4) Zaman asimi orani ~%100 DEGIL (senaryolar gercekten sonuclaniyor mu)
    all_results = res_normal + res_mirror
    timeout_rate = sum(1 for r in all_results if r.outcome == "zaman_asimi") / len(all_results)
    not_all_timeout = timeout_rate < 0.90
    ok &= not_all_timeout
    print(f"[{'PASS' if not_all_timeout else 'FAIL'}] zaman asimi orani: {timeout_rate:.0%} "
          f"(<%90 olmali -- senaryolarin coğu gercekten bir sonuca ULASMALI)")

    print(f"\nSONUC: {'TUM OZ-DENETIMLER GECTI' if ok else 'EN AZ BIR OZ-DENETIM SORUNLU -- once bunu incele'}")
    return ok


# ============================================================
# CLI
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--n", type=int, default=200, help="senaryo (tohum) sayisi")
    ap.add_argument("--seed-start", type=int, default=1000,
                     help="tohumlar bu degerden baslar (crank_sweep/pursuit_cost/self-check "
                          "ile kullanilan kucuk tohumlarla CAKISMASIN diye varsayilan yuksek)")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--no-mirror", action="store_true",
                     help="Aynalamayi ATLA -- SADECE hizli deneme icin, istatistiksel karar icin KULLANMA")
    ap.add_argument("--self-check", action="store_true",
                     help="Hizli oz-denetim (10 tohum, ~40 kosu) -- UZUN KOSU DEGIL, onay gerekmez")
    ap.add_argument("--csv", type=str, default=None, help="Ham sonuclari CSV'ye yaz")
    ap.add_argument("--experiment", choices=("warning", "gate", "gate-sym", "evade-diag", "evade-delay"), default="warning",
                     help="warning: truth vs rwr (EVAL-03, varsayilan). gate: A=35v35 referans, "
                          "B=mavi --gate-nm / kirmizi 35 (ASIMETRIK, EVAL-04). Kollar AYNI kosuda, "
                          "AYNI kod surumuyle sifirdan kosulur (eski CSV satirlari kullanilmaz). "
                          "gate-sym: A=35v35, C=iki taraf da --gate-nm (SIMETRIK, EVAL-06; TAZE tohum kullan). "
                          "evade-diag: C=rwr kacis, N=HIC kacis yok, ikisi de --gate-nm (TANI, EVAL-09; TAZE tohum). "
                          "evade-delay: A=mevcut kacis, B=mavi kacisi --evade-delay-s gecikmeli (EVAL-11; TAZE tohum).")
    ap.add_argument("--evade-delay-s", type=float, default=PRIMARY_EVADE_DELAY_S,
                     help="evade-delay deneyinde MAVI kacisinin kilit-tetikleyici gecikmesi (s). Onceden "
                          "sabitlenmis aile: 15 ve inf (yalniz fuze); baska deger KESIF.")
    ap.add_argument("--gate-nm", type=float, default=PRIMARY_GATE_NM,
                     help=f"gate deneyinde mavinin atis kapisi. ONCEDEN SABITLENMIS birincil deger "
                          f"{PRIMARY_GATE_NM:g}; baska deger KESIF sayilir (p-hacking onlemi).")
    args = ap.parse_args()

    if args.self_check:
        ok = self_check(args.model, workers=args.workers)
        sys.exit(0 if ok else 1)

    # --- TAM DEGERLENDIRME: UZUN KOSU SINIFI ---
    print("UYARI: bu tam degerlendirme bir 'uzun kosu'dur (n=200 icin ~800 kosu).")
    print("Kullanicinin acik onayi olmadan BURADAN baslatilmamalidir.")
    print("Onay verildiyse: python -m scripts.eval_commander <model.zip> --n 200 --workers N\n")

    arm_a, arm_b = experiment_arms(args.experiment, args.gate_nm, args.evade_delay_s)
    if args.experiment == "evade-delay" and args.evade_delay_s not in PRE_REGISTERED_EVADE_DELAYS:
        print(f"!! KESIF KOSUSU: gecikme={args.evade_delay_s:g} s onceden sabitlenmis aile {PRE_REGISTERED_EVADE_DELAYS} "
              f"disinda. Bonferroni esigi bu aile icindir; bu sonucu 'birincil bulgu' diye raporlama.\n")
    if args.experiment in ("gate", "gate-sym", "evade-diag") and args.gate_nm != PRIMARY_GATE_NM:
        print(f"!! KESIF KOSUSU: kapi={args.gate_nm:g} nmi onceden sabitlenmis birincil deger "
              f"({PRIMARY_GATE_NM:g}) DEGIL. Birden cok deger denenirse p-degerleri duzeltmesiz "
              f"yorumlanamaz -- bu sonucu 'birincil bulgu' diye raporlama.\n")

    seeds = list(range(args.seed_start, args.seed_start + args.n))
    if args.experiment in ("gate-sym", "evade-diag", "evade-delay") and overlaps_seen_seeds(seeds):
        print("!! UYARI: bu tohumlar onceki deneylerde GORULDU (1000-1199, 2000-2199, 3000-3199, 4000-4199). Bu deney o verilerin "
              "dogurdugu YENI bir hipotezi sinar -- ayni senaryolarla kosarsan ayni veriye ikinci kez bakmis "
              "olursun. Taze tohum kullan: --seed-start 5000\n")
    include_mirror = not args.no_mirror
    total_per_arm = args.n * (2 if include_mirror else 1)
    print(f"model: {args.model}")
    print(f"deney={args.experiment}  kol A={arm_a.label}  kol B={arm_b.label}")
    print(f"n={args.n} tohum, ayna={'evet' if include_mirror else 'hayir'}, "
          f"kol basina {total_per_arm} kosu, toplam {total_per_arm * 2} kosu, "
          f"{args.workers} worker")

    t0 = time.perf_counter()
    tasks_a = build_tasks(seeds, (arm_a,), include_mirror)
    tasks_b = build_tasks(seeds, (arm_b,), include_mirror)
    # AYNI SIRA korunmali (eslestirme buna dayanir) -- iki ayri run_tasks
    # cagrisi worker init'ini iki kez yapar ama sira karisikligi RISKINI
    # sifira indirir; maliyeti toplam kosu suresine gore ihmal edilebilir.
    results_a = run_tasks(args.model, tasks_a, workers=args.workers)
    results_b = run_tasks(args.model, tasks_b, workers=args.workers)
    elapsed = time.perf_counter() - t0

    if args.csv:
        import csv
        os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            rows = []
            for arm, results in ((arm_a, results_a), (arm_b, results_b)):
                for r in results:
                    row = {"arm": arm.label}
                    row.update(asdict(r))
                    row.update(scenario_csv_fields(r.scenario_seed, r.mirrored))
                    rows.append(row)
            fields = list(rows[0].keys())
            w.writerow(fields)
            for row in rows:
                w.writerow([row[k] for k in fields])
        print(f"Ham sonuclar yazildi: {args.csv}")

    cmp_run = compare_arms(results_a, results_b, arm_a.label, arm_b.label)
    cmp_ = compare_arms_clustered(results_a, results_b, arm_a.label, arm_b.label)

    print(f"\n== SONUC ({elapsed:.1f}s, {elapsed/max(len(tasks_a)+len(tasks_b),1):.2f}s/kosu) ==")
    for arm, results in ((arm_a, results_a), (arm_b, results_b)):
        s_ = summarize_arm(results)
        print(f"[{arm.label}] n={s_['n']}  kazanma={s_['win_rate']:.3f} "
              f"(%95 GA [{s_['ci95'][0]:.3f}, {s_['ci95'][1]:.3f}])  "
              f"kor={s_['mean_kor']:.2f} hedefsiz={s_['mean_hedefsiz']:.2f} "
              f"atis/isabet={s_['shots_per_hit']:.1f}")
        print(f"        nz: en kotu negatif-g={s_['nz_min_worst']:+.2f} (izleme esigi -4.8), "
              f"tepe +g cekisi={s_['nz_max_worst']:+.2f}")
        sb = seat_balance(results)
        if arm.symmetric:
            flag = "OK" if sb["balanced"] else "UYARI -- OLCUM ARACI TARAF TUTUYOR, sonuclara guvenme"
        else:
            flag = ("ASIMETRIK KOL -- ~0.5 BEKLENMEZ (mavi bilerek farkli oynuyor); "
                    "burada mavi payinin yukselmesi kapinin etkisidir, olcum onyargisi degil")
        print(f"        koltuk dengesi: karar verilen {sb['decisive']}, mavi payi {sb['blue_share']:.2f} "
              f"(%95 GA [{sb['ci95'][0]:.2f}, {sb['ci95'][1]:.2f}]) -> {flag}")
        eff = side_efficiency(results)
        print(f"        atis verimi: mavi {eff['blue']['fired']} atis/{eff['blue']['hits']} isabet "
              f"(%{100*eff['blue']['hit_per_shot']:.1f}, ilk atis ort. {eff['blue']['mean_first_shot_nm']:.1f} nmi)  |  "
              f"kirmizi {eff['red']['fired']} atis/{eff['red']['hits']} isabet "
              f"(%{100*eff['red']['hit_per_shot']:.1f}, ilk atis ort. {eff['red']['mean_first_shot_nm']:.1f} nmi)")
        gr = gate_report(results)
        gb, gr_red = gr["blue"], gr["red"]
        print(f"        kapi: mavi {gb['bound']}/{gb['n']} savasta BAGLADI, kirmizi {gr_red['bound']}/{gr_red['n']}  |  "
              f"HIC ATAMADAN OLEN: mavi {gb['died_unfired']} (kapi bagliyken {gb['died_unfired_gate_bound']} = "
              f"gec-kalma ADAYI, kapidan bagimsiz {gb['died_unfired'] - gb['died_unfired_gate_bound']}), "
              f"kirmizi {gr_red['died_unfired']} (temel oran)")
        print(f"        kacis (evade) suresi, savas basina ort.: mavi {sum(r.evade_ticks_blue for r in results) / max(len(results), 1) * 0.1:.1f} s, "
              f"kirmizi {sum(r.evade_ticks_red for r in results) / max(len(results), 1) * 0.1:.1f} s")
        mo = side_missile_outcomes(results)
        for side, lab in (("blue", "mavi"), ("red", "kirmizi")):
            m = mo[side]
            print(f"        fuze sonu ({lab}, {m['fired']} atis): isabet {m['isabet']}  kor {m['kor']}  "
                  f"hedefsiz {m['hedefsiz']}  tukenme {m['tukenme']}  iska {m['iska']}  havada-kaldi {m['havada']}")
        print(f"        sonuc dagilimi: {s_['outcome_counts']}")

    tag = ("IKINCIL (bu deneyde birincil olcut DEGIL; birincil olcut asagidaki BIRINCIL satirinda)"
           if args.experiment in ("gate-sym", "evade-diag") else "ASIL KARAR")
    print(f"\nESLESMIS TEST -- {tag}: senaryo duzeyinde kumelenmis "
          f"({cmp_['n_clusters']} senaryo, ayna cifti TEK gozlem): "
          f"{arm_a.label}-ustun={cmp_['discordant_a_only']}  {arm_b.label}-ustun={cmp_['discordant_b_only']}  "
          f"esit={cmp_['concordant']}  p={cmp_['p_value']:.4f}")
    print(f"  (bilgi: kosu duzeyinde McNemar, {len(results_a)} cift bagimsiz varsayilarak -- "
          f"IYIMSER olabilir: {arm_a.label}-only={cmp_run['discordant_a_only']} "
          f"{arm_b.label}-only={cmp_run['discordant_b_only']} uyumlu={cmp_run['concordant']} "
          f"p={cmp_run['p_value']:.4f})")
    print("  (not: yukaridaki kazanma orani GA'lari da kosulari bagimsiz sayar; "
          "ayna ciftleri iliskili oldugu icin hafif dardir -- KARAR icin yukaridaki eslesmis testi kullan.)")
    primary_p = cmp_["p_value"]
    alpha = 0.05
    if args.experiment == "evade-delay":
        c_net = compare_arms_clustered_metric(results_a, results_b, arm_a.label, arm_b.label, duel_net_score)
        wl = lambda rs: (sum(r.outcome == "galibiyet" for r in rs), sum(r.outcome == "maglubiyet" for r in rs))
        (wa, la), (wb, lb) = wl(results_a), wl(results_b)
        print(f"\nBIRINCIL (evade-delay, EVAL-11): MAVI NET SKOR (galibiyet +1, magnubiyet -1), senaryo-kumelenmis "
              f"isaret testi, Bonferroni esigi {EVADE_ALPHA} (iki karsilastirma ailesi):")
        print(f"   {arm_a.label}: galibiyet {wa} / mag. {la} (net {wa - la:+d})   {arm_b.label}: galibiyet {wb} / mag. {lb} (net {wb - lb:+d})")
        print(f"   {arm_a.label}-ustun={c_net['a_more']}  {arm_b.label}-ustun={c_net['b_more']}  esit={c_net['tied']}  "
              f"p={c_net['p_value']:.4f}  ({'ESIGI GECTI' if c_net['p_value'] < EVADE_ALPHA else 'esigi GECMEDI'})")
        primary_p = c_net["p_value"]
        alpha = EVADE_ALPHA
    if args.experiment == "gate-sym":
        hits = total_hits
        stale = lambda r: int(r.outcome == "muhimmatsiz")
        c_hits = compare_arms_clustered_metric(results_a, results_b, arm_a.label, arm_b.label, hits)
        c_stale = compare_arms_clustered_metric(results_a, results_b, arm_a.label, arm_b.label, stale)
        shots = lambda rs: sum(r.blue_fired + r.red_fired for r in rs)
        print(f"\nBIRINCIL (gate-sym, EVAL-06): senaryo basina TOPLAM ISABET (mavi+kirmizi, ayna dahil), "
              f"{c_hits['n_clusters']} senaryo, kumelenmis isaret testi:")
        print(f"   toplam isabet: {arm_a.label}={c_hits['total_a']:.0f}  {arm_b.label}={c_hits['total_b']:.0f}  |  "
              f"atis basina isabet (pooled): {arm_a.label} %{100*c_hits['total_a']/max(shots(results_a),1):.1f}  "
              f"{arm_b.label} %{100*c_hits['total_b']/max(shots(results_b),1):.1f}")
        print(f"   {arm_a.label}-ustun={c_hits['a_more']}  {arm_b.label}-ustun={c_hits['b_more']}  "
              f"esit={c_hits['tied']}  p={c_hits['p_value']:.4f}")
        print(f"IKINCIL: sonucsuz (muhimmatsiz) savas sayisi: {arm_a.label}={c_stale['total_a']:.0f}  "
              f"{arm_b.label}={c_stale['total_b']:.0f}  (senaryo bazli: {arm_a.label}-cok={c_stale['a_more']} "
              f"{arm_b.label}-cok={c_stale['b_more']} esit={c_stale['tied']} p={c_stale['p_value']:.4f})")
        n_bound = len(gate_bound_seeds(results_b))
        print(f"KAPI: {n_bound}/{len(seeds)} senaryoda en az bir tik BAGLADI (%{100 * n_bound / max(len(seeds), 1):.0f}).")
        primary_p = c_hits["p_value"]
    if args.experiment == "evade-diag":
        # BIRINCIL: en az bir isabetle biten savas (SANSURE DUYARSIZ -- kacis olmayinca duello erken biter,
        # kalan fuzeler sonuclanmadan kesilir; tukenme PAYI bu yuzden tek basina yanilticidir).
        killed = duel_had_kill
        c_kill = compare_arms_clustered_metric(results_a, results_b, arm_a.label, arm_b.label, killed)
        n_a, n_b = int(c_kill["total_a"]), int(c_kill["total_b"])
        tot = len(results_a)
        print(f"\nBIRINCIL (evade-diag, EVAL-09): EN AZ BIR ISABETLE BITEN SAVAS ORANI (sansure duyarsiz), "
              f"{c_kill['n_clusters']} senaryo, kumelenmis isaret testi:")
        print(f"   {arm_a.label}: {n_a}/{tot} (%{100*n_a/max(tot,1):.1f})   {arm_b.label}: {n_b}/{tot} (%{100*n_b/max(tot,1):.1f})   "
              f"|  {arm_a.label}-ustun={c_kill['a_more']}  {arm_b.label}-ustun={c_kill['b_more']}  esit={c_kill['tied']}  p={c_kill['p_value']:.4f}")
        for lab, rs in ((arm_a.label, results_a), (arm_b.label, results_b)):
            hits_t = [r.first_hit_t for r in rs if r.first_hit_t is not None]
            print(f"   {lab}: ilk isabet zamani ort. {sum(hits_t)/max(len(hits_t),1):.1f} s (n={len(hits_t)});  "
                  f"toplam atis {sum(r.blue_fired + r.red_fired for r in rs)}")
        primary_p = c_kill["p_value"]
    if args.experiment == "gate":
        bound = gate_bound_seeds(results_b)
        print(f"\nKAPI ETKI BUYUKLUGU: kapi {len(bound)}/{len(seeds)} senaryoda en az bir tik BAGLADI "
              f"(%{100 * len(bound) / max(len(seeds), 1):.0f}); geri kalan senaryolarda kapi hicbir sey yapmadi, "
              f"yukaridaki birincil fark bu oranda SEYRELMISTIR.")
        if bound:
            cmp_sub = compare_arms_clustered(restrict_to_seeds(results_a, bound),
                                              restrict_to_seeds(results_b, bound),
                                              arm_a.label, arm_b.label)
            print(f"  IKINCIL/KESIF -- yalniz kapinin bagladigi {cmp_sub['n_clusters']} senaryo: "
                  f"{arm_a.label}-ustun={cmp_sub['discordant_a_only']}  {arm_b.label}-ustun={cmp_sub['discordant_b_only']}  "
                  f"esit={cmp_sub['concordant']}  p={cmp_sub['p_value']:.4f}")
            print("  (uyari: 'bagladi' kosul-sonrasi bir degisken -- kilit zamanlamasina/yorungeye bagli. "
                  "Bu satir ETKI BUYUKLUGUNU yorumlamak icindir, birincil karar DEGIL.)")
    if primary_p < alpha:
        print(f"YORUM: iki kol arasindaki BIRINCIL olcut farki istatistiksel olarak anlamli (p<{alpha}).")
    else:
        print("YORUM: iki kol arasinda anlamli bir fark GOSTERILEMEDI (p>=0.05) -- "
              "ORNEKLEM buyutulmeli ya da etki yok/kucuk.")


if __name__ == "__main__":
    main()
