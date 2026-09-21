"""
bvr/combat/tests/test_duel_gate.py

Faz 2.3 atis kapisi (EVAL-04) -- KOMUTANIN ek atis disiplini. Kapi yanlis
uygulanirsa (yanlis tarafa, hic uygulanmazsa, iki tarafa birden uygulanirsa)
4 dakikalik kosu degil, ondan cikan SONUC cope gider -- bu yuzden kosudan
ONCE burada kilitleniyor.

Simulasyonlu testler (JSBSim + dondurulmus SAC) model dosyasi yoksa ATLANIR;
saf mantik testleri (kol tanimi, gorev eslestirmesi) her zaman kosar.
"""
import dataclasses
import os
from types import SimpleNamespace

import pytest

from bvr.combat.duel import DuelScenario, generate_scenario, run_duel
from scripts.eval_commander import (
    ArmSpec, PRIMARY_GATE_NM, build_tasks, experiment_arms, run_tasks,
    gate_report, gate_bound_seeds, restrict_to_seeds,
    compare_arms_clustered_metric, overlaps_seen_seeds, total_hits, duel_had_kill,
)

MODEL_PATH = "runs/reward_r3_both/sac_1999968_steps.zip"
needs_model = pytest.mark.skipif(not os.path.exists(MODEL_PATH),
                                  reason="dondurulmus SAC modeli yok")

# 30 nmi burun buruna, kalabalik yok -- ilk atis ~29.25 nmi'de (kapisiz olculdu).
SMOKE = DuelScenario(
    seed=0, separation_nm=30.0, aspect_deg=0.0, lateral_offset_nm=0.0,
    alt_blue_ft=25000.0, alt_red_ft=25000.0, mach_blue=0.9, mach_red=0.9,
    fuel_blue=0.75, fuel_red=0.75, turb_blue_fps=0.0, turb_red_fps=0.0,
    turb_blue_dir_deg=0.0, turb_red_dir_deg=0.0,
)
SHORT_S = 40.0   # ilk atis birkac saniyede; kosuyu kisa tut


@pytest.fixture(scope="module")
def cfg_model():
    from stable_baselines3 import SAC
    from bvr.config import load_experiment
    cfg = load_experiment(f"{os.path.dirname(MODEL_PATH)}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    return cfg, SAC.load(MODEL_PATH, device="cpu")


def _without_volatile(r):
    # wall_time_s asla ayni cikmaz; kapi alanlari kasten farkli olabilir.
    return dataclasses.replace(r, wall_time_s=0.0, fire_gate_blue_nm=None, fire_gate_red_nm=None)


# ------------------------------------------------------------------ saf mantik
def test_1_gate_deneyi_kollari_asimetrik_ve_onceden_sabit():
    a, b = experiment_arms("gate")
    assert a.symmetric and a.fire_gate_blue_nm is None and a.fire_gate_red_nm is None
    # B: SADECE mavi kapili (25), kirmizi 35'te (kapi yok) -> ASIMETRIK.
    assert not b.symmetric
    assert b.fire_gate_blue_nm == PRIMARY_GATE_NM == 25.0
    assert b.fire_gate_red_nm is None
    assert a.label != b.label
    # Uyari deneyinde iki kol da simetrik ve kapisiz (eski davranis).
    for arm in experiment_arms("warning"):
        assert arm.symmetric and arm.fire_gate_blue_nm is None


def test_2_kollar_ayni_tohumlari_ayni_sirayla_kosar_CRN():
    a, b = experiment_arms("gate")
    ta = build_tasks([5, 6, 7], (a,), True)
    tb = build_tasks([5, 6, 7], (b,), True)
    assert [(s, m) for s, m, _ in ta] == [(s, m) for s, m, _ in tb]
    assert {arm for _, _, arm in ta} == {a} and {arm for _, _, arm in tb} == {b}
    assert len(ta) == 3 * 2                         # ayna dahil


# ------------------------------------------------------------- simulasyonlu
@needs_model
def test_3_kapi_Rmax_veya_ustunde_etkisiz(cfg_model):
    # 35 = LaunchRules.max_launch_nm: yetki zaten 35'te keser, ek kapi hicbir sey degistirmemeli.
    cfg, model = cfg_model
    base = run_duel(cfg, model, SMOKE, duration_s=SHORT_S)
    gated = run_duel(cfg, model, SMOKE, duration_s=SHORT_S,
                     fire_gate_nm_blue=35.0, fire_gate_nm_red=35.0)
    assert _without_volatile(base) == _without_volatile(gated)
    assert base.first_shot_range_blue_nm is not None and base.first_shot_range_blue_nm > 25.0


@needs_model
def test_4_mavi_kapisi_SADECE_maviyi_kisitlar(cfg_model):
    cfg, model = cfg_model
    base = run_duel(cfg, model, SMOKE, duration_s=SHORT_S)
    r = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, fire_gate_nm_blue=25.0)
    # Mavi 25 nmi icinde ilk atisi yapti (kapisizken ~29 nmi'deydi) ...
    assert r.first_shot_range_blue_nm is not None
    assert r.first_shot_range_blue_nm <= 25.0
    assert base.first_shot_range_blue_nm > 25.0
    # ... KIRMIZI'nin ilk atisi degismedi (yanlis tarafa uygulanmadi).
    assert r.first_shot_range_red_nm == pytest.approx(base.first_shot_range_red_nm, abs=1e-9)
    # Kapi degerleri sonuca yazildi (CSV kendi kendini aciklasin).
    assert r.fire_gate_blue_nm == 25.0 and r.fire_gate_red_nm is None
    # Kapi BAGLADI (yetki vardi ama mavi bekledi): tik sayaci >0; kapisiz taraf/kosuda 0.
    assert r.gate_blocked_ticks_blue > 0 and r.gate_blocked_ticks_red == 0
    assert base.gate_blocked_ticks_blue == 0 and base.gate_blocked_ticks_red == 0


@needs_model
def test_5_kirmizi_kapisi_SADECE_kirmiziyi_kisitlar(cfg_model):
    cfg, model = cfg_model
    base = run_duel(cfg, model, SMOKE, duration_s=SHORT_S)
    r = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, fire_gate_nm_red=25.0)
    assert r.first_shot_range_red_nm <= 25.0
    assert r.first_shot_range_blue_nm == pytest.approx(base.first_shot_range_blue_nm, abs=1e-9)
    # Sayac de DOGRU tarafa yazilmali (M5 mutasyonu: kirmizi tiklari maviye yaziliyordu).
    assert r.gate_blocked_ticks_red > 0 and r.gate_blocked_ticks_blue == 0


@needs_model
def test_6_eval_hatti_kapiyi_worker_boyunca_tasir():
    # Kapi ArmSpec -> gorev -> _run_task -> run_duel zincirinde SESSIZCE dusmemeli.
    # Kapisiz ilk atisin 25 nmi'nin ustunde oldugu bir tohum sec (test guclu olsun).
    seed = next(s for s in range(2000, 2100) if generate_scenario(s).separation_nm > 33.0)
    arm = ArmSpec("B_test", "rwr", fire_gate_blue_nm=25.0)
    res = run_tasks(MODEL_PATH, [(seed, False, arm)], workers=1)[0]
    assert res.fire_gate_blue_nm == 25.0
    assert res.first_shot_range_blue_nm is not None and res.first_shot_range_blue_nm <= 25.0


# ------------------------------------------------- kapi raporu (saf mantik)
def _fake(seed, *, blue_alive=True, blue_fired=2, red_alive=True, red_fired=2, gb=0, gr=0):
    return SimpleNamespace(scenario_seed=seed, blue_alive=blue_alive, blue_fired=blue_fired,
                            red_alive=red_alive, red_fired=red_fired,
                            gate_blocked_ticks_blue=gb, gate_blocked_ticks_red=gr)


def test_7_gate_report_bagladi_sayisi_ve_hic_atamadan_olen_ayrimi():
    results = [
        _fake(1, gb=12),                                            # kapi bagladi, mavi atti, yasiyor
        _fake(2, gb=0),                                             # kapi hicbir sey yapmadi
        _fake(3, blue_alive=False, blue_fired=0, gb=30),            # bekledi VE atamadan oldu -> gec kalma ADAYI
        _fake(4, blue_alive=False, blue_fired=0, gb=0),             # atamadan oldu ama kapi baglamadi -> bagimsiz
        _fake(5, blue_alive=False, blue_fired=3, gb=5),             # atarak oldu -> SAYILMAZ
        _fake(6, red_alive=False, red_fired=0),                     # kirmizi atamadan oldu (temel oran)
    ]
    g = gate_report(results)
    assert g["blue"] == dict(n=6, bound=3, died_unfired=2, died_unfired_gate_bound=1)
    assert g["red"] == dict(n=6, bound=0, died_unfired=1, died_unfired_gate_bound=0)


def test_8_kapi_bagladi_senaryo_kumesi_ve_kisitlama():
    results = [_fake(1, gb=3), _fake(1), _fake(2), _fake(2), _fake(3, gr=1)]
    # 1: aynalardan biri bagladi -> senaryo "bagladi" sayilir; 3: kirmizi tarafta bagladi da sayilir.
    assert gate_bound_seeds(results) == {1, 3}
    assert {r.scenario_seed for r in restrict_to_seeds(results, {1, 3})} == {1, 3}
    assert len(restrict_to_seeds(results, {1, 3})) == 3
    assert gate_bound_seeds([_fake(9), _fake(9)]) == set()


# ------------------------------------------ simetrik kapi deneyi (EVAL-06, saf mantik)
def test_9_gate_sym_kollari_SIMETRIK_ve_iki_tarafa_25():
    a, c = experiment_arms("gate-sym")
    assert a.symmetric and a.fire_gate_blue_nm is None and a.fire_gate_red_nm is None
    # C: IKI taraf da 25 -> simetrik (koltuk dengesi ~0.5 BEKLENIR, uyari devrede kalir).
    assert c.symmetric
    assert c.fire_gate_blue_nm == PRIMARY_GATE_NM == 25.0 and c.fire_gate_red_nm == 25.0
    assert a.label != c.label and c.label == "C_25v25"


def _res(seed, blue_hits=0, red_hits=0, outcome="muhimmatsiz"):
    return SimpleNamespace(scenario_seed=seed, blue_hits=blue_hits, red_hits=red_hits, outcome=outcome)


def test_10_kumelenmis_metrik_ayna_toplanir_esitler_bilgisiz():
    hits = lambda r: r.blue_hits + r.red_hits
    # seed 1: A 3 (iki ayna: 1+2), C 1 (0+1) -> A lehine. seed 2: A 1, C 1 (dagilim farkli) -> esit.
    # seed 3: A 0, C 2 -> C lehine.
    A = [_res(1, 1, 0), _res(1, 0, 2), _res(2, 1, 0), _res(2, 0, 0), _res(3), _res(3)]
    C = [_res(1, 0, 0), _res(1, 0, 1), _res(2, 0, 0), _res(2, 1, 0), _res(3, 2, 0), _res(3, 0, 0)]
    r = compare_arms_clustered_metric(A, C, "A", "C", hits)
    assert (r["a_more"], r["b_more"], r["tied"], r["n_clusters"]) == (1, 1, 1, 3)
    assert (r["total_a"], r["total_b"]) == (4, 4)
    # Kosu duzeyi (kumelenmemis) sayim FARKLI cikardi: 6 kosuda A-lehine 2, C-lehine 1 -- kumeleme onu degistirir.
    assert r["p_value"] == pytest.approx(1.0)


def test_11_kumelenmis_metrik_farkli_tohum_kumesi_reddedilir():
    with pytest.raises(AssertionError):
        compare_arms_clustered_metric([_res(1)], [_res(2)], "A", "C", lambda r: r.blue_hits)


def test_12_taze_tohum_uyarisi_gorulmus_tohumlarla_cakisirsa_tetiklenir():
    # Gorulmus: EVAL-05/03b (1000-1199), EVAL-06/07/08 (2000-2199), EVAL-09 (3000-3199), EVAL-10 (4000-4199). Taze: 5000+.
    assert overlaps_seen_seeds(range(1000, 1200)) is True
    assert overlaps_seen_seeds([1199]) is True and overlaps_seen_seeds([1000]) is True
    assert overlaps_seen_seeds(range(2000, 2200)) is True
    assert overlaps_seen_seeds([2000]) is True and overlaps_seen_seeds([2199]) is True
    assert overlaps_seen_seeds(range(3000, 3200)) is True          # EVAL-09
    assert overlaps_seen_seeds([3000]) is True and overlaps_seen_seeds([3199]) is True
    assert overlaps_seen_seeds(range(4000, 4200)) is True          # EVAL-10
    assert overlaps_seen_seeds(range(5000, 5200)) is False         # taze
    assert overlaps_seen_seeds([999, 1200, 1999, 2200, 2999, 3200, 3999, 4200]) is False   # aralik sinirlarinin hemen disi


# ------------------------------------------------ tani kolu: hic kacis yok (EVAL-09)
def test_13_evade_diag_kollari_simetrik_ayni_kapi_tek_fark_kacis():
    c, n = experiment_arms("evade-diag")
    assert c.warning_mode == "rwr" and n.warning_mode == "none"
    for arm in (c, n):
        assert arm.symmetric and arm.fire_gate_blue_nm == 25.0 and arm.fire_gate_red_nm == 25.0
    assert c.label == "C_25v25" and n.label == "N_25v25"


def test_14_bilinmeyen_warning_mode_reddedilir_sessizce_rwr_olmaz():
    # Eskiden 'truth' disindaki HER deger sessizce 'rwr' olarak kosuyordu (yazim hatasi gizlenirdi).
    for bad in ("RWR", "nome", "", "omniscient"):
        with pytest.raises(ValueError):
            run_duel(None, None, SMOKE, warning_mode=bad)


@needs_model
def test_15_none_modunda_kimse_kacmaz_rwr_modunda_kacar(cfg_model):
    cfg, model = cfg_model
    none = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, warning_mode="none")
    rwr = run_duel(cfg, model, SMOKE, duration_s=SHORT_S, warning_mode="rwr")
    assert none.evade_ticks_blue == 0 and none.evade_ticks_red == 0
    assert rwr.evade_ticks_blue > 0 and rwr.evade_ticks_red > 0     # test guclu olsun: rwr GERCEKTEN kaciyor
    assert none.warning_mode == "none"


def test_16_birincil_olcut_fonksiyonlari_total_hits_ve_duel_had_kill():
    # total_hits: iki tarafin toplami. duel_had_kill: EN AZ BIR isabet (0/1) -- karsilikli imhada 1, 2 DEGIL.
    assert total_hits(_res(1, blue_hits=1, red_hits=1)) == 2
    assert total_hits(_res(1, blue_hits=0, red_hits=3)) == 3
    assert total_hits(_res(1)) == 0
    assert duel_had_kill(_res(1, blue_hits=1, red_hits=1)) == 1     # karsilikli imha: TEK savas, 1
    assert duel_had_kill(_res(1, blue_hits=0, red_hits=1)) == 1     # yalniz kirmizi vurdu (mavi kaybetti) da 1
    assert duel_had_kill(_res(1, blue_hits=1, red_hits=0)) == 1
    assert duel_had_kill(_res(1)) == 0                              # sonucsuz: 0


@needs_model
def test_17_kacis_sayaci_taraflari_ayirir_asimetrik_senaryolarda(cfg_model):
    # Simetrik senaryoda (SMOKE) iki taraf birebir ayni sayiyi verir ve taraf yer degistirmesini GIZLER
    # (M4 mutasyonu ilk denemede hayatta kaldi). Rastgele, asimetrik iki senaryo TERS yonde ayrisiyor:
    # seed 1026 (60 s): mavi 565 > kirmizi 479;  seed 1012: mavi 473 < kirmizi 565 (olculdu).
    cfg, model = cfg_model
    a = run_duel(cfg, model, generate_scenario(1026), duration_s=60.0)
    b = run_duel(cfg, model, generate_scenario(1012), duration_s=60.0)
    assert a.evade_ticks_blue > a.evade_ticks_red
    assert b.evade_ticks_blue < b.evade_ticks_red
