"""
bvr/combat/tests/test_engagement.py

Faz 1.4 Angajman Muhasebesi Kabul Kriterleri (1 - 8) Test Paketi.
"""

import math
from dataclasses import dataclass
import numpy as np
import pytest

from bvr.combat.engagement import Engagement, LaunchRules, Loadout
from bvr.combat.geometry import relative_geometry
from bvr.combat.missile import MissileConfig
from bvr.combat.radar import Radar, RadarConfig

# RadarConfig.lock_delay_s varsayilani 2.5s -- tek bir dt=0.1 cagrisi kilit
# KURMAZ (progress=0.1 < 2.5), sadece reason="acquiring" doner. Kilidi tek
# adimda kurmak icin dt'yi bu esigin uzerine cikariyoruz (radar/fuze
# testlerinde kullandigimiz ayni desen).
LOCK_DT = 3.0


@dataclass
class MockAircraftState:
    # NOT: radyan-tabanli sozlesme (test_geometry.py'deki MockFlightState ile
    # AYNI) -- relative_geometry() (Faz 1.1) bunu bekliyor. test_radar.py'nin
    # derece-tabanli mock'uyla karistirma; o dosya relative_geometry()'yi hic
    # cagirmiyor, bu yuzden orada sorun cikmiyordu.
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


def test_1_kilit_yokken_atesle():
    # Kriter 1: Kilit yokken ateşle -> can_fire False, sebep "kilit yok"
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0)
    red = MockAircraftState(20.0 * 6076.11549, 0.0, 30000.0)
    
    eng.add_aircraft("blue", blue, Radar())
    eng.add_aircraft("red", red, Radar())

    can, reason = eng.can_fire("blue", "red")
    assert not can
    assert reason == "kilit yok"


def test_2_40nm_menzil_disi():
    # Kriter 2: 40 nmi'den ateşle (limit 35) -> False, "menzil"
    eng = Engagement(LaunchRules(max_launch_nm=35.0))
    blue = MockAircraftState(0.0, 0.0, 30000.0)
    red = MockAircraftState(40.0 * 6076.11549, 0.0, 30000.0)

    r_blue = Radar()
    # Radarın hedefi görmesini sağla
    geom = relative_geometry(blue, red)
    r_blue.update(LOCK_DT, "red", geom)

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    can, reason = eng.can_fire("blue", "red")
    assert not can
    assert reason == "menzil"


def test_3_dort_fuze_sonrasi_muhimmat_bitti():
    # Kriter 3: 4 füze at, 5.'yi dene -> False, "muhimmat"
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0)
    # red'e blue'dan farkli yon (karsi karsiya) veriyoruz -- ayni yon+hizda
    # bagil hiz tam sifir cikar, Vc=0 + elevation=0 notch kosulunu (RAD-04/05)
    # tetikler ve radar hicbir zaman kilitlenemez (bu testin amaci bu degil).
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue, Loadout(amraam=4))
    eng.add_aircraft("red", red, Radar())

    # 4 kez ateşleme hakkı için max_per_target limitini geçici esnetelim
    eng.rules.max_per_target = 10

    for _ in range(4):
        assert eng.fire("blue", "red")

    can, reason = eng.can_fire("blue", "red")
    assert not can
    assert reason == "muhimmat"


def test_4_ayni_hedefe_ucuncu_fuze_hedef_doygun():
    # Kriter 4: Aynı hedefe 3. füzeyi at (limit 2) -> False, "hedef doygun"
    eng = Engagement(LaunchRules(max_per_target=2))
    blue = MockAircraftState(0.0, 0.0, 30000.0)
    # bkz. test_3 notu: notch kosulunu tetiklememek icin karsi yon
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue, Loadout(amraam=4))
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")
    assert eng.fire("blue", "red")

    can, reason = eng.can_fire("blue", "red")
    assert not can
    assert reason == "hedef doygun"


def test_5_atesle_ucak_agirligi_azalmali():
    # Kriter 5: Ateşle -> uçak ağırlığı 335 lb azalmalı
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, mass_lb=25000.0)
    # bkz. test_3 notu: notch kosulunu tetiklememek icin karsi yon
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")
    assert blue.mass_lb == 25000.0 - 335.0


def test_6_gimbal_asimi_datalink_memory_sonrasi_kor():
    # Kriter 6: Füze uçarken atan uçak gimbal aşsın -> füze datalink_memory kadar dayanmalı, sonra "kor"
    # Not: datalink hafizasi Missile'in kendi config'inde (MSL-06) -- Engagement
    # kendi basina ikinci bir tolerans sayaci TUTMUYOR (bkz. engagement.py notu).
    eng = Engagement(missile_cfg=MissileConfig(datalink_memory_s=4.0))
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(20.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")
    dt = 0.1

    # Mavi uçak aniden 90 derece dönüp gimbal limitini aşsın (ATA = 90 deg > 60 deg)
    blue.psi_rad = math.pi / 2

    # 2 saniye uçuş (2.0s < 4.0s datalink_memory) -> Füze hâlâ yaşamalı
    for _ in range(20):
        events = eng.update(dt, {"blue": blue, "red": red})

    msl = eng.missiles[0].missile
    assert msl.alive

    # 3 saniye daha uçuş (Toplam kayıp süresi 5.0s > 4.0s) -> Füze "kor" olmalı
    for _ in range(30):
        events = eng.update(dt, {"blue": blue, "red": red})

    assert not msl.alive
    assert msl.result == "kor"
    assert any(e.kind == "kor" for e in eng.events)


def test_7_isabet_hedef_olur_ve_olay_gunlugu():
    # Kriter 7: İsabet -> hedef uçak alive=False, olay günlüğüne "isabet"
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0, vt_fps=900.0)
    red = MockAircraftState(8.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi, vt_fps=800.0)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")
    dt = 0.05

    # Hedefe çarpana kadar koştur
    for _ in range(600):
        # Basit kinematik yaklaşım: uçaklar birbirine doğru uçsun
        blue.north_ft += blue.vt_fps * dt
        red.north_ft -= red.vt_fps * dt
        events = eng.update(dt, {"blue": blue, "red": red})
        if not eng.aircraft["red"].alive:
            break

    assert not eng.aircraft["red"].alive
    assert any(e.kind == "isabet" and e.target == "red" for e in eng.events)


def test_8_iki_ucak_karsilikli_ates_bagimsiz():
    # Kriter 8: İki uçak birbirine ateş etsin -> iki füze bağımsız izlenmeli, karışmamalı
    eng = Engagement()
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0)
    red = MockAircraftState(15.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi)

    r_blue = Radar()
    r_red = Radar()

    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))
    r_red.update(LOCK_DT, "blue", relative_geometry(red, blue))

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, r_red)

    # Karşılıklı atış
    assert eng.fire("blue", "red")
    assert eng.fire("red", "blue")

    assert len(eng.missiles) == 2
    m1, m2 = eng.missiles

    assert m1.shooter_id == "blue" and m1.target_id == "red"
    assert m2.shooter_id == "red" and m2.target_id == "blue"

    # Bir adım ilerlet
    eng.update(0.1, {"blue": blue, "red": red})

    # İki füzenin de bağımsız pozisyon ve yön güncellediğini doğrula
    assert m1.missile.vel[0] > 0.0   # Mavi füze kuzeye (+x) gidiyor
    assert m2.missile.vel[0] < 0.0   # Kırmızı füze güneye (-x) gidiyor


def test_9_olu_hedefe_ikinci_fuze_hedefsiz_olur():
    # Regresyon: ayni hedefe (ayni an, ayni kosullarla) iki fuze atilirsa,
    # listede ONCE islenen (ilk atilan) isabet edip hedefi dusurur; hemen
    # ardindan AYNI tikte islenen ikinci fuze "isabet" URETMEMELI -- olu bir
    # ucaga ikinci kez vurulmus sayilmamali (t_entry.alive kontrolu onu
    # "hedefsiz"e yonlendirmeli).
    eng = Engagement(LaunchRules(max_per_target=2))
    blue = MockAircraftState(0.0, 0.0, 30000.0, psi_rad=0.0, vt_fps=900.0)
    red = MockAircraftState(8.0 * 6076.11549, 0.0, 30000.0, psi_rad=math.pi, vt_fps=800.0)

    r_blue = Radar()
    r_blue.update(LOCK_DT, "red", relative_geometry(blue, red))

    eng.add_aircraft("blue", blue, r_blue)
    eng.add_aircraft("red", red, Radar())

    assert eng.fire("blue", "red")
    assert eng.fire("blue", "red")  # ayni hedefe, ayni an, ayni kosullarla ikinci fuze
    dt = 0.05

    for _ in range(600):
        blue.north_ft += blue.vt_fps * dt
        red.north_ft -= red.vt_fps * dt
        eng.update(dt, {"blue": blue, "red": red})
        if not eng.aircraft["red"].alive:
            break

    isabet_events = [e for e in eng.events if e.kind == "isabet" and e.target == "red"]
    assert len(isabet_events) == 1
    assert any(e.kind == "hedefsiz" for e in eng.events)