"""
bvr/combat/tests/test_eval_stats.py

Faz 2.2 degerlendirme aracinin ISTATISTIK katmani -- bilinen referans
degerlerle ve kumeleme mantigiyla. (Ilk surumde bu fonksiyonlar sadece elle
dogrulanmisti, pytest'te hicbir sey kilitlemiyordu.)
"""
from types import SimpleNamespace

import pytest

from scripts.eval_commander import (
    wilson_interval, mcnemar_p_value, compare_arms, compare_arms_clustered,
    scenario_csv_fields,
)


def _res(seed: int, outcome: str) -> SimpleNamespace:
    # compare_* sadece bu iki alana bakar (tam DuelResult kurmaya gerek yok).
    return SimpleNamespace(scenario_seed=seed, outcome=outcome)


def test_1_wilson_bilinen_referans():
    # 50/100 icin standart Wilson %95 GA: [0.4038, 0.5962] (ders kitabi degeri).
    lo, hi = wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=5e-4)
    assert hi == pytest.approx(0.5962, abs=5e-4)
    # Uc durum: hic basari -> alt sinir 0'a yapisik ama negatife dusmez; n=0 -> (0,1).
    lo0, hi0 = wilson_interval(0, 50)
    assert lo0 == pytest.approx(0.0, abs=1e-12) and 0.0 < hi0 < 0.1
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_2_mcnemar_bilinen_deger():
    # Ilk gecerli tam kosunun kosu-duzeyi sayilari: 19 vs 7 -> p=0.0290.
    assert mcnemar_p_value(19, 7) == pytest.approx(0.0290, abs=5e-4)
    assert mcnemar_p_value(5, 5) == pytest.approx(1.0)
    assert mcnemar_p_value(0, 0) == 1.0              # kanit yok -> fark gosterilemedi
    assert mcnemar_p_value(7, 19) == mcnemar_p_value(19, 7)   # simetrik


def test_3_kumelenmis_ayna_cifti_tek_gozlem_sayilir():
    # Tek senaryo: truth iki aynada da kazanir, rwr ikisinde de kazanmaz.
    # Kosu duzeyi test bunu 2 uyumsuz cift sayar; kumelenmis test 1 senaryo.
    truth = [_res(1, "galibiyet"), _res(1, "galibiyet")]
    rwr = [_res(1, "muhimmatsiz"), _res(1, "muhimmatsiz")]
    run = compare_arms(truth, rwr, "truth", "rwr")
    clu = compare_arms_clustered(truth, rwr, "truth", "rwr")
    assert run["discordant_a_only"] == 2
    assert clu["discordant_a_only"] == 1 and clu["n_clusters"] == 1
    assert clu["concordant"] == 0 and clu["discordant_b_only"] == 0


def test_4_kumelenmis_esit_sayilar_uyumlu():
    # Seed 1: truth ilk aynada, rwr ikinci aynada kazaniyor -> 1'e 1 = ESIT (uyumlu).
    # Seed 2: truth 2, rwr 1 -> truth lehine. Seed 3: ikisi de hic -> uyumlu.
    truth = [_res(1, "galibiyet"), _res(1, "muhimmatsiz"),
             _res(2, "galibiyet"), _res(2, "galibiyet"),
             _res(3, "muhimmatsiz"), _res(3, "maglubiyet")]
    rwr = [_res(1, "muhimmatsiz"), _res(1, "galibiyet"),
           _res(2, "galibiyet"), _res(2, "muhimmatsiz"),
           _res(3, "muhimmatsiz"), _res(3, "muhimmatsiz")]
    clu = compare_arms_clustered(truth, rwr, "truth", "rwr")
    assert (clu["discordant_a_only"], clu["discordant_b_only"], clu["concordant"]) == (1, 0, 2)
    assert clu["n_clusters"] == 3


def test_5_kumelenmis_farkli_tohum_kumesi_reddedilir():
    with pytest.raises(AssertionError):
        compare_arms_clustered([_res(1, "galibiyet")], [_res(2, "galibiyet")], "a", "b")


def test_6_csv_senaryo_sutunlari_ayna_dogru():
    n = scenario_csv_fields(1234, False)
    m = scenario_csv_fields(1234, True)
    assert set(n) == set(m)
    for key in ("scn_separation_nm", "scn_aspect_deg", "scn_lateral_offset_nm",
                "scn_blue_offset_deg", "scn_alt_blue_ft", "scn_initial_ata_blue_deg",
                "scn_initial_ata_red_deg"):
        assert key in n
    # Ayna: isaretli alanlar tersine, buyuklukler ayni.
    assert m["scn_aspect_deg"] == pytest.approx(-n["scn_aspect_deg"])
    assert m["scn_blue_offset_deg"] == pytest.approx(-n["scn_blue_offset_deg"])
    assert m["scn_separation_nm"] == n["scn_separation_nm"]
    assert m["scn_alt_blue_ft"] == n["scn_alt_blue_ft"]
    # 'seed'/'mirrored' DuelResult'ta zaten var -> cakisan sutun uretilmemeli.
    assert not any(k in ("seed", "mirrored", "scn_seed", "scn_mirrored") for k in n)
