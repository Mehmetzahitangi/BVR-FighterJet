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

---

## Doğrulama araçları

| Gereksinim grubu | Test |
|---|---|
| INN-01…09 | `scripts/test_inner_loop.py` (16 test) |
| MDL-01 | `scripts/collect_sysid.py` (kapsama raporu) |
| MDL-02…05 | `scripts/compare_models.py` |
| SAF, GUI, SYS-02/03 | `scripts/safety_eval.py -n 100` (bootstrap %95 GA) |
| SYS-04/05 | `scripts/reproduce.py` |
