"""
bvr/combat/tests/test_duel_side_counts.py

EVAL-05 sonrasi: fuze sonlanma nedenleri (kor/hedefsiz/iska/tukenme) ATAN TARAFA
gore kaydediliyor. Bu sayaclar "kacis rakibin KENDI fuzesini korletiyor mu?"
hipotezini ayirt edecek -- yanlis tarafa yazilirlarsa hipotezi TERS yonde
"kanitlarlar". Bu yuzden atif dogrulugu burada kilitleniyor.
"""
import os
from types import SimpleNamespace

import pytest

from bvr.combat.duel import DuelScenario, generate_scenario, mirror_scenario, run_duel, tally_missile_end
from scripts.eval_commander import side_missile_outcomes

MODEL_PATH = "runs/reward_r3_both/sac_1999968_steps.zip"
needs_model = pytest.mark.skipif(not os.path.exists(MODEL_PATH), reason="dondurulmus SAC modeli yok")


def _fresh():
    kc = {"kor": 0, "hedefsiz": 0, "iska": 0, "tukenme": 0}
    return kc, {"blue": dict.fromkeys(kc, 0), "red": dict.fromkeys(kc, 0)}


# ------------------------------------------------------------------ saf mantik
def test_1_sayim_ATAN_tarafa_yazilir_toplam_ve_taraf_tutarli():
    kc, sc = _fresh()
    # (tur, atan): mavi 2 kor + 1 tukenme, kirmizi 1 kor + 1 iska
    for kind, shooter in [("kor", "blue"), ("kor", "blue"), ("tukenme", "blue"),
                          ("kor", "red"), ("iska", "red")]:
        assert tally_missile_end(kind, shooter, kc, sc) is True
    assert kc == {"kor": 3, "hedefsiz": 0, "iska": 1, "tukenme": 1}
    assert sc["blue"] == {"kor": 2, "hedefsiz": 0, "iska": 0, "tukenme": 1}
    assert sc["red"] == {"kor": 1, "hedefsiz": 0, "iska": 1, "tukenme": 0}
    for k in kc:                                    # toplam = mavi + kirmizi
        assert kc[k] == sc["blue"][k] + sc["red"][k]


def test_2_sonlanma_olmayan_olaylar_sayaca_dokunmaz():
    kc, sc = _fresh()
    for kind in ("ates", "pitbull", "isabet", "bilinmeyen"):     # isabet blue_hits/red_hits'te
        assert tally_missile_end(kind, "blue", kc, sc) is False
    assert kc == dict.fromkeys(kc, 0)
    assert sc["blue"] == dict.fromkeys(kc, 0) and sc["red"] == dict.fromkeys(kc, 0)


def test_3_side_missile_outcomes_havada_kalan_hesabi():
    r = SimpleNamespace(blue_fired=4, blue_hits=1, blue_kor_count=1, blue_hedefsiz_count=0,
                        blue_iska_count=0, blue_tukenme_count=1,
                        red_fired=3, red_hits=0, red_kor_count=0, red_hedefsiz_count=1,
                        red_iska_count=0, red_tukenme_count=1)
    mo = side_missile_outcomes([r, r])              # iki savas: pooled toplanir
    assert mo["blue"] == dict(fired=8, isabet=2, kor=2, hedefsiz=0, iska=0, tukenme=2, havada=2)
    assert mo["red"] == dict(fired=6, isabet=0, kor=0, hedefsiz=2, iska=0, tukenme=2, havada=2)


# ----------------------------------------------------------- simulasyonlu
@needs_model
def test_4_gercek_savasta_kor_dogru_tarafa_yazilir():
    # Seed 1026 (normal): EVAL-05 verisinde mavinin 2 fuzesi 'kor' oldu, kirmizinin HIC.
    # Toplam-taraf tutarliligi VE asimetrik atif birlikte sinanir.
    from stable_baselines3 import SAC
    from bvr.config import load_experiment
    cfg = load_experiment(f"{os.path.dirname(MODEL_PATH)}/config.resolved.yaml").env
    cfg.episode_s = 1e9
    model = SAC.load(MODEL_PATH, device="cpu")
    res = run_duel(cfg, model, generate_scenario(1026), warning_mode="rwr")
    for k in ("kor", "hedefsiz", "iska", "tukenme"):
        assert getattr(res, f"blue_{k}_count") + getattr(res, f"red_{k}_count") == getattr(res, f"{k}_count")
    assert res.kor_count > 0                        # test guclu olsun: anlamli bir sayi var
    assert res.blue_kor_count > 0 and res.red_kor_count == 0
