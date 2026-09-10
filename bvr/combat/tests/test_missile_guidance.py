"""
Faz 1.3 Kabul Kriterleri (Kriter 1, 2, 3, 4, 6, 7, 8) Doğrulama Testleri.
"""

import numpy as np
import pytest
from bvr.combat.missile import Missile, MissileConfig


class MockLaunchState:
    def __init__(self, pos_ft: list[float], vel_fps: list[float]):
        self.pos_ft = np.array(pos_ft, dtype=float)
        self.vel_fps = np.array(vel_fps, dtype=float)


def test_1_head_on_10nm_isabet():
    # Kriter 1: Manevrasız hedef, 10 nmi head-on -> isabet
    cfg = MissileConfig()
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([10.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-800.0, 0.0, 0.0])
    dt = 0.05

    for _ in range(800):
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        if not state.alive:
            break

    assert state.result == "isabet"


def test_2_head_on_40nm_tukenme():
    # Kriter 2: Aynı hedef 40 nmi -> Yavaş varır, Mach 1.5 altına düşerse tükenme
    cfg = MissileConfig()
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([40.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-600.0, 0.0, 0.0])
    dt = 0.05

    for _ in range(2500):
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        if not state.alive:
            break

    assert state.result == "tukenme"


def test_3_los_rate_azalmali():
    # Kriter 3: PN calistikca hedef manevra yapmiyorsa lambda_dot sonumlenmeli
    cfg = MissileConfig()
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    # 12 nmi mesafede hafif ofsetli hedef (3000 ft)
    target_pos = np.array([12.0 * 6076.11549, 3000.0, 30000.0])
    target_vel = np.array([-800.0, 0.0, 0.0])
    dt = 0.05

    los_rates = []
    for _ in range(700):
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        los_rates.append(state.los_rate_radps)
        if not state.alive:
            break

    # Baslangictaki acisal sapma hizi, carpisma rotasina oturduktan sonrakinden belirgin buyuk olmalidir
    assert np.mean(los_rates[:20]) > np.mean(los_rates[150:200])
    assert state.result == "isabet"


def test_4_yandan_gecen_hedef_one_kestirmeli():
    # Kriter 4: Yandan gecen hedef -> Fuze hedefin arkasina degil, onune kestirmeli
    cfg = MissileConfig()
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    # Hedef tam burun ekseninde baslayip Doguya (+y) dik ucuyor
    target_pos = np.array([30000.0, 0.0, 30000.0])
    target_vel = np.array([0.0, 800.0, 0.0])
    dt = 0.05

    for _ in range(600):
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        if not state.alive:
            break

    # Fuze Doguya (+y) dogru one kestirme acisi almali ve hedefi vurmalidir
    assert state.vel_fps[1] > 200.0
    assert state.result == "isabet"


def test_6_datalink_pitbull_oncesi_uzun_sure_kesilirse_kor():
    # Kriter 6 (guncellendi, MSL-06): Pitbull menzilinden once datalink
    # datalink_memory_s'ten (5.0s) UZUN sure kesilirse -> kor.
    # Kisa kesintiler artik tolere ediliyor (asagidaki test_6b), bu yuzden
    # kesintiyi hafiza suresini acikca asacak kadar (5.2s) uzatiyoruz.
    cfg = MissileConfig(pitbull_range_nm=8.0, datalink_memory_s=5.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([20.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-800.0, 0.0, 0.0])
    dt = 0.1

    # 2 saniye uçuş (menzil ~18 nmi, pitbull'dan uzak, kilit var)
    for _ in range(20):
        target_pos += target_vel * dt
        missile.update(dt, target_pos, target_vel, datalink_ok=True)

    # datalink_memory_s'i (5.0s) acikca asan bir kesinti -> kor
    state = None
    for _ in range(52):
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=False)
        if not state.alive:
            break

    assert not state.alive
    assert state.result == "kor"


def test_6b_datalink_kisa_kesinti_tolere_edilir():
    # MSL-06: datalink_memory_s'ten (5.0s) KISA bir kesinti fuzeyi
    # OLDURMEMELI -- eski (sert, anlik "kor") davranista bu test basarisiz
    # olurdu. Tam senaryonun kendisi: 3.0-4.0s arasi (1.0s) datalink kesik.
    cfg = MissileConfig(datalink_memory_s=5.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([10.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-800.0, 0.0, 0.0])
    dt = 0.1

    state = None
    for i in range(400):
        target_pos += target_vel * dt
        t = i * dt
        dl_ok = not (3.0 <= t < 4.0)
        state = missile.update(dt, target_pos, target_vel, datalink_ok=dl_ok)
        if not state.alive:
            break

    assert state.result == "isabet"


def test_7_datalink_pitbull_sonrasi_kesilirse_isabet():
    # Kriter 7: Pitbull içine girdikten sonra datalink kopsa bile füze bağımsız vurmalı
    cfg = MissileConfig(pitbull_range_nm=8.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([10.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-800.0, 0.0, 0.0])
    dt = 0.05

    for _ in range(800):
        target_pos += target_vel * dt
        r_nm = np.linalg.norm(target_pos - missile.pos) / 6076.11549
        
        # Pitbull içine girince datalink bilerek kesilsin
        dl = False if r_nm <= 8.0 else True
        state = missile.update(dt, target_pos, target_vel, datalink_ok=dl)
        if not state.alive:
            break

    assert state.result == "isabet"


def test_8_komut_ivmesi_max_g_asilmamali():
    # Kriter 8: Aşırı agresif senaryoda dahi yanal komut ivmesi max_g (30g) sınırını geçmemeli
    cfg = MissileConfig(max_g=30.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    # Çok yakın ve 90 derece dik hızla geçen hedef (yüksek lambda_dot üretir)
    target_pos = np.array([5000.0, 2000.0, 30000.0])
    target_vel = np.array([0.0, 1200.0, 0.0])
    dt = 0.01

    for _ in range(100):
        state = missile.update(dt, target_pos, target_vel, datalink_ok=True)
        assert state.applied_g <= cfg.max_g + 1e-6
        if not state.alive:
            break


def test_9_seeker_pitbullda_yakalar_isabet():
    # MSL-09 Kriter 1: Datalink pitbull'a KADAR acik, girince kesiliyor,
    # hedef pitbull'dan sonra 7g'lik lateral manevraya basliyor.
    # Beklenen: seeker, inanc GERCEKLE tam ortusurken (belief=truth, off-
    # boresight ~0) yakalar ve manevraya ragmen izlemeye devam eder -> isabet.
    cfg = MissileConfig(pitbull_range_nm=8.0, seeker_fov_deg=30.0, seeker_range_nm=10.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([15.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-700.0, 0.0, 0.0])
    dt = 0.05
    g0 = 32.174049

    state = None
    for _ in range(1600):
        r_nm = np.linalg.norm(target_pos - missile.pos) / 6076.11549
        dl_ok = r_nm > cfg.pitbull_range_nm
        if r_nm <= cfg.pitbull_range_nm:
            target_vel[1] += 7.0 * g0 * dt
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=dl_ok)
        if not state.alive:
            break

    assert state.result == "isabet"


def test_9b_seeker_erken_kesintide_sepeti_kacirir_iska():
    # MSL-09 Kriter 2: Datalink BASTAN İTİBAREN hiç alınmıyor (sürekli kör
    # ekstrapolasyon), hedef de baştan itibaren 7g'lik yanal manevraya
    # başlıyor. datalink_memory_s bilinçli olarak büyük tutuldu (60 s) ki
    # burada test edilen şey adi datalink zaman aşımı (MSL-06) değil,
    # SEEKER KAPISI (MSL-09) olsun -- yoksa füze pitbull'a hiç varmadan
    # zaten "kor" olurdu.
    #
    # Ölçek notu: 8 nmi'de 30° FOV'u aşmak için gereken yanal sapma
    # tan(30°)*8nmi ~= 4.6 nmi (~28000 ft). Bunu üretmek için kısa/geç bir
    # kesinti (ör. pitbull'dan 2 nmi önce) yetmiyor -- uçuşun (nerdeyse)
    # tamamı boyunca kör kalmak gerekiyor.
    #
    # Beklenen: inanç hiç düzeltilmeden başından itibaren sapıyor; pitbull'a
    # varıldığında seeker sepeti (FOV) dışında kalır, hiçbir zaman
    # yakalayamaz -> hayalet hedefi kovalar -> ıska.
    cfg = MissileConfig(
        pitbull_range_nm=8.0,
        seeker_fov_deg=30.0,
        seeker_range_nm=10.0,
        datalink_memory_s=60.0,
    )
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    missile = Missile(cfg, launch, target_id="red")

    target_pos = np.array([15.0 * 6076.11549, 0.0, 30000.0])
    target_vel = np.array([-700.0, 0.0, 0.0])
    dt = 0.05
    g0 = 32.174049

    state = None
    for _ in range(1600):
        target_vel[1] += 7.0 * g0 * dt
        target_pos += target_vel * dt
        state = missile.update(dt, target_pos, target_vel, datalink_ok=False)
        if not state.alive:
            break

    assert state.result == "iska"