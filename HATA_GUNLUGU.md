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
