"""
Faz 1.2 Radar Kabul Kriterleri Doğrulama Testleri
Testler geometri motorundan bağımsız doğrudan teorik değerlerle sınanır
"""

import math
from bvr.combat.geometry import RelativeGeometry
from bvr.combat.radar import Radar, RadarConfig, rcs_for_aspect, detection_range_nm


def make_geom(
    range_nm: float = 20.0,
    ata_deg: float = 0.0,
    aa_deg: float = 180.0,
    closure_fps: float = 1000.0,
    elevation_deg: float = -5.0
) -> RelativeGeometry:
    """Radar testleri için bağımsız geometri nesnesi üretir."""
    return RelativeGeometry(
        range_ft=range_nm * 6076.11549,
        range_nm=range_nm,
        ata_deg=ata_deg,
        aa_deg=aa_deg,
        hca_deg=0.0,
        closure_fps=closure_fps,
        los_rate_radps=0.0,
        elevation_deg=elevation_deg,
        off_boresight_deg=abs(ata_deg)
    )


def test_1_rcs_menzil_iliskisi():
    # Kriter 1: RCS 5.0 -> 0.5 m^2 olduğunda tespit menzili 40.0 -> 22.4936 nmi olmalı
    # 40 * (0.5 / 5.0)^0.25 = 40 * (0.1)^0.25 = 40 * 0.5623413 = 22.4936 nmi
    cfg = RadarConfig(ref_range_nm=40.0, ref_rcs_m2=5.0)
    menzil = detection_range_nm(0.5, cfg)
    assert math.isclose(menzil, 22.4936, rel_tol=1e-3)


def test_2_gimbal_siniri():
    # Kriter 2: ATA = 61 deg -> Gimbal (60 deg) aşıldı -> tracked=False, reason="gimbal"
    radar = Radar()
    geom = make_geom(ata_deg=61.0)
    contact = radar.update(dt=0.1, target_id="kirmizi", geom=geom)

    assert not contact.detected
    assert not contact.tracked
    assert contact.reason == "gimbal"


def test_3_doppler_notch_asagida():
    # Kriter 3: Vc = 50 fps, hedef aşağıda (elevation = -5 deg) -> detected=False, reason="notch"
    radar = Radar()
    geom = make_geom(closure_fps=50.0, elevation_deg=-5.0)
    contact = radar.update(dt=0.1, target_id="kirmizi", geom=geom)

    assert not contact.detected
    assert contact.reason == "notch"


def test_4_doppler_notch_yukarida():
    # Kriter 4: Vc = 50 fps, hedef yukarıda (elevation = +5 deg) -> detected=True (yer yankısı yok)
    # Not: tek bir 0.1s'lik çağrı kilit gecikmesini (lock_delay_s=2.5) aşamaz,
    # bu yüzden reason "ok" değil "acquiring" -- notch'un engellemediğini "detected"
    # zaten kanıtlıyor.
    radar = Radar()
    geom = make_geom(closure_fps=50.0, elevation_deg=5.0)
    contact = radar.update(dt=0.1, target_id="kirmizi", geom=geom)

    assert contact.detected
    assert contact.reason == "acquiring"


def test_5_coast_kilit_korunumu():
    # Kriter 5: Kilit varken temas kesilsin, 3 saniye sonra kilit (tracked) devam etmeli (Coast 4 saniye)
    radar = Radar(RadarConfig(coast_s=4.0))
    geom_gorunen = make_geom(closure_fps=1000.0, elevation_deg=-5.0)
    geom_notched = make_geom(closure_fps=50.0, elevation_deg=-5.0)

    # Adım 1: Kilit kur (dt=3.0 >= lock_delay_s=2.5, tek adımda kilit kurulur)
    c1 = radar.update(dt=3.0, target_id="kirmizi", geom=geom_gorunen)
    assert c1.detected and c1.tracked

    # Adım 2: 3 saniye notch uygula (3.0s < 4.0s)
    c2 = radar.update(dt=3.0, target_id="kirmizi", geom=geom_notched)
    assert not c2.detected
    assert c2.tracked
    assert c2.reason == "coast"


def test_6_coast_sure_asimi():
    # Kriter 6: Kilit varken temas kesilsin, 5 saniye sonra kilit tamamen kopmalı (5.0s > 4.0s)
    radar = Radar(RadarConfig(coast_s=4.0))
    geom_gorunen = make_geom()
    geom_notched = make_geom(closure_fps=50.0, elevation_deg=-5.0)

    # Adım 1: Kilit kur (dt=3.0 >= lock_delay_s=2.5, tek adımda kilit kurulur)
    radar.update(dt=3.0, target_id="kirmizi", geom=geom_gorunen)

    # Adım 2: 5 saniye notch uygula
    c_lost = radar.update(dt=5.0, target_id="kirmizi", geom=geom_notched)
    assert not c_lost.detected
    assert not c_lost.tracked


def test_7_rcs_beam_tepesi():
    # Kriter 7: AA 0 -> 180  tepe noktası kesin olarak Beam'de (90 deg) olmalı
    rcs_0 = rcs_for_aspect(0.0)      # Kuyruk: 4.0
    rcs_45 = rcs_for_aspect(45.0)    # Ara değer
    rcs_90 = rcs_for_aspect(90.0)    # Beam: 50.0 (Tepe)
    rcs_135 = rcs_for_aspect(135.0)  # Ara değer
    rcs_180 = rcs_for_aspect(180.0)  # Burun: 2.0

    assert rcs_0 == 4.0
    assert rcs_90 == 50.0
    assert rcs_180 == 2.0

    # 0 -> 90 monotonic artış, 90 -> 180 monotonic azalış kontrolü
    assert rcs_0 < rcs_45 < rcs_90
    assert rcs_90 > rcs_135 > rcs_180

    # Tepe kontrolü
    for deg in range(0, 181, 5):
        assert rcs_for_aspect(deg) <= rcs_90


def test_8_menzil_siniri():
    # Kriter: AA=180 (varsayılan) -> RCS=2.0 -> det_range = 40*(2/5)^0.25 = 31.81 nmi
    # range_nm=50.0 bunu acıkça aşıyor -> detected=False, reason="menzil"
    radar = Radar()
    geom = make_geom(range_nm=50.0)
    contact = radar.update(dt=0.1, target_id="kirmizi", geom=geom)

    assert math.isclose(contact.detect_range_nm, 31.8115, rel_tol=1e-3)
    assert not contact.detected
    assert not contact.tracked
    assert contact.reason == "menzil"


def test_9_iki_hedef_durumu_karismiyor():
    # Regresyon: ayni Radar nesnesi iki farkli hedefi (A, B) ayni turda izliyor.
    # A gorunur ve kilitleniyor; B ayni anda menzil disi.
    # B, A'nin coast/kilit durumunu MIRAS ALMAMALI (eskiden alıyordu -- hayalet kilit).
    radar = Radar()
    geom_A = make_geom(range_nm=20.0)  # gorunur (aa=180 varsayilan -> det_range~31.8 nmi)
    geom_B = make_geom(range_nm=50.0)  # menzil disi

    contact_A = radar.update(dt=3.0, target_id="kirmizi_A", geom=geom_A)  # dt>=lock_delay_s, tek adımda kilit
    contact_B = radar.update(dt=0.1, target_id="kirmizi_B", geom=geom_B)

    assert contact_A.detected and contact_A.tracked
    assert not contact_B.detected
    assert not contact_B.tracked
    assert contact_B.reason == "menzil"  # "coast" DEGIL -- B kendi durumunu taşımalı, A'nınkini değil


def test_10_kilit_gecikmesi_henuz_kilitlenmedi():
    # RAD-09 Kriter 1: Sürekli tespit, 2.0 s (< lock_delay_s=2.5) -> detected=True, tracked=False
    radar = Radar()
    geom = make_geom()
    contact = radar.update(dt=2.0, target_id="kirmizi", geom=geom)

    assert contact.detected
    assert not contact.tracked
    assert contact.reason == "acquiring"


def test_11_kilit_gecikmesi_kilitlendi():
    # RAD-09 Kriter 2: Sürekli tespit, 3.0 s (>= 2.5) -> tracked=True
    radar = Radar()
    geom = make_geom()
    contact = radar.update(dt=3.0, target_id="kirmizi", geom=geom)

    assert contact.detected
    assert contact.tracked
    assert contact.reason == "ok"


def test_12_ilerleme_azalir_sifirlanmaz():
    # RAD-10 Kriter 3: 2.0 tespit -> 1.0 kayıp -> 2.0 tespit => ilerleme = 2-1+2 = 3.0 >= 2.5 -> KİLİT VAR
    # Bu, kısa bir kesintinin ilerlemeyi SIFIRLAMADIĞINI, sadece AZALTTIĞINI kanıtlar.
    radar = Radar()
    geom_gorunur = make_geom()
    geom_kayip = make_geom(closure_fps=50.0, elevation_deg=-5.0)  # notch

    radar.update(dt=2.0, target_id="kirmizi", geom=geom_gorunur)            # ilerleme=2.0
    radar.update(dt=1.0, target_id="kirmizi", geom=geom_kayip)              # ilerleme=1.0
    contact = radar.update(dt=2.0, target_id="kirmizi", geom=geom_gorunur)  # ilerleme=3.0

    assert contact.tracked


def test_13_uzun_kayip_ilerlemeyi_tabana_indirir():
    # RAD-10 Kriter 4: 2.0 tespit -> 2.5 kayıp -> 0.4 tespit => ilerleme=max(0,2.0-2.5)+0.4=0.4 < 2.5 -> KİLİT YOK
    # Bu da decay'in GERÇEKTEN uygulandığını kanıtlar -- test_12 ile birlikte
    # "sert sıfırlama" ve "decay hiç yok" yanlış implementasyonlarının ikisini de yakalar.
    radar = Radar()
    geom_gorunur = make_geom()
    geom_kayip = make_geom(closure_fps=50.0, elevation_deg=-5.0)

    radar.update(dt=2.0, target_id="kirmizi", geom=geom_gorunur)            # ilerleme=2.0
    radar.update(dt=2.5, target_id="kirmizi", geom=geom_kayip)              # ilerleme=max(0,2.0-2.5)=0.0
    contact = radar.update(dt=0.4, target_id="kirmizi", geom=geom_gorunur)  # ilerleme=0.4

    assert not contact.tracked


def test_14_coast_bitince_yeniden_kilit_gecikmeli():
    # RAD-09/10 Kriter 5: Kilit kur -> coast bitir -> hedef geri gelsin -> kilit ANINDA gelmemeli
    radar = Radar(RadarConfig(coast_s=4.0))
    geom_gorunur = make_geom()
    geom_kayip = make_geom(closure_fps=50.0, elevation_deg=-5.0)

    radar.update(dt=3.0, target_id="kirmizi", geom=geom_gorunur)  # kilit kuruldu (ilerleme=3.0>=2.5)
    radar.update(dt=5.0, target_id="kirmizi", geom=geom_kayip)    # coast (4.0s) aşıldı -> kilit tamamen koptu

    contact = radar.update(dt=0.1, target_id="kirmizi", geom=geom_gorunur)  # hedef geri geldi
    assert contact.detected
    assert not contact.tracked
    assert contact.reason == "acquiring"


def test_15_gimbal_aninda_ilerlemeyi_sifirlar():
    # RAD-09/10 Kriter 6: Gimbal aşımı sırasında ilerleme sıfırlanır, kilit yok
    radar = Radar()
    geom_gorunur = make_geom()
    geom_gimbal = make_geom(ata_deg=61.0)

    radar.update(dt=2.0, target_id="kirmizi", geom=geom_gorunur)  # ilerleme=2.0 (henüz kilitli değil)
    radar.update(dt=0.1, target_id="kirmizi", geom=geom_gimbal)   # gimbal ihlali -> ilerleme=0

    # Sıfırlanmasaydı: 2.0 (eski) + 2.0 (yeni) = 4.0 >= 2.5 -> yanlışlıkla kilitlenirdi.
    contact = radar.update(dt=2.0, target_id="kirmizi", geom=geom_gorunur)
    assert not contact.tracked


def test_16_is_tracking_adim_atmadan_sorgular():
    # is_tracking(): update() cagirmadan, en son bilinen kilit durumunu okur.
    radar = Radar()

    # Hic gorulmemis bir hedef icin False donmeli -- VE _state'e kirletici
    # bir kayit EKLEMEMELI (update()'teki setdefault'un aksine).
    assert not radar.is_tracking("hic_gorulmemis")
    assert "hic_gorulmemis" not in radar._state

    geom = make_geom()
    radar.update(dt=3.0, target_id="kirmizi", geom=geom)  # kilit kuruldu (3.0 >= lock_delay_s)

    # Ek bir update() cagirmadan (simulasyonu ilerletmeden) kilit sorgulanabilmeli
    assert radar.is_tracking("kirmizi")
    assert not radar.is_tracking("baska_hedef")