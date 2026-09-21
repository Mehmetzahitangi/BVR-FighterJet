"""
Faz 2.2 -- duel.py (paylasilan angajman kaynagi + rastgele senaryo) testleri.

Bu dosya iki seyi kilitler:
  (A) Senaryo uretiminin TEKRAR URETILEBILIRLIGI ve aynalamanin dogrulugu
      (degerlendirme aracinin butun istatistigi bunlara dayanir).
  (B) 1v1 ve 2v2 betiklerinin pick_target/Aircraft'in KENDI KOPYASINI
      TASIMAMASI -- daha once 2v2 kendi kopyasini tasiyordu ve komutan/crank
      mantigi degisince sessizce geride kalabilirdi (HANDOFF tuzak 47/51'in
      "iki kopya" dersi). Bu yapisal test, birisi kopyayi geri getirirse
      KIRILIR.
"""

import dataclasses
import pathlib

from bvr.combat import duel
from bvr.combat.duel import generate_scenario, mirror_scenario

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_1_ayni_tohum_ayni_senaryo():
    # Tekrar uretilebilirlik: eval_commander'in butun CRN/eslestirme mantigi
    # "ayni tohum = ayni senaryo" varsayimina dayanir.
    assert generate_scenario(123) == generate_scenario(123)


def test_2_farkli_tohum_farkli_senaryo():
    # Tohum gercekten bir sey degistiriyor mu (sabit bir senaryo uretmiyor mu).
    assert generate_scenario(1) != generate_scenario(2)


def test_3_ayna_iki_kez_uygulaninca_orijinale_doner():
    # KAYAN NOKTA HASSASIYETINDE geri doner: (360-(360-x)%360)%360 son
    # basamakta 1 ulp fark birakabilir (bkz. duel.py::mirror_scenario) --
    # bu bir mantik hatasi degil, `==` yerine yaklasik esitlik gerekir.
    import math
    for seed in (7, 8, 9, 10):
        s = generate_scenario(seed)
        back = mirror_scenario(mirror_scenario(s))
        a, b = dataclasses.asdict(s), dataclasses.asdict(back)
        assert a.keys() == b.keys()
        for k in a:
            if isinstance(a[k], float):
                assert math.isclose(a[k], b[k], rel_tol=0, abs_tol=1e-9), k
            else:
                assert a[k] == b[k], k


def test_4_ayna_yalnizca_yone_bagli_alanlari_cevirir():
    s = generate_scenario(11)
    m = mirror_scenario(s)
    # Yone bagli olanlar isaret degistirir / yansir:
    assert m.aspect_deg == -s.aspect_deg
    assert m.lateral_offset_nm == -s.lateral_offset_nm
    assert m.turb_blue_dir_deg == (360.0 - s.turb_blue_dir_deg) % 360.0
    assert m.turb_red_dir_deg == (360.0 - s.turb_red_dir_deg) % 360.0
    assert m.mirrored != s.mirrored
    # Yon-BAGIMSIZ buyukluklere DOKUNULMAZ (ayna bir geometri islemi,
    # senaryonun fiziksel "zorlugunu" degistirmemeli):
    for name in ("separation_nm", "alt_blue_ft", "alt_red_ft", "mach_blue", "mach_red",
                 "fuel_blue", "fuel_red", "turb_blue_fps", "turb_red_fps", "seed"):
        assert getattr(m, name) == getattr(s, name), name


def test_5_uretilen_parametreler_bildirilen_araliklarda():
    # 300 tohum: hicbiri bildirilen araligin disina tasmamali.
    def within(v, rng):
        return rng[0] <= v <= rng[1]

    for seed in range(300):
        s = generate_scenario(seed)
        assert within(s.separation_nm, duel.SEPARATION_NM_RANGE)
        assert within(s.aspect_deg, duel.ASPECT_DEG_RANGE)
        assert within(s.lateral_offset_nm, duel.LATERAL_OFFSET_NM_RANGE)
        assert within(s.alt_blue_ft, duel.ALT_FT_RANGE)
        assert within(s.alt_red_ft, duel.ALT_FT_RANGE)
        assert within(s.mach_blue, duel.MACH_RANGE)
        assert within(s.mach_red, duel.MACH_RANGE)
        assert within(s.fuel_blue, duel.FUEL_FRAC_RANGE)
        assert within(s.fuel_red, duel.FUEL_FRAC_RANGE)
        assert within(s.turb_blue_fps, duel.TURBULENCE_FPS_RANGE)
        assert within(s.turb_red_fps, duel.TURBULENCE_FPS_RANGE)


def test_6_turbulans_yaklasik_bildirilen_olasilikta():
    # 500 tohumun ~%30'unda turbulans acik olmali (iki tarafin da 0 olmasi
    # olasiligi ihmal edilebilir: uniform(0,60)'in tam 0 cikmasi). Genis
    # tolerans -- bu bir dagilim SAGLIK kontrolu, istatistiksel test degil.
    n = 500
    on = sum(1 for seed in range(n)
             if generate_scenario(seed).turb_blue_fps > 0.0)
    frac = on / n
    assert 0.22 <= frac <= 0.38, f"turbulans orani {frac:.2f}, beklenen ~0.30"


def test_7_betikler_kendi_pick_target_veya_aircraft_kopyasini_tasimiyor():
    # Yapisal kilit: 1v1 VE 2v2 betikleri angajman mantigini duel.py'den
    # ALMALI, kendi kopyalarini TASIMAMALI. Birisi "kucuk bir degisiklik"
    # icin kopyayi geri getirirse, komutan/crank mantigi iki yerde
    # yasamaya baslar ve biri sessizce eskir.
    for rel in ("scripts/bvr_1v1_smoke.py", "scripts/bvr_2v2_smoke.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "def pick_target" not in src, f"{rel} kendi pick_target kopyasini tasiyor"
        assert "class Aircraft" not in src, f"{rel} kendi Aircraft kopyasini tasiyor"
        # Gercek KULLANIMI ara (yorumdaki aciklamayi degil): eski desen
        # `seed=abs(hash(name)) % 1000` idi.
        assert "abs(hash(" not in src, f"{rel} surecler-arasi rastgele hash() tohumu kullaniyor"
    src_2v2 = (REPO_ROOT / "scripts/bvr_2v2_smoke.py").read_text(encoding="utf-8")
    assert "from bvr.combat.duel import" in src_2v2


def test_8_duel_aircraft_seed_acikca_verilmeli():
    # Tekrar uretilebilirlik: Aircraft'in seed'i hash()'ten degil cagirandan
    # gelmeli (imza seviyesinde -- varsayilan bile sabit bir tam sayi).
    import inspect
    sig = inspect.signature(duel.Aircraft.__init__)
    assert "seed" in sig.parameters
    assert isinstance(sig.parameters["seed"].default, int)
    assert dataclasses.is_dataclass(duel.DuelScenario)


def test_9_koltuk_simetrisi_geometri():
    # Faz 2.2 tam kosusunun buldugu gercek olcum hatasi: ilk surumde mavi hep
    # burnu rakibe donuk basliyordu (ort. |ATA| 8.6 derece), kirmizi ise +-60
    # derece rastgele (ort. 30.3) -- AYNI model iki tarafta oldugu halde mavi
    # karar verilen angajmanlarin %70'ini kazandi. Iki tarafin baslangic
    # |ATA| dagilimi ozdes OLMALI (simulasyonsuz, anlik kontrol).
    import numpy as np
    geo = [duel.initial_ata_deg(generate_scenario(s)) for s in range(3000)]
    mb = float(np.mean([g[0] for g in geo]))
    mr = float(np.mean([g[1] for g in geo]))
    assert abs(mb - mr) / max(mb, mr) < 0.05, f"koltuk tarafli: mavi {mb:.1f} vs kirmizi {mr:.1f}"


def test_9b_ayna_baslangic_aci_buyukluklerini_korur():
    # Ayna bir GEOMETRI yansimasi: her iki tarafin baslangic |ATA|'si AYNI
    # kalmali. mirror_scenario() blue_offset_deg'i cevirmeyi unutursa mavinin
    # |ATA|'si degisir ve bu test kirilir.
    for seed in range(200):
        s = generate_scenario(seed)
        a = duel.initial_ata_deg(s)
        b = duel.initial_ata_deg(mirror_scenario(s))
        assert abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9, seed


def test_10_cizim_sirasi_eski_tohumlari_bozmaz():
    # generate_scenario'ya yeni parametre EN SONA eklenmeli (bkz. duel.py
    # basligi). Tohum 42'nin ilk Faz 2.2 kosusunda basilan degerleri kilitler:
    # blue_offset_deg eklenmeden ONCE de bu degerler bunlardi.
    s = generate_scenario(42)
    assert s.separation_nm == 36.60934072833945
    assert s.aspect_deg == -7.334587229753723
    assert s.lateral_offset_nm == 7.171958398227648
    assert s.alt_blue_ft == 28947.360581187277
