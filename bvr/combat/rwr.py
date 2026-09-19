from dataclasses import dataclass, field

_HIERARCHY = {"arama": 0, "kilit": 1, "fuze": 2}


@dataclass
class RWRConfig:
    # Ayarlar tutulacak
    # Bu sınıf RWR'ın ne kadar hassas ve ne kadar gecikmeli çalışacağını belirleyen denge parametrelerini tutar. Bunlar fiziksel kanunlar değil oyun/simülasyon tasarımındaki zorluk ayarlarımız
    detect_delay_s: float = 1.0 # Düşmanın radarı uçağımız üzerinden kısa bir süre geçse (sweep), sistemin gereksiz yere alarm vermesini engeller.
    hold_s: float = 2.0 # Düşman radarı uçağımızı taramayı kestiği (aydınlatma bittiği) an, RWR sinyali hemen ekrandan silmez. "Son bilinen tehdidi" bir süre daha hafızada tutar (Histerezis)
    missile_detect_delay_s: float = 0.5  # Üzerine gelen füzenin kendi aktif radarı (Pitbull) açıldığında, bunu uçağın ana radarından (Level 1'den) ayırıp "Bu bir füze" (Level 2) demek için gereken işlem süresidir. Füzeler çoh hızlıdır, bu yüzden bu süreyi kısa tutmak gerekir. Bu süreyi çok uzun tutarsak, füze bize yaklaşırken RWR bunu algılayamaz ve pilotun tepki süresi azalır.
    bearing_quant_deg: float = 15.0 #  RWR menzil vermez. 15 derecelik'lik dilimler, ajanın menzil hesabı yapmasını imkansız kılar, sadece kabaca yönü bilmesini sağlar.


@dataclass
class RWRContact:
    # Ajana verilecek bilgiler
    emitter_id: str # Sinyali gönderen şeyin kimliği (Örn: "red_1" veya "missile_3"). Her bir vericiyi (uçak veya füze) ayrı ayrı takip etmek zorunda.
    kind: str            # "arama" | "kilit" | "fuze"
    bearing_deg: float # Tehdidin geldiği yön (uçağın kendi burnuna göre bağıl kerteriz). Yukarıdaki bearing_quant_deg kuralıyla yuvarlanmış halde gelir.
    age_s: float # Sinyali ne kadar süredir duyduğumuz (veya sinyal koptuysa hafızada ne kadar süredir tuttuğumuz hold_s).Ajanın "Bu taze bir tehdit mi yoksa kaybolmak üzere olan bir hayalet mi?" sorusunu sormasını sağlar.


@dataclass
class _RWRTrackState:
    """RWR'ın kendi içinde her bir emitter_id için tuttuğu özel durum.

    SEVIYE BASINA AYRI DURUM (Hata 2 duzeltmesi): "arama"/"kilit"/"fuze"
    ARTIK TEK bir `current_kind` alanina sikistirilmiyor -- her seviyenin
    KENDI yukselme sayaci (rise_progress) ve KENDI hafiza sayaci
    (hold_timers) var. Boylece "kilit" sinyali kesilip sadece "arama" AKMAYA
    DEVAM ederse, kilit kendi hold_s'i dolunca DUSER, arama ise (halen
    besleniyor oldugu icin) raporlanmaya devam eder. Eski tasarimda
    (tek current_kind + "sadece yukselt" kurali) kilit hicbir zaman
    dusmuyordu -- HANDOFF tuzak 47'nin ("mock'ta calisiyor, canli yolda
    hicbir zaman calismiyor" degil ama) bir kuzeni: "yukselt calisiyor,
    dusur hic yazilmamis" hatasi.

    Alanlar dict/set oldugu icin @dataclass + field(default_factory=...)
    SART -- duz class'ta `hold_timers: dict = {}` yazmak TUM ornekler
    arasinda TEK bir sozlugu paylastirir (klasik Python mutable-default
    tuzagi). Onceki surumde bu sorun yoktu cunku alanlar hep immutable
    (str/float/bool) idi; simdi dict/set eklenince bu artik zorunlu.
    """

    hold_timers: dict = field(default_factory=dict)     # kind -> kalan hafiza suresi (s)
    rise_progress: dict = field(default_factory=dict)    # kind -> bu seviye kesintisiz kac saniyedir besleniyor
    validated: dict = field(default_factory=dict)        # kind -> detect_delay'i gecip RAPORLANABILIR mi
    fed_this_tick: set = field(default_factory=set)      # kind -> bu tikte feed_signal cagrildi mi
    last_bearing: float = 0.0    # Kuantize edilmeden once, en son beslenen HAM aci
    age_s: float = 0.0           # Bu yayinci ilk tespit edildiginden beri gecen sure


class RWR:
    """Radar Warning Receiver (RWR) - Radar Uyarı Alıcısı

    Bu sınıf, uçağın etrafındaki düşman radarlarını ve füzeleri tespit etmek için kullanılır."""

    def __init__(self, cfg: RWRConfig = None):
        self.cfg = cfg if cfg else RWRConfig()
        # Hangi (emitter_id) ne durumda takip ettiğimizi tutan sözlük
        self._tracks: dict[str, _RWRTrackState] = {}
        # Hata 1 duzeltmesi: update()'in URETTIGI (kuantize edilmis) liste
        # BURADA saklanir. Disaridan (smoke betikleri, ileride komutan)
        # BUNU okumali -- `_tracks[...].last_bearing` gibi ozel alanlara
        # DOGRUDAN erismek HAM (kuantize edilmemis) veriyi sizdirir, "RWR
        # menzil/hassas aci vermez" ilkesini arka kapidan deler.
        self._contacts: list[RWRContact] = []

    def _quantize_bearing(self, bearing_deg: float) -> float:
        """Ajan hile yapamasın diye kerterizi(bearing_deg) cfg.bearing_quant_deg dilimlerine yuvarlar."""

        q = self.cfg.bearing_quant_deg
        if q <= 0:
            return bearing_deg

        # -180 ile 180 arasında tut
        b = (bearing_deg + 180.0) % 360.0 - 180.0
        # Dilime yuvarla (Örn: 15'in katlarına)
        return round(b / q) * q

    def feed_signal(self, emitter_id: str, kind: str, bearing_deg: float):
        """
        Oyun döngüsünden her tick'te gelen ham aydınlatma (illumination) verisi.
        Bu fonksiyon sadece 'Bu adımda BU SEVIYEDE sinyal aldık' işaretini koyar
        -- gercek yukselt/dusur/kuantize mantigi update()'te, TUM emitter'lar
        icin TEK SEFERDE calisir (feed_signal cagri SIRASINA bagli KALMAMALI).
        """
        track = self._tracks.setdefault(emitter_id, _RWRTrackState())
        track.fed_this_tick.add(kind)
        track.last_bearing = bearing_deg

    def update(self, dt: float) -> list[RWRContact]:
        """
        Her simülasyon adımında (tüm feed_signal çağrılarından SONRA) çalışır.
        Her SEVIYE icin ayri ayri: besleniyorsa yukselme sayacini ilerlet ve
        (esigi gecince) 'validated' isaretle, beslenmiyorsa hafiza sayacini
        azalt ve (tukenince) 'validated'i geri dusur. Raporlanan seviye,
        halen validated olan en yuksek seviyedir -- boylece "kilit" duserken
        "arama" (halen besleniyorsa) hemen ortaya cikar, YENIDEN detect_delay
        beklemez (zaten orada duruyordu, sadece ekrana yansimiyordu).
        """
        active_contacts: list[RWRContact] = []
        dead_emitters: list[str] = []

        for emitter_id, track in self._tracks.items():
            track.age_s += dt

            for kind in _HIERARCHY:
                delay = (self.cfg.missile_detect_delay_s if kind == "fuze"
                         else self.cfg.detect_delay_s)
                if kind in track.fed_this_tick:
                    track.hold_timers[kind] = self.cfg.hold_s
                    track.rise_progress[kind] = track.rise_progress.get(kind, 0.0) + dt
                    if track.rise_progress[kind] >= delay:
                        track.validated[kind] = True
                else:
                    remaining = track.hold_timers.get(kind, 0.0) - dt
                    track.hold_timers[kind] = remaining
                    if remaining <= 0.0:
                        # Hafiza da tukendi -- bu seviye artik hic yok,
                        # bir dahaki sefere sifirdan (yeniden detect_delay
                        # bekleyerek) kanitlanmali.
                        track.hold_timers[kind] = 0.0
                        track.validated[kind] = False
                        track.rise_progress[kind] = 0.0

            live_kinds = [k for k in _HIERARCHY if track.validated.get(k, False)]
            still_tracked = any(track.hold_timers.get(k, 0.0) > 0.0 for k in _HIERARCHY)

            if not live_kinds and not still_tracked:
                dead_emitters.append(emitter_id)
            elif live_kinds:
                current_kind = max(live_kinds, key=lambda k: _HIERARCHY[k])
                active_contacts.append(RWRContact(
                    emitter_id=emitter_id,
                    kind=current_kind,
                    bearing_deg=self._quantize_bearing(track.last_bearing),
                    age_s=track.age_s,
                ))

            track.fed_this_tick.clear()

        for e_id in dead_emitters:
            del self._tracks[e_id]

        self._contacts = active_contacts
        return active_contacts

    def contacts(self) -> list[RWRContact]:
        """En son update()'in urettigi (kuantize edilmis) liste -- disaridan
        okumanin TEK yolu bu olmali, `_tracks` ozel alanina erismek DEGIL."""
        return self._contacts

    def get_worst_threat(self, active_contacts: list[RWRContact] = None) -> RWRContact | None:
        """Verilen (veya en son update()'ten kalan) temaslar icindeki en
        yuksek tehdidi dondurur. Tehdit yoksa None doner."""
        if active_contacts is None:
            active_contacts = self._contacts
        if not active_contacts:
            return None

        # Hiyerarşiye göre en tehlikeli olanı (ve eşitse en eski/uzun süredir takip edileni) bul
        worst = max(
            active_contacts,
            key=lambda c: (_HIERARCHY.get(c.kind, 0), c.age_s)
        )
        return worst
