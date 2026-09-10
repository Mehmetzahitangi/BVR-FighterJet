"""
Görüş Ötesi (BVR) Darbe-Doppler Radar Modeli (APG-68 Referanslı)
- 4. Kök Menzil Denklemi
- Açıya Bağlı RCS (Aspect Dependent RCS)
- Look-Down/Look-Up Doppler Notch Filtresi
- Gimbal Limitleri (Azimut ve Yükselme)
- Durum Tutan Takip ve Hafıza (Track ve Coast State)
"""

from dataclasses import dataclass
from bvr.combat.geometry import RelativeGeometry, wrap_to_180

@dataclass
class RadarConfig:
    # APG-68 açık kaynak tahmini referans değerleri kullanılmıştır 5.0 m^2 RCS hedefe karşı yaklaşık 40 nmi tespit menzili.

    ref_range_nm: float = 40.0      # sigma_ref'e karsi tespit menzili
    ref_rcs_m2: float = 5.0
    gimbal_az_deg: float = 60.0     # Anten yatay dönüş sınırı (+-60 deg)
    gimbal_el_deg: float = 60.0     # Anten dikey dönüş sınırı (+-60 deg)
    notch_fps: float = 100.0        # |Vc| bunun altinda -> elenir, < 100 fps (~60 knot) ise yer yankısına karışır
    coast_s: float = 4.0            # temas kesilince kilitin ne kadar süreceği
    # lock_delay_s ve coast_s FIZIKSEL SABIT DEGIL, bir denge (balance) parametresidir.
    # Ikisi birlikte notching'in gucunu belirler: uzun gecikme + kisa coast -> notch
    # cok guclu (kacmak kolay); kisa gecikme + uzun coast -> notch neredeyse ise
    # yaramaz. 2.5/4.0 gerekceli bir baslangic tahmini (tarama periyodu ~2s x M-of-N
    # mantigi), OLCULMUS bir sonuc degil. Ajanlar egitilince olculup ayarlanacak --
    # bkz. REQUIREMENTS.md RAD-09/10.
    lock_delay_s: float = 2.5       # ARAMA -> KILIT gecisi icin gereken (net) tespit suresi
    # Kesinti aninda ilerlemeyi SIFIRLAMIYORUZ, sadece azaltiyoruz (asagida decay ile).
    # Sebep: sert sifirlama, tespit menzili/notch sinirinda titreyen bir hedefi asla
    # kilitlenemez hale getirir (kirilgan esik) -- ajan bunu fiziksel olmayan bir
    # sekilde somurmeyi ogrenebilir. Azalma modeli duzgun bir gradyan verir.
    lock_decay: float = 1.0         # kesinti sirasinda ilerlemenin saniyede azalma carpani

@dataclass
class RadarContact:
    detected: bool          # bu adimda fiziksel bir enerji dönüyor mu
    tracked: bool           # kilit var mi (coast dahil)
    range_nm: float
    rcs_m2: float
    detect_range_nm: float  # bu RCS icin azami tespit menzili
    reason: str             # "ok" | "gimbal" | "notch" | "menzil" | "coast" | "acquiring"

def rcs_for_aspect(aa_deg: float) -> float:
    """
    Hedefin görünüş açısına (AA) göre Radar Kesit Alanını (RCS / sigma) hesaplar [m^2].
    Üç ana nokta üzerinden simetrik doğrusal enterpolasyon (piecewise linear):
    - Kuyruk (AA = 0 deg): 4.0 m^2
    - Yan / Beam (AA = +-90 deg): 50.0 m^2 (Geniş gövde yansıtma alanı)
    - Burun (AA = 180 deg): 2.0 m^2

    Taktik Önemi: Düşman uçağı füzenden veya radarından kaçmak için 90 derece dönüp notch pozisyonu aldığında
      Doppler filtresine takılsa bile gövdesi radarda 25 kat daha büyük bir yansıma oluşturur.
    """
    aa = abs(wrap_to_180(aa_deg)) # Açı simetrik oldu için mutlak değer alıyoruz. [-180, 180] -> [0, 180]
    if aa <= 90.0:
        # Kuyruk (4.0) -> Yan (50.0)
        fraction = aa / 90.0
        return 4.0 + fraction * (50.0 - 4.0)
    else:
        # Yan (50.0) -> Burun (2.0)
        fraction = (aa - 90.0) / 90.0
        return 50.0 - fraction * (50.0 - 2.0)

def detection_range_nm(rcs_m2: float, cfg: RadarConfig | None = None) -> float:
    """Radar tespit menzilini hesaplar (RCS ve referans menzile gore)
    (4. kök kuralı):
    R_tespit = R_ref * (sigma / sigma_ref)^(1/4)
    """
    cfg = cfg if cfg is not None else RadarConfig()
    
    if rcs_m2 <= 0.0:
        return 0.0
    
    return cfg.ref_range_nm * (rcs_m2 / cfg.ref_rcs_m2) ** 0.25

@dataclass
class _TrackState:
    """Tek bir hedefin kilit/coast/kilit-kurma durumu. Radar._state sözlüğünde target_id ile tutulur."""
    tracked: bool = False
    coast_timer: float = 0.0
    progress: float = 0.0   # ARAMA durumunda birikin/azalan kilit-kurma ilerlemesi (s)


class Radar:
    """Tek fiziksel anten/tarayıcıyı modeller -- birden fazla hedefi target_id ile ayırt ederek izler (İleride kol uçuşu 2v2 gibi senaryolar için).

    Neden Radar basina bir nesne degil de tek nesnede sozluk: gercek radarin
    TEK anteni var, tarama kaynagi hedefler arasinda paylasilir. Ileride
    "ayni anda en fazla N hedef izlenebilir" (TWS limiti) gibi bir kisit
    eklenirse, o kisit ancak tum hedeflerin durumu tek nesnede birlikte
    goruldugunde uygulanabilir.
    """

    def __init__(self, cfg: RadarConfig | None = None):
        self.cfg = cfg if cfg is not None else RadarConfig()
        self._state: dict[str, _TrackState] = {}

    def reset(self, target_id: str | None = None) -> None:
        """Radar iç durumunu sıfırla. target_id verilirse sadece o hedef, verilmezse tüm hedefler silinir."""
        if target_id is None:
            self._state.clear()
        else:
            self._state.pop(target_id, None)

    def is_tracking(self, target_id: str) -> bool:
        """Simulasyonu ilerletmeden sorgu: belirtilen hedefte su an aktif kilit (coast dahil) var mi.
        Saf okuma -- `update()`'in aksine yeni bir target_id icin durum yaratmaz (setdefault kullanmaz)."""
        state = self._state.get(target_id)
        return state.tracked if state is not None else False

    def update(self, dt: float, target_id: str, geom: RelativeGeometry) -> RadarContact:
        state = self._state.setdefault(target_id, _TrackState())

        # 1. RCS ve Azami Tespit Menzil Hesabı
        rcs = rcs_for_aspect(geom.aa_deg) # O anki açıyla hedefin RCS'i bulunur
        det_range = detection_range_nm(rcs, self.cfg) # Radarın o büyüklükteki bir hedefi kaç deniz milinden görebileceği anlık olarak hesaplanır.

        detected = False

        # 2. Karar Hiyerarşisi: Gİmbal > Menzil > Notch
        #
        # A. Gimbal Sınırı: Antenin mekanik dönüş açısı

        if (abs(geom.ata_deg) > self.cfg.gimbal_az_deg) or (abs(geom.elevation_deg) > self.cfg.gimbal_el_deg):
            # Anten fiziksel olarak +- 60derece'den fazla dönemez.
            #  Hedef bu açıyı aşarsa mekanik körlük yaşanır; coast sayacı sıfırlanır ve kilit anında kopar.
            # Tasarımsal olarak: Mekanik körleşmede coast işletilmez, kilit anında düşer

            state.tracked = False
            state.coast_timer = 0.0
            state.progress = 0.0
            return RadarContact(
                detected=False,
                tracked=False,
                range_nm=geom.range_nm,
                rcs_m2=rcs,
                detect_range_nm=det_range,
                reason="gimbal"
            )

        # B. Menzil Sınırı: Radyo dalgasının enerji seviyesi
        # Hedef, antenin baktığı koni içinde olsa bile aradaki mesafe, dönen radyo sinyalinin tespit eşiğini aşamayacağı kadar uzaktır.
        elif geom.range_nm > det_range:
            reason = "menzil"

        # C. Doppler Notch Filtresi: Yer yankısı (Clutter) elemesi
        # Look-down/Look-up: Sadece hedef aşağıdaysa (elevation_deg <= 0) yer yankısı oluşur.
        # Hedef yukarıdaysa arkasında gökyüzü olduğu için notch filtresi devreye girmez.
        elif geom.elevation_deg <= 0.0 and abs(geom.closure_fps) < self.cfg.notch_fps:
            reason = "notch"

        else: # üç engeli de geçerse, radar hedefi tespit eder ve kilitlenebilir.
            detected = True
            reason = "ok"


        # 3. Kilit Kurma (ARAMA) ve Kilit/Coast (KİLİT) Durum Takibi (hedefe özel `state` üzerinde)

        if state.tracked:
            # KİLİT: mevcut coast mantığı aynen çalışır.
            if detected:
                state.coast_timer = self.cfg.coast_s # Hedef tespit edildiği sürece coast_timer sürekli tazelenir.
                tracked = True
            else:
                state.coast_timer -= dt # Hedef bir anda notch'a girerse veya menzil sınırını hafifçe aşarsa (detected = False), sayaç her karede geçen süre (dt) kadar düşürülür.
                if state.coast_timer > 0.0:
                    tracked = True
                    reason = "coast"
                else:
                    # Kilit tamamen koptu -- ARAMA'ya don, ilerleme sifirdan basliyor.
                    # (Bu, ARAMA icindeki kisa kesintilerde uygulanan "azalma"dan
                    # FARKLI: kilidi tamamen kaybetmenin bedeli budur.)
                    state.tracked = False
                    state.coast_timer = 0.0
                    state.progress = 0.0
                    tracked = False
        else:
            # ARAMA: kilit henüz kurulmadı, ilerleme birikiyor/azalıyor.
            if detected:
                state.progress += dt
            else:
                state.progress = max(0.0, state.progress - dt * self.cfg.lock_decay)

            if state.progress >= self.cfg.lock_delay_s:
                state.tracked = True
                state.coast_timer = self.cfg.coast_s
                tracked = True
                reason = "ok"
            else:
                tracked = False
                if detected:
                    reason = "acquiring"

        return RadarContact(
            detected=detected,
            tracked=tracked,
            range_nm=geom.range_nm,
            rcs_m2=rcs,
            detect_range_nm=det_range,
            reason=reason
        )