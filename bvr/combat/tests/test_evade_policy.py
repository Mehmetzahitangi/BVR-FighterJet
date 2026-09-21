"""
bvr/combat/tests/test_evade_policy.py

EVAL-11: RWR kacisinin 'kilit' tetikleyicisi GECIKMELI (age_s tabanli). Karar mantigi saf bir
fonksiyona (`should_evade`) cikarildi ki simulasyonsuz sinansin; yanlis uygulanirsa
(gecikme fuzeye de uygulanir, esik sinirinda kayar, inf yine kilitte kacar...) deney sonucu cope gider.
"""
import os
from types import SimpleNamespace

import pytest

from bvr.combat.duel import DuelScenario, run_duel, should_evade
from scripts.eval_commander import (
    ArmSpec, PRIMARY_EVADE_DELAY_S, PRE_REGISTERED_EVADE_DELAYS, EVADE_ALPHA, experiment_arms, duel_net_score,
)

MODEL_PATH = "runs/reward_r3_both/sac_1999968_steps.zip"
needs_model = pytest.mark.skipif(not os.path.exists(MODEL_PATH), reason="dondurulmus SAC modeli yok")

SMOKE = DuelScenario(
    seed=0, separation_nm=30.0, aspect_deg=0.0, lateral_offset_nm=0.0,
    alt_blue_ft=25000.0, alt_red_ft=25000.0, mach_blue=0.9, mach_red=0.9,
    fuel_blue=0.75, fuel_red=0.75, turb_blue_fps=0.0, turb_red_fps=0.0,
    turb_blue_dir_deg=0.0, turb_red_dir_deg=0.0,
)
SHORT_S = 40.0


def _t(kind, age):
    return SimpleNamespace(kind=kind, age_s=age)


# ------------------------------------------------------------------ saf mantik
def test_1_should_evade_eski_davranis_gecikme_sifir():
    # delay=0 (varsayilan) = eski: kilit veya fuze -> kac; arama/yok -> kacma.
    assert should_evade(None) is False
    assert should_evade(_t("arama", 99.0)) is False
    assert should_evade(_t("kilit", 0.0)) is True
    assert should_evade(_t("kilit", 5.0)) is True
    assert should_evade(_t("fuze", 0.0)) is True


def test_2_should_evade_kilit_gecikmeli_esik_dahil():
    assert should_evade(_t("kilit", 14.9), 15.0) is False
    assert should_evade(_t("kilit", 15.0), 15.0) is True            # esikte kac (>=)
    assert should_evade(_t("kilit", 40.0), 15.0) is True


def test_3_fuze_HER_ZAMAN_kacirir_gecikme_fuzeye_uygulanmaz():
    for d in (0.0, 15.0, float("inf")):
        assert should_evade(_t("fuze", 0.0), d) is True             # taze fuze bile


def test_4_inf_gecikme_yalniz_fuzede_kacar():
    inf = float("inf")
    assert should_evade(_t("kilit", 1e9), inf) is False             # hicbir yas yetmez
    assert should_evade(_t("fuze", 0.0), inf) is True
    assert should_evade(None, inf) is False


def test_5_evade_delay_kollari_asimetrik_onceden_sabit_aile():
    a, b = experiment_arms("evade-delay")
    assert a.symmetric and a.evade_delay_blue_s == 0.0 and a.evade_delay_red_s == 0.0
    # B: SADECE mavi gecikmeli (15 s, onceden sabit); kirmizi mevcut politika -> ASIMETRIK.
    assert not b.symmetric
    assert b.evade_delay_blue_s == PRIMARY_EVADE_DELAY_S == 15.0 and b.evade_delay_red_s == 0.0
    assert b.fire_gate_blue_nm is None and b.fire_gate_red_nm is None      # kapi YOK (gercek oyun)
    assert b.warning_mode == "rwr" and a.label != b.label
    _, binf = experiment_arms("evade-delay", evade_delay_s=float("inf"))
    assert binf.evade_delay_blue_s == float("inf") and "fuzeOnly" in binf.label
    assert PRE_REGISTERED_EVADE_DELAYS == (15.0, float("inf")) and EVADE_ALPHA == 0.025


def test_6_symmetric_gecikme_farkini_da_yakalar():
    assert ArmSpec("x", "rwr").symmetric
    assert ArmSpec("x", "rwr", evade_delay_blue_s=5.0, evade_delay_red_s=5.0).symmetric
    assert not ArmSpec("x", "rwr", evade_delay_blue_s=5.0).symmetric


def test_7_duel_net_score_isaretleri():
    r = lambda o: SimpleNamespace(outcome=o)
    assert duel_net_score(r("galibiyet")) == 1
    assert duel_net_score(r("maglubiyet")) == -1
    assert duel_net_score(r("karsilikli_imha")) == 0
    assert duel_net_score(r("muhimmatsiz")) == 0 and duel_net_score(r("zaman_asimi")) == 0


def test_8_gecikme_rwr_disi_modda_reddedilir_sessizce_yok_sayilmaz():
    for mode in ("none", "truth"):
        with pytest.raises(ValueError):
            run_duel(None, None, SMOKE, warning_mode=mode, evade_delay_s_blue=5.0)
        with pytest.raises(ValueError):
            run_duel(None, None, SMOKE, warning_mode=mode, evade_delay_s_red=5.0)


# ----------------------------------------------------------- simulasyonlu
@pytest.fixture(scope="module")
def cfg_model():
    from stable_baselines3 import SAC
    from bvr.config import load_experiment
    cfg = load_experiment(f"{os.path.dirname(MODEL_PATH)}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    return cfg, SAC.load(MODEL_PATH, device="cpu")


@needs_model
def test_9_varsayilan_gecikme_eski_davranisla_birebir_ve_inf_mavinin_kacisini_azaltir(cfg_model):
    import dataclasses
    cfg, model = cfg_model
    base = run_duel(cfg, model, SMOKE, duration_s=SHORT_S)
    zero = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, evade_delay_s_blue=0.0, evade_delay_s_red=0.0)
    vol = lambda r: dataclasses.replace(r, wall_time_s=0.0)
    assert vol(base) == vol(zero)                                    # 0.0 = eski davranis birebir
    fo = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, evade_delay_s_blue=float("inf"))
    assert fo.evade_ticks_blue < base.evade_ticks_blue               # yalniz fuzede kacan mavi daha az kacar
    assert fo.evade_delay_blue_s == float("inf") and fo.evade_delay_red_s == 0.0


@needs_model
def test_10_gecikme_YALNIZ_belirtilen_tarafi_etkiler(cfg_model):
    # Kirmizi gecikmeli, mavi normal: mavinin kacisi kirmizinin gecikmesinden bagimsiz ~ayni baslamali,
    # kirmizinin kacisi AZALMALI (yanlis tarafa uygulanmadi).
    cfg, model = cfg_model
    base = run_duel(cfg, model, SMOKE, duration_s=SHORT_S)
    r = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, evade_delay_s_red=float("inf"))
    assert r.evade_ticks_red < base.evade_ticks_red
    assert r.evade_delay_red_s == float("inf") and r.evade_delay_blue_s == 0.0


@needs_model
def test_11_eval_hatti_gecikmeyi_dogru_tarafa_tasir():
    # ArmSpec -> gorev -> _run_task -> run_duel zincirinde gecikme SESSIZCE dusmemeli ve tarafi
    # karismamali (M8 mutasyonu ilk denemede hayatta kaldi: kirmizinin gecikmesi mavininkinden turetiliyordu).
    from scripts.eval_commander import run_tasks
    inf = float("inf")
    arm = ArmSpec("B_test", "rwr", evade_delay_blue_s=inf)
    res = run_tasks(MODEL_PATH, [(2000, False, arm)], workers=1)[0]
    assert res.evade_delay_blue_s == inf and res.evade_delay_red_s == 0.0
    arm2 = ArmSpec("R_test", "rwr", evade_delay_red_s=7.0)
    res2 = run_tasks(MODEL_PATH, [(2000, False, arm2)], workers=1)[0]
    assert res2.evade_delay_red_s == 7.0 and res2.evade_delay_blue_s == 0.0
