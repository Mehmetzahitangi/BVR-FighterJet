# Hata Günlüğü — "bu bir hata mıydı?" araştırmalarının kısa kaydı

> Bu dosya, beklenmeyen/şüpheli bir davranışla karşılaşıp "gerçek bir hata mı,
> yoksa yanlış anladığımız/tasarım gereği bir şey mi?" sorusunu araştırdığımız
> HER seferi kısaca kaydeder. Amaç: aynı şüpheyi tekrar tekrar araştırmamak,
> ve "hata değildi" kararlarının GEREKÇESİNİ hatırlamak (aksi halde birisi
> altı ay sonra aynı belirtiyi görüp yeniden alarma geçer).
>
> Ayrıntılı teknik anlatım için her maddenin işaret ettiği `REQUIREMENTS.md`/
> `HANDOFF.md` bölümüne bakın — burası sadece özet ve karar.
>
> **Yeni bir madde eklerken şablon:**
> ```
> ## H-XX — <kısa başlık>
> **Ne ile karşılaştık:** ...
> **Ne yaptık (araştırma):** ...
> **Gerçekten hata mıydı?** EVET / HAYIR
>   - EVET ise → **Düzeltme:** ...
>   - HAYIR ise → **Nasıl anladık:** ...  **Bizi nasıl etkiler:** ...
> **Bağlam:** Faz X.Y, ayrıntı: <dosya/bölüm>
> ```

---

## H-01 — `GuidanceDriver`de eksik komut savurma (slew-rate) sınırı

**Ne ile karşılaştık:** `GuidanceEnv` ile `GuidanceDriver`'ı aynı aksiyon
dizisiyle koşturunca sonuçlar ayrışıyordu (200 adımda ~200 ft irtifa farkı).

**Ne yaptık:** Önce tohum (seed) farkını şüpheli buldum, eşitledim — fark
AYNI kaldı (kanıt: seed sebep değildi). Sonra `GuidanceEnv.step()`'in her
satırını `GuidanceDriver.tick()` ile karşılaştırdım.

**Gerçekten hata mıydı?** EVET.
- **Düzeltme:** `GuidanceConfig.action_rate_limit` (varsayılan 0.25, kapalı
  değil) `GuidanceDriver.tick()`'te hiç uygulanmıyordu — "eğitime özgü bir
  şey" sanılmıştı, oysa dondurulmuş model TAM DA bu filtre altında kalibre
  olmuştu. Eklendi, fark <1e-11'e (kayan nokta gürültüsü) düştü.

**Bağlam:** Faz 1.5b. Ayrıntı: `HANDOFF.md` tuzak 41.

---

## H-02 — `ACMIRecorder` çok nesnede isimsiz/çakışık nesneler

**Ne ile karşılaştık:** Tacview kaydına ikinci uçak/füzeler eklendiğinde
isimsiz görünüyordu; iki ayrı `F16Sim` örneğinden gelen uçaklar aynı yerde
çakışık duruyordu.

**Ne yaptık:** `ACMIRecorder`'ın başlık yazma ve konum hesaplama mantığını
tek-uçaklı orijinal kullanımla karşılaştırdım.

**Gerçekten hata mıydı?** EVET.
- **Düzeltme:** (a) `_header_written` tek bir `bool`'du, `set[int]` yapılıp
  `obj_id` başına izlendi. (b) Konum `lon_deg`/`lat_deg`'den (her `F16Sim`'in
  KENDİ özel orijini) değil, paylaşılan `north_ft`/`east_ft`'ten TEK bir
  referans noktasıyla türetildi.

**Bağlam:** Faz 1.5d. Ayrıntı: `REQUIREMENTS.md` SIM2-05, `HANDOFF.md` tuzak 43.

---

## H-03 — Tacview'de füze izi atış anında değil, bir tik sonra başlıyor

**Ne ile karşılaştık:** Zaman damgaları dosyada GERİYE atlıyordu
(`#2.400 → #2.500 → #2.400`); yeni fırlatılan bir füzenin ilk konumu, atış
anındaki değil BİR TİK SONRAKİ uçak konumuyla birebir aynıydı.

**Ne yaptık:** Uçak ve füze kayıtlarının zaman damgası KAYNAKLARINI ayrı ayrı
izledim.

**Gerçekten hata mıydı?** EVET.
- **Düzeltme:** Uçak kaydı `FlightState.t`'yi (adım SONRASI) kullanıyordu,
  füze kaydına ise betiğin yerel `t = k·dt` (adım ÖNCESİ) veriliyordu — 1 dt
  kayıyorlardı. Füze kaydına da `st.t` verildi, tek saat.

**Bağlam:** Faz 1.5d. Ayrıntı: `REQUIREMENTS.md` SIM2-05, `HANDOFF.md` tuzak 44.

---

## H-04 — Füze kütlesi gerçek uçuşta hiç düşmüyordu

**Ne ile karşılaştık:** Bağımsız bir inceleme, kalkıştaki JSBSim ağırlığının
(22.859 lb) 4 AMRAAM yüklüyken olması gerekenden (24.199 lb) düşük olduğunu
buldu.

**Ne yaptık:** `Engagement.fire()`'ın kütle-düşürme kodunu (`hasattr(state,
"mass_lb")`) gerçek `FlightState` üzerinde test ettim.

**Gerçekten hata mıydı?** EVET.
- **Düzeltme:** `FlightState`'te `mass_lb`/`weight_lb` alanı hiç yok — kod
  sadece `test_engagement.py`'nin mock'unda çalışıyordu, gerçek uçuşta
  sessizce hiçbir şey yapmıyordu. `GuidanceDriver.set_payload()` eklendi
  (gerçek JSBSim `pointmass[0]`'a yazıyor, `payload_check.py` yöntemiyle CG
  korunarak). `Engagement.fire()`'ın mock-uyumlu kodu DOKUNULMADAN kaldı
  (gerçek testin dayandığı davranış).

**Bağlam:** Faz 2.0 hazırlığı (SIM2-07). Ayrıntı: `HANDOFF.md` tuzak 47.

---

## H-05 — Kaçış manevrası (crank) 90° kendi füzesini köreltiyordu

**Ne ile karşılaştık:** 1v1/2v2 duman testlerinde TÜM füzeler `"kor"`
(datalink kaybı) ile bitiyordu, hiç isabet yoktu. İlk yorum: "betikli
komutan her tehditte tam kaçıyor, dengelemiyor" — kasıtlı bir sadelik olarak
kabul edilip düzeltilmeden bırakılmıştı.

**Ne yaptık:** Bağımsız bir inceleme farklı crank açılarını (90°, 50°, 45°,
35°) ölçtü: komut edilen açı ile gerçekleşen tepe ATA arasındaki farkı ve
bunun radar gimbal sınırıyla (60°) ilişkisini.

**Gerçekten hata mıydı?** KISMEN — ilk açıklama YANLIŞ DEĞİLDİ ama EKSİKTİ.
- **Düzeltme (1. tur):** 90°'lik (tam beam) kaçış, gimbal sınırını aşıp
  ATICININ KENDİ kilidini kırıyordu (50° komut → 65.5° gerçek tepe ATA, TEK
  ölçüm). "Kaçıyor" ile "kendi füzesini köreltiyor" aynı olay sanılmıştı,
  ikincisi ayrı ve ölçülebilir bir geometrik sınır ihlaliydi. `--crank-deg`
  parametresi eklendi, varsayılan **35°**'ye çekildi — zincir (atış→pitbull→
  seeker→isabet) ilk kez uçtan uca çalıştı, 1v1'de karşılıklı imha.
- **Düzeltme (2. tur — tek ölçüm yetmedi):** `crank_sweep.py`'nin TAM
  taraması (9 açı × 3 irtifa × 2 Mach + yön kontrolü) 35°'nin EN KÖTÜ
  koşulda (15 kft, M0.8) 56.4° tepe ATA'ya çıkıp kendi 55°'lik güvenlik
  eşiğimizi aştığını buldu — SIM2-07'nin tek gözlemi (25 kft, M0.9) bu en
  kötü koşulu hiç örneklememiş. AYRICA sağ/sol crank'in SİMETRİK OLMADIĞI
  ortaya çıktı (H-06'nın sağa-yatık önyargısı sağ kırmayı güçlendiriyor, sol
  kırmayı söndürüyor). Kendi karar kuralına ("en kötü koşulda ATA_peak≤55°
  veren en büyük θ") harfiyen uyulunca sabit **30°** çıktı, `CRANK_DEG_
  DEFAULT` güncellendi, gerçek 1v1/2v2'de yeniden doğrulandı.
- **Düzeltme (3. tur — "35 aşıyor, 30 aşmıyor" hükmü de EKSİKTİ):**
  bağımsız bir inceleme, ölçülen "tepe ATA"nın neredeyse her koşuda 60
  saniyelik ölçüm PENCERESİNİN TAM SON ÖRNEĞİNDE çıktığını fark etti —
  yani bu bir geçici aşım değil, pencere bitene kadar HÂLÂ BÜYÜMEKTE olan
  bir sürüklenmeydi. Kendim tekrar ürettim: pencereyi 90 s'ye uzatınca
  30° de **69.9°**'ye, 35° **75.2°**'ye çıkıyor — ikisi de 55°'yi aşıyor,
  aralarındaki fark sanılandan (5°) çok daha küçük ve süreye bağlı. Doğru
  çerçeve açı değil MENZİL: her crank açısının güvenli kaldığı bir menzil
  bandı var (30°→~6 nmi, 35°→~9 nmi). **Karar (30°) değişmedi ama gerekçesi
  değişti** — "35 aşıyor, 30 aşmıyor" değil, "30, kilidi ~3 nmi daha yakına
  kadar koruyor". Faz 2.3'e (davranış ağacı) taşınan tasarım önerisi: crank
  sabit açıyla değil, |ATA| geri beslemesiyle sürülsün (eşiği aşınca açıyı
  otomatik kıs) — bu hem asimetriyi hem menzil sürüklenmesini kendiliğinden
  çözer.

**Bağlam:** Faz 2.0 (SIM2-07, SIM2-09). Ayrıntı: `HANDOFF.md` tuzak 45, 49.

---

## H-06 — Guidance, hedef tam karşıdayken bile (be=0) agresif yatış komutu veriyor

**Ne ile karşılaştık:** `crank_sweep.py`'nin θ=0 (crank yok) kontrol koşusu,
80 saniyelik saf `"intercept"` modunda ATA'nın ~20°'ye kadar sürüklendiğini
gösterdi — öz-denetim "|ATA_peak| < 5°" beklentisiyle **FAIL** verdi.

**Ne yaptık:**
1. Önce kendi betiğimden şüphelendim → `GuidanceEnv` ile `GuidanceDriver`'ı
   AYNI senaryoda yan yana koşturdum: aksiyon farkı tam 0.0000. Kod hatası
   DEĞİL.
2. Menzili tarayıp be=0'da action'ın nasıl değiştiğini ölçtüm: eğitim
   aralığının (3.3-14.8 nmi) TAM ORTASINDA bile ~34° yatış komutu çıkıyordu.
   Bu bir kenar-durum değil, dondurulmuş politikanın GERÇEK davranışıydı.
3. Kullanıcının aktardığı dış bir analiz "gözlemde cross-track error eksik,
   Proportional Navigation/lead gerekir, retrain edelim" dedi. Bu teşhisi
   sınadım: kavram olarak "cross-track error" bir HATTA göre tanımlıdır,
   burada tek nokta kovalanıyor (hat yok) — TAM UYMUYOR. Doğru eksik
   kavramın **LOS dönme hızı (λ̇)** olduğunu belirledim (gözlemde hiç yok;
   bu proje füze güdümünde `a=N·V·λ̇` ile zaten doğru kullanıyor, ama uçağın
   kendi güdümü saf takip/pure pursuit).

**Gerçekten hata mıydı?** HAYIR (kod hatası değil) — ama GERÇEK bir mimari
sınırlama, sadece MALİYETİ ÖLÇÜLENE KADAR "hata" damgası vurulmadı.
- **Nasıl anladık:** Yukarıdaki 3 adım — GuidanceEnv≡GuidanceDriver eşitliği
  (kod değil), be=0'daki tepkinin eğitim aralığının içinde tekrar üretilmesi
  (rastgele değil), ve λ̇'nın gözlemde gerçekten yokluğu (mekanizma).
- **Bizi nasıl etkiler:** `scripts/pursuit_cost.py` ile gerçek angajman
  ölçeğinde (30 nmi→10 nmi kapanma) maliyet ölçüldü: zaman farkı en kötü
  +2.3%, yol farkı +0.1%, gimbal payı en dar +41.9° (60°'lik sınırdan çok
  uzak). **Önemsiz çıktı.** Retrain (guidance'ın gözlem vektörünü değiştirip
  λ̇ eklemek) ERTELENDİ — donmuş katmanı (guidance+CBF) açmanın bedeli
  (haftalarca yeniden ölçüm) bu ölçülen faydaya değmiyor. İzlenecek: 2v2/4v4
  gibi daha uzun sürdürülen intercept fazlarında veya daha dar menzilli
  senaryolarda maliyet büyürse bu karar yeniden ölçümle gözden geçirilecek.

**Bağlam:** Faz 2.0. Ayrıntı: `REQUIREMENTS.md` SIM2-08, `HANDOFF.md` tuzak 50.

---

## H-07 — RWR: kod çalışıyor GİBİ görünüyordu, ama durum makinesinin yarısı hiç tetiklenmemişti

**Ne ile karşılaştık:** `bvr/combat/rwr.py` (RWR modeli) ilk sürümünde
yazıldı, `Engagement.update()`'e bağlandı, 46/46 mevcut test geçti ve
gerçek 1v1'de "atış görünmez" davranışı (kilit sabitken füze atılınca RWR
çıktısı değişmiyor) doğru çalışıyordu. Kod incelemesinden geçmiş gibiydi.

**Ne yaptık (araştırma):** Bağımsız bir inceleme, "çalışıyor" sonucuna
güvenmeden CANLI YOLUN (smoke betiğinin GERÇEKTE okuduğu değerlerin)
`RWR.update()`'in ÜRETTİĞİ değerlerle aynı olup olmadığını ayrıca ölçtü.
Ayrıca "seviye düşüyor mu" ve "arama hiç beslenmiş mi" gibi hiç kimsenin
sormadığı soruları test etti.

**Gerçekten hata mıydı?** EVET — üç ayrı, birbirinden bağımsız hata, hepsi
"mekanizma doğru yazılmış ama devrede değil" türünden:

1. **Kuantizasyon canlı yolda hiç uygulanmıyordu.** `RWR.update()`
   kuantize edilmiş listeyi doğru üretiyordu ama dönüş değeri
   `Engagement.update()` içinde çöpe gidiyordu; smoke betiği bunun yerine
   `rwr._tracks[...].last_bearing` (özel alan) okuyup HAM açıyı alıyordu.
   Ölçülen: ham +10.26° vs olması gereken kuantize +15.00°. **Düzeltme:**
   `RWR.contacts()` public okuyucusu eklendi, smoke betikleri artık
   sadece bunu çağırıyor.
2. **Seviye hiçbir zaman düşmüyordu.** `feed_signal()` sadece
   yükseltiyordu, düşüş yolu hiç yazılmamıştı — "kilit" bir kez
   raporlanınca sonsuza kadar öyle kalıyordu, altına sadece "arama"
   beslense bile. **Düzeltme:** her seviye kendi bağımsız yükselme/hafıza
   sayacını tutacak şekilde yeniden yazıldı; raporlanan seviye o an hâlâ
   taze olan en yükseği.
3. **"arama" aşaması hiç beslenmiyordu.** Kablolamada sadece
   `contact.tracked` → "kilit" vardı; `contact.detected and not tracked`
   → "arama" dalı unutulmuştu. Üç aşamalı zincir iki aşamaya inmişti.
   **Düzeltme:** ayrım eklendi.

**Neden şimdiye kadar hiç yakalanmadı:** mevcut testler (46/46) ve "atış
görünmez" doğrulaması bu üç hatanın HİÇBİRİNİN tetiklendiği bir senaryoyu
kapsamıyordu — kuantizasyon her zaman bir tık öteden (özel alan) okunuyordu,
seviye düşüşü hiç denenmemişti, "arama" hiç aranmamıştı. Kod "çalışıyor"
görünüyordu çünkü kimse eksik yarısını TETİKLEYEN bir test yazmamıştı.
Bu, H-01/H-04'ten farklı bir tür: onlarda mekanizma YANLIŞ çalışıyordu,
burada mekanizmanın YARISI hiç yazılmamıştı ama diğer yarısı gayet
düzgün çalıştığı için gözden kaçıyordu.

**Bizi nasıl etkiler:** Üçü de düzeltildi, izole testlerle (kuantizasyon,
seviye düşüşü, tam sessizlikte silinme) ve gerçek 1v1/2v2 koşularıyla
doğrulandı — sonuçlar (isabet zamanlaması, imha sayıları) düzeltme
öncesiyle aynı mertebede, RWR'nin gerçekçi gecikmesi (~1 s) beklenen
küçük bir farkı üretti. `test_rwr.py` yazıldı (10/10 geçiyor, `bvr/combat/
tests` toplamı 56/56) — bu üç hatanın hiçbiri artık commit'lenmiş testsiz
değil; her test, düzeltmeden önceki koda karşı koşulsaydı kırılırdı
(HANDOFF tuzak 46 disiplini). Bağımsız incelemenin ikinci turu iki eksiği
daha buldu ve ikisi de eklendi: (a) ilk testler "sinyal TAMAMEN kesilirse"
senaryosunu sınıyordu, asıl hata senaryosu olan "kilit kesilip arama
DEVAM ederse seviye gerçekten arama'ya düşer mi" ayrı ve eksikti; (b)
kuantizasyon hatası bir BİRİM testiyle hiç yakalanamazdı çünkü hata `RWR`
sınıfının içinde değil KABLOLAMADAYDI (smoke betiğinin özel alana erişmesi)
— bunun için smoke betiklerinin kaynağını tarayıp `_tracks` erişimi
olmadığını doğrulayan yapısal bir test eklendi, hatanın tek örneğini değil
SINIFINI kapatan türden.

**Üçüncü tur — mutasyon testi, "10/10 geçiyor" ifadesinin kendisini
sorguladı.** Bağımsız inceleme, TÜM testler yeşilken kodu BİLEREK bozdu:
kuantizasyonu kapattı ve füzeyi pitbull yerine atış anından besledi.
**İkisi de 10/10'u hiç etkilemedi.** Sebep aynı desenin bir kez daha
tekrarı: mevcut Engagement testlerinin hepsi head-on (ham kerteriz=0°,
kuantize edilse de edilmese de 0 kalıyor) geometri kullanıyordu, ve "atış
görünmez" testi atıştan sonra sadece TEK TİK ilerliyordu
(`missile_detect_delay_s=0.5`'i aşacak kadar değil) — yani iddia ettiği
şeyi değil, "anında sızıntı yok"u ölçüyordu. İki test eklendi (`test_10`:
açılı geometri + `RWR`'in kendi kuantize formülüyle beklenen değeri
hesaplayıp canlı yoldan geleni karşılaştırma; `test_5b`: atıştan sonra 5 s
boyunca her tikte "fuze" sızmadığını kontrol) ve AYNI iki mutasyon TEKRAR
uygulanıp bu sefer ikisinin de yakalandığı doğrulandı (dosyalar md5 ile
orijinaline geri yüklendi). `bvr/combat/tests` artık **58/58** (12/12
`test_rwr.py`).

**Genel ders (HANDOFF tuzak 51):** "test paketi geçiyor" bir davranışın
SINANDIĞI anlamına gelmez. Yazdığın her kritik testi bilerek bozup
kırmızıya döndüğünü GÖRMEDEN, o testin gerçekten bir şey sınadığını
varsayma — bu, tuzak 46/48'in ("başarısız olamayan test test değildir")
daha sistemli, tekrarlanabilir bir uygulaması.

**Bağlam:** Faz 2.1. Ayrıntı: `REQUIREMENTS.md` RWR-01/02/03,
`HANDOFF.md` tuzak 51.

---

## H-08 — `DuelResult`'ın otomatik eşitliği tekrar-üretilebilirlik testini HER ZAMAN başarısız gösteriyordu

**Ne ile karşılaştık:** `duel.py::run_duel()` yazıldıktan sonra, aynı
senaryo tohumunu iki kez koşturup `r1 == r2` diye karşılaştırdım —
**False** döndü. İlk bakışta ciddi bir tekrar-üretilebilirlik hatası gibi
göründü.

**Ne yaptık (araştırma):** İki sonucu alan alan yazdırıp karşılaştırdım —
`wall_time_s` (gerçek duvar-saati süresi) HARİÇ her şey birebir aynıydı.

**Gerçekten hata mıydı?** HAYIR (koddaki fizik/mantık doğru) — ama
öz-denetimin KENDİSİNDE gerçek bir tuzak vardı.
- **Nasıl anladık:** `DuelResult` düz bir `@dataclass` — Python'ın
  otomatik ürettiği `__eq__` TÜM alanları karşılaştırır. `wall_time_s`
  gerçek duvar-saati süresidir (performans izleme için eklendi), fiziksel
  simülasyondan bağımsızdır ve iki koşuda ASLA aynı çıkmaz (işletim
  sistemi zamanlaması, CPU yükü vb.). Bu yüzden `r1 == r2` HER ZAMAN
  False dönerdi, tekrar üretilebilirlik gerçekte tam sağlanmışken bile.
- **Bizi nasıl etkiler:** `eval_commander.py`'nin öz-denetimi, karşılaştırmadan
  önce `dataclasses.replace(r, wall_time_s=0.0)` ile bu alanı sıfırlıyor.
  Genel ders: bir sonuç nesnesine "bu koşuya özgü, doğası gereği
  belirsiz" bir alan (performans ölçümü, zaman damgası vb.) eklerken,
  o nesnenin eşitlik/tekrar-üretilebilirlik testlerinde KULLANILMAYACAĞINI
  açıkça düşünmek gerekir — dilin otomatik ürettiği `__eq__` bunu bilemez,
  sessizce "hiçbir zaman eşit değil" der. Bu, mutasyon testi (H-07/tuzak 51)
  disiplininin ERKEN bir uygulamasıydı: öz-denetimi yazar yazmaz gerçek
  bir koşuyla sınadım ve beklenmeyen bir False ile karşılaştım — "neden
  False" sorusunu sormak, kodu düzeltmekten önce geldi.

**Bağlam:** Faz 2.2. Ayrıntı: `REQUIREMENTS.md` EVAL-01.

---

## H-09 — Değerlendirme aracı TARAF TUTUYORDU (koltuk önyargısı) + nz işareti + kusurlu öz-denetim

**Ne ile karşılaştık:** İlk tam koşu (n=200, 800 savaş) bitince sonuçlara
bakarken mavi, aynı modelin kendisine karşı oynadığı halde karar verilen
angajmanların %70'ini kazanmıştı (155 galibiyet : 65 mağlubiyet). Simetrik
bir ölçümde bu ~%50 olmalı.

**Ne yaptık (araştırma):** Şüphelenmek yerine CSV'den ölçtüm: senaryoları
tohumdan yeniden üretip her iki tarafın BAŞLANGIÇ burun-hedef açısını
hesapladım. Mavi ort. 8.6°, kırmızı ort. 30.3°. Mavinin galibiyet payı bu
farkla monoton artıyordu (0.55 → 0.69 → 0.90). Aynı bakışta `nz_min`
sütununun 800 satırda da negatif çıktığını (en büyüğü −1.47) fark ettim.

**Gerçekten hata mıydı?** EVET — üçü de ölçüm aracının hatası, modelin değil:
1. **Koltuk önyargısı.** Spesifikasyon "yalnızca kırmızının yönü ±60° rastgele"
   diyordu; mavi hep burnu rakibe dönük başlıyordu. Doğu-batı aynası sol/sağ
   önyargısını dengeler, mavi/kırmızı koltuğunu DEĞİL (normal 0.70, ayna
   0.71). **Düzeltme:** mavinin yönü de kırmızıyla aynı dağılımdan çekiliyor
   (`blue_offset_deg`, çizim EN SONA eklendi, ayna onu da çeviriyor).
2. **`nz_min` işareti.** Proje sözleşmesinde düz uçuş = +1, ham `st.nz` düz
   uçuşta ≈ −1 (tuzak 5). Ham değerin minimumu = +g çekişiydi (−8.08 =
   +8.08 g), izleme listesindeki negatif-g eşiğiyle ilgisiz. **Düzeltme:**
   `g = −st.nz`, `nz_min` + `nz_max` ayrı.
3. **Öz-denetim kriteri.** "Tüm koşularda kazanma oranı %50'yi içermeli"
   beraberlikleri hesaba katmıyordu. n=10'da GA geniş olduğu için sorun
   gizli kalmıştı; n=400'de sırf bu yüzden düşerdi. **Düzeltme:** geometri
   simetri kontrolü (simülasyonsuz, keskin) + karar verilenlerde mavi payı;
   tam koşu raporuna yerleşik "ölçüm aracı taraf tutuyor" uyarısı.

**Neden şimdiye kadar yakalanmadı:** 40 koşuluk öz-denetim ve 10 örnekli
kontroller Wilson aralığı genişken bu önyargıyı GÖREMEZDİ. Önyargı ancak
n=400'de ve sonuçlara "aynı model, neden bir taraf kazanıyor?" diye
bakınca göründü. Spesifikasyonun kendi §9-3 maddesi ("kendisine karşı →
%50") doğru soruyordu; benim uygulamam yanlış soruyu (beraberlik dahil
tüm oran) sordu.

**Bizi nasıl etkiler:** İlk koşunun sayıları (truth 0.388 / rwr 0.367,
McNemar p=0.096) asimetrik bir dağılım üzerinde ölçüldü — NİHAİ DEĞİL.
Paired karşılaştırma büyük ölçüde etkilenmez (her iki kol aynı önyargıyı
taşıyor) ama mutlak kazanma oranları ve Faz 4'ün RL-vs-betikli
karşılaştırması için araç simetrik olmak zorunda. Düzeltilmiş araçla koşu
yeniden yapılacak.

**Genel ders (HANDOFF tuzak 52):** ölçüm aracının kendisini, sonucu
bilinen bir duruma (aynı model kendisine karşı → simetri) karşı sına — ve
bunu SİMÜLASYONSUZ, anlık yapabildiğin yerde yap (geometri kontrolü).

**Bağlam:** Faz 2.2. Ayrıntı: `REQUIREMENTS.md` EVAL-02.


---

## H-10 — 5439 füzenin sıfırı `iska`: hata mı, yoksa hiç olmuyor mu?

**Ne ile karşılaştık:** 800 savaşta 5439 füze atıldı; `iska_count` hep 0.
"Hiç olmuyor" ile "olsa da raporlanmıyor" arasını ayıramıyorduk (MSL-09'un
atıl kapısıyla aynı aile).

**Ne yaptık (araştırma):** Zinciri üç halkaya böldüm. (1) `Missile`:
`test_9b` zaten `iska` üretiyor. (2) `Engagement`: olay türü
`state.result`'tan geliyor (`kind=state.result`), ama gerçek bir angajmanda
hiç sınanmamıştı. (3) `run_duel`: `iska` `kind_counts` sözlüğünde; aynı
genel dal `kor/hedefsiz/tukenme` için 800 koşuda sıfırdan farklı sayılar
üretiyor — yani dal çalışıyor. Eksik halka (2) idi: enerjili bir füzeyi
öldürme yarıçapının dışından geçirip olayı ve hedefin hayatta kalmasını
denedim. Önce ölçtüm: 8 nmi kafa kafaya, en iyi mesafe ~8 ft.

**Gerçekten hata mıydı?** HAYIR — raporlama zinciri sağlam.
- **Nasıl anladık:** Yarıçapı 2 ft yapınca aynı füze `iska` olay günlüğüne
  yazıyor, hedef hayatta, `tukenme` yok (`test_engagement.py::test_10`,
  mutasyonla sınandı: engagement `iska`→`kor` ve missile hep-`isabet`
  ikisi de yakalanıyor). 30 ft'lik gerçek yarıçapta 3-DOF PN + 0.05 s
  entegrasyon ~8-24 ft'e iniyor: enerjisi olan füze ya vuruyor ya
  enerjisini tüketiyor; ıska penceresi ince.
- **Bizi nasıl etkiler:** `iska=0` bir raporlama hatası değil, model
  gerçekçiliğinin (3-DOF PN, manevra-gürültüsüz hedef) bir sonucu.
  Gerçek füzeler daha çok ıskalar; tezde "füze modeli kusursuz güdümlü,
  ıska yalnız enerji/seeker kaybından" cümlesi açık yazılmalı (MSL-09).

**Bağlam:** Faz 2.2, EVAL-03b.

## H-11 — Eşleşmiş veriyi bağımsız çiftmiş gibi test etmek (iyimser p)

**Ne ile karşılaştık:** Özet tabloda iki Wilson aralığı örtüşüyordu
(0.253 [0.212, 0.297] vs 0.223 [0.184, 0.266]) ama McNemar p=0.029 çıkmıştı.
İnceleme: hangisi doğru, ve 400 çift gerçekten bağımsız mı?

**Ne yaptık:** Aynı veriyi üç şekilde çözümledim: ham 400 çift (p=0.029),
ayna kopyaları ayrı ayrı (p≈0.15–0.18, tek başına güçsüz), senaryo düzeyinde
kümelenmiş — 200 tohum, ayna çifti tek gözlem (18:6, p=0.023).

**Gerçekten hata mıydı?** KISMEN — sonuç aynı kaldı ama YÖNTEM eksikti.
- **Düzeltme:** Ayna kopyaları aynı tohumdan (ortak yakıt/irtifa/Mach/
  türbülans büyüklükleri) geldiği için bağımsız değil; araç 400 bağımsız
  çift varsayıyordu, oysa 200 senaryo var. `compare_arms_clustered` eklendi
  ve ASIL karar oldu; koşu düzeyi test bilgi olarak basılıyor. Örtüşen
  Wilson aralıkları EŞLEŞMİŞ karşılaştırmada karar kriteri değil (eşleşmeyi
  harcıyor) — rapora not eklendi.

**Bağlam:** Faz 2.2, EVAL-03b. Ayrıntı: `HANDOFF.md` tuzak 53.


## H-12 — Menzil–isabet ilişkisi müdahalede tutmadı: hata mı, yanlış yorum mu?

**Ne ile karşılaştık:** EVAL-03b'de "başlangıç ayrımı arttıkça isabet düşüyor
(%80→%38→%19)" bulgusuna dayanarak atış kapısını 35→25 nmi'ye çektik. Beklenti:
atış başına isabet birkaç kat artar. Sonuç: mavinin atış başına isabeti
%6.5→%6.6 (değişmedi), kazanma p=0.90, mavi kaybı 89→120.

**Ne yaptık (araştırma):** (1) A kolunu önceki koşuyla 400/400 birebir
karşılaştırdık → kod kayması yok. (2) Kapının kaç senaryoda bağladığına baktık
→ 392/400, seyrelme yok. (3) Yeni CSV sütunlarıyla A kolunda atış-başına-isabeti
İLK ATIŞ MENZİLİNE göre kırdık → ilişki gerçek (%17.8/%12.3/%6.1/%2.8).
(4) Sonuç geçişlerini ve kayıpları senaryo düzeyinde inceledik.

**Gerçekten hata mıydı?** HAYIR — ölçüm ve kod doğru; YORUM eksikti.
- **Nasıl anladık:** İlişki gözlemsel olarak sağlam ama müdahalede
  tutmuyor; iki açıklama var: senaryo geometrisiyle karışıklık veya
  atış-kaçış eşleşmesi (bir tarafın gecikmesi rakibi kaçıştan kurtarıyor,
  rakibin isabeti %6.5→%8.7 çıkıyor). Hangisi olduğunu şu anki veri ayırt
  edemiyor (füze sonlanma nedenleri taraf bazında yok).
- **Bizi nasıl etkiler:** Gözlemsel korelasyonu müdahale sonucu diye
  sunmuyoruz; "atış kapısı" davranış ağacına olduğu gibi girmiyor. Önceden
  yazılmış tahmin sayesinde çürütme net ve tartışmasız.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ (2.3'ün kendisi başlamadı), EVAL-05. Ayrıntı: `HANDOFF.md` tuzak 56.


## H-13 — "Füzelerin %71'i enerji tüketiyor, menzil yüzünden": varsayım yanlış çıktı

**Ne ile karşılaştık:** EVAL-03b'de füzelerin ~%70'i `tukenme` ile bitiyordu ve
başlangıç ayrımıyla isabet düşüyordu (%80→%38→%19); "çok uzaktan atıyoruz"
varsayımıyla atış kapısı deneyleri kuruldu (EVAL-04..06).

**Ne yaptık (araştırma):** (1) Simetrik kapıyla (iki taraf 25 nmi, taze tohum)
tükenme oranını ölçtük → %70.8→%71.1, DEĞİŞMEDİ. (2) Taraf bazlı füze sonlarıyla
kazancın nereden geldiğine baktık → kör füze %3.0→%0.6. (3) Füze zarfını kusursuz
kilitle ölçtük (`scripts/missile_envelope.py`): enerji bütçesi ~70 s, kafa kafaya
azami menzil ~30–33 nmi, hedef döndükçe daha kısa.

**Gerçekten hata mıydı?** HAYIR — ölçüm ve kod doğru; VARSAYIM yanlıştı.
- **Nasıl anladık:** Müdahale (menzili 10 nmi kısaltmak) çalıştı (isabet +%23,
  p=7.5e-7) ama beklenen kanaldan değil: tükenme kıpırdamadı, kör füze çöktü.
  "Müdahale çalıştı" ile "varsayım doğruydu" aynı şey değil.
- **Bizi nasıl etkiler:** Tükenmenin nedeni bilinmiyor; en olası aday hedefin
  dönmesi/kaçışı (SIM2-09 crank sürüklenmesiyle tutarlı, sınanmadı). Atış menzili
  küçük bir kaldıraç (+1.3 puan); büyük kaldıraç savunma manevrası/kaçış tasarımında
  olabilir → Faz 2.3 davranış ağacının odağı buraya kayıyor.
- Yan bulgu: `LaunchRules.max_launch_nm=35`, füzenin KENDİ kafa kafaya kinematik
  menzilinden (~33) uzun (35 nmi'de kusursuz kilitle bile tükeniyor). Hata değil
  (yetki ≠ Rmax), ama tez metninde ayrı kavramlar olarak yazılmalı.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ (2.3'ün kendisi başlamadı), EVAL-07. Ayrıntı: `HANDOFF.md` tuzak 58.


## H-14 — "Kaçış rakibin füzesini körletir, o yüzden geç atan kaybeder" hipotezi çürüdü

**Ne ile karşılaştık:** EVAL-05'te mavi 25 nmi'de (kırmızı 35) atınca mavi kaybı 89→120,
kırmızının isabeti %6.5→%8.7 çıktı. Hipotezim: mavi geç atınca kırmızı erken kaçışa
zorlanmıyor, kendi füzelerini kilitli tutuyor (kör füze payı düşer).

**Ne yaptık (araştırma):** Taze tohumda (2000–2199) tekrar; tahmin ve yorum tablosu
sonuçtan ÖNCE yazıldı (EVAL-08). Bu sefer taraf bazlı füze sonları vardı.

**Gerçekten hata mıydı?** HAYIR — etki gerçek ve tekrarlandı; MEKANİZMA hipotezim
yanlıştı.
- **Nasıl anladık:** Mavi kaybı 94→123 (6:28, p=2e-4; EVAL-05 ile birleşik 7:53,
  p=7.7e-10) → etki tekrarlandı. Ama kırmızının kör payı DEĞİŞMEDİ (%2.7→%2.6);
  değişen şey mavinin havada-kalan füze payı (%12.9→19.0). Kör-eşleşme değil,
  atış yarışı + sansür (isabet düelloyu bitirir, geç atanın füzeleri kesilir) daha
  olası — henüz kanıt değil, yalnız veriyle uyumlu.
- **Bizi nasıl etkiler:** Tek taraflı atış gecikmesi güvenilir biçimde zarar verir;
  atış kapısı davranış ağacına girmez. "Ham atış başına isabet" geç atan taraf için
  yanıltıcı (kesilen füzeler payda) — sonuca ulaşan füze başına orana da bak.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ (2.3'ün kendisi başlamadı), EVAL-08. Ayrıntı: `HANDOFF.md` tuzak 59.


## H-15 — N kolunda "ölçüm aracı taraf tutuyor" uyarısı: şans mı, önyargı mı? (KAPANDI: şans; küçük artık İZLENİYOR)

**Ne ile karşılaştık:** Hiç-kaçış tanı kolunda (N) yerleşik koltuk uyarısı tetiklendi: karar
verilen 378 savaşta mavi payı 0.56 (GA [0.51, 0.61]). Diğer 7 simetrik kolda 0.49–0.52 idi.

**Ne yaptık (araştırma):** (1) normal/ayna ayrımı: 0.58 / 0.54 → geometri değil koltuk.
(2) Senaryo düzeyi: mavi-çok-isabet 79, kırmızı 53 (p=0.029); C kolunda 42:37. (3) TAM simetrik
senaryoda (verbose) düello birebir simetrik: aynı anda atış, aynı anda isabet, karşılıklı imha
→ temel döngüde sıra yanlılığı yok. (4) Örneklemdeki mavi−kırmızı irtifa/Mach/yakıt farkı
+0.6–0.7σ (anlamsız) ve mavinin kazanmasıyla ilişkisi sıfır/ters. (5) İlk atış menzili ve
zamanı eşit (24.9864 nmi), atış sayısı 969/979.

**Gerçekten hata mıydı?** HAYIR — EVAL-10 taze tohumlu tekrarıyla ŞANS olarak kapandı (aşağıdaki güncelleme).
- **Nasıl anladık / anlayamadık:** Kod yanlılığı ve örnekleme dengesizliği elendi; kalan en olası
  açıklama şans (8 simetrik kol kontrolünde en az bir %5'lik uyarı olasılığı ~%34). Kanıt değil.
- **Bizi nasıl etkiler:** EVAL-09'un birincil sonucu (%57.8 → %100, p=1e-28) koltuk-bağımsız bir
  ölçüte dayanır ve 42 puanlık farkı bir koltuk yanlılığı açıklayamaz → sonuç etkilenmiyor. Ama
  gelecekteki N-benzeri (belirlenimci yarış rejimi) karşılaştırmalarında mavi kazanmaya
  güvenilmemeli; şüphe replikasyonla (N kolu taze tohumda) kapanmalı.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ (2.3'ün kendisi başlamadı), EVAL-09. Ayrıntı: `HANDOFF.md` tuzak 60.

**GÜNCELLEME (EVAL-10, 2026-09-20) — kapanış:** N kolu taze tohumda (4000–4199) tekrarlandı:
mavi payı **0.491 [0.441, 0.541]** (senaryo düzeyi 72:74) → önceden yazılmış karar kuralı gereği
**şans**, madde kapandı. Uyarı bu sefer C koluna kaydı (0.572, GA 0.5'i dışlar) — çoklu kontrol
örüntüsü. 8 benzersiz simetrik koşunun birleşik mavi payı 1050/2021 = 0.5195 [0.498, 0.541]
(p=0.083); ≥2 uyarının şans olasılığı 0.057. Küçük (~2 puan) bir mavi avantajı TAMAMEN dışlanmadı
→ İZLEME maddesi (yeni simetrik koşularla güncellenir); eşleşmiş tasarımlarda sadeleşir.
Ders: tek bir uyarıyı hemen açıklamaya çalışmak yerine, kod yanlılığını ele, örnekleme dengesizliğini
ele, TEKRARLA (tuzak 60).


## H-16 — "Kaçış en büyük kaldıraç, hep kaçmak savunmada iyi": çıkarım yarı yanlıştı

**Ne ile karşılaştık:** EVAL-09'da kaçışı tamamen kapatınca (N) ≥1 isabetle biten savaş %57.8 → %100 oldu;
buradan "füzeleri asıl kaçış başarısız kılıyor, en büyük kaldıraç savunma politikası, sürekli kaçış savunmada
iyi (sağ kalıyor) ama saldırıyı öldürüyor" sonucunu çıkardım ve EVAL-11'de tetikleyiciyi geciktirmenin
hayatta kalmayı kötüleştireceğini (net skor düşer, ~%90) tahmin ettim.

**Ne yaptık (araştırma):** Mavi kaçışı geciktirilen asimetrik kollar (T=15 s ve T=∞ yalnız-fuze), taze
tohum, Bonferroni. Sonra kaçış moduna dair sağlık kontrolü (kaçış süresi medyan 15.5 s = aktif arayıcı
penceresi, gecikme alanı doğru kaydedilmiş).

**Gerçekten hata mıydı?** KISMEN — ölçüm/kod doğru; çıkarımım ve tahminim yanlıştı.
- **Nasıl anladık:** B2'de mavi net skor −2 → +144 (p=8e-15); kayıp yalnız +%33 (86→114), kazanma 84 → 258.
  EVAL-09 doğruydu (kaçış füzeleri yeniyor) ama TEK TARAFLI erken kaçışın hayatta kalma faydası, atağa
  maliyetinden çok küçük: aktif arayıcıdan sonra başlayan kaçış bile ~%80 hayatta bırakıyor. EVAL-09'dan
  çıkardığım "sürekli kaçış savunmada iyi" cümlesi YANLIŞTI. Füze zarfı ölçümüne dayanarak "yalnız-fuze
  neredeyse önceden belli (kaçış pitbull'da kurtarmaz)" demiştim — ölçüm doğruydu, çıkarım değil (15 nmi'de
  kusursuz kilitle bile isabet ≠ gerçek savaşta kaçışın kurtarmadığı).
- **Bizi nasıl etkiler:** Betikli taban çizgisi ("kilitte kaç") sömürülebilir. Faz 4'ün "RL, betikli tabanı
  geçsin" ölçütü zayıf tabana karşı yanıltıcı olurdu. Taban ÖNCE güçlendirilmeli. Bkz. tuzak 61.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ (2.3'ün kendisi başlamadı), EVAL-11. Ayrıntı: `HANDOFF.md` tuzak 61, `REQUIREMENTS.md` EVAL-11.


## H-17 — Sabit menzil kapısı "küçük kaldıraç" sonucu irtifa karışımının ortalamasıymış

**Ne ile karşılaştık:** EVAL-07'de simetrik 25 nmi kapısı isabeti yalnız ~+1.3 puan artırmıştı; H-13'te "atış menzili küçük kaldıraç" dedik.
Kalibrasyon ölçümü (`missile_envelope.py --sweep`) füze zarfının irtifaya çok bağlı olduğunu gösterdi (kafa kafaya Rmax 22.8/32.7/49.0
nmi, 15/25/35 kft, M0.9) — oysa atış yetkisi ve kapı her irtifada sabit.

**Ne yaptık (araştırma):** EVAL-07 verisini atıcı irtifa dilimine böldük (simülasyonsuz): <20 kft'te isabet %1.0→%4.3 (tükenme %84→%85),
20–30 kft'te %7.2→%8.0, ≥30 kft'te %14.0→%13.3.

**Gerçekten hata mıydı?** HAYIR (veri ve kod doğru) — YORUM eksikti.
- **Nasıl anladık:** Kapının etkisi yalnız alçak irtifada görünüyor ve orada bile 25 nmi zarfın dışında kalıyor (tükenme %85); yüksekte
  zarf 35 nmi'yi zaten aşıyor (kapı gereksiz). Ortalama bu üç farklı rejimi sildi (Simpson'a benzer bir karışım).
- **Bizi nasıl etkiler:** "Menzil kapısı etkisiz" cümlesi YANLIŞ genelleme olurdu; doğrusu "SABİT menzil kapısı ortalamada zayıf". İrtifa/
  hız-farkında bir atış kapısı hipotezi 2.3c'de ölçülecek (post-hoc; ölçülmedi). Tuzak 62.

**Bağlam:** Faz 2.3 ÖN ÖLÇÜMÜ, kalibrasyon (§13.5).
