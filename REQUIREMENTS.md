# Gereksinimler ve Doğrulama Matrisi

Bu doküman, sistemin **ne yapması gerektiğini** tanımlar ve her gereksinimin
hangi testle doğrulandığını gösterir. Havacılık pratiğinde kontrol yasası
tasarımı böyle başlar: önce kabul kriteri, sonra tasarım, sonra doğrulama.

> **Dürüstlük notu:** Bu doküman projenin ortasında yazıldı, başında değil.
> Bazı kriterler ölçümden *sonra* belirlendi (post-hoc). Aşağıda hangilerinin
> tasarım öncesi konduğu, hangilerinin sonradan yazıldığı işaretlenmiştir.
> Gerçek bir program bunu tersine yapar; bunu gizlemek yerine kaydediyoruz.

Durum kodları: **✅ doğrulandı** · **⚠️ kısmen** · **⬜ açık** · **📋 gelecek faz**

---

## 0. Kapsam ve tanımlar

| Terim | Tanım |
|---|---|
| **İşletme zarfı** | 10.000–42.000 ft, M0.55–1.35, ±80° yatış, ±30° uçuş yolu açısı |
| **Güvenlik zarfı** | α ≤ 22°, \|β\| ≤ 10°, −3 ≤ n ≤ 9 g, M ≥ 1.25×stall(h), h ≥ 5.000 ft |
| **Sonlandırma zarfı** | α ≤ 26°, \|β\| ≤ 15°, −3.5 ≤ n ≤ 9.5 g, M ≥ stall(h), h ≥ 3.000 ft |
| **Zarf ihlali** | 60 Hz'de örneklenmiş durumun güvenlik zarfı dışında olması |

**Zarf hiyerarşisi kuralı:** işletme ⊂ güvenlik ⊂ sonlandırma ⊂ fiziksel limit.
Üçünün de ayrı olması zorunludur; ikisi çakışırsa filtre ya sürekli tetiklenir
ya da koruduğu sınır bölümün öldüğü sınırdan dışarıda kalır. (İkisi de yaşandı,
bkz. ARCHITECTURE.md § Ölçüm metodolojisi.)

---

## 1. Sistem seviyesi (SYS)

| ID | Gereksinim | Durum | Doğrulama |
|---|---|---|---|
| SYS-01 | Sistem, komutan katmanından gelen (konum, irtifa, hız) hedeflerini otonom olarak gerçekleştirecek | ✅ | `safety_eval.py` |
| SYS-02 | Sistem, klasik güdüm yasasından **ölçülebilir şekilde daha iyi** görev performansı gösterecek | ✅ | ödül 2101 [2028, 2174] vs 1915 [1798, 2021], GA örtüşmüyor |
| SYS-03 | Sistem, güvenlik zarfını korumak için bir filtre içerecek; filtre görev performansını **%5'ten fazla** düşürmeyecek | ✅ | 2099 vs 2101 (maliyet ≈ 0) |
| SYS-04 | Tüm sonuçlar tek komutla yeniden üretilebilecek | ✅ | `scripts/reproduce.py` |
| SYS-05 | Her koşunun tam konfigürasyonu kalıcı olarak kaydedilecek | ✅ | `config.resolved.yaml` |

---

## 2. İç döngü (INN) — *kriterler tasarım öncesi konuldu*

Doğrulama koşulları: 15k/M0.7 · 25k/M0.85 · 35k/M1.0 · 45k/M1.3

| ID | Gereksinim | Kriter | Ölçülen | Durum |
|---|---|---|---|---|
| INN-01 | Yatış açısı basamak yanıtı (0→45°) yükselme zamanı | < 2.5 s | 0.70–0.77 s | ✅ |
| INN-02 | Yatış açısı aşımı | < %20 | %3–17 | ✅ |
| INN-03 | Yatış açısı kalıcı hatası | < 2.0° | 0.07–0.16° | ✅ |
| INN-04 | Uçuş yolu açısı basamak yanıtı (0→8°) yükselme zamanı | < 4.0 s | 1.3–2.4 s | ✅ |
| INN-05 | Uçuş yolu açısı aşımı | < %25 | %3.5–10 | ✅ |
| INN-06 | Uçuş yolu açısı kalıcı hatası | < 1.0° | ≈ 0.00° | ✅ |
| INN-07 | Mach kalıcı hatası | < 0.02 | 0.0001–0.006 | ✅ |
| INN-08 | Koordineli dönüşte (45° bank, 20 s) irtifa sapması | < 500 ft | 27–51 ft | ✅ |
| INN-09 | İç döngü kazançları sabit olacak (ortam durağanlığı) | — | q̄ ile çizelgeli, durumun deterministik fonksiyonu | ✅ |
| INN-10 | Doğrulama **tüm zarfı** kapsayan Monte Carlo kampanyasıyla yapılacak | ≥ 500 koşul | **4 koşul** | ⚠️ |

> INN-10 açık: 4 nokta bir "clearance" değildir. Gerçek bir programda zarf
> boyunca ızgara + rüzgâr/ağırlık/CG dağılımıyla Monte Carlo gerekir.

---

## 3. Dinamik model (MDL) — *kriterler post-hoc*

| ID | Gereksinim | Kriter | Ölçülen (EDMD-fizik+poly2) | Durum |
|---|---|---|---|---|
| MDL-01 | Veri kalıcı uyarım (persistent excitation) koşulunu sağlayacak | cond([X\|U]) < 1000 | 24.5 | ✅ |
| MDL-02 | 1-adım (0.1 s) tahmin, persistence tabanını yenecek | beceri > %40 | %52.3 | ✅ |
| MDL-03 | 20-adım (2 s) tahmin, persistence tabanını yenecek | beceri > %40 | %51.8 | ✅ |
| MDL-04 | A matrisi birim çember dışında özdeğer içermeyecek | ρ(A) ≤ 1 | 1.000018 (20 adımda ×1.0004) | ⚠️ |
| MDL-05 | Kaldırma fonksiyonu durum-içeren olacak (Ψ(x)[:n] = x) | zorunlu | çalışma anında denetleniyor | ✅ |
| MDL-06 | Model **offline** fit edilecek, RL döngüsünde güncellenmeyecek | zorunlu | ✅ | ✅ |
| MDL-07 | Model, RL eğitimi sonrası on-policy veride yeniden doğrulanacak | — | yapılmadı | ⬜ |

> **Açıklanabilirlik notu (MDL-08, sertifikasyon):** Deep-Koopman daha doğrudur
> (20 adım: 0.117 vs 0.155) ama encoder denetlenemez. EDMD'nin her gözlenebilirinin
> fiziksel karşılığı vardır (`cos φ`, `V sin γ`, `q̄·α`). Güvenlik filtresinde
> **denetlenebilirlik doğruluktan önceliklidir**; varsayılan model EDMD'dir.

---

## 4. Güvenlik filtresi (SAF)

| ID | Gereksinim | Kriter | Ölçülen | Durum |
|---|---|---|---|---|
| SAF-01 | Filtre, zarf içindeyken komuta müdahale etmeyecek | müdahale = 0 | nominal durumda 0/2000 | ✅ |
| SAF-02 | Filtre gerçek zamanlı çalışacak | < 10 ms | 0.24 ms | ✅ |
| SAF-03 | Çözücü hata oranı | < %1 | %0.13 (233/180.000) | ✅ |
| SAF-04 | β ihlali içeren bölüm oranı | < %2 | **%0** (0/150) | ✅ |
| SAF-05 | n (g yükü) ihlali içeren bölüm oranı | < %20 | **%16** (24/150) — kalkansız %13 (20/150), **fark yok** | ⚠️ |
| SAF-06 | α ihlali içeren bölüm oranı | %0 | **%0** (0/150) | ✅ |
| SAF-07 | Enerji/Mach tabanı ihlali içeren bölüm oranı | < %5 | %0.7 (1/150) — kalkansızla **aynı** | ⬜ |
| SAF-08 | Bariyer limitleri sonlandırma limitlerinin **içinde** olacak | zorunlu | ✅ | ✅ |
| SAF-09 | Filtre eğitim döngüsünde bulunacak (sonradan takılmayacak) | zorunlu | ✅ | ✅ |
| SAF-10 | Filtrenin kapsamı **açıkça sınırlanacak** | zorunlu | aşağıda | ✅ |

> **SAF-05 GERİ ALINDI.** Önceki satır "%8 vs %33, GA'lar örtüşmüyor, ✅"
> diyordu. O ölçüm **ayrı ayrı eğitilmiş** iki politikayı (`guidance_shield`
> vs `guidance_noshield`) karşılaştırıyordu — yani kalkanın etkisiyle politika
> farkını birbirine karıştırıyordu. Seçilen model üzerinde **aynı politika**
> kalkanlı/kalkansız koşturulduğunda `nz_min` üzerinde **ölçülebilir etki
> yok** (24/150 vs 20/150). "Kalkan g ihlallerini azaltıyor" iddiası bu
> ölçümle desteklenmiyor ve geri çekilmiştir.

#### SAF-10 — Filtrenin kapsamı ve SINIRI

`scripts/violation_depth.py` · seçilen model · 150 bölüm · adım-içi 60 Hz

| | r3 (seçilen) | taban |
|---|---|---|
| ihlalli bölüm | 24/150 | 23/150 |
| ihlalli adım | 106 (%0.039) | 47 (%0.017) |
| **ihlal derinliği medyan** | −3.152 g | −3.130 g |
| medyan süre | **1 adım (0.1 s)** | 1 adım (0.1 s) |
| en uzun süre | 1.1 s | 0.4 s |
| %90 derinlik | −3.430 g | −3.553 g |
| **en kötü geçici** | **−4.581 g** | −3.837 g |
| −3.5 g'yi aşan adım | 8 | 6 |

**Tipik ihlal zararsızdır:** bariyeri 0.15 g aşan, 0.1 saniye süren bir
sıçrama — üstelik bariyer sonlandırma sınırının 0.5 g içinde. Oturmuş,
süregelen bir zarf ihlali yok.

**Ama kuyruk zararsız değil ve saklanmamalıdır:** en kötü geçici −4.581 g,
F-16'nın yapısal negatif g sınırının belirgin ötesinde. Tabanda da mevcut
(−3.837 g), yani ödül değişikliğinin *yarattığı* bir tehlike sınıfı değil —
sıklığını artırdı (106 vs 47 adım), sınıfını değil.

**Mekanizma:** iç döngünün komut sınırı −2.0 g iken gerçekleşen −4.58 g.
Aradaki farkı komut üretmiyor; **rüzgâr darbesi ve dinamik aşım** üretiyor.
CBF kalkanı 10 Hz'de bir **komut yöneticisidir**; 60 Hz'de gerçekleşen
dinamik ve atmosferik geçici aşımları yapısı gereği engelleyemez. Bu, ayrık
zamanlı CBF'in bilinen sınırıdır.

> **SAF-10 — savunulabilir iddia budur:**
> CBF kalkanı, *komut seviyesinde* zarf ihlali üreten girdileri filtreler.
> 60 Hz'de gerçekleşen dinamik ve atmosferik geçici aşımları **engellemez**.
> "Kalkan zarfı garanti eder" **denemez**.

**Elenen çözümler** (analiz edildi, uygulanmadı): bariyeri −3'ten −2.7'ye
çekmek; kalkanı sert moda almak. İkisi de komut seviyesinde çalışır, sorun
komut seviyesinde değil — medyanı iyileştirir, kuyruğu kapatmaz.

#### Stres testi — komutan gelmeden ÖNCE karar (2026-09-03)

`scripts/stress_commander.py` · betikli 2 Hz komutan · 80 bölüm/seviye

Gerekçe: iç döngüye dokunmak guidance'ı, guidance'ı değiştirmek (sözleşme
bozulursa) komutanı yeniden eğitmeyi gerektirir. Komutanı yeniden eğitmek
guidance'tan kat kat pahalı. O yüzden komutanın **komut dağılımı**, komutan
eğitilmeden taklit edildi.

| seviye | komut/bölüm | ihlalli bölüm | nz_min oranı | en kötü |
|---|---|---|---|---|
| nominal | 10.3 | 6/80 | 0.000 [0.000, 0.000] | −3.296 g |
| agresif | 18.3 | 22/80 | 0.001 [0.000, 0.002] | −3.867 g |
| aşırı | 31.4 | 46/80 | 0.002 [0.001, 0.003] | −4.194 g |
| *hedef yakalamalı ortam* | — | 24/150 | *0.042 [0.023, 0.062]* | *−4.581 g* |

**Karar: eşik (0.084) hiçbir seviyede aşılmadı.** İç döngü değişikliği
BVR'dan önce gerekli değil.

##### KARAR GEREKÇESİ — sade anlatım

**Neden endişelendik?** İki ölçüm vardı: (a) `r3`, tabana göre zarf
ihlallerinde 4 kat kötüydü (0.057 vs 0.014); (b) en kötü geçici −4.581 g
ölçülmüştü — hem sonlandırma sınırının (−3.5) hem uçağın yapısal negatif g
sınırının ötesinde. Komutan çok daha sert komut vereceği için "acaba iç
döngüye bir fren koyup sistemi baştan mı eğitsek?" diye soruldu.

**Ne yaptık?** Komutanı eğitmeden, komut dağılımını **taklit ettik**.
Betikli bir komutan 2 Hz'de peş peşe sert komutlar verdi — üç agresiflik
seviyesinde, 80'er bölüm.

**Sonuç.** En vahşi seviyede bile ihlal oranı **0.002**; dur eşiği
**0.084** idi. Yani **40 kat marj** var.

> **Dikkat, "hiç aşmadı" DEĞİL.** İhlaller oldu: aşırı seviyede 80 bölümün
> 46'sında en az bir ihlal, en kötüsü −4.194 g. Doğru ifade şu: **ihlaller
> nadir ve çok kısa** (medyan 0.1 saniye), oran eşiğin çok altında.

**Karar: iç döngüye dokunmuyoruz, ajanları baştan eğitmeye gerek yok.**
Ucuz müdahaleler (bariyeri −2.7'ye çekmek, sert mod) zaten analizle
elenmişti — ikisi de komut seviyesinde çalışır, sorun komut seviyesinde
değil. Kalanlar (iç döngüde g sınırlama, 60 Hz filtre) dondurulmuş katman
açmayı gerektirir ve ölçüm bunu haklı çıkarmıyor.

**Kararın sınırı.** Betikli komutan, öğrenilmiş bir komutanın **yaklaşık**
taklididir; öğrenilmiş bir komutan rastgele betiklerin bulamayacağı komut
dizileri keşfedebilir. Karar "sistem savaşa tam hazır" değil, **"şimdi
müdahale etmek için gerekçe yok"**tur. Metrik izlenmeye devam eder.

> **DİKKAT — bu bölümde bir açıklama YANLIŞ ÇIKTI ve düzeltildi.**
> İlk yazımda "ihlaller varış öncesi hassasiyet düzeltmesinden geliyor"
> denmişti. `scripts/violation_where.py` ile ölçüldü ve **çürütüldü**:
> ihlallerin yalnızca %2'si yakalama yarıçapının iki katından yakın;
> ihlallerin medyan menzili 6.51 nmi, tüm adımların medyanı 6.04 nmi —
> neredeyse aynı. Varış anında yığılma **yoktur**.

##### GERÇEK MEKANİZMA — ölçüldü (`scripts/violation_where.py`, 150 bölüm)

| | ihlal anında | tüm adımlar | oran |
|---|---|---|---|
| yatış açısı (medyan) | **55.2°** | 33.2° | — |
| uçuş yolu açısı (medyan) | **−6.3°** | −0.1° | — |
| irtifa hatası (medyan) | **−3789 ft** (hedefin üstünde) | +78 ft | — |
| yatış > 45° | %57.5 | %39.0 | 1.5× |
| **alçalma (γ < −5°)** | **%59.4** | %13.9 | **4.3×** |
| **ikisi birden** | **%35.8** | %10.1 | **3.5×** |

**İhlaller yatık alçalmada oluşuyor.** Baskın etken alçalmanın kendisi
(4.3×); yatış onu büyütüyor. Mekanizma iç döngü formülünde açık:

```
n = (V·γ̇/g + cos γ) / cos φ
```

`1/cos φ` çarpanı 55° yatışta komutu **1.74 kat** büyütür. Alçalma komutu
zaten negatif tarafa gidiyorsa, yatıklık negatif g'yi derinleştirir.

##### İÇ DÖNGÜ SORUMLU DEĞİL — ölçüldü (`scripts/test_inner_loop.py`)

İhlallerin "yatık alçalmada" oluştuğu belirlendikten sonra iç döngünün kabul
testlerine iki grup eklendi. **İlk 16 test kanat düzdü** (dönüş testinde bank
vardı ama γ=0), yani en çok ihlal üreten çalışma noktası hiç sınanmamıştı —
gerçek bir doğrulama boşluğu.

| grup | koşul | en kötü nz | sonuç |
|---|---|---|---|
| 5 · yatık alçalma | φ=55°, γ=−8°, 6 uçuş şartı | **−2.81 g** | 6/6 ✅ |
| 6 · ani ters dönüş | φ=70°, γ +10°→−20° basamak | **−2.70 g** | 6/6 ✅ |

Şartlar ortamın alt köşesini de kapsar (10 kft / M0.60). **Toplam 28/28.**

> **Sonuç: temiz komutlarla sürüldüğünde iç döngü bariyeri hiç aşmıyor.**
> 70° yatışta anlık 30°'lik γ tersine dönüşü bile −2.70 g'de kalıyor.
> Oysa ortamda **sakin havada** −3.762 g ölçülmüştü.
>
> Demek ki derin negatif g, iç döngünün basamak yanıtından değil,
> **ajanın sürekli değişen komut akışından** doğuyor: dış döngü 10 Hz'de
> komut yeniliyor, uçak hiç oturmuş bir duruma gelmiyor, ardışık komutlar
> birikiyor. Tek basamaklı hiçbir test bunu üretmiyor.

**Bunun müdahale seçeneklerine etkisi:**

| seçenek | önceki değerlendirme | GÜNCEL |
|---|---|---|
| A · `n` döngüsü PI/ileri-besleme ayarı | umut verici | **zayıf** — döngü 28/28 geçiyor, ayar bozuk değil |
| B · `n_cmd_min`'i yatışa göre kıs | yardımcı | **hâlâ geçerli** — komut akışı ne olursa olsun pay bırakır |
| C · γ komutuna eğim sınırı | makul | **riskli** — taramada slew sınırını sıkmak (`s3_slew`) en kötü koşuydu |
| D · Koopman sözlüğüne `sec φ` | ilginç | **en umut verici** — kalkan bağlaşımı görürse komut akışını kaynağında düzeltir |

##### AÇIK KALAN SORU — dürüst kayıt

Stres testinin neden 20 kat düşük çıktığı **açıklanamadı**. İlk açıklama
(varış paniği) ölçümle çürütüldü; yerine geçecek doğrulanmış bir açıklama
yok. Uydurma bir açıklamayla doldurulmamıştır.

**Bunun pratik sonucu, referans düzeltmesini GERİ ALMAKTIR.** Referansı
0.042'den 0.001'e indirme gerekçesi "BVR kullanımı stres testine benzer"
idi ve bu gerekçe çürütülen mekanizmaya dayanıyordu. Gerçek mekanizma
yatık alçalma olunca beklenti tersine döner: **BVR'da yatık alçalma
boldur** (füze kaçınma, enerji yönetimi, savunma manevraları). Yani BVR,
stres testinden daha iyi değil **daha kötü** olabilir.

**BVR faz referansı — MUHAFAZAKÂR (yüksek) uç kullanılır:**

| kurulum | oran | en kötü |
|---|---|---|
| betikli komutan, agresif | 0.001 [0.000, 0.002] | −3.867 g |
| hedef yakalamalı ortam | **0.042 [0.023, 0.062]** | **−4.581 g** |

İki kurulum arasındaki 20 katlık fark açıklanamadığı için **yüksek uç
referans alınır**: oran 0.042, derinlik −4.581 g. İzleme eşiği 0.084.
Komutanın komut dağılımı görüldükçe referans yeniden değerlendirilir.

**Doğru çözüm yeri, bu fazın DIŞINDA:** iç döngüde rüzgâr darbesine karşı g
sınırlama, ya da 60 Hz'de çalışan bir filtre. İkisi de dondurulmuş katmanları
açmayı gerektirir.

---

#### Aday model üzerinde AYNI-POLİTİKA ablasyonu (yeni ölçüm)

Yukarıdaki SAF-04/05/07 satırları **ayrı ayrı eğitilmiş** iki politikayı
(`guidance_shield` vs `guidance_noshield`) kıyaslıyordu; oradaki fark
kalkanın etkisi ile politika farkını birbirine karıştırıyor olabilir.
Aşağıdaki ölçüm **aynı politikayı** kalkanlı ve kalkansız koşturur —
kalkanın kendi katkısını izole eden temiz ablasyon budur.

`scripts/safety_eval.py --model runs/guidance_final_s1/sac_1999968_steps.zip`
· 100 bölüm · tohum bloğu 50000 · `data/models/edmd_physics.pkl`

**SEÇİLEN MODEL** (`reward_r3_both`, 150 bölüm, tohum bloğu 50000):

| bariyer | kalkanlı | kalkansız | karar |
|---|---|---|---|
| alpha | 0.000 (0/150) | 0.000 (1/150) | — |
| beta | 0.000 (0/150) | 0.003 [0, 0.009] (2/150) | yön doğru, GA'lar örtüşüyor |
| nz_max | 0.000 (0/150) | 0.000 (0/150) | — |
| nz_min | 0.042 [0.023, 0.062] (24/150) | 0.177 [0.019, 0.473] (20/150) | **fark yok** |
| stall | 0.015 (1/150) | 0.094 (1/150) | GA'lar örtüşüyor |
| **toplam** | 0.057 [0.027, 0.097] | 0.275 [0.027, 0.652] | **anlamlı değil** |

Müdahale %14.5, slack %1.3, ortalama sapma 0.036, çözücü hatası
146/270.000 = **%0.05**.
**Ödül maliyeti yok:** 2418 [2319, 2512] vs 2501 [2401, 2599] — örtüşüyor.

> **Dürüst okuma.** Seçilen model üzerinde **hiçbir bariyerde istatistiksel
> olarak anlamlı iyileşme gösterilemiyor.** İhlal *oranı* 5 kat düşük
> (0.057 vs 0.275) ama kalkansız taraftaki birkaç uzun ihlal güven aralığını
> devasa yapıyor. **İhlalli bölüm sayısı ise aynı** (24 vs 23): kalkan
> tehlikeli duruma *girmeyi* engellemiyor, girildiğinde **çıkışı kısaltıyor**.
>
> Bu, taban modelde alınan sonuçtan **daha zayıftır** — orada β ihlalleri
> 8/100 → 0/100 ile ayrışıyordu. Sebep: `r3` zaten daha iyi davranan bir
> politika, kalkanın düzeltecek daha az şeyi kalıyor.

**Önceki (taban model, 100 bölüm) ölçüm, referans için:** β 8/100 → 0/100
(GA'lar örtüşmüyordu), `nz_min` 12/100 vs 12/100 (fark yok), toplam
0.014 [0.006, 0.023] vs 0.033 [0.018, 0.049] (örtüşüyor).

> **Ödül değişikliğinin ÜÇÜNCÜ bedeli (önceden ölçülmemişti).** `r3`, tabana
> göre zarf ihlallerinde daha kötü: toplam 0.057 [0.027, 0.097] vs
> 0.014 [0.006, 0.023] — aralıklar kıl payı örtüşmüyor, ~4 kat. Mekanizma
> makul: `r3` toleransı tutturmak için hedefe yaklaşırken daha sert manevra
> yapıyor. Mutlak seviye hâlâ çok düşük (adımların %0.06'sı, kaza yok, erken
> sonlanma %1) ama **yön kötü ve BVR tam bu boyutu zorlayacak**.
> Kalite/verim ödünleşmesinin yanında bu üçüncü boyut da vardır.
| SAF-10 | Zarf **dışındayken** (h<0) kurtarma davranışı tanımlı olacak | — | tanımsız | ⬜ |

> SAF-10 açık: h < 0 iken saf projeksiyon anlamsız komut üretebilir.
> Çözümü yedek politikalı filtre (backup controller / terminal safe set) —
> şu an kritik yolda değil.

---

## 5. Guidance (GUI)

Guidance katmanının **dondurulabilmesi** için "Kabul" sütunundaki eşiklerin
tamamı sağlanmalıdır. "Hedef" sütunu arzu edilen seviyedir, zorunlu değildir.

Ölçüm: `scripts/mission_eval.py -n 200 --seed0 50000` (bootstrap %95 GA ile)

> **Örneklem 40 → 200'e çıkarıldı. Sebep ölçüldü, tercih değil.**
> Aynı üç model, üç farklı 60-bölümlük blokta değerlendirildi:
>
> | model | blok 10000 | blok 20000 | blok 50000 (n=200) |
> |---|---|---|---|
> | s0 @ 2M | 0.541 | 0.664 | **0.587** [0.54, 0.64] |
> | s1 @ 2M | 0.571 | 0.695 | **0.650** [0.60, 0.70] |
> | s2 @ 2M | 0.507 | 0.605 | **0.592** [0.54, 0.64] |
>
> Bloklar arası fark ~0.10 — yani *karşılaştırdığımız etkilerle aynı
> mertebede*. 60 bölüm, bölüm zorluğunu ortalamaya yetmiyor. Blok **içi**
> karşılaştırmalar geçerli kalır (aynı bölümler), ama **mutlak** kabul
> kararı tek blokta verilemez. Bu, "bölüm istatistiksel birimdir" dersinin
> bir üst seviyedeki tekrarıdır: birim doğru olsa da **sayısı** yetersizse
> sonuç yine kırılgandır.

Aday model: **`runs/guidance_final_s1/sac_1999968_steps.zip`** (2M adım, tohum 1).
Parantez içindeki değerler diğer iki tohumun aralığıdır.

| ID | Gereksinim | **Kabul** | Hedef | Ölçülen (n=200, 3 tohum) | Durum |
|---|---|---|---|---|---|
| GUI-01 | Bacak yakalama oranı (zamanı olan bacaklar) | %100 | %100 | **%100** (1238/1238) | ✅ |
| GUI-02 | Seyrüsefer verimi (ideal süre / gerçek süre) | ≥ 0.85 | ≥ 0.90 | **0.864** [0.850, 0.878] (0.852–0.864) | ✅ |
| GUI-03 | Varışta irtifa toleransı (±500 ft) | ≥ %85 | ≥ %92 | %82.1 [0.78, 0.86] (0.718–0.821) | ❌ |
| GUI-04 | Varışta Mach toleransı (±0.05) | ≥ %80 | ≥ %90 | %77.2 [0.73, 0.81] (0.756–0.795) | ❌ |
| GUI-05 | Varışta **ikisi birden** | ≥ %70 | ≥ %85 | %65.0 [0.60, 0.70] (0.587–0.650) | ❌ |
| GUI-06 | Erken sonlanma oranı | < %3 | < %1 | **%1.0** (2/200) (%0.5–%1.5) | ✅ |
| GUI-07 | Komut düzgünlüğü: **\|Δa\| RMS** | < 0.20 | < 0.15 | **0.152** (w_ar=0.5) | ✅ |

> **GUI-06 önceki ⚠️ işareti küçük örneklem gürültüsüymüş.** n=40'ta
> "%5 (2/40)" ölçülmüştü; n=200'de %1.0 (2/200). İki bölümlük fark,
> 40 bölümde eşiğin iki katına sıçramaya yetiyor. Aynı ders: örneklem.

> **GUI-07 metriği veri görüldükten SONRA değiştirildi — gerekçe kayıtlı.**
> Önceki tanım "yön değiştirme oranı < %35" idi ve test edilen **hiçbir**
> `w_action_rate` değeri geçemedi (%64 / %56 / %50 / %36). Sebep eşiğin
> katılığı değil, **metriğin geçersizliği**: yön değiştirme oranı
> **ölçek-bağımsızdır** — komut ±0.001 salınsa da %100 çıkar, ±0.5 salınsa
> da. Fiziksel olarak anlamlı olan değişimin **büyüklüğüdür**.
> Orijinal titreme problemi rms 0.30 ve adımların %16'sında \|Δa\|>0.5 idi;
> seçilen konfigürasyon rms **0.152** veriyor (yarısı) ve Tacview'de titreme
> görsel olarak da kayboldu. Yön değiştirme oranı bilgi amaçlı tutulur.
| GUI-08 | Komut değişim hızı sınırı | ≤ 0.25/adım | — | yapısal garanti | ✅ |
| GUI-09 | Gerçek ölçekte eğitim | ≥ 8M adım, ≥ 3 tohum | — | **8M × 3 tohum tamamlandı** | ✅ |

> **GUI-09 sağlandı ama sonucu OLUMSUZ: uzun eğitim performansı DÜŞÜRDÜ.**
> Aynı blokta (10000), aynı konfigürasyonla:
>
> | adım | s0 | s1 | s2 | ortalama |
> |---|---|---|---|---|
> | 2M | 0.541 | 0.571 | 0.507 | **0.540** |
> | 3M | 0.560 | 0.479 | 0.239 | 0.426 |
> | 8M | 0.245 | 0.457 | 0.246 | 0.316 |
>
> 2M hem en iyi hem tohumlar arası en tutarlı; sonrasında hem düşüyor hem
> savruluyor. Sebep ölçüldü → aşağıdaki "Ödül–kriter uyumsuzluğu".

### Ödül aralığı ve tavan (`scripts/reward_audit.py`)

Ödül fonksiyonu bizim tasarımımız olduğu için **teorik aralık ağırlıklardan
hesaplanır**; ama *ulaşılabilir* tavan hesapla çıkmaz, ölçülmesi gerekir —
çünkü terimler birbiriyle yarışır (menzili maksimum hızla kapatırken irtifa
hatasını da maksimum hızla kapatamazsın).

| | değer | açıklama |
|---|---|---|
| Adım ödülü aralığı | **[−2.23, +2.80]** | ağırlıklardan hesaplandı |
| Olay bazlı | hedef +4…+10, çarpma −10 | |
| Kaba üst sınır | 5040 | **ulaşılamaz** (terimler yarışır) |
| **Ulaşılabilir tavan** | **≈ 3260** | hedefe doğrudan uçan + toleransta olan uçak |
| Ölçülen (2M koşu) | **2479** | tavanın **%76**'sı |

Ödülün kaynak dağılımı — navigasyon terimi neredeyse doyurulmuş (max 1800'ün
%82'si), kalan boşluk hassasiyet terimlerinde:

| terim | bölüm başı | pozitifin %'si |
|---|---|---|
| ilerleme (navigasyon) | 1471 | 57.4 |
| mach_hassasiyet | 426 | 16.6 |
| irtifa_hassasiyet | 420 | 16.4 |
| irtifa_ilerleme | 183 | 7.1 |
| mach_ilerleme | 41 | 1.6 |
| hedef bonusu | 21 | 0.8 |
| komut cezası | −91 | — |
| çarpma | **0** | — |

| ID | Gereksinim | Kabul | Ölçülen |
|---|---|---|---|
| GUI-10 | Ödül / ulaşılabilir tavan | ≥ %85 | %76 ⚠️ |

> GUI-03…07, 09, 10 açık: bunlar **3. adımın** (gerçek ölçekte eğitim) hedefi.
> Yukarıdaki ölçümler 2M adımlık **tek bir tarama koşusuna** aittir.

---


### Ödül–kriter uyumsuzluğu (GUI-03/04/05 başarısızlığının kök nedeni)

`scripts/reward_audit.py` ile bölüm getirisinin fiili dağılımı (20 bölüm):

| terim | bölüm başı | pozitif içinde pay |
|---|---|---|
| ilerleme | 1456.8 | %58.8 |
| irtifa hassasiyet | 410.9 | %16.6 |
| mach hassasiyet | 398.0 | %16.1 |
| irtifa ilerleme | 161.2 | %6.5 |
| mach ilerleme | 35.5 | %1.4 |
| **hedef bonusu** | **16.8** | **%0.7** |
| komut cezası | −112.2 | — |
| **TOPLAM** | **2374.1** | |

Hedef bonusu `r_waypoint × (0.4 + 0.4·irtifa_ok + 0.2·mach_ok)` biçiminde.
Bölüm başına ~2.65 hedefte 16.8 puanın **~10.6'sı koşulsuzdur** (sadece
konuma varma, 0.4 çarpanı). Yani:

> **Kabul kriterine bağlı ödül = 6.2 puan = getirinin %0.26'sı.**

SAC'ın kritiği, yoğun şekillendirme terimlerinin varyansı içinde %0.26'lık
bir sinyali çözemez. Kabul kriteri **fiilen kısıtsızdır**; eğitim uzadıkça
politika, aynı toplam ödülü koruyarak hassasiyeti ilerlemeye takas eder.
Bu, `ep_rew_mean`'in 1.5M adımda doyup kalitenin sürüklenmesini birebir
açıklar. `ent_coef` 0.045'te sabit kalıyor — bu bir keşif çökmesi değil.

**İkinci uyumsuzluk (ölçülüp DARALTILDI):** ödülün %32.7'si hassasiyet
terimlerinde ve Gauss çekirdekleri toleransın iki katı geniş (`alt_prec_ft`
1000 vs ±500 ft; `mach_prec` 0.08 vs ±0.05).

İlk yorum "bu blok yanlış yeri ödüllendiriyor" idi; `scripts/reward_whatif.py`
ile ölçülünce bu **fazla güçlü** çıktı: mevcut çekirdeklerle bile hassasiyet
ödülünün **%89.3'ü zaten tolerans içinde** toplanıyor (r1 ile %96.2). Sorun
ödül *kütlesinin yeri* değil, hedefe yakınken **eğim**:

| hata | mevcut çekirdek (1000) | r1 çekirdeği (500) |
|---|---|---|
| 250 ft | terimin %94'ü | %78'i |
| 500 ft (tolerans sınırı) | %78'i | **%37'si** |

Tolerans sınırında durmak şu an terimin yalnızca %22'sine mal oluyor; r1'de
%63'üne. "Son 300 ft'i kapat" baskısı ~4 kat artar. Ama bu değişiklik
kaliteye bağlı ödül **payını değiştirmez** (%0.50 → %0.54, ölçüldü).

**SONUÇ — dört konfigürasyon koşuldu (2026-09-02, her biri 2M adım).**
Ölçüm: `mission_eval -n 100 --seed0 50000` + `command_hold_test` (14 durum).

| config | değişiklik | kalite | verim | tutma irtifa | tutma mach |
|---|---|---|---|---|---|
| taban | — | 0.650 [0.604, 0.695] | **0.864** ✅ | 10/14 | 10/14 |
| `r1_kernel` | çekirdek 500/0.05 | **0.510 [0.441, 0.578]** ❌ | 0.854 ✅ | 9/14 | 12/14 |
| `r2_bonus` | `r_waypoint` 60 | 0.758 [0.697, 0.818] | 0.860 ✅ | 11/14 | 14/14 |
| **`r3_both`** | ikisi + `w_progress` 0.4 | **0.818 [0.755, 0.874]** ✅ | 0.832 ❌ | **14/14** | **14/14** |
| `r4_strong` | ikisi + `w_progress` 0.3 | 0.814 [0.754, 0.868] | 0.816 ❌ | 14/14 | 10/14 |

**Ana sonuç:** `r3_both` kaliteyi 0.650 → 0.818'e çıkardı ve **güven aralıkları
örtüşmüyor** (0.755 > 0.695) — istatistiksel olarak gösterilmiş bir iyileşme.
Komut tutma sözleşmesi 10/14+10/14 → **14/14+14/14** oldu; en büyük irtifa
hatası 184 ft, en büyük Mach hatası 0.019.

**Beklenmeyen sonuç — çekirdek hizalaması TEK BAŞINA ZARARLI.** `r1_kernel`
kaliteyi 0.650'den 0.510'a düşürdü (GA'lar örtüşmüyor). Sebep: çekirdek 500 ft
olunca 2000 ft hatada ödül `exp(−16) ≈ 0`; yani projenin başında düzeltilen
**"uzakta gradyan yok"** hatası (tuzak 11) geri geliyor. `r3`'te çalışmasının
sebebi hedef bonusunun bu boşluğu doldurmasıdır. **Etkiler toplanabilir
değildir** — bileşenler tek başına zararlı/yetersizken kombinasyon en iyisi.

**Bileşenlerin rolleri (ablasyonla ayrıştırıldı):**

| bileşen | etkisi |
|---|---|
| hedef bonusu (10→60) | kaliteyi yükseltir (+0.108), **bedeli yok** |
| ilerleme kısıntısı (1.0→0.4) | **irtifa tutmayı düzeltir** (11/14 → 14/14) |
| aşırı kısıntı (→0.3) | Mach tutmayı bozar (14/14 → 10/14) |
| çekirdek daraltma | tek başına zararlı, bonusla birlikte faydalı |

**Açık kalan tek kriter:** GUI-02 seyrüsefer verimi 0.832 (eşik 0.85).

`r5_mid` (`w_progress` 0.7) bu boşluğu kapatmak için koşuldu ve **başarısız
oldu** — üstelik interpolasyon varsayımını da çürüterek:

| config | `w_progress` | kalite | verim | tutma irtifa | tutma mach |
|---|---|---|---|---|---|
| r2 | 1.0 | 0.758 | 0.860 ✅ | 11/14 | 14/14 |
| **r5** | **0.7** | **0.545** | 0.855 ✅ | **0/14** | 14/14 |
| **r3** | **0.4** | **0.818** | 0.832 ❌ | **14/14** | **14/14** |
| r4 | 0.3 | 0.814 | 0.816 ❌ | 14/14 | 10/14 |

`r5` her koşulda **sabit +910 ft yüksek** uçuyor (+550…+1191 ft, koşul-içi
σ 0–10) ve kalitesi tabanın bile altında. Verim eşiği geçmesine rağmen iki
bağımsız metrik birden olumsuz, dolayısıyla tohum şanssızlığıyla açıklanamaz.

> **Ders:** `w_progress`–verim ilişkisinin doğrusal olduğu varsayımı YANLIŞTI.
> 0.7, iki uç arasında bir ara sonuç vermedi; nitel olarak farklı bir davranış
> (sabit irtifa ofseti) üretti. Üç noktadan interpolasyon yapmak, ödül
> ağırlıklarının politika davranışına eşlenmesinde geçerli değil.

### Tohum doğrulaması (n=200, 3 bağımsız koşu)

Yukarıdaki karşılaştırmaların hepsi tek tohuma dayanıyordu. 8M deneyinde aynı
konfigürasyon tohumdan tohuma 0.245–0.457 arasında değişmişti, yani tohum
etkisi ölçtüğümüz farklarla aynı mertebede olabilirdi. `r3_both` ayarları iki
ek tohumda tekrar eğitildi:

| tohum | kalite | irtifa | mach | verim | erken son | komut tutma |
|---|---|---|---|---|---|---|
| 0 | **0.795** [0.751, 0.836] | 0.927 | 0.842 | 0.833 | %1 | **14/14 + 14/14** |
| 1 | 0.759 [0.712, 0.806] | 0.909 | 0.815 | 0.813 | %0 | **14/14 + 14/14** |
| 2 | 0.741 [0.693, 0.786] | 0.863 | 0.845 | 0.825 | %1 | **14/14 + 14/14** |
| **aralık** | **0.741–0.795** | 0.863–0.927 | 0.815–0.845 | 0.813–0.833 | %0–1 | tümü 14/14 |

**Üç sonuç:**

1. **Kalite üç tohumda da eşiği geçiyor** (≥0.70). Yayılım 0.054 — 8M
   deneyindeki 0.212'nin dörtte biri. Konfigürasyon yalnızca daha iyi değil,
   **daha kararlı**.
2. **Komut tutma üç tohumda da 14/14 + 14/14.** Bu tohum şansı değil,
   ayarın **yapısal** sonucudur — dondurma kararının dayandığı sözleşme budur.
3. **Verim üç tohumda da başarısız** (0.813–0.833 < 0.85). Bu da gürültü değil;
   konfigürasyonun gerçek bedeli.

**KARAR: `r3_both` @2M, tohum 0 seçildi.** GUI-02 **"sağlanmadı"** olarak
raporlanır (0.833 vs 0.85, üç tohumda da); eşik gevşetilmemiştir. Diğer altı
kriter üç tohumda da sağlanmıştır.

Seçilen model: `runs/reward_r3_both/sac_1999968_steps.zip`

> Nihai rakam **0.795** (n=200). Tek tohumlu tarama sırasında n=100 ile 0.818
> ölçülmüştü; ikisi güven aralığı içinde uyumlu, raporlanan değer daha büyük
> örneklemli olandır.

**Yapısal düzeltme (uygulandı):** `BestByCaptureQuality` callback'i
250k adımda bir kabul kriterini ölçüp `sac_best.zip` saklar (değerlendirme
tohumları 30000 bloğunda; eğitim 100000+, rapor 10000/20000/50000 ile
çakışmaz). Ödül düzeltilse bile **son modeli almak yanlıştır** — bu koşuda
son model, 2M'deki modelin yarısı kadar iyiydi.

### GUI-11 — Komut tutma (üst katmana verilen ASIL sözleşme)

`scripts/command_hold_test.py` · 7 koşul · komut sabit tutulur, son 30 s ölçülür

Taktik komutan, *yakalama anındaki* hassasiyeti hiç kullanmaz — 2 Hz'de
komut yeniler. Onun bağlı olduğu sözleşme **"komutu sabit tutarsam kalıcı
hata ne?"**dir. Bu, iç döngüdeki basamak yanıtı testinin guidance
seviyesindeki karşılığıdır ve dondurma kararının asıl dayanağı olmalıdır.

Aday model `runs/guidance_final_s1/sac_1999968_steps.zip` (2M, tohum 1):

| ID | Gereksinim | Kabul | Ölçülen (aday) | önceki (sweep_s8, 2M) |
|---|---|---|---|---|
| GUI-11a | Kalıcı irtifa hatası ≤ ±500 ft | ≥ 6/7 koşul | **6/7** ✅ | 6/7 |
| GUI-11b | Kalıcı Mach hatası ≤ ±0.05 | ≥ 6/7 koşul | 4/7 ⚠️ | 3/7 |
| GUI-11c | Kalıcı rejimde **salınım** (std) | irtifa <100 ft, Mach <0.01 | 6/7 koşulda ✅ | ✅ |

Aday modelin sapmaları (son 30 s ortalaması):

| başlangıç → komut | irtifa | Mach |
|---|---|---|
| 20000/0.80 → 20000/0.80 | −392 ft (σ 408) | +0.024 |
| 20000/0.80 → 25000/0.80 | −93 (σ 3) | +0.038 |
| 30000/0.90 → 25000/0.90 | −193 (σ 0) | +0.056 |
| 25000/0.75 → 25000/1.00 | −79 (σ 38) | +0.060 |
| 25000/1.10 → 25000/0.85 | −174 (σ 17) | +0.049 |
| 15000/0.70 → 22000/0.95 | −531 (σ 29) | +0.055 |
| 35000/1.00 → 30000/0.80 | +346 (σ 3) | +0.019 |

**Bulgu:** hatalar gürültü değil **sistematik sapma** (bir koşul hariç σ ≤ 38).
Sistematik sapmayı üst katmanın geri besleme döngüsü düzeltebilir; gürültü
düzeltilemezdi. Mach sapması aday modelde **tek yönlü pozitif** (+0.02…+0.06),
yani ajan komut edilenden tutarlı biçimde biraz hızlı uçuyor — bu, sabit bir
ileri-besleme düzeltmesiyle kapatılabilecek en elverişli hata biçimidir.

**Bir koşulda salınım var:** saf tutma (20000/0.80 → aynı) σ 408 ft. Diğer
altı koşulda σ ≤ 38 ft. Yani sapma değil, o çalışma noktasında bir limit
çevrimi. İzlenmeli.

**Kök neden — GÜNCELLENDİ.** Önceki not "hassasiyet çekirdekleri 2 kat geniş,
180 ft'te ajan ödülün %97'sini alıyor" diyordu. Bu doğru ama **eksikti**:
`reward_whatif.py` ile ölçüldüğünde asıl sorunun sinyal *genişliği* değil
sinyal *gücü* olduğu görüldü — kabul kriterine bağlı ödül getirinin
%0.50'si. Çekirdek daraltma bu payı yalnızca %0.54'e taşıyor. Tam analiz:
yukarıdaki "Ödül–kriter uyumsuzluğu" bölümü.

## 6. Taktik komutan (TAC) — 📋 gelecek faz

| ID | Gereksinim |
|---|---|
| TAC-01 | Gözlem/aksiyon uzayı **çok uçaklı son durum** için tasarlanacak; 1v1'de maskeli |
| TAC-02 | Komutan 2 Hz'de karar verecek |
| TAC-03 | Guidance ve filtre katmanları komutan eğitimi boyunca **dondurulmuş** olacak |
| TAC-04 | Karma aksiyon uzayı (sürekli yön/irtifa/hız + kesikli ateş/hedef/mod) → PPO |
| TAC-05 | Düşman modeli tak-çıkar olacak (3-DOF eğitim / JSBSim demo) |
| TAC-06 | Rakip havuzu: scripted taktikler + dondurulmuş eski ajan sürümleri |
| TAC-07 | Kanat uçağı önce scripted, sonra MARL (paylaşılan politika, sıcak başlangıç) |
| **TAC-08** | **Komutanın yön komutu, sanal hedef olarak 5–25 nmi arasına konacak** |

### BVR fazı — KİLİTLİ KARARLAR (2026-09-04, kullanıcı onayladı)

| # | karar | gerekçe |
|---|---|---|
| 1 | **Füze: 3-DOF nokta kütle + oransal seyrüsefer (PN)** | BVRGym/LAG de aynısını kullanıyor; yeterince gerçekçi, eğitim için hızlı |
| 2 | **Radar: RCS + Doppler/notching dahil** | notching BVR'ın temel taktiği; basit koni+menzil modelde ajan gerçek taktik öğrenemez |
| 3 | **Altyapı 2v2'ye hazır kurulacak, eğitim 1v1'den başlayacak** | TAC-01 ile tutarlı; sonradan yeniden yazmamak için |
| 4 | **Füze uyarısı MAW değil RWR** | ↓ aşağıya bak |
| 5 | **IRST faz 2'ye ertelendi** | ↓ aşağıya bak |
| 6 | **4 AMRAAM** | 2 taktik derinlik vermiyor, 6 mühimmat yönetimini önemsizleştiriyor |
| 7 | **Füze kütlesi modellenecek** | ölçüldü, sözleşme korunuyor (aşağıdaki tablo) |

**4 — neden MAW değil RWR.** MAW füzenin egzoz alevini görür; AMRAAM roketi
~8–10 s yanar biter ve kalan 50+ km'yi süzülerek gelir, yani görünecek alev
yoktur. BVR'da uyarı zinciri şudur:

| aşama | RWR ne görür |
|---|---|
| düşman kilitler | **spike** — kilitlendiğini bilirsin |
| füze atılır | **hiçbir şey** — ataletsel gidiyor |
| füze son safhada aktif olur | **yeni tehdit** — füzenin kendi radarı |

Bu belirsizlik penceresi BVR'ı ilginç yapan şeydir. MAW koymak onu yok eder
ve ajan füzeyi anında görüp kaçar.

**5 — neden IRST ertelendi.** IRST pasiftir ve **notching'i yenmez** — yani
en temel BVR taktiğini işlevsiz kılar. Ayrıca F-16'da standart değildir
(Blok 70 / pod hariç). Önce radar+RWR ile çalışan bir sistem kurulacak;
IRST eklenirse "bazı senaryolarda var" biçiminde olacak ki ajan iki duruma
da hazırlansın.

### Muhimmat kütlesi — dondurulmuş guidance hâlâ sözleşmesini tutuyor mu?

`scripts/payload_check.py` · AMRAAM 335 lb/adet · 14 manevra × 90 s

JSBSim'den ölçülen gerçek ağırlıklar: boş+pilot 17.630 lb, yakıt %30 →
19.722 lb, yakıt %100 → 24.602 lb. 4 AMRAAM = +1.340 lb, yani tam yakıt +
tam mühimmat **25.942 lb** — eğitim üst sınırının **%5.5 üstünde**.

| konfigürasyon | ağırlık | irtifa | mach | en kötü irtifa |
|---|---|---|---|---|
| referans: 0 füze, yakıt %60 | 21.813 lb | 14/14 | 14/14 | 161 ft |
| 0 füze, yakıt %100 | 24.602 lb | 14/14 | 14/14 | 146 ft |
| 4 füze, yakıt %30 | 21.062 lb | 14/14 | 14/14 | 181 ft |
| 4 füze, yakıt %60 | 23.153 lb | 14/14 | 14/14 | 161 ft |
| **4 füze, yakıt %100 (en ağır)** | **25.942 lb** | **14/14** | **14/14** | **109 ft** |

**Beşinde de 14/14 + 14/14.** Ağırlık ile bozulma arasında eğilim **yok**;
en ağır durumda irtifa hatası referanstan bile küçük. Sebep: guidance zaten
yakıt %30–100 aralığında, yani **4.880 lb'lik bir ağırlık bandında**
eğitildi (domain randomization). 1.340 lb ek yük o bandın %27'si kadar bir
genişleme — görülmemiş bir rejim değil. Ayrıca ağırlık uçağın yunuslama
tepkisini **yavaşlatır**, bu da tutma açısından zararsızdır.

> **KARAR: füze kütlesi modellenir, guidance yeniden EĞİTİLMEZ.** Seçenek B
> (önce ölç) uygulandı, C (yeniden eğit) gerekmedi.

#### ⚠️ YAN BULGU: mühimmat, Mach tabanı bariyerinin varsayımını ihlal ediyor

`aircraft.py` içinde `COMBAT_WEIGHT_LB = 25000` **bilerek "en ağır durum"**
seçilmişti ve `MACH_FLOOR_A/B` doğrusal fiti buna göre üretildi. 4 AMRAAM +
tam yakıt = **25.942 lb**, yani varsayılandan **942 lb ağır**. Bariyer o
köşede muhafazakâr olmaktan çıkıp iyimser olur.

| irtifa | bariyer tabanı | 1.25×stall @25000 | 1.25×stall @yüklü | pay |
|---|---|---|---|---|
| **10.000** | 0.3246 | 0.3263 | 0.3324 | **−0.0078** ❌ |
| 15.000 | 0.3800 | 0.3603 | 0.3670 | +0.0130 |
| 20.000 | 0.4353 | 0.3992 | 0.4067 | +0.0286 |
| 25.000 | 0.4907 | 0.4443 | 0.4526 | +0.0381 |
| 30.000 | 0.5460 | 0.4966 | 0.5059 | +0.0401 |
| 35.000 | 0.6014 | 0.5579 | 0.5683 | +0.0330 |
| 42.000 | 0.6788 | 0.6601 | 0.6724 | +0.0065 |

**Yalnızca 10.000 ft'te bariyer yüklü uçağı kapsamıyor** (1/7 irtifa).

**İkinci bulgu:** 10 kft'te bariyer **varsayılan ağırlıkta bile** 0.0017
yetersiz. Yani bu tamamen mühimmatın sonucu değil — doğrusal fit alçak uçta
zaten kısa kalıyor, mühimmat onu −0.0078'e büyütüyor.

**Ciddiyeti:** uçak stall'a **girmiyor**. 10 kft'te yüklü gerçek stall
0.266, bariyer 0.325. Kaybedilen şey manevra payı: `STALL_MARGIN_FACTOR`
fiilen 1.25 → **1.22** oluyor (%2.4 daralma).

**KARAR: şimdilik düzeltilmiyor, belgelenip izleniyor.** Gerekçe: Mach
tabanı bariyerinin zaten **ölçülebilir etkisi gösterilemedi** (SAF-07 açık).
Etkisi olmayan bir bariyeri %2.4 sıkmak için dondurulmuş katmanı açıp tüm
doğrulamayı tekrarlamak orantısız.

> **BVR izleme listesine eklendi.** BVR'da alçak irtifa gerçekten kullanılır
> (alçalarak notch, drag). Komutan zamanının önemli kısmını **15 kft
> altında** geçirirse bu yeniden değerlendirilmeli. Düzeltme yolu:
> `COMBAT_WEIGHT_LB` → 26.000 ve `MACH_FLOOR_A/B` yeniden fit; ardından
> GUI-11 ve SAF ölçümleri tekrarlanır.

**İki uygulama ayrıntısı:**
- F-16 modelinde yalnızca `pointmass[0]` (pilot, 230 lb @ X=−336.2) kütle
  dengesine girer; `[1]` yazılabilir ama **etkisizdir**. Mühimmat kütlesi
  `[0]`'a eklenir ve konumu **birleşik momenti koruyacak** şekilde seçilir —
  aksi halde CG 8.4 inç geriye kayar ve gevşek kararlı bir uçakta ölçüm
  yanlı olur. Doğru kurulumda CG −190.94 → −190.95.
- **Nokta kütle `reset()` arasında KALICIDIR** (türbülans gibi). Referans
  koşuya geçerken açıkça sıfırlanmazsa "yüksüz" ölçüm yüklü çıkar — bu betik
  yazılırken tam olarak bu hata yapıldı ve yakalandı.

## 7. Radar (RAD) — Faz 1.2

`bvr/combat/radar.py` · APG-68 referanslı, açık kaynak tahmini değerlerle.

| ID | Gereksinim | Değer / kriter | Durum |
|---|---|---|---|
| RAD-01 | Tespit menzili RCS ile **dördüncü kök** ölçeklenir | `R = R_ref·(σ/σ_ref)^¼` | ✅ |
| RAD-02 | RCS **açıya bağlı** olacak | kuyruk 4 · beam 50 · burun 2 m² | ✅ |
| RAD-03 | Gimbal sınırı | az ±60°, el ±60° | ✅ |
| RAD-04 | Doppler notch | `\|Vc\| < 100 fps` → elenir | ✅ |
| RAD-05 | Notch **yalnızca aşağı bakışta** çalışacak | hedef yukarıdaysa yer yankısı yok | ✅ |
| RAD-06 | Temas kesilince kilit **coast** edecek | 4.0 s | ✅ |
| RAD-07 | Gimbal kaybında coast **işletilmeyecek** | mekanik körlük ≠ sinyal kaybı | ✅ |
| RAD-08 | Çok hedefli durum **hedefe özel** tutulacak | `target_id` anahtarlı | ✅ |
| RAD-09 | Kilit kurma **gecikmeli** olacak | 2.5 s | ✅ |
| RAD-10 | Gecikme sırasında temas kesilirse ilerleme **azalacak**, sıfırlanmayacak | `decay = 1.0` | ✅ |
| RAD-11 | Kilit kaybında (coast bitişi) ilerleme **tam sıfırlanacak** | ARAMA'ya dönüş | ✅ |

**Ölçülen davranış** (`bvr/combat/tests/test_radar.py`, 20/20 test):

| senaryo | sonuç |
|---|---|
| 2.0 s sürekli tespit | kilit yok, `reason="acquiring"` ✅ |
| 3.0 s sürekli tespit | kilit ✅ |
| 2.0 tespit → 1.0 kayıp → 2.0 tespit (net 3.0) | kilit ✅ azalma çalışıyor |
| 2.0 tespit → 2.5 kayıp → 0.4 tespit | kilit yok ✅ taban 0'da |
| kilit → coast bitti → hedef döndü | anında kilit yok, 2.5 s daha ✅ |
| ARAMA sırasında gimbal | ilerleme sıfırlandı ✅ |
| **kilitliyken kısa kesinti** | `coast` kullanılıyor, `progress` değil ✅ |

Son satır kritikti: iki mekanizma (ARAMA ilerlemesi ve KİLİT coast'ı)
birbirine karışmamalı. Durum makinesi `if state.tracked` ile önce ayırıyor.

### RAD-09/10 — kilit gecikmesi: neden bu değerler, ve neden bunlar SABİT DEĞİL

**Fiziksel dayanak.** Radar tarama yapar; bir noktayı tekrar ziyaret süresi
tarama desenine bağlıdır: ±60°/4 bar geniş arama ~5–6 s, ±30°/2 bar ~1.5–2 s,
±10°/1 bar < 1 s. Üstüne radar tek dönüşle kilit kurmaz — yanlış alarm elemek
için **M-of-N** mantığı vardır (ör. 3 taramada 2 tespit), yani ~2 tarama
periyodu gerekir. BVR'da hedefin kabaca yeri bilinir ve tarama daraltılır →
gerçekçi çalışma aralığı **2–4 s**. Varsayılan **2.5 s**.

**Neden sert sıfırlama değil, azalma.** İki gerekçe:
1. *Fizik:* M-of-N zaten kayan penceredir; bir taramayı kaçırmak süreci
   sıfırlamaz, geriye götürür.
2. *Bu projeye özgü:* sert sıfırlama **kırılgan bir eşik** yaratır. Tespit
   menzilinin veya notch'un sınırında titreşen bir hedef, her kaçırmada
   sıfırlandığı için asla kilitlenemez; ajan bunu keşfedip fiziksel olmayan
   bir sömürü öğrenir. Bu projede kırılgan eşiklerin sorun çıkardığı ölçüldü
   (yatış bariyeri %42 müdahale; ödül çekirdeği–tolerans uyumsuzluğu).
   Azalma modeli düzgün gradyan verir: **kısmi notch → kısmi bozulma.**

> ⚠️ **BU SAYILAR DENGE PARAMETRESİDİR, FİZİKSEL SABİT DEĞİL.**
> `lock_delay_s` ve `coast_s` birlikte notching'in gücünü belirler:
>
> | ayar | sonuç |
> |---|---|
> | uzun gecikme + kısa coast | notch çok güçlü, kaçmak kolay |
> | kısa gecikme + uzun coast | notch neredeyse işe yaramaz |
>
> 2.5 / 4.0 **makul bir başlangıç**, doğru değer değil. Ajanlar ortaya
> çıkınca ölçülüp ayarlanacak. "Bu sayı nereden geldi?" sorusunun cevabı
> budur: gerekçeli bir başlangıç tahmini, ölçülmüş bir sonuç değil.

### 📋 Ertelenen: yeniden kilitlenme gecikmesi

Gerçek radarlarda **yeniden kilitlenme**, sıfırdan aramadan hızlıdır —
antenin nereye bakacağı bilinir (hedefin tahmin edilen konumu). Şu anki
model coast bitince ilerlemeyi **tam sıfırlıyor**, yani yeniden kilit
sıfırdan aramayla aynı maliyette.

Eklenecekse: `reacquire_delay_s < lock_delay_s` (ör. 1.0 s), coast'tan
düşülen hedefler için kısa süre geçerli bir "sıcak" durum. **Şimdilik
gerekmiyor** — önce temel davranış ölçülsün. Notching'in gücü fazla
çıkarsa ilk başvurulacak ayarlardan biri budur.

### TAC-08 — KOMUTAN ARAYÜZÜ TASARIM KURALI ⚠️

**Kural: komutanın verdiği yön komutu, güdüm katmanına sanal bir hedef
olarak aktarılırken o hedef 5–25 deniz mili arasına konmalıdır. 40 nmi ve
ötesi YASAKTIR.**

**Neden — ölçüldü, tahmin değil.** Güdüm katmanı yön komutu anlamaz, *hedef
noktası* anlar. Komutanın "şu yöne dön" komutunu bir sanal hedefe çevirmek
zorundayız. "Hiç varmasın diye çok uzağa koyayım" düşüncesi doğaldır ve
**tam olarak yanlıştır**:

| sanal hedef menzili | yatış std | limit çevrimi |
|---|---|---|
| 200 nmi | 37.3° | var, periyot 12.7 s |
| 60 nmi | 37.3° | var, 12.7 s |
| 40 nmi | 30.5° | var, 12.4 s |
| **25 nmi** | **6.4°** | **yok** |
| 15 nmi | 14.4° | yok |
| *eğitim aralığı* | *3.3–14.8 nmi* | — |

**Mekanizma:** hedef yakınken uçak yön değiştirince kerteriz hızla değişir;
bu geri besleme kurs takip döngüsünü **doğal olarak sönümler**. Uzak hedefte
kerteriz uçağın yönüne neredeyse duyarsızdır, sönümleme kaybolur ve politika
**sönümsüz bir limit çevrimine** girer.

Kanıt: yatış ile kerteriz hatası arasında **2.2 s gecikmeyle r = −0.949**;
çevrim periyodu 12.7 s; yatış ±60° salınırken kerteriz hatası yalnızca ±10°.

**Bu kural nasıl bulundu:** `command_hold_test.py` hedefi 200 nmi'ye
koyuyordu ve kullanıcı Tacview'de uçağın sürekli sağa-sola yattığını fark
etti. Test aracı düzeltildi (200 → 30 nmi); GUI-11 sonucu **14/14 + 14/14
korundu** ve kalıcı rejim sapmaları 33 ft'ten 5–6 ft'e düştü — yani sözleşme
iddiası zayıflamadı, **güçlendi**.

> **Uyarı — bu, aynı kalıbın üçüncü tekrarı.** Politika, eğitim dağılımının
> dışına çıkarıldığında beklenmedik davranıyor (bkz. HANDOFF tuzak 31).
> Komutanın komut dağılımı da eğitimden farklı olacak; TAC-08 bilinen bir
> tuzağı kapatır, dağılım kayması riskini tümüyle ortadan kaldırmaz.

## 8. Füze (MSL) — Faz 1.3

`bvr/combat/missile.py` · 3-DOF nokta kütle + True PN, AMRAAM tipi açık kaynak tahmini değerlerle.

| ID | Gereksinim | Değer / kriter | Durum |
|---|---|---|---|
| MSL-01 | Güdüm: **3D True PN** | `a⃗ = N·Vc·(ω⃗ × û)` | ✅ |
| MSL-02 | İtki/sürükleme: boost→coast, `Cd(M)` transonik tepeli | boost 9 s, tepe M≈1.15 | ✅ |
| MSL-03 | Komut ivmesi **max_g'yi aşamaz** | 30 g, gerçek doğrulamalı test | ✅ |
| MSL-04 | Yerçekimi **telafili** manevra bütçesinden uygulanır | gizli bozan değil | ✅ |
| MSL-05 | Pitbull menzilinde füze **bağımsızlaşır** | 8 nmi, kendi tahmini menzile göre | ✅ |
| MSL-06 | Datalink kesintisi **hafızalı** (kademeli), anlık ölüm değil | `datalink_memory_s = 5.0` (10.0 denendi, geri alındı — bkz. MSL-09) | ✅ |
| MSL-07 | Sonlanma (isabet/ıska) **gerçek** hedef konumuna göre karar verilir | füzenin inancına göre değil | ✅ |
| MSL-08 | Segment bazlı CPA — ayrık adımlar arası "atlama" (tunneling) önlenir | sürekli enterpolasyon | ✅ |
| MSL-09 | Pitbull **otomatik bağımsızlık değildir** — seeker hedefi kendi sepetinde (FOV) ve menzilinde yakalamalı | FOV 30°, menzil 10 nmi — **bilerek atıl bırakıldı, SAF-07 kategorisi** | ⬜ |

### MSL-06 — datalink hafızası: neden anlık ölüm değil

**Fiziksel dayanak.** AMRAAM orta safhada ataletsel uçar; atan uçağın datalink
güncellemesi konum tahminini *iyileştirir*, **varlığı şart değildir**. Füze
birkaç saniye güncelleme almadan uçabilir — hata yalnızca zamanla ve hedefin
gerçek manevrasıyla büyür, anlık bir bilgi kaybı füzeyi köreltmez.

**Bu projeye özgü gerekçe — RAD-09/10 ile birebir aynı kalıp.** Radar
gimbal aşımında kilidi anında bırakır (coast yok, bilinçli bir karar —
mekanik körlük gerçekten anlık). Ama bu, crank'i bir an fazla sertleştirmenin
füzeyi **anında** öldürmesi anlamına gelmemeli — gerçekte birkaç saniyelik
pay vardır ve kilit geri kazanılabilir. Eski davranış (`datalink_ok=False` →
anında `"kor"`) tam olarak RAD-09/10'da bilerek kaçındığımız kırılgan eşik
kalıbının füze tarafındaki (daha sert) hali.

**Uygulama:** `datalink_ok=False` iken füze son bilinen hedef konumundan
**sabit hızla ekstrapole ederek** (ataletsel) uçmaya devam eder; sayaç
`datalink_memory_s` kadar geri sayar, biterse `"kor"`. Sonlanma kararı
(isabet/ıska) her zaman **gerçek** hedef konumuna göre verilir — füzenin
inandığı (ekstrapole edilmiş) konum sadece güdümü besler, fizik gerçeği
değiştirmez.

> ⚠️ **Bu da RAD-09/10 gibi bir DENGE PARAMETRESİDİR.** `datalink_memory_s`
> ile `radar.coast_s`/`gimbal_az_deg` birlikte "crank ne kadar sert
> yapılabilir" sorusunun cevabını belirler. 5.0 s gerekçeli bir başlangıç
> tahmini, ölçülmüş bir sonuç değil.

### MSL-09 — pitbull sadece bir eşik değil, bir yakalama olayıdır

**Bulunan hata.** İlk uygulamada pitbull'a girmek füzeyi otomatik olarak
"bağımsız" sayıyordu — datalink sayacı sıfırlanıyordu ama füzenin **inandığı**
hedef konumu tazelenmiyordu. Sonuç: datalink erken kesilmiş bir füze,
pitbull'a girdikten SONRA bile eski (bayat) ekstrapolasyonla uçmaya devam
ediyordu — ne gerçekten kör (`"kor"` dönmüyor, sayaç pitbull'da anlamsız
kılınıyor) ne gerçekten bağımsız (hâlâ eski veriyle güdülüyor). Ölçüldü:
datalink pitbull'dan 2 s önce kesilip hedef 7g manevra yaptığında inanç
hatası pitbull'a girerken 0 iken sonrasında **22.016 ft (3.6 nmi)**'ye kadar
büyümeye devam ediyordu.

**Düzeltme.** Pitbull'a giriş artık sadece bir menzil eşiği değil, bir
**yakalama denemesi**: aktif radar hedefi kendi burun sepetinde (±30° FOV)
VE kendi menzilinde (10 nmi) görmedikçe inanç tazelenmez, füze kör
ekstrapolasyona devam eder ve **her adım tekrar dener**. Yakaladığı an
inanç gerçeğe eşitlenir ve o andan sonra sürekli tazelenir (aktif radar
artık kesintisiz izliyor varsayımı).

**Taktik sonucu — bilinçli bir tasarım tercihi.** Bu, "füzeni pitbull'a
kadar destekle" kuralını basit bir ikili sonuçtan (ya pitbull öncesi
ölürsün ya kesin isabet) **kısmi destek → kısmi isabet olasılığı**na
çeviriyor: datalink'i erken kesersen inanç kayar, pitbull anında hedef
sepetin dışında kalabilir, füze temiz ıskalar — tıpkı radarın kilit
ilerlemesinde sert sıfırlama yerine kademeli azalmayı seçmemizle aynı
gerekçeyle (RAD-09/10).

**⬜ Ölçüldü: bu gradyan İŞLEMİYOR — SAF-07 ile aynı kategori (var,
fiziksel olarak doğru, ölçülebilir etkisi gösterilemedi).** Farklı
geometrilerde (head-on, yandan, çapraz; manevrasız ve 7g manevralı hedef)
pitbull anındaki gerçek off-boresight açısı, `datalink_memory_s=5.0` iken:

| geometri | manevrasız | 7g manevra |
|---|---|---|
| head-on | 0.0° | 11.1° |
| yandan | 17.0° | 6.8° |
| çapraz | 12.5° | 13.1° |

Hepsi 30°'lik sepetin belirgin şekilde içinde. **Sebep:**
`datalink_memory_s=5.0`, inanç hatası sepeti aşacak kadar (≳4.6 nmi, bkz.
yukarıdaki hesap) büyümeden füzeyi zaten `"kor"` yapıp öldürüyor.

**Denenen düzeltme ve neden geri alındı.** Hipotez: "hafıza süresini
uzatırsak (5.0→10.0) inanç hatası büyümeye daha çok zaman bulur, sepeti
aşar." Uygulanıp ölçüldü — **hipotez çürüdü:**

| kesinti (pitbull'dan önce) | off-boresight | sonuç |
|---|---|---|
| 4 s | 1.9° | isabet |
| 8 s | 5.5° | isabet |
| 10 s | 6.7° | isabet |
| 12 s | pitbull'a hiç varamadı | kor |

En kötü durumda bile 6.7° — 30°'lik sepetin çok altında. **Hafızayı
uzatmak açıyı büyütmüyor, sadece füzenin daha uzun süre "kör ama hayatta"
kalmasını sağlıyor** — inanç hatasının büyüme hızı, kapanma geometrisi
tarafından belirleniyor, hafıza süresi tarafından değil. Üstelik bunun
**gerçek bir bedeli** ölçüldü: `datalink_memory_s=10.0`, 25 nmi'lik bir
atışta (~29 s uçuş) füzeni desteksiz bırakabileceğin süreyi ~%34'ten
~%69'a çıkarıp "füzeni pitbull'a kadar destekle" kuralını belirgin biçimde
gevşetiyordu — kazanç sıfır, bedel gerçek. **Bu yüzden `datalink_memory_s`
5.0'a geri alındı** (`HANDOFF.md` tuzak #32 ile aynı ders: bir açıklama
çürüyünce ona dayanan karar da geri alınır).

**Kalan seçenek ve neden uygulanmıyor.** Sepeti canlandırmanın tek kalan
yolu `seeker_fov_deg`'i (30°→10-15°) veya `seeker_range_nm`'i daraltmak —
ama bu fiziksel olarak zorlama olur, gerçek AMRAAM seeker'ı geniş
sepetlidir; sırf testi geçirmek için gerçekçi olmayan bir sayı seçmek
olurdu.

**Karar: MSL-09 bilinçli olarak atıl bırakılıyor.** Kod doğru, mekanizma
fiziksel olarak savunulabilir, ama mevcut geometri/parametre rejiminde
hiçbir zaman devreye girmiyor — tıpkı SAF-07'nin enerji bariyeri gibi.
Zorla "çalıştırmaya" çalışmak (ne hafızayı büyütüp ne sepeti daraltarak)
gerçekçiliği bozmadan başarılamadı. Faz 2'de gerçek komutan/ajan
davranışları ortaya çıkınca (özellikle daha agresif crank/notch
manevraları) bu tablo değişebilir — o zaman yeniden ölçülmeli.

### 📋 Bilinen basitleştirme: `max_g` sabit

Gerçekte kullanılabilir manevra kabiliyeti dinamik basınca bağlıdır
(`q̄ = ½ρV²`) — yüksekte ve yavaşken füze yapısal `max_g`'yi çekemez, kanat
otoritesi düşer. Şu anki model bunu kaba bir eşikle (`min_speed_mach = 1.5`
altında manevra tamamen biter) temsil ediyor; M4 ile M1.5 arasında manevra
kabiliyeti **sabit** kalıyor, bu gerçekçi değil.

**Şimdilik düzeltilmiyor** — enerji hikâyesi (kriter 1-2, azami/etkili
menzil farkı) mevcut haliyle doğru çıkıyor, ek karmaşıklık şu an
gerekçesiz. **Ajanlar öğrenmeye başlayınca "azami menzilden at, yine de
sert dönerim" gibi fiziksel olmayan bir strateji keşfederlerse ilk
bakılacak yer burasıdır.**

## 9. Angajman Muhasebesi (ENG) — Faz 1.4

`bvr/combat/engagement.py` · geometri + radar + füzeyi "kim neyi ne zaman
yapabilir" kurallarıyla birbirine bağlayan muhasebe katmanı.

| ID | Gereksinim | Durum |
|---|---|---|
| ENG-01…08 | Kabul kriterleri 1-8 (kilit/menzil/mühimmat/doygunluk/kütle/datalink/isabet/bağımsızlık) | ✅ 8/8 |
| ENG-09 | Ölü hedefe ikinci kez "isabet" **yazılmaz** | ✅ |
| ENG-10 | Füze fiziği dış (10 Hz) muhasebe adımından **bağımsız**, kendi içinde alt-adımlı çalışır | `missile_substeps=5` (50 Hz) | ✅ |

### ENG-09 — çifte imha: ölü hedef füze güdemez

**Bulunan hata.** Aynı hedefe iki füze atıldığında, ilki isabet edip hedefi
düşürdükten sonra **ikincisi de "isabet" olayı üretiyordu** — ölü bir
uçağa ikinci kez vurulmuş sayılıyordu. Sebep: füze güncelleme döngüsü
`t_entry`'nin var olup olmadığına bakıyordu (`alive=False` olsa bile hâlâ
"var"), füze ölü uçağın durumuna karşı güdülmeye devam edip CPA eşiğini
geçince "isabet" yazıyordu.

**Neden önemli — sadece muhasebe değil.** Taktik komutan (Faz 2) "isabet"
başına ödül alacak. Bu haliyle ajan, zaten düşmüş bir hedefe fazladan füze
atarak ödül toplamayı öğrenebilirdi — bu projede ödül uyumsuzluğunun ne
yaptığını (`HANDOFF.md` tuzak #24) bir kez gördük; bunu şimdi kapatmak
sonradan teşhis etmekten çok ucuz.

**Fizik de bunu destekliyor:** hedef patladıysa ikinci füzenin güdeceği
bir şey kalmaz, enkazın içinden geçer.

**Düzeltme.** Füze güncelleme döngüsünün başında `t_entry.alive` kontrol
edilir; hedef zaten imha olmuşsa füze `alive=False, result="hedefsiz"`
olarak sonlandırılır, `"isabet"` yazılmaz. `"hedefsiz"` sonucu bilinçli
olarak `"iska"`dan ayrı tutuldu — sonraki analizde "boşa harcanan mühimmat"
ile "kaçırılan atış" ayrımı korunur. Regresyon: `test_9_olu_hedefe_ikinci_fuze_hedefsiz_olur`.

### ENG-10 — 10 Hz muhasebe adımı füze fiziği için yetersiz, alt-adımlandı

**Soru.** `Engagement` 10 Hz'de çalışıyor (guidance ile aynı hız). Füze
fiziğini de aynı 10 Hz ile mi güncellemeli, yoksa kendi içinde daha ince
adımlarla mı?

**Ölçüldü (`scripts/missile_dt_convergence.py`).** Manevrasız bir hedefe
karşı `dt` önemsizdi (PN neredeyse sıfır ıskaya yakınsıyor). Ama **6g
sürekli manevra yapan, marjinal bir angajmanda** sonuç `dt`'ye göre
**monoton olmayan** şekilde değişti:

| dt | Hz | sonuç | min menzil (ft) |
|---|---|---|---|
| 0.002 | 500 | isabet | 30.14 (sınırda) |
| 0.02 | 50 | isabet | 22.49 |
| **0.05** | **20** | **ISKA** | **52.09** |
| 0.1 | 10 | isabet | 4.45 |

**Gerçek Python ile doğrulandı** (`scripts/missile_dt_convergence.py`, `bvr.combat.missile.Missile` doğrudan çalıştırılarak) — yukarıdaki sayılar tahmini değil, ölçülmüş.

500 Hz'den 50 Hz'e kadar hep isabet iken tam 20 Hz'de temiz bir ıska
çıkıyor, 10 Hz'de tekrar isabete dönüyor — yani **10 Hz'in "yeterli" olduğu
iddia edilemez**, sonuç kabaca rastgele bir rejimde. Olası mekanizma:
MSL-08'in sürekli CPA hesabı adım içinde **doğrusal** hedef hareketi
varsayıyor; hedef gerçekten ivmeleniyorsa (6g) bu varsayım her adımda
farklı miktarda bozuluyor.

**Karar: füze fiziği `Engagement`'ın 10 Hz adımından bağımsız, kendi
içinde `missile_substeps=5` (50 Hz) alt-adımla çalışıyor.** Hedefin
konum/hızı iki tik arasında doğrusal enterpole edilir (aynı varsayım,
bir seviye yukarıda). Radar/muhasebe mantığına dokunulmadı — onların
zaman sabitleri (`coast_s`, `lock_delay_s`) saniyeler mertebesinde, 10 Hz
onlar için fazlasıyla yeterli; sorun yalnızca füzenin kendi PN döngüsündeydi.

> ⚠️ **`missile_substeps=5` de bir denge/doğruluk parametresidir, kanıtlanmış
> alt sınır değil.** Tabloda 50 Hz ile 500 Hz arasındaki fark, 20 Hz ile
> aralarındaki farktan belirgin şekilde küçük — makul bir güvenlik payı
> ama "yeterli" olduğu ayrıca kanıtlanmadı. Taktik komutan daha agresif
> (>6g) manevralar üretmeye başlarsa `scripts/missile_dt_convergence.py`
> yeniden çalıştırılıp `missile_substeps` gerekirse artırılmalı.

## 10. Çok Uçaklı Simülasyon (SIM2) — Faz 1.5

Kapsam: yeni fizik yok, zorluk bağlantıda. Sıra: 1.5a (iki JSBSim yan yana)
→ 1.5b (guidance ikisini birden sürsün) → 1.5c (muhasebe bağlansın, 1v1) →
1.5d (Tacview çoklu nesne) → 1.5e (2v2, 4 uçak × 4 AMRAAM = 16 kapasite).

### SIM2-01 — 1.5a: iki JSBSim örneği arasında sızıntı yok (ölçüldü)

**Soru.** Türbülans ve nokta kütlenin **bir örnek İÇİNDE** `reset()`
çağrıları arasında kalıcı olduğu biliniyor (`HANDOFF.md` tuzak 2, 37).
Ama iki **AYRI** `F16Sim` nesnesi arasında paylaşılan/sızan bir durum
olup olmadığı hiç sınanmamıştı.

**Ölçüldü** (`scripts/two_jsbsim_smoke.py`): iki `F16Sim`, aynı koşulda
(20 kft, M0.8, düz) trim edilip 60 s düz uçuşla (İç Döngü, `phi=0,
gamma=0`) sürüldü — biri diğeri hâlâ bellekteyken açılıp çalıştırıldı.

| örnek | başlangıç | final | sapma (final) | sapma (tepe) |
|---|---|---|---|---|
| A (tek başına) | 20000.0 ft | 20004.4 ft | 4.43 ft | 4.43 ft |
| B (A açıkken sonra) | 20000.0 ft | 20004.4 ft | 4.43 ft | 4.43 ft |

**A ve B'nin sonucu birbirinin BİREBİR AYNISI (fark 0.00 ft) — sızıntı
yok.** İki `F16Sim` nesnesi birbirinden tamamen bağımsız.

**Not — "12–76 ft" iddiası doğrulanamadı, farklı bir şey ölçüyor olabilir.**
Faz 1.5 tasarım notunda 1.5a'nın kabulü için "12–76 ft" aralığı
belirtilmişti; bu proje dosyalarında (`HANDOFF.md`, `test_inner_loop.py`)
bulunamadı. Yukarıdaki 4.43 ft, TEK bir koşulda (20 kft/M0.8, düz kanat)
düz uçuş sapması — muhtemelen "12–76 ft" iddiası `HANDOFF.md`'deki farklı
bir ölçüme (**koordineli dönüş** 45°/20s: 27–51 ft, birden fazla irtifa/Mach
koşulu) atıfta bulunuyor, aynı şey değil. Sızıntı sorusu (asıl soru)
kesin cevaplandı; sayı referansı belirsiz kaldıysa kaynağı ayrıca
teyit edilmeli.

**Kaynak bulundu (2026-09-11):** "12–76 ft", `TEKNIK_NOTLAR.md:233`'teki trim
ölçümü — `scripts/smoke_trim.py`'nin birkaç irtifa/Mach koşulunda trim
sonrası 60 s düz uçuş sapması. Tek koşuldaki 4.43 ft onunla çelişmiyor. Ama
sızıntı için doğru kabul kriteri o aralık değil, **"A açıkken B ≡ B tek
başına"**dır — ve A ile B aynı kurulduğu için bu testte o kriter sınanamıyor
(bkz. SIM2-07 "Hâlâ açık" madde 3). Asimetrik sürüm bit bit aynı çıktı.

### 📋 İzlenecek: guidance politikası sabit hedefe eğitildi, hareketli hedefe değil

`bvr/envs/guidance_env.py::_new_waypoint()` incelendi: hedef **sabit**
üretiliyor, yakalanana (ya da rastgele yürüyüşle bir sonraki bacağa
geçilene) kadar değişmiyor. 1.5c'de komutan (TAC-08, sanal hedef 5–25 nmi)
bu hedefi düşman uçağın **hareketli** konumuna göre her 10 Hz tikte
kaydırırsa, politika eğitiminde hiç görmediği bir dağılımla (sürekli kayan
hedef) karşılaşır — `HANDOFF.md` tuzak #31/35 ailesinden bir dağılım kayması
riski.

**Şimdilik düzeltilmiyor, gözlemleniyor.** 1.5c'nin kabul kriterine (180 s
çökmeden koşsun) ek olarak **davranışsal** kontrol de yapılmalı: Tacview'de
uçak TAC-08'in bulunuş şeklindeki gibi (sürekli yatış sallanması) titriyor
mu diye bakılmalı — sayısal metrikler bunu daha önce hiç yakalamamıştı.

### SIM2-02 — paylaşılan gözlem modülü + `GuidanceDriver` (ölçüldü)

**Adım 1 — `bvr/envs/guidance_shared.py`.** `GuidanceEnv`'in gözlem/açı/
komut-dönüşüm formülleri (`_bearing_error`, `_range_to_target`, `_obs`,
`_action_to_cmd`, `_cmd_to_action`) saf fonksiyonlara çıkarıldı;
`guidance_env.py`'nin kendi metodları artık bu modüle **delege ediyor**
(çağrı yerleri değişmedi). **Regresyon kanıtı:** `scripts/command_hold_test.py
runs/reward_r3_both/sac_1999968_steps.zip` çıktısı çıkarma öncesi/sonrası
**byte-byte özdeş** (14/14 + 14/14, her satır aynı sayı).

**Adım 2 — `bvr/envs/guidance_driver.py`.** `GuidanceEnv.step()`'in fizik
kısmı (JSBSim + İç Döngü + Kalkan), ödül/rastgele-hedef/Gym mantığı
olmadan `GuidanceDriver.tick(action)` olarak yeniden kuruldu.

**Bulunan eksik — ölçülerek yakalandı.** İlk sürüm `GuidanceEnv` ile
`GuidanceDriver`'a **aynı aksiyon dizisi** verilip çıkan `FlightState`'ler
karşılaştırıldığında (`scripts/guidance_driver_smoke.py`), adım 2'den
itibaren sapma büyüyordu (200 adımda irtifa farkı ~200 ft, `nz` farkı 1.65).
Sebep: `GuidanceConfig.action_rate_limit` varsayılanı `0.25` (**kapalı
değil**) — `GuidanceEnv.step()` aksiyonu komuta çevirmeden önce bir **komut
yavaşlatma (slew-rate) sınırı** uyguluyor; `GuidanceDriver` bunu atlamıştı.
Bu eğitime özgü bir ayrıntı değil — dosyanın kendi başlığında "gerçek bir
güdüm sistemi de komutu 10 Hz'de tam ölçekte savurmaz" diye açıklanan,
dondurulmuş modelin **altında kalibre olduğu** bir şekillendirme filtresi.
Düzeltme sonrası aynı test: **tüm alanlarda fark <1e-11 (kayan nokta
gürültüsü seviyesinde) — birebir aynı fizik.**

> ⚠️ Bu, projede tekrar eden bir dersin yeni bir örneği: "eğitim ortamının
> neyin eğitime özgü, neyin sözleşmenin kendisi olduğunu" varsaymak yerine
> **ölçmek** gerekiyor. `action_rate_limit` ilk bakışta bir ödül/pürüzsüzlük
> ayrıntısı gibi görünüyordu; aslında `step()`'in HER çağrısında koşulsuz
> uygulanan, modelin kalibre olduğu bir fizik kısıtıydı.

### SIM2-03 — 1.5b: iki `GuidanceDriver` eşzamanlı, kontaminasyon yok (ölçüldü)

**Yöntem** (`scripts/guidance_driver_dual_hold_test.py`): 14 orijinal
`command_hold_test` durumu 7 eşzamanlı **çifte** ayrıldı — bilerek AYNI değil
**FARKLI** manevra tipleri eşlendi (ör. "tutma" ile "birleşik-alçalma"), RAD-08
kalıbını (iki hedefi tek nesneyle izlerken durum sızması) burada da aramak
için. Her çift 90 s eşzamanlı koşturuldu, sonuç tek-uçaklı referansla
(`command_hold_test.py`'nin aynı modelle ürettiği sayılar) karşılaştırıldı.

**Sonuç: 14/14 + 14/14, tek-uçaklı referanstan en büyük sapma 0.45 ft /
0.000048 Mach** — kayan nokta gürültüsü seviyesinde. İki `GuidanceDriver`
örneği arasında paylaşılan durum yok; `F16Sim`, `InnerLoop` ve (kalkan
açıksa) `CBFShield`'in her örnek için bağımsız kurulduğu doğrulandı.

### SIM2-04 — 1.5c: ilk uçtan uca 1v1 koşusu (`scripts/bvr_1v1_smoke.py`)

**Mimari not — ortak koordinat çerçevesi.** Her `F16Sim`, kendi `reset()`
anını yerel (0,0) kabul eder (`origin_lat/lon` o anda sabitlenir). İki
uçağı aynı sahnede (30 nmi ayrı) başlatmak için her uçağın kendi
`north_ft`/`east_ft`'ine sabit bir ofset eklenip **paylaşılan** çerçeveye
taşınması gerekti (`dataclasses.replace()` ile `FlightState`'in konumu
düzeltilmiş bir kopyası üretilip muhasebe/radar/füzeye O verildi — sürücünün
kendi iç durumu hiç değişmedi).

**Sonuç: 180 s'nin tamamı çökmeden, NaN olmadan koştu.** Basit betikli
komutan (birbirine dön — TAC-08, 12 nmi sanal hedef; düşmanın aktif bir
füzesi varsa 90° kır) ile: t=2.4-2.5s'de karşılıklı ikişer füze (`max_per_
target=2` sınırına kadar), t=13.7 ve 27.9-28.7s'de hepsi sırayla `"kor"`,
mühimmat (4/4) tükenince olaysız devam. Menzil/zamanlama fizikle tutarlı.

**Gözlem — hiçbir füze isabet etmedi, hepsi `"kor"` oldu.** İlk yorum:
sebep kod hatası değil, betiğin **kasıtlı basitliği**: "düşmanın aktif
füzesi var → anında 90° kaç" kuralı, iki taraf da neredeyse eşzamanlı ateş
ettiği için **her ikisinin de anında kaçmasına** yol açıyor — kaçarken
kendi fırlattığı füzeyi de desteksiz bırakıyor. Bu, projenin baştan beri
vurguladığı "füzeni desteklemek için dönük kalman lazım, ama dönük
kalırsan sen de hedefsin" ödünleşmesinin ta kendisi.

**⚠️ DÜZELTME (bkz. SIM2-07): bu yorum EKSİKTİ.** Bağımsız bir inceleme
90°'nin (tam beam) SEBEP olduğunu ölçtü: gimbal sınırını (60°) aşıp
ATICI ucağın KENDİ kilidini kırıyor — "betik dengelenmiyor" doğru ama
"düzeltilmiyor" YANLIŞ çıktı. `--crank-deg` parametresi eklenip
varsayılan 35°'ye çekilince zincir (atış→pitbull→seeker→isabet)
ÇALIŞIYOR — 1v1'de karşılıklı imha, ayrıntı SIM2-07'de. Ders: "betiğin
kasıtlı basitliği" açıklaması BİR olası mekanizmaydı, TEK mekanizma
olduğu ÖLÇÜLMEDEN "düzeltilmiyor" kararı erken verilmişti (bkz.
HANDOFF.md tuzak 31: "tek yapısal fark şu" akıl yürütmesi delil değildir).

---

### SIM2-05 — 1.5d: çok nesneli Tacview kaydı (`bvr/sim/acmi.py`, `scripts/bvr_1v1_smoke.py --acmi`)

**Bulunan iki hata (tek uçaklı kullanımda gizli kalmış):**

1. `ACMIRecorder._header_written` tek bir `bool`'du — sadece İLK kaydedilen
   nesne Name/Type/Color/Pilot başlığı alıyordu; ikinci uçak (kırmızı) veya
   herhangi bir füze isimsiz/tipsiz görünürdü. `set[int]` yapılıp `obj_id`
   başına izlenerek düzeltildi.
2. Konum `st.lon_deg`/`st.lat_deg`'den okunuyordu — bunlar her `F16Sim`'in
   KENDİ özel `reset()` orijinine (her zaman ~0,0) göredir. İki ayrı
   `F16Sim` örneğinden gelen iki uçak, gerçek muhasebe-çerçevesi ayrımları
   ne olursa olsun Tacview'de ÇAKIŞIK görünürdü. Düzeltme: yeni `_lonlat()`
   yardımcısı, `st.north_ft`/`st.east_ft` (paylaşılan NEU muhasebe çerçevesi
   — çağıran taraf `dataclasses.replace()` ile ofsetliyor, bkz. SIM2-04) ve
   TEK bir `ref_lat`/`ref_lon`'dan türetiyor; `jsbsim_bridge.py::state()`
   ile AYNI `364000 ft/derece enlem` yaklaşık sabiti kullanılıyor.
   Geriye dönük uyumluluk `demo_inner_loop.py`'nin `git stash` öncesi/sonrası
   çıktısı diff'lenerek doğrulandı: tek fark, sabit `ref_lat` ile o anki
   gerçek enlem arasındaki kosinüs terimi farkından gelen ~9 mm (7.
   ondalık basamak) boylam sapması — zararsız, projenin kendi düz-dünya
   yaklaşımıyla (aynı dosyanın kendi yorumu) tutarlı.

**Üçüncü hata — sadece çok nesneli kayıtta ortaya çıktı (zaman damgası
kayması).** İlk uygulamada füze/nesne-kaldırma çağrılarına betiğin YEREL
`t = k*DT` (adım ÖNCESİ, k-indeksli) değişkeni veriliyordu, ama
`ACMIRecorder.record()` uçak zaman damgasını `st.t`'den (adım SONRASI,
`(k+1)*DT`) alıyor — ikisi tam 1 DT (0.1 s) kayıyor. Sonuç: dosyada
zaman damgaları GERİYE atlıyordu (`#2.400` → `#2.500` → `#2.400` tekrar)
ve yeni fırlatılan füzenin İLK kaydı, atış anındaki değil BİR TİK
SONRAKİ uçak pozisyonunda görünüyordu (füze izi atış karesinde
"boşlukta" başlıyormuş gibi görünürdü). Ölçümle yakalandı: `msl_blue_1`in
"#2.400" altındaki ilk konumu, uçağın "#2.400" değil "#2.500" altındaki
konumuyla bit-bir aynıydı. Düzeltme: füze kaydı/kaldırma çağrılarına
artık `st_blue_combat.t` (uçağınkiyle AYNI iç saat) veriliyor —
`missile_dt_convergence`/`GuidanceDriver` doğrulamalarında defalarca
işe yarayan disiplin burada da geçerli: "aynı anı temsil eden iki
değer, gerçekten AYNI kaynaktan gelsin, iki ayrı sayaçtan değil."

**Doğrulama:** `scripts/bvr_1v1_smoke.py <model> --duration 60 --acmi
<path>` koşusu (`runs/reward_r3_both/sac_1999968_steps.zip`) — düzeltme
sonrası üretilen dosyada: (a) zaman damgaları tamamen monoton (script ile
otomatik kontrol edildi), (b) her yeni füzenin ilk kaydı, atan uçağın O
KARESİNDEKİ konumuyla bit-bir aynı, (c) `"kor"` ile sonuçlanan 4 füzenin
`-obj_id` kaldırma satırları, konsolun bastığı `"t=13.7s kor"` olay
zamanıyla birebir aynı `#13.700` bloğunda. `bvr/combat/tests` (46/46)
etkilenmedi.

---

### SIM2-06 — 1.5e: 2v2 angajman (`scripts/bvr_2v2_smoke.py`)

**Beklenenden az kod değişikliği gerekti — bu kendi başına bir bulgu.**
`Engagement`/`Radar` zaten N-uçaklı tasarlanmıştı (`Radar` hedefleri
`target_id` sözlüğüyle ayırıyor — kendi docstring'i "ileride kol uçuşu
2v2" diyordu; `Engagement.aircraft`/`missiles` zaten genel `dict`/`list`,
hiçbir yerde "tam 2 uçak" varsayımı yok). Gerçekte yeni gereken SADECE
betik-seviyesi (komutan) mantığıydı:
1. **Hedef seçimi** — 1v1'de düşman sabitti; 2v2'de her uçak HER TİKTE
   kendi takımından bağımsız en yakın CANLI düşmanı seçiyor
   (`nearest_alive_enemy`, `relative_geometry(...).range_nm` ile).
   `pick_target()`'in kendisi DEĞİŞMEDİ — sadece "düşman" artık değişken.
2. **Ateş döngüsü** — 1v1'in tek (shooter,target) çiftine karşı, burada
   takım-çaprazı 4 çift her tikte ayrı `can_fire` kontrolünden geçiyor.

**Bilinen sadeleştirme (bilerek düzeltilmedi):** `Engagement.update()`
radarı düşmanlara olduğu kadar TAKIM ARKADAŞINA karşı da çalıştırıyor
(gerçek radar IFF/dost-düşman ayrımı yapar). Zararsız — her hedef kendi
`target_id`'siyle ayrı izleniyor, kilit durumları karışmıyor, sadece
boşuna bir kontak var. Düzeltilmedi çünkü hiçbir kabul kriterini etkilemiyor.

**Doğrulama (crank=90°, düzeltmeden ÖNCE):** `scripts/bvr_2v2_smoke.py
<model> --duration 180 --acmi <path>` (`runs/reward_r3_both/
sac_1999968_steps.zip`, 2 mavi + 2 kırmızı, kanat aralığı 3 nmi, takımlar
arası 30 nmi). Sonuç: 180 s boyunca çökme/NaN yok; her 4 uçak da 4'er
füze (toplam 16/16 mühimmat) attı, hepsi `"kor"` ile sonuçlandı; dört
taraf da hayatta kaldı (mühimmat tükenmesiyle bitti). Tacview kaydında:
4 uçak nesnesi (obj 1-4) ayrı konumlarda, aynı tikte birden fazla füze
fırlatan bir uçağın İKİ füzesi de ATIŞ KARESİNDE tam olarak o uçağın
pozisyonunda beliriyor, zaman damgaları uçtan uca monoton, `-obj_id`
kaldırma satırları konsolun `"kor"` zaman damgasıyla birebir aynı blokta.
`bvr/combat/tests` (46/46) etkilenmedi.

**⚠️ DÜZELTME (bkz. SIM2-07):** "hepsi kor" burada da SIM2-04'teki aynı
eksik yorumun sonucuydu (90° crank, gimbal aşımı). `--crank-deg 35`
(yeni varsayılan) ile tekrar koşulunca: bazı çiftler `"kor"` olmaya devam
etti, bazıları GERÇEK karşılıklı imhaya ulaştı (blue1↔red2 birbirini
vurdu, blue2/red1'in füzeleri kor oldu) — yani 2v2, dört bağımsız
(shooter,target) çiftinin FARKLI sonuçlar üretebildiği, tekdüze olmayan
bir sonuç veriyor artık. Tacview/olay-sayısı doğrulaması aynı şekilde
geçerliliğini korudu.

---

### SIM2-07 — crank açısı gimbal sınırını aşıyordu + füze kütlesi canlı yolda hiç uygulanmıyordu (düzeltildi)

**Bağımsız bir inceleme** (bu oturumun dışından, `guidance_env.py`
refaktörünü ve 1.5 smoke betiklerini denetleyen ayrı bir oturum) SIM2-04/
06'daki "hepsi kor, betik dengelemiyor" yorumunun EKSİK olduğunu ölçtü.
İki gerçek hata bulundu, ikisi de bağımsız olarak koddan doğrulandı ve
düzeltildi:

**1) Kaçış (evade) manevrası SABİT 90° (tam beam) idi, parametre değildi.**
`pick_target()`'te `brg += math.pi / 2.0` hardcoded'dı. Ölçüm: komut
edilen kırma açısı ile GERÇEKLEŞEN tepe ATA arasında fark var (aşım) —
50° komutla bile gerçek ATA ~65.5°'ye çıkıyor, `RadarConfig.
gimbal_az_deg=60°` sınırını aşıyor ve **ATICI ucağın KENDİ radar kilidi**
kopuyor (`is_tracking(target)` false dönüyor → `datalink_ok=False` →
füze zaten `MSL-06`'daki hafıza süresi (**5.0 s**; 10.0 denenip geri alındı, bkz. MSL-06/MSL-09) dolunca `"kor"`). Yani
90°'lik "tam kaçış" hem düşmanın füzesinden kaçıyor HEM DE atıcının kendi
füzesini köreltiyor — SIM2-04'ün "füzeni desteksiz bırakıyor" tespiti
DOĞRUYDU ama mekanizması "davranışsal tercih" değil, **geometrik bir
sınır aşımıydı**. Ölçülen taramada 35° ilk kez zinciri (atış → pitbull →
seeker → isabet) uçtan uca çalıştırdı; bu **fiziksel sabit değil, DENGE
PARAMETRESİ** (crank arttıkça kaçış iyileşir ama kendi füzeni riske
atarsın) — Faz 2'nin öğrenilmiş komutanı için ilk somut girdi.

*Düzeltme:* `pick_target()`/`Aircraft.step()`'e `crank_rad` parametresi
eklendi, her iki betiğe de `--crank-deg` CLI argümanı (varsayılan **35**)
eklendi. `math.pi/2.0` sabiti kaldırıldı.

**2) Füze kütlesi `GuidanceDriver`'ın gördüğü GERÇEK JSBSim durumuna hiç
ulaşmıyordu.** `Engagement.fire()`'daki kütle-düşürme denemesi
(`for mass_attr in ("mass_lb","weight_lb"): if hasattr(...)`) `FlightState`
dataclass'ında böyle bir alan OLMADIĞI için her zaman `hasattr=False`
dönüyordu — sessizce hiçbir şey yapmıyordu. Bu, `test_engagement.py`'deki
`MockAircraftState(mass_lb=...)` testinde GEÇİYORDU (mock'ta alan var)
ama gerçek uçuşta hiç çalışmıyordu; üstelik `combat_state` her adımda
`dataclasses.replace()` ile üretilen bir KOPYA olduğu için, alan olsa
bile yazılan değer bir sonraki tikte kaybolurdu. Ölçüm: başlangıç JSBSim
ağırlığı 22.859 lb (0 füze) idi, 4 AMRAAM yüklüyken 24.199 lb olmalıydı.

*Düzeltme:* `GuidanceDriver.set_payload(extra_lb)` eklendi —
`payload_check.py`'de doğrulanan yöntemle (`inertia/pointmass-weight-
lbs[0]`, CG korunarak `pointmass-location-X-inches[0]`) DOĞRUDAN JSBSim'e
yazıyor. `Aircraft.__init__` artık `reset()`'ten ÖNCE tam mühimmatla
(4×335 lb) trim ediyor (payload_check'in ölçtüğü en ağır durum — GUI-11
sözleşmesi 25.942 lb'de zaten sağlam çıkmıştı); her `fire()` sonrası
`Aircraft.drop_missile()` kalan mühimmata göre ağırlığı güncelliyor
(yeniden trim GEREKMİYOR — yakıt tüketimi gibi sürekli bir kütle
değişimine iç döngü zaten uyum sağlıyor). `Engagement.fire()`'daki mock-
uyumlu döngüye DOKUNULMADI (`test_engagement.py`'nin gerçek bir testi bu
davranışa dayanıyor, 46/46 hâlâ geçiyor).

**Doğrulama (crank=35°, kütle düzeltmesiyle):**
- Kütle mekanizması izole test edildi: `set_payload(4×335)` sonrası
  JSBSim `inertia/weight-lbs` = **24199.0** (beklenen tam eşleşme, önceki
  ölçümün "24.199 olmalıydı" tahminini doğruladı); `set_payload(0)` sonrası
  **22859.0** — fark tam **1340 lb**.
- `guidance_driver_smoke.py`: dondurulmuş katman hâlâ <1e-6 toleransla
  bit-bit aynı (yeni metod opt-in, mevcut hiçbir çağrı yolunu değiştirmedi).
- `bvr_1v1_smoke.py --duration 180` (varsayılan crank=35°): t=2.4-2.5s
  ilk volley, t=43.3s pitbull (İLK KEZ — önceki koşularda hiç görülmemişti),
  **t=62.2s KARŞILIKLI İSABET** — iki taraf da imha oldu (`blue alive=False
  red alive=False`), ikinci füzeler `"hedefsiz"` (hedef zaten ölü).
- `bvr_2v2_smoke.py --duration 180` (varsayılan crank=35°): karışık sonuç
  — blue1↔red2 karşılıklı isabetle imha oldu, blue2/red1'in füzeleri
  `"kor"` kaldı. Toplam 2/4 uçak imha, 2/4 mühimmatsız hayatta.
- `bvr/combat/tests` (46/46) ve `guidance_driver_smoke.py` etkilenmedi.

**Ders (bu oturum için):** SIM2-04/06 yazılırken "kor" sonucuna TEK bir
olası açıklama ("betik dengelemiyor") bulununca orada durulmuş, ALTERNATİF
mekanizmalar (gimbal aşımı, ölü kütle-düşürme kodu) aranmamıştı. HANDOFF.md
tuzak 31'in ("bir korelasyon gördün diye mekanizmayı bildiğini sanma")
tam bir tekrarı — bu sefer başka bir oturumun bağımsız denetimiyle
yakalandı. Bundan sonra "X çünkü Y" tarzı bir yoruma "başka bir Z de aynı
sonucu üretir mi?" sorusu sorulmadan "düzeltilmiyor" kararı verilmeyecek.

#### Bağımsız doğrulama — 2026-09-11 (düzeltme sonrası denetim)

| kontrol | sonuç |
|---|---|
| `set_payload` reset'ten önce → trim ağır uçağa göre mi | ✅ 22.859 → **24.199 lb** (+1.340 birebir), trim gazı 0.3641 → 0.3676 |
| Atış sonrası `drop_missile()` | ✅ **−335.1 lb** (bir tik, yakıt dahil); 4 atış sonrası 22.858,8 lb |
| CG korunuyor mu | ✅ −190.19 (boş) → −190.23 (yüklü) → −190.19 (hepsi atıldı) in |
| `drop_missile` gerçekten `eng.fire` sonrası mı | ✅ `bvr_1v1_smoke.py:186`, `bvr_2v2_smoke.py:217` |
| 1v1 smoke (crank 35°) | ✅ pitbull t=43.3 s, karşılıklı isabet t=62.2 s, ikinci füzeler `hedefsiz`, **0 kor** |
| 2v2 smoke (crank 35°) | ✅ blue1↔red2 karşılıklı imha; 16 atışın **2'si isabet, 6'sı hedefsiz, 8'i kor** |
| Refaktör sonrası donmuş katman | ✅ 3600 gerçek politika adımında gözlem/komut farkı **0.000**; GUI-11 14/14 + 14/14 |
| Örnekler arası sızıntı (asimetrik) | ✅ A sert türbülans + 1.340 lb + 35 kft/M1.1 iken B, tek başına koşusuyla **bit bit aynı** |

**Crank taraması** (40 nmi başlangıç):

> ⚠️ **Etiket düzeltmesi (2026-09-11):** bu tablo ilk yazıldığında başlıkta
> `datalink_memory_s = 10.0` yazıyordu. Kodda (`missile.py:104`) ve MSL-06'da
> değer **5.0** — 10.0 denenip geri alınmıştı. Taramanın hangi değerle
> koşulduğu sonradan kanıtlanamadı. 35° satırı, 5.0 ile koşan 1v1 smoke'la
> (yukarıdaki doğrulama tablosu) aynı sonucu verdi. 45° satırı 5.0 ile
> yeniden doğrulanmadı. Faz 2.0'daki crank → ATA eğrisi bundan ETKİLENMEZ:
> o ölçüm yalnızca geometriye bakar, füze hafızasına bakmaz.

| crank | atış ≤ 20 nmi | atış ≤ 28 nmi |
|---|---|---|
| 35° | 2 isabet, karşılıklı imha | 2 isabet, karşılıklı imha |
| 45° | 1 isabet | 0 — hepsi `kor` |
| 50° | — | 0 — tepe ATA 65.5° |
| 90° | — | 0 — kilit ATA −61°'de düştü |

**Hâlâ açık:**
1. ~~**Crank → tepe ATA eğrisi ölçülmedi.**~~ ✅ **KAPANDI (Faz 2.0,
   SIM2-09).** `scripts/crank_sweep.py` ile ölçüldü. "Etkili crank sınırı
   ~40°" hipotezi YANLIŞ çıktı: sabit bir açı sınırı yok, |ATA| menzil
   kapandıkça büyüyor — sınır açı+menzil çiftidir (35° ~9 nmi, 30° ~6 nmi,
   25° ~5 nmi @ 55° eşiği). `CRANK_DEG_DEFAULT` 35 → 30.
2. **2v2'de aşırı atış (overkill):** 16 atışın 6'sı `hedefsiz` — iki kanat
   da aynı "en yakın düşmanı" seçip aynı hedefe yığılıyor. Hedef paylaşımı
   (sorting) Faz 6'ya (kol uçuşu) bırakıldı — Faz 2 betikli tabanı 1v1.
3. **1.5a testi hâlâ simetrik** (`two_jsbsim_smoke.py`): iki örnek aynı
   kurulduğu için sızıntı olsa da fark 0 çıkar — test başarısız olamaz.
   Sonuç yukarıdaki asimetrik testle doğrulandı, ama commit'lenmiş test o değil.
4. `F16Sim(seed=...)` → `self.rng` hiçbir yerde kullanılmıyor; smoke'lardaki
   `hash(name)` her koşuda farklı tohum veriyor. Şu an zararsız (tohum ölü),
   ama biri `rng`'yi kullanmaya başlarsa tekrar üretilebilirlik sessizce bozulur.

---

### SIM2-08 — Guidance saf takip (pure pursuit) kullanıyor, PN değil: be=0'da bile agresif yatış (ölçüldü, retrain ERTELENDİ)

**Nasıl bulundu:** Faz 2.0 (`crank_sweep.py`) öz-denetimi θ=0 (crank yok) kontrol
koşusunda `|ATA_peak| < 5°` bekliyordu; gerçek değer ~20°'ye kadar çıktı,
öz-denetim **FAIL** verdi. "0-20s intercept → ATA≈0 taban çizgisi" varsayımı
tutmuyordu.

**Kod hatası mı diye önce elendi.** `GuidanceEnv` ve `GuidanceDriver`'ı AYNI
senaryoda (30 nmi, aynı seed) yan yana koşturuldu: 30 tikte aksiyon farkı
**tam 0.0000**, gözlem farkı makine hassasiyetinde. `GuidanceDriver` doğru —
sorun dondurulmuş POLİTİKANIN kendisinde.

**Asıl bulgu — eğitim aralığının TAM İÇİNDE.** Hedef tam karşıda (bearing_error
=0) sabitlenip sadece menzil tarandı:

| menzil | action[0] (yatış) |
|---|---|
| 3.3 nmi (eğitim alt ucu) | +0.370 (~17°) |
| 12 nmi | +0.760 (~34°) |
| 14.8 nmi (eğitim üst ucu) | +0.761 (~34°) |
| 25 nmi ve ötesi | +0.277 (~12°, menzil kanalı 3.0'da doyuyor) |

Yani "3.3–14.8 nmi" diye belgelenen eğitim aralığının **TAM ORTASINDA**, hedef
tam karşıdayken bile politika ~34° yatış komutu veriyor — bu bir kenar-durum
değil. `command_hold_test.py`'nin bunu hiç yakalamamasının sebebi netleşti:
o test 30 nmi kullanıyor (menzil kanalı doygun, "sakin" bölgeye denk geliyor)
VE sadece irtifa/Mach'a bakıyor, yatışa/rotaya hiç bakmıyor.

**Mekanizma (kontrol teorisi):** gözlem vektörü (`guidance_shared.py::
build_obs`) sadece ANLIK kerteriz hatasını (`sin(be), cos(be)`) veriyor,
**LOS DÖNME HIZINI (λ̇) hiç vermiyor**. Saf takip (pure pursuit), "kerteriz
sıfırsa dümdüz git" diyemiyor çünkü be=0'ın iki farklı sebebi var: (a) gerçek
çarpışma rotası (λ̇=0, doğru davranış hiçbir şey yapmamak), (b) bir dönüşün
ORTASINDA hedefin üzerinden anlık geçiş (λ̇≠0, ama gözlemde hiç yok). Ağ,
eğitimde be=0'ı muhtemelen hep (b) türü geçici bir an olarak gördüğü için
"dönmeye devam et" öğrenmiş. Bunun doğru çözümü zaten bu projenin füze
kodunda VAR (`a = N·V·λ̇`, Oransal Seyrüsefer, bkz. MSL bölümü) ama UÇAĞIN
KENDİ güdümü hiç bu prensiple tasarlanmadı.

**Dış bir incelemenin ilk teşhisi ("gözlemde cross-track error eksik, PN/lead
gerekir, retrain edelim") yön olarak DOĞRU ama kavram YANLIŞ** çıktı:
cross-track error bir HATTA (rota/koridor) göre tanımlanır; burada tek bir
NOKTA kovalanıyor, hat yok. Doğru eksik kavram **LOS dönme hızı**dır.

**Neden HEMEN retrain edilmedi.** Gözlem vektörünün ŞEKLİNİ değiştirmek
(19→20 boyut, λ̇ eklemek) demek: guidance'ı yeniden eğitmek, üzerine kalibre
edilmiş CBF kalkanını yeniden ölçmek (eğitim döngüsü içinde eğitildiği için
sökülemez), GUI-11/stres testi/safety_eval'i hepsini yeniden koşmak —
"Faz 2'de küçük bir alt adım" değil, **Faz 3'ün (guidance) tamamının yeniden
açılması**. HANDOFF.md §2'nin ("katmanları aşağıdan yukarı dondur") doğrudan
ihlali, üstelik henüz PRATİKTE bir sorun yarattığı gösterilmemişti.

**Ölçüldü (`scripts/pursuit_cost.py`): gerçek angajman ölçeğinde maliyet
ÖNEMSİZ.** Kurulum: aynı kinematik hedef, 30 nmi başlangıç, 10 nmi'ye
kapanana kadar `mode="intercept"` (hiç crank yok), 3 irtifa × 2 Mach:

| ölçüt | en kötü değer | yorum |
|---|---|---|
| zaman farkı (gerçek vs. sıfır-sapma ideal) | +2.3% | ~65-70 s'lik kapanmada gürültü düzeyinde |
| yol farkı (katedilen vs. düz çizgi) | +0.1% | pratikte sıfır |
| gimbal payı (60° − |ATA|_tepe) | +41.9° | |ATA| en fazla 18.1°'ye çıkıyor, kilide 42° pay var |
| Mach (min) | 0.802 | sadece başlangıç hızlanma geçişi, banking kaynaklı değil |

Neden bu kadar zararsız: toplam düz-çizgi mesafesi (~18 nmi) çok uzun; birkaç
derecelik sapmanın yol uzunluğuna etkisi `(1-cosθ)` ile ölçekleniyor, küçük
açılarda ihmal edilebilir. |ATA| tepe noktası (13-18°) gimbal sınırından
(60°) o kadar uzak ki kilit hiçbir an tehdit altında değil.

**KARAR: retrain ERTELENDİ.** Bulgu gerçek (guidance saf takip kullanıyor,
LOS dönme hızından habersiz) ama ölçülen mission-level maliyeti önemsiz —
donmuş katmana DOKUNULMADI. `HATA_GUNLUGU.md`'ye H-06 olarak işlendi. İleride
bu izlenmeli: 2v2/4v4'te daha uzun süreli sürdürülen intercept fazları, ya da
daha kısa menzilli/daha agresif komutan senaryoları maliyeti büyütebilir --
o zaman bu karar yeniden ölçümle gözden geçirilir.

**crank_sweep.py'ye etkisi:** "0-20s intercept → ATA≈0 taban çizgisi"
varsayımı TAM tutmuyor (13-20° sapma var) ama bu sapma mission açısından
önemsiz olduğu için sweep'e devam edilebilir — θ=0 satırı "saf crank etkisi
sıfır" değil "taban çizgisi + sıfır ek crank" olarak okunmalı; her θ'nın
sonucundan θ=0'ınki çıkarılarak net crank etkisi hesaplanabilir.

---

### SIM2-09 — crank_sweep tam taraması: 35° kendi güvenlik eşiğini aşıyor, 30°'ye düzeltildi ⚠️ AŞAĞIDA DÜZELTİLDİ

**Tam tarama** (`scripts/crank_sweep.py`, 9 açı × 3 irtifa × 2 Mach + yön
kontrolü = 60 koşu) SIM2-07'nin tek-noktalı gözlemine (50° komut → 65.5°
tepe ATA) dayanan 35°'lik crank seçimini iki yeni bulguyla düzeltti.

**Bulgu 1 — sağ/sol crank simetrik değil.** θ=35 hem +1 (sağ) hem −1 (sol)
işaretle koşulunca:

| yön | tepe ATA | aşım |
|---|---|---|
| sağ (+35°) | ~52-56° | **+21°** |
| sol (−35°) | ~25-39° | **−10°** |

Sebep SIM2-08'in kendisi: guidance'ın be=0'daki doğal sağa-yatık önyargısı
sağa kırmayı GÜÇLENDİRİYOR, sola kırmayı SÖNDÜRÜYOR. Yani aynı crank_deg
sabiti, dönüş yönüne göre FARKLI güvenlik payı bırakıyor — davranış ağacı
sağ/sol için aynı sayıyı kullanamaz; sınır daha kötü (sağ) yöne göre
seçilmeli.

**Bulgu 2 — 35°, kendi karar kuralını geçemiyor.** Faz 2.0 protokolünün
önceden yazılı kararı: *"komutan sabiti = en kötü koşuldaki θ_max,
ATA_peak ≤ 55° şartını sağlayan en büyük θ"*. Sağ-kırma (bağlayıcı) verisine
uygulanınca:

| θ | en kötü \|ATA_peak\| (3 irtifa × 2 Mach) | ≤55° mi? |
|---|---|---|
| 25° | 46.9° | ✅ |
| 30° | 51.8° | ✅ |
| **35°** | **56.4°** (15 kft, M0.8) | ❌ |
| 40° | 61.7° | ❌ |

35° en kötü koşulda (15 kft, M0.8) 56.4°'ye çıkıp kendi 55°'lik eşiğini
aşıyor — SIM2-07'nin tek gözlemi (25 kft, M0.9) bu en kötü koşulu hiç
örneklememiş. Kurala harfiyen uyan doğru sabit **30°**.

**Karar: `CRANK_DEG_DEFAULT` her iki smoke betiğinde de 35→30'a çekildi.**
Gerçek angajmanlarda yeniden doğrulandı (`--duration 180`, varsayılan 30°):
- 1v1: t=42.7s pitbull, **t=61.3s isabet** (red imha, blue hayatta).
- 2v2: t=42.6-44.4s pitbull (4 çift), **t=61.2s TÜM 4 uçak da imha**
  (blue1↔red1, blue1↔red2, red2↔blue1, red2↔blue2 — 35°'deki 2/4 imhadan
  daha kesin bir sonuç).

`bvr/combat/tests` (46/46) etkilenmedi. Ders: HANDOFF.md tuzak 46'nın
("başarısız olamayan test test değildir") bir kuzeni — **tek gözlemle
seçilen bir güvenlik sabiti, en kötü koşulu örneklemediği sürece
doğrulanmış sayılmaz.** Tam hikaye: `HATA_GUNLUGU.md` H-05.

**⚠️ DÜZELTME — "35 aşıyor, 30 aşmıyor" hükmü de EKSİKTİ (bağımsız bir
inceleme yakaladı, ben kendim tekrar ürettim).** `metrics()`'te `t_peak`
neredeyse her koşuda pencerenin TAM SON ÖRNEĞİNDE (t=79.9 s, 60 s'lik kaçış
penceresinin bitişi) çıkıyordu — yani ölçtüğümüz "tepe ATA" gerçek bir
geçici aşım DEĞİL, pencere bitene kadar HÂLÂ BÜYÜMEKTE olan bir sürüklenmeydi.
Kaçış penceresini 90 s'ye uzatınca:

| kaçış süresi | 30° | 35° |
|---|---|---|
| 60 s (orijinal ölçüm) | 51.4° ✅ | 56.4° ❌ |
| 90 s (gerçek tepe, artık pencere sonunda değil) | **69.9° ❌** | 75.2° ❌ |

**30° de 55°'yi aşıyor, sadece 35°'den DAHA GEÇ.** "35 eşiği aşıyor, 30
aşmıyor" ayrımı crank açısının değil, keyfi seçilmiş 60 saniyelik ölçüm
penceresinin bir eseriymiş. İkinci işaret aynı yöne bakıyor: taranan 3
irtifa × 2 Mach ızgarası sonucu ~0.1° oynatırken (56.4 vs 56.3), pencere
UZUNLUĞU 19° oynattı (56→75) — taranan eksenler neredeyse etkisizken asıl
etkili eksen (süre/menzil) hiç taranmamıştı. Ayrıca `pick_target()` hedef
Mach'ı hep `CMD_MACH=0.90`'a sabitlediği için "M0.8" satırları birkaç
saniye içinde zaten 0.9'a yakınsıyordu — o eksen de göründüğü kadar bağımsız
değildi.

**Doğru çerçeve: açı değil, MENZİL.** Crank sonsuza kadar sürdürülmez —
sadece tehdit geçene/pitbull olana kadar tutulur. Aynı kurulumda |ATA|'yı
zamana değil MENZİL işaretlerine göre ölçmek anlamlı sonuç veriyor (15 kft,
M0.8, sağ crank):

| θ | 20 nmi | 15 nmi | 12 nmi | 10 nmi | 8 nmi | 6 nmi | 4 nmi |
|---|---|---|---|---|---|---|---|
| 25° | 15.8° | 25.9° | 32.6° | 38.1° | 44.0° | 47.0° | 52.4° |
| 30° | 16.8° | 28.2° | 35.7° | 42.0° | 49.1° | 52.3° | 59.8° |
| 35° | 17.8° | 30.6° | 39.1° | 46.1° | 54.4° | 58.3° | 62.4° |

Yorum: her crank açısının güvenli olduğu bir menzil bandı var — 35° ~9 nmi'ye
kadar, 30° ~6 nmi'ye kadar, 25° ~5 nmi'ye kadar güvenli kalıyor. Uzak
menzilde (15 nmi+) üçü de rahat, aralarındaki fark sadece birkaç derece.

**Karar (değişmedi ama gerekçesi değişti): `CRANK_DEG_DEFAULT=30` KALIYOR.**
30° "35 aşıyor da 30 aşmıyor" diye değil, **"30, kilidi 35'e göre ~3 nmi
daha yakın menzile kadar koruyor"** diye tercih ediliyor — küçük ama gerçek
bir fark, "sonsuza kadar güvenli" iddiası değil.

**Faz 2.3'e (davranış ağacı) taşınan tasarım önerisi:** komutan crank'ı
SABİT bir açıyla değil, GERİ BESLEMEYLE sürmeli — |ATA| belli bir eşiği
(ör. 50°) geçerse açıyı otomatik kıs. Bu hem sağ/sol asimetrisini hem de
menzil/süre sürüklenmesini kendiliğinden çözer, elle ayarlanan tek bir sayı
yerine duruma uyarlanan bir kural koyar. Açık soru: pitbull menzili ~8 nmi
olduğu için, uçağın 8 nmi altında kilidi korumaya ZORUNLU olması bile
gerekmeyebilir (füze zaten bağımsız); bu kısıt Faz 2.3'te netleşecek.

Ders (bir kez daha, ama farklı bir açıdan): **bir ölçüm aracının kendi
gizli varsayımlarını (burada: pencere uzunluğu) fark etmek, ölçtüğü şeyi
fark etmek kadar önemli.** İlk turda "hangi θ eşiği aşıyor" sorusunu
sorarken "ne kadar SÜRE için" sorusunu sormamıştım.

---

## 11. RWR (Radar Uyarı Alıcısı) — Faz 2.1

### RWR-01 — model ve canlı yola bağlama

**Ne işe yarıyor:** Kilitli karar #4 ("füze uyarısı RWR ile, MAW değil")
buraya kadar hiç uygulanmamıştı — betikli komutan kaçış kararını doğrudan
`eng.missiles` listesinden alıyordu, yani uçak füzeyi ATILDIĞI ANDA
hiçbir sensöre ihtiyaç duymadan "görüyordu". `bvr/combat/rwr.py`
(`RWRConfig`, `RWRContact`, `RWR`) bu bilgiyi gerçekçi şekilde geri
kısıtlıyor: uçak sadece (a) düşman radarının aydınlatması (arama/kilit,
`Radar.update()`'in zaten ürettiği `detected`/`tracked`) ve (b) füzenin
kendi arayıcısının açılması (pitbull + arayıcı konisi içinde olmak) kadarını
görür. **Menzil ve füzenin gerçek konumu YOK** — `RWRContact`'ta böyle bir
alan bilerek açılmadı (yapısal kilit).

Mimari: `Engagement.update()` her (atıcı, hedef) çifti için zaten
`relative_geometry`+`Radar.update()` çağırıyordu (bkz. RAD bölümü);
RWR sadece bu SONUCU (önceden çöpe giden `RadarContact` dönüş değeri)
biriktirip TERS yönden (hedefin burnuna göre) ilgili `RWR.feed_signal()`'a
yönlendiriyor. Füze tehdidi için `missile.py`'nin kendi arayıcı-kilidi
formülü (`off_boresight_deg`) modül seviyesine çıkarılıp HEM füzenin kendi
pitbull mantığı HEM RWR aynı fonksiyonu kullanıyor — tek doğruluk kaynağı.

**Uyarı zincirindeki asıl değer, boşlukta:** atıştan pitbull'a kadar
(ölçülen 1v1'de ~40 s) füzenin kendisi hiç görünmez — atıcının radar
kilidi (varsa) hâlâ görünür, ama "füze havada mı" sorusu doğrudan
cevaplanamaz. Bu, BVR'ı ilginç yapan bilgi asimetrisinin tam kendisi.

**Bilerek modellenmeyenler:** menzil, füzenin gerçek konumu, atış anının
kendisi, irtifa/yükseliş açısı, PRF/tip tanıma, TWS/STT ayrımı, LPI,
karıştırma. Hepsi gerçek ama şu an taktik kararı değiştirmiyor.

Bir tanesi ayrıca not edilmeli çünkü **taktik sonucu var: tek yönlü yol
kaybı.** Gerçekte RWR sinyali TEK yön (düşmandan bana) kat eder, radar
yankısı ise GİDİP GELİR (iki yön) — bu yüzden gerçek bir RWR, düşmanı o
seni görmeden ÖNCE duyar ("ilk uyarı" avantajı). Bizim modelde uyarı,
düşmanın radarının beni tespit/kilit etmesine bağlı, yani bu erken-duyma
avantajı YOK. Eklemek ucuz (`detect_range_nm`'e bir çarpan), ama önce
ajanların bunu sömürüp sömürmediği görülmeli — Faz 2.4/3'te ölçülüp
karara bağlanacak.

### RWR-02 — bağımsız incelemede bulunan üç hata (hepsi düzeltildi)

İlk uygulama kod incelemesinden geçti (46/46 test, gerçek 1v1'de "atış
görünmez" davranışı bile doğru çalışıyordu) ama bağımsız bir inceleme,
canlı yolu (smoke betiğinin gerçekte OKUDUĞU değerleri) ayrıca ölçünce üç
gerçek hata buldu — tam hikaye `HATA_GUNLUGU.md` H-07'de, özet:

1. **Kuantizasyon canlı yolda hiç uygulanmıyordu.** `RWR.update()`
   kuantize edilmiş `RWRContact` listesini doğru üretiyordu ama dönüş
   değeri `Engagement.update()` içinde hiçbir yere kaydedilmiyordu; smoke
   betiği bunun yerine `rwr._tracks[...].last_bearing` gibi ÖZEL bir alana
   erişip HAM (kuantize edilmemiş) açıyı okuyordu. Ölçülen fark: ham
   +10.26° vs kuantize olması gereken +15.00°. Bu, MSL kütlesi hatasıyla
   (RWR-01'in referans verdiği "canlı yola hiç ulaşmayan mekanizma" deseni)
   aynı aile: mekanizma doğru yazılmış ama gerçek tüketici ona hiç
   erişmiyor. **Düzeltme:** `RWR.contacts()` public okuyucusu eklendi,
   `RWR.update()` sonucunu kendi içinde önbelleğe alıyor; smoke betikleri
   artık SADECE bunu (veya `get_worst_threat()`'i) çağırıyor, özel alana
   dokunmuyor.
2. **Seviye hiçbir zaman düşmüyordu.** `feed_signal()` sadece YÜKSELTİYORDU
   (`hierarchy[kind] > hierarchy[current_kind]`); düşüş yolu hiç yazılmamıştı.
   Ölçüldü: "kilit" bir kez raporlanınca, sonrasında sadece "arama"
   beslense bile RWR sonsuza kadar "kilit" göstermeye devam ediyordu.
   **Düzeltme:** her seviye (arama/kilit/füze) artık KENDİ bağımsız
   yükselme (`rise_progress`) ve hafıza (`hold_timers`) sayacını tutuyor;
   raporlanan seviye, o an hâlâ "taze" (hold süresi dolmamış) olan en
   yüksek seviye. İzole test: "kilit" beslendikten sonra 2 s (`hold_s`)
   sadece "arama" beslenince doğru şekilde "arama"ya geriliyor.
3. **"arama" aşaması hiç beslenmiyordu.** `Engagement.update()`'teki
   kablolama sadece `contact.tracked` → "kilit" durumunu işliyordu;
   `contact.detected and not contact.tracked` → "arama" dalı hiç yoktu.
   Üç aşamalı zincir fiilen iki aşamaya inmişti, `detect_delay_s`'in
   gerekçesi (tarama sırasında yanlış alarmı önlemek) boşta duruyordu.
   **Düzeltme:** ayrım eklendi.

**Ders (H-07'nin özeti):** üçü de "kod çalışıyor GİBİ görünüyordu" —
46/46 test geçiyordu ve "atış görünmez" davranışı GERÇEKTEN doğruydu
(bu üç hatadan etkilenmeyen bir yol). Ama hiçbir test seviyenin
DÜŞTÜĞÜNÜ, kuantizasyonun CANLI YOLA ulaştığını, ya da "arama"nın hiç
üretildiğini kontrol etmiyordu — eksik yarısı hiç TETİKLENMEYEN bir
durum makinesi, çalışan bir durum makinesinden ayırt edilemez.

**Doğrulama (düzeltme sonrası):** izole testler (kuantizasyon, seviye
düşüşü, tam sessizlikte silinme) 3/3 geçti; gerçek 1v1 (`--warning rwr`,
varsayılan): kilit t=3.5s'de kuantize 0.0°, karşılıklı isabet t=61.2s
(truth moduna göre ~1 s'lik makul bir gecikme farkıyla — beklenen
gerileme). 2v2'ye de aynı `--warning truth|rwr` bayrağıyla bağlandı:
4 uçaklı gerçek koşu (RWR modu) sorunsuz, 3/4 uçak imha. `bvr/combat/tests`
46/46 etkilenmedi.

**Bilinen sınırlama (2v2, düzeltilmedi — RAD bölümündeki mevcut
sadeleştirmenin bir uzantısı):** `Engagement.update()`'in radar döngüsü
takım ayrımı yapmadığı için (bkz. SIM2-06 "Bilinen sadeleştirme"), bir
uçağın RWR'ı KENDİ KANAT UÇAĞININ radarından da "kilit" sinyali alabilir.
Radar için bu zararsızdı (ateş yetkisi zaten çapraz-takım kontrolüyle
sınırlı) ama RWR-güdümlü kaçışta, teorik olarak bir uçak kendi kanadını
tehdit sanıp gereksiz kaçabilir. Ölçülen 2v2 koşularında gözlenen bir
sonuç bozukluğu yok (angajmanlar normal şekilde sonuçlanıyor) ama bu,
gerçek bir IFF (dost/düşman) ayrımı eklenene kadar açık bir sınırlama
olarak not düşülüyor.

**`test_rwr.py` yazıldı — 12/12 geçiyor** (`bvr/combat/tests` toplamı artık
**58/58**). Öncelik listesindeki 8 madde + bağımsız incelemenin ikinci
turda istediği 2 ek test: detect_delay debounce, hold_s düşüşü (tam
sessizlik), **"kilit kesilip arama devam ederse seviyenin gerçekten
arama'ya düşmesi"** (H-07 Hata-2'nin asıl senaryosu — ilk testin
yakalamadığı, tam sessizlikten FARKLI), arama/kilit önceliği, yapısal
"range yok" kilidi, atış görünmezliği (en kritik), pitbull'da "fuze"
belirmesi, 2v2 koni testi, kendi radarımın kendi RWR'ımı tetiklememesi,
ve **smoke betiklerinin `_tracks` gibi özel bir alana asla erişmediğini**
doğrulayan yapısal (kaynak-tarama) bir test — Hata-1'in tek örneğini değil
SINIFINI kapatır. 2v2'nin gerçek smoke koşusuyla son doğrulaması
(`--warning rwr`) kullanıcı tarafından yapıldı.

**Mutasyon testiyle 2 ek boşluk bulundu (10/10 "geçiyor" yeterli
değilmiş).** Bağımsız bir inceleme, testler yeşilken KODU BİLEREK
BOZDU: (a) kuantizasyonu kapattı, (b) füzeyi pitbull yerine atış anından
besledi. **İkisi de 56/56'yı hiç etkilemedi.** Sebep: mevcut Engagement
testlerinin HEPSİ head-on (ham kerteriz=0°, kuantize edilse de edilmese
de 0 kalıyor) geometri kullanıyordu; "atış görünmez" testi de atıştan
sonra sadece TEK TİK ilerliyordu (`missile_detect_delay_s=0.5`'i aşacak
kadar değil). İki test eklendi: `test_10` (bilerek AÇILI bir geometri,
`RWR._quantize_bearing`'in KENDİ formülüyle hesaplanan beklenen değerle
canlı yoldan geleni karşılaştırır) ve `test_5b` (atıştan sonra 5 s boyunca
HER TİKTE "fuze" sızmadığını kontrol eder). Aynı iki mutasyon TEKRAR
uygulanıp bu sefer İKİSİNİN DE yakalandığı doğrulandı (dosyalar md5 ile
orijinaline geri yüklendi). `bvr/combat/tests` artık **58/58**. Genel ders
`HANDOFF.md` tuzak 51'e işlendi: "test geçiyor" güvence değildir, testi
bilerek bozup kırmızıya döndüğünü GÖRMEDEN bir şey sınadığı varsayılamaz.

### RWR-03 — `truth` ↔ `rwr` A/B'sinde tek koşuda sonuç değişti (anekdot, 2.2'yi doğrular)

Aynı 1v1 senaryosu, tek fark uyarı kaynağı: `--warning truth` (eski,
omniscient) blue'yu hayatta bıraktı, `--warning rwr` (gerçekçi) karşılıklı
imhayla sonuçlandı. Sebep izlendi: `truth` modunda kaçış t=2.4s'de (füze
atılır atılmaz) başlıyordu; `rwr` modunda kilit doğrulanana kadar
t=3.5s'ye erteleniyor. **1.1 saniyelik gecikme sonucu çevirdi.**

Bu, bilgi kısıtlamasının GERÇEKTEN taktik sonucu olduğunun bir kanıtı —
ama TEK koşu, TEK tohum. GUI-02'nin öğrettiği ders burada da geçerli:
"tek koşuda sonuç değişti" bir istatistik değil bir anekdot; sonucun ne
kadar bıçak sırtı (marjinal) olduğunu gösteriyor olabilir de, gerçek bir
etkiyi de gösteriyor olabilir — n=1 ile ayırt edilemez. Faz 2.2'nin
(n=200, bootstrap GA) var olma sebeplerinden biri tam olarak bu: bu
gözlemin gürültü mü gerçek etki mi olduğunu, `truth` ↔ `rwr` karşılaştırması
üzerinden ilk ölçeceği şey olacak.

---

## 12. Değerlendirme Düzeneği (EVAL) — Faz 2.2

### EVAL-01 — mimari: tek angajman kaynağı, rastgele senaryo, aynalama, CRN, McNemar/Wilson

**Ne işe yarıyor:** RWR-03'ün gösterdiği gibi tek bir angajmanın sonucu
anekdot — 1.1 saniyelik bir gecikme farkı sonucu çevirmişti. Bu düzenek
"hangi komutan/uyarı modu daha iyi" sorusunu güven aralığıyla cevaplıyor.
Faz 4'ün kabul ölçütü ("RL, betikli tabanı geçsin, güven aralıkları
örtüşmesin") aynı bu araçla ölçülecek.

**Mimari — tek kaynak.** `bvr_1v1_smoke.py`'nin angajman döngüsü
`bvr/combat/duel.py::run_duel()`'e taşındı; hem duman testi hem
değerlendirme aracı (`scripts/eval_commander.py`) onu çağırıyor —
`crank_sweep.py`'nin `pick_target`'ı kopyalamayıp import etme gerekçesiyle
aynı (iki kopya olursa biri düzelir diğeri unutulur, bu projede fiilen
iki kez oldu: füze kütlesi, RWR kablolaması). `scripts/crank_sweep.py` ve
`scripts/pursuit_cost.py`'nin `pick_target`/`CMD_MACH` import satırları da
yeni konuma (`bvr.combat.duel`) güncellendi.

**Rastgele senaryo:** `DuelScenario` — ayrım (25-40 nmi), açılı yaklaşım
(±60°), yanal ofset (±10 nmi), irtifa (her iki taraf BAĞIMSIZ, 15-35 kft),
Mach (0.75-0.95), yakıt (%50-100), türbülans (%30 olasılık, 0-60 fps).
Hepsi TEK bir tam sayı tohumdan `numpy.random.default_rng` ile SIRALI
üretiliyor — aynı tohum her zaman aynı senaryoyu (ve JSBSim seed'leri
sabit olduğu için aynı sonucu) üretir.

**Tekrar üretilebilirlik için düzeltilen eksik:** `Aircraft.__init__`
eskiden `seed=abs(hash(name)) % 1000` kullanıyordu — `hash()` Python
süreçler arası RASTGELE (hash randomization), yani "tekrar üretilebilir"
iddiası kağıt üzerindeydi. `duel.py::Aircraft` artık seed'i AÇIKÇA parametre
olarak alıyor, `run_duel()` bunu `scenario.seed`'den türetiyor
(`seed*2`/`seed*2+1`) — deterministik.

**Aynalama:** SIM2-08'de ölçülen "guidance be=0'da bile sağa yatık"
önyargısı rastgele senaryolara sistematik karışabilir. Her senaryo NORMAL
ve DOĞU-BATI AYNA görüntüsüyle (aspect/lateral/türbülans yönü işaret
değiştirir) olmak üzere iki kez koşulur — kendisiyle döven bir komutanın
POOLED (normal+ayna) kazanma oranı ~%50 olmalı.

**Ortak rastgele sayılar (CRN):** iki kol (`truth`↔`rwr`) AYNI senaryo
tohumunda koşturulur — aynı rüzgar, aynı geometri, tek fark komutan/uyarı
modu. Fark senaryo gürültüsüne karışmaz (guidance fazının "blok etkisi"
dersinin doğrudan karşılığı).

**İstatistik:**
- **Wilson skor aralığı** (kapalı form, bootstrap değil — hem daha doğru
  hem hesapsız) tek bir oran (kazanma oranı) için. Doğrulandı:
  `wilson_interval(100, 200)` → `[0.431, 0.568]`, yarı genişlik ≈0.069
  (beklenen ~%7 ile eşleşiyor).
- **McNemar kesin testi** (binom tabanlı) eşleşmiş A/B için — SADECE
  uyumsuz çiftler (bir kol kazandı diğeri kazanmadı) bilgi taşır.
  Doğrulandı: `mcnemar_p_value(10, 2)` → `p≈0.039` (bilinen referansla
  eşleşiyor), `mcnemar_p_value(5, 5)` → `p=1.0` (tam simetrik, beklenen).

**Paralelleştirme:** `multiprocessing.Pool`, model WORKER BAŞINA BİR KEZ
yüklenir (`_worker_init`), görev başına değil — tek bir angajmanın gerçek
maliyeti (~2.5-4 s, SB3+JSBSim başlatma dahil değil) ölçüldüğünde bunun
önemi netleşti. Yan fayda: her koşu ayrı süreçte olduğu için 1.5a'nın
"iki JSBSim örneği birbirine sızıyor mu" sorusu süreç izolasyonuyla
otomatik kapanıyor.

**Öz-denetim (`--self-check`, HIZLI, onay gerekmez) — 10 tohum × 2 (ayna)
× 2 (kol) = 40 koşu ile doğrulandı:**

| kontrol | sonuç |
|---|---|
| Tekrar üretilebilirlik (aynı tohum 2 kez) | ✅ birebir aynı |
| Ayna dengesi + kendine-karşı (pooled kazanma oranı) | ✅ 6/20=0.30, %95 GA [0.15,0.52] — 0.5 içeriyor (n=10 küçük, GA geniş) |
| Zaman aşımı oranı | ✅ %0 (senaryolar gerçekten sonuçlanıyor) |

**Bulunan bir gerçek tuzak (kendi mutasyonuyla yakalandı, düzeltildi):**
`DuelResult` düz bir `@dataclass` olduğu için otomatik `__eq__` TÜM
alanları karşılaştırır — `wall_time_s` (gerçek duvar-saati süresi) ASLA
iki koşuda aynı çıkmaz. İlk deneme `r1 == r2` şeklinde karşılaştırdı ve
**HER ZAMAN False döndü**, tekrar üretilebilirlik gerçekte sağlanmışken
bile. Düzeltme: karşılaştırmadan önce `dataclasses.replace(r, wall_time_s=0.0)`
ile bu alan sıfırlanıyor. Ders: bir sonuç nesnesine "bu koşuya özgü,
belirsiz" bir alan (performans ölçümü gibi) eklerken, o nesnenin eşitlik/
tekrar-üretilebilirlik testlerinde KULLANILMAYACAĞINI açıkça düşünmek
gerekir — otomatik `__eq__` bunu bilmez. `HATA_GUNLUGU.md` H-08.

**Kasıtlı olarak YAPILMAYAN (kapsam dışı, ileriki fazlar):** 2v2'nin
`duel.py`'ye taşınması (Faz 6, kol uçuşu); `bvr_2v2_smoke.py` hâlâ kendi
ayrı (kopya) angajman mantığını kullanıyor. Tam n=200 istatistiksel
karşılaştırma HENÜZ KOŞULMADI — kullanıcının "uzun koşu" onayını
bekliyor (bkz. STATUS.md).

---

## Doğrulama araçları

| Gereksinim grubu | Test |
|---|---|
| INN-01…09 | `scripts/test_inner_loop.py` (16 test) |
| MDL-01 | `scripts/collect_sysid.py` (kapsama raporu) |
| MDL-02…05 | `scripts/compare_models.py` |
| SAF, GUI, SYS-02/03 | `scripts/safety_eval.py -n 100` (bootstrap %95 GA) |
| SYS-04/05 | `scripts/reproduce.py` |
