"""
BÖLÜM A: RWR sınıfının izole (Engagement'sız) testleri -- test_radar.py'nin
izole test deseniyle aynı, gerçek zaman yerine büyük dt'lerle eşikler tek
adımda aşılır.

BÖLÜM B: Engagement entegrasyonu -- test_engagement.py'nin MockAircraftState
+ Radar + LOCK_DT deseniyle aynı. Buradaki testler H-07'de bulunan üç hatayı
(kuantizasyon canlı yola ulaşmıyordu, seviye hiç düşmüyordu, "arama" hiç
beslenmiyordu) YENİDEN üretebilecek şekilde yazıldı -- HANDOFF tuzak 46
("başarısız olamayan test test değildir"): her biri, düzeltmeden önceki
koda karşı çalıştırılsaydı KIRILIRDI.
"""

import dataclasses
import math

from bvr.combat.engagement import Engagement
from bvr.combat.geometry import relative_geometry
from bvr.combat.missile import MissileConfig
from bvr.combat.radar import Radar
from bvr.combat.rwr import RWR, RWRConfig, RWRContact

LOCK_DT = 3.0  # bkz. test_engagement.py -- lock_delay_s=2.5'i tek adımda aşar


@dataclasses.dataclass
class MockAircraftState:
    # test_engagement.py::MockAircraftState ile AYNI (radyan-tabanlı sözleşme).
    north_ft: float
    east_ft: float
    alt_ft: float
    psi_rad: float = 0.0
    theta_rad: float = 0.0
    vt_fps: float = 900.0
    gamma_rad: float = 0.0
    beta_rad: float = 0.0
    mass_lb: float = 25000.0
    alive: bool = True


# ============================================================
# BÖLÜM A -- RWR sınıfı izole testleri
# ============================================================

def test_1_kilit_detect_delay_icinde_gelir():
    # RWR-Madde-1: düşman kilitlerse detect_delay_s içinde "kilit" uyarısı çıkar,
    # ONDAN ÖNCE çıkmaz (debounce -- kısa bir taramayı gerçek kilit sanmamalı).
    rwr = RWR(RWRConfig(detect_delay_s=1.0, hold_s=2.0))

    rwr.feed_signal("red1", "kilit", bearing_deg=30.0)
    rwr.update(0.5)  # 0.5s < 1.0s -- henüz raporlanmamalı
    assert rwr.get_worst_threat() is None

    rwr.feed_signal("red1", "kilit", bearing_deg=30.0)
    rwr.update(0.6)  # kümülatif 1.1s >= 1.0s -- artık raporlanmalı
    threat = rwr.get_worst_threat()
    assert threat is not None
    assert threat.kind == "kilit"


def test_2_kilit_birakilinca_hold_s_sonra_duser():
    # RWR-Madde-4 (H-07 Hata-2'yi yeniden üretir): sinyal kesilince uyarı
    # ANINDA değil hold_s sonra düşmeli -- histerezis.
    rwr = RWR(RWRConfig(detect_delay_s=0.5, hold_s=2.0))
    for _ in range(6):  # 0.6s >= detect_delay_s=0.5
        rwr.feed_signal("red1", "kilit", bearing_deg=10.0)
        rwr.update(0.1)
    assert rwr.get_worst_threat().kind == "kilit"

    # Sinyal TAMAMEN kesildi. 1.9s sonra (< hold_s=2.0) HÂLÂ görünmeli.
    for _ in range(19):
        rwr.update(0.1)
    threat = rwr.get_worst_threat()
    assert threat is not None and threat.kind == "kilit"

    # 0.2s daha (kümülatif 2.1s > hold_s=2.0) -- artık tamamen kaybolmalı.
    rwr.update(0.2)
    assert rwr.get_worst_threat() is None


def test_2b_kilit_kesilir_arama_devam_ederse_seviye_duser():
    # H-07 Hata-2'nin TAM DÜZELTME senaryosu -- test_2'den FARKLI: sinyal
    # TAMAMEN kesilmiyor, sadece "kilit" kesilip "arama" akmaya DEVAM
    # ediyor (gerçek hayatta olan tam olarak bu: dusman kilidi birakip
    # taramaya donuyor, sinyal yok olmuyor). Eski ("sadece yukselt") kod
    # bu durumda SONSUZA KADAR "kilit" gosterirdi -- bu test o kusurun
    # SINIFINI kapatir, test_2'nin (tam sessizlik) yakalamadigi.
    rwr = RWR(RWRConfig(detect_delay_s=0.5, hold_s=2.0))
    for _ in range(6):
        rwr.feed_signal("red1", "kilit", bearing_deg=10.0)
        rwr.update(0.1)
    assert rwr.get_worst_threat().kind == "kilit"

    # "kilit" ARTIK BESLENMİYOR ama "arama" KESİNTİSİZ akmaya devam ediyor.
    for _ in range(25):  # 2.5s > hold_s=2.0 -- "kilit" hafızası tükenmeli
        rwr.feed_signal("red1", "arama", bearing_deg=10.0)
        rwr.update(0.1)

    threat = rwr.get_worst_threat()
    assert threat is not None, "sinyal kesintisiz akiyorken emitter TAMAMEN kaybolmamali"
    assert threat.kind == "arama", "kilit hafizasi tukendikten sonra arama'ya GERILEMELI"


def test_3_kilit_arama_ayni_anda_kilit_kazanir():
    # RWR-Madde-5 (H-07 Hata-2/3'ü birlikte sınar): aynı yayıncıdan aynı tikte
    # HEM "arama" HEM "kilit" beslenirse (fiziksel olarak nadir ama RWR'in
    # kendisi öncelik garantisi vermeli), raporlanan seviye HER ZAMAN daha
    # yüksek olan ("kilit") olmalı -- besleme sırasına bağlı olmamalı. Ayrıca
    # "kilit"in raporlanabilmesi için önce "arama"nın onaylanmış olması
    # GEREKMEDİĞİni de kanıtlar (ikisi bağımsız seviyelerdir).
    rwr = RWR(RWRConfig(detect_delay_s=0.5, hold_s=2.0))
    for _ in range(6):
        rwr.feed_signal("red1", "arama", bearing_deg=10.0)
        rwr.feed_signal("red1", "kilit", bearing_deg=10.0)
        rwr.update(0.1)
    threat = rwr.get_worst_threat()
    assert threat is not None and threat.kind == "kilit"


def test_4_yapisal_menzil_alani_yok():
    # RWR-Madde-7: RWR pasif bir alıcıdır, menzil ÖLÇEMEZ. RWRContact'a
    # ilerde biri "range_nm"/"range_ft" eklerse bu test KIRILMALI --
    # omnisiyansın arka kapıdan sızmasına karşı yapısal kilit.
    fields = {f.name for f in dataclasses.fields(RWRContact)}
    assert "range_nm" not in fields
    assert "range_ft" not in fields
    assert fields == {"emitter_id", "kind", "bearing_deg", "age_s"}


# ============================================================
# BÖLÜM B -- Engagement entegrasyonu
# ============================================================

def test_5_atis_gorunmez():
    # RWR-Madde-2 (EN KRİTİK -- modelin var olma sebebi budur, bkz. dosya
    # başlığı ve REQUIREMENTS.md RWR-01). Kilit sabit tutulurken bir füze
    # atılsın: RWR çıktısı atıştan ÖNCE ve SONRA BİREBİR AYNI kalmalı --
    # füzenin ataletsel/datalink fazı hiçbir iz bırakmaz.
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))
    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    dt = 0.1
    for _ in range(20):
        eng.update(dt, {"blue": blue, "red": red})

    threat_before = eng.aircraft["red"].rwr.get_worst_threat()
    assert threat_before is not None and threat_before.kind == "kilit"

    assert eng.fire("blue", "red")  # <-- ATIŞ

    eng.update(dt, {"blue": blue, "red": red})
    threat_after = eng.aircraft["red"].rwr.get_worst_threat()

    assert threat_after is not None
    assert threat_after.kind == threat_before.kind == "kilit"
    assert threat_after.bearing_deg == threat_before.bearing_deg


def test_5b_atis_sonrasi_uzun_sure_fuze_sizmaz():
    # test_5'in TAMAMLAYICISI -- mutasyon testiyle bulunan gerçek boşluk.
    # test_5 atıştan sonra SADECE TEK TİK (0.1s) ilerletiyor; ama
    # missile_detect_delay_s=0.5s olduğu için, biri "fuze"yi PİTBULL yerine
    # ATIŞ ANINDAN beslese bile o TEK tikte hiçbir zaman doğrulanmaya
    # (validate) vakit bulamaz -- mutasyon test_5'i KIRMADI, bu boşluğu
    # kanıtladı. Burada atıştan sonra detect_delay'i FAZLASIYLA aşan (5 s)
    # ama gerçek pitbull menziline (varsayılan pitbull_range_nm=8 nmi,
    # başlangıç 15 nmi) HÂLÂ ÇOK UZAK bir pencere boyunca HER TİKTE
    # kontrol ediliyor -- "fuze" bir kez bile sızarsa test düşer.
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))
    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    dt = 0.1
    # ONCE RWR'in kendisinin "kilit"i DOGRULAMASINA firsat ver (varsayilan
    # detect_delay_s=1.0) -- yoksa atistan sonraki ilk kontrolde threat=None
    # cikar, bu da "fuze sizdi" ile KARISTIRILMAMALI (bkz. test_5).
    for _ in range(20):
        eng.update(dt, {"blue": blue, "red": red})
    assert eng.aircraft["red"].rwr.get_worst_threat().kind == "kilit"

    assert eng.fire("blue", "red")

    for _ in range(50):  # 5 s -- detect_delay_s(0.5) fazlasiyla asilir, pitbull'a hala uzak
        eng.update(dt, {"blue": blue, "red": red})
        t = eng.aircraft["red"].rwr.get_worst_threat()
        assert t is not None and t.kind == "kilit", f"ataletsel fazda fuze sizdi: {t}"


def test_6_fuze_uyarisi_pitbull_ile_gelir():
    # RWR-Madde-3: füze pitbull olunca "fuze" (Level 2) belirir, ÖNCESİNDE
    # yok. pitbull_range_nm bilerek baslangic menzilinin (15 nmi) USTUNE
    # cekildi ki fuze ILK tikte pitbull olsun -- gercek ucus suresini (~40s)
    # beklemeye gerek kalmasin. seeker_fov_deg=180 geometriyi testin disinda
    # tutar (bu testin konusu koni degil, faz gecisi).
    eng = Engagement(missile_cfg=MissileConfig(pitbull_range_nm=50.0, seeker_fov_deg=180.0))
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))
    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")

    threat0 = eng.aircraft["red"].rwr.get_worst_threat()
    assert threat0 is None or threat0.kind != "fuze"

    dt = 0.1
    for _ in range(8):  # missile_detect_delay_s=0.5 asilana kadar besle
        eng.update(dt, {"blue": blue, "red": red})

    threat = eng.aircraft["red"].rwr.get_worst_threat()
    assert threat is not None and threat.kind == "fuze"


def test_7_kanadima_giden_konimin_disindaki_fuze_uyarmaz():
    # RWR-Madde-6 (2v2): blue1, red1'e ateş ediyor. red2 (red1'in kanadı),
    # red1'in HEMEN yanında ama füzenin DAR arayıcı konisinin (seeker_fov_deg
    # =10) DIŞINDA geniş bir yanal ofsette duruyor. Füze pitbull olunca
    # red1 "fuze" uyarısı almalı, kanadı red2 ALMAMALI -- kontrol "bana mı
    # nişan alınmış" değil "onun konisinde miyim" olduğu için.
    eng = Engagement(missile_cfg=MissileConfig(pitbull_range_nm=50.0, seeker_fov_deg=10.0))
    blue1 = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red1 = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)
    # red2: red1 ile AYNI menzilde ama 10 nmi doguda -- atan blue1'den bakildiginda
    # atan(10/15) =~ 33.7 derece sapma, 10 derecelik koninin cok disinda.
    red2 = MockAircraftState(15.0 * 6076.11549, 10.0 * 6076.11549, 30000.0, psi_rad=math.pi)

    r_blue1 = Radar()
    r_blue1.update(LOCK_DT, "red1", relative_geometry(blue1, red1))
    eng.add_aircraft("blue1", blue1, r_blue1)
    eng.add_aircraft("red1", red1, Radar())
    eng.add_aircraft("red2", red2, Radar())

    assert eng.fire("blue1", "red1")

    dt = 0.1
    for _ in range(8):
        eng.update(dt, {"blue1": blue1, "red1": red1, "red2": red2})

    threat_r1 = eng.aircraft["red1"].rwr.get_worst_threat()
    threat_r2 = eng.aircraft["red2"].rwr.get_worst_threat()

    assert threat_r1 is not None and threat_r1.kind == "fuze"
    assert threat_r2 is None or threat_r2.kind != "fuze"


def test_8_kendi_radarim_kendi_rwrimi_tetiklemez():
    # RWR-Madde-8: Engagement.update()'in radar döngüsü s_id==t_id'yi zaten
    # atlıyor (bkz. engagement.py) -- tek uçaklı bir Engagement'ta hiçbir
    # illumination üretilmemeli, RWR'a hiçbir şey beslenmemeli.
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    eng.add_aircraft("blue", blue, Radar())

    dt = 0.1
    for _ in range(int(LOCK_DT / dt) + 5):
        eng.update(dt, {"blue": blue})

    assert eng.aircraft["blue"].rwr.get_worst_threat() is None


def test_9_smoke_betikleri_ozel_alana_erismiyor():
    # H-07 Hata-1'in SINIFINI kapatir (tek ornegini degil, bkz. bagimsiz
    # incelemenin onerisi). Smoke betikleri RWR'in PUBLIC arayuzunu
    # (contacts()/get_worst_threat()) kullanmali -- `rwr._tracks` gibi ozel
    # bir alana DOGRUDAN erismek, kuantizasyon/hold/rise mantigini ikinci
    # (ve kolayca yanlis) bir yerde yeniden uygulamak anlamina gelir. Bu
    # kod-tarayici test, "birisi tekrar ozel alana erisirse" bunu YAKALAR --
    # RWR sinifinin kendi davranisini degil, CAGIRANLARIN disiplinini sinar.
    import pathlib
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    for script_rel in ("scripts/bvr_1v1_smoke.py", "scripts/bvr_2v2_smoke.py"):
        src = (repo_root / script_rel).read_text(encoding="utf-8")
        assert "._tracks" not in src, (
            f"{script_rel} bir RWR ozel alanina (_tracks) dogrudan erisiyor -- "
            "contacts()/get_worst_threat() kullanilmali"
        )


def test_10_kuantizasyon_canli_yolda_calisiyor():
    # RWR-Madde-1/H-07-Hata-1'in canli-yol dogrulamasi -- mutasyon testiyle
    # bulunan gercek boşluk. test_4 (yapısal) ve test_5/6/7/8'in HEPSİ
    # HEAD-ON (ham kerteriz = 0.0 derece) kurulum kullanıyor; 0, kuantize
    # edilse de edilmese de 0 kaldığı için hiçbiri kuantizasyonun CANLI
    # YOLDA gerçekten uygulandığını sınamıyordu (kuantizasyonu tamamen
    # kapatmak 56/56'yi ETKİLEMEDİ). Burada BİLEREK AÇILI bir geometri
    # kuruluyor (red.psi_rad = 170°, 180° DEĞİL) ve `RWR._quantize_bearing`
    # ile AYNI formülle (round(ham/15)*15) hesaplanan beklenen değer,
    # `Engagement` üzerinden GERÇEKTEN gelen değerle karşılaştırılıyor.
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.radians(170.0))

    raw_bearing = relative_geometry(red, blue).ata_deg
    expected_quantized = round(raw_bearing / 15.0) * 15.0
    assert expected_quantized != raw_bearing, (
        "test kurulumu kazayla zaten 15'in katina denk geldi -- geometriyi degistir"
    )

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))
    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    dt = 0.1
    for _ in range(20):
        eng.update(dt, {"blue": blue, "red": red})

    threat = eng.aircraft["red"].rwr.get_worst_threat()
    assert threat is not None and threat.kind == "kilit"
    assert threat.bearing_deg == expected_quantized, (
        f"kuantizasyon canli yolda calismiyor: ham {raw_bearing:.2f} derece, "
        f"beklenen kuantize {expected_quantized}, gelen {threat.bearing_deg}"
    )
