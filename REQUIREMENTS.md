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

**2v2'nin `duel.py`'den ayrışmasını önleme (EVAL-01b).** `run_duel()`
tam iki uçağa sabit — 2v2'yi ona taşımak (4 uçaklı senaryo, takım sonucu,
kanat aynalaması) gerçek bir tasarım işi ve Faz 6'ya (kol uçuşu) ait; o
yüzden `run_duel()` 2v2'ye GENİŞLETİLMEDİ. Ama `bvr_2v2_smoke.py` daha
önce `pick_target`, `Aircraft` ve sabitlerin KENDİ KOPYASINI taşıyordu —
komutan/crank mantığı `duel.py`'de değişince 2v2 sessizce eski kalırdı
(HANDOFF tuzak 47/51'in "iki kopya" dersi). Bu yüzden 2v2 artık
`Aircraft`, `pick_target` ve sabitleri `bvr.combat.duel`'den IMPORT
ediyor (sadece paylaşılan parçalar; döngü hâlâ kendi içinde). Ek olarak
2v2'nin ölü/rastgele `seed=abs(hash(name))%1000`'i de temizlendi (artık
roster sırasından `seed=i`).

Doğrulama: refaktörden ÖNCE ve SONRA aynı 2v2 koşusu (180 s, RWR modu)
`diff` ile karşılaştırıldı — **42 olayın hepsi satır satır birebir aynı**
(3/4 uçak imha). Koruma: `bvr/combat/tests/test_duel.py::test_7` 1v1 ve
2v2 betiklerinin kaynağını tarayıp `def pick_target`, `class Aircraft`
ve `abs(hash(` desenlerinin GERİ GELMEDİĞİNİ kilitliyor; tuzak 51
disiplini gereği bilerek bozularak sınandı (kopyayı geri getirmek de,
`hash()` tohumunu geri getirmek de testi kırdı; dosya md5 ile geri
yüklendi). `test_duel.py` 8/8, `bvr/combat/tests` toplamı **66/66**.

Not (dürüst): ilk yazımda test_3 (ayna iki kez uygulanınca orijinale
döner) `==` kullandığı için düştü — `(360-(360-x)%360)%360` son basamakta
1 ulp fark bırakıyor (mantık hatası değil, kayan nokta); test yaklaşık
eşitliğe çevrildi. test_7 de ilk halinde 2v2'ye yazdığım AÇIKLAMA
yorumundaki "hash(name)" metnine takıldı; gerçek kullanımı (`abs(hash(`)
arayacak şekilde daraltıldı.

### EVAL-02 — ilk tam koşu (n=200, 800 savaş) ve bulduğu üç ÖLÇÜM ARACI hatası

**Koşu:** `eval_commander --n 200 --workers 22`, 800 savaş, **259 s**
(kullanıcı "başlat" dedikten sonra). Ham sonuç `runs/eval_truth_vs_rwr.csv`.

| kol | kazanma (mavi) | %95 GA | sonuç dağılımı |
|---|---|---|---|
| `truth` | 0.388 | [0.341, 0.436] | muhimmatsiz 178, galibiyet 155, mağlubiyet 65, karşılıklı 2 |
| `rwr` | 0.367 | [0.322, 0.416] | muhimmatsiz 193, galibiyet 147, mağlubiyet 60 |

McNemar (400 eşleşmiş senaryo-örneği): sadece-truth-kazandı **13**,
sadece-rwr-kazandı **5**, uyumlu 382 → **p = 0.096** (5% eşiğinde anlamlı
DEĞİL). Yorum (ihtiyatlı): RWR-03'ün n=1 anekdotu (1.1 s gecikme sonucu
çevirdi) gerçekti ama NADİR — senaryoların yalnızca %4.5'inde (18/400) mavinin
galibiyet durumu iki mod arasında değişti; yön `truth` lehine (13:5) ama bu
örneklemle gürültüden ayırt edilemiyor. Keşifsel (önceden kayıtlı değil):
karar verilen savaş sayısı 222→207.

**⚠️ Bu sayılar NİHAİ DEĞİL — aşağıdaki üç hata sonradan bulundu.** Aynı
CSV'yi yorumlamaya çalışırken şunlar fark edildi:

1. **Koltuk önyargısı (en önemlisi).** Aynı model iki tarafta oynadığı halde
   mavi karar verilen angajmanların **%70'ini** kazandı (155:65, truth;
   147:60, rwr). Sebep: spesifikasyondaki "yalnızca KIRMIZININ yönü ±60°
   rastgele" tasarımı taraf-simetrik değildi — mavi her zaman burnu rakibe
   dönük başlıyordu (ort. başlangıç |ATA| **8.6°**), kırmızı ±60° (ort.
   **30.3°**). Mavinin galibiyet payı bu farkla monoton artıyordu:
   (kırmızı_ATA − mavi_ATA) < 10° → 0.55, 10–30° → 0.69, 30–50° → 0.90.
   Doğu-batı aynası bunu düzeltmiyor (normal 0.70 / ayna 0.71) çünkü sol/sağ
   önyargısını dengeler, mavi/kırmızı koltuğunu değil. **Düzeltme:**
   `DuelScenario.blue_offset_deg` eklendi, mavinin yönü kırmızıyla AYNI
   dağılımdan çekiliyor; ayna bunu da çeviriyor (`blue_offset_deg` `generate_
   scenario`'da EN SONA çizildi, eski tohumların diğer parametreleri
   değişmedi). Düzeltme sonrası başlangıç |ATA|: mavi 30.9°, kırmızı 30.7°.
2. **`nz_min` işareti yanlıştı.** Bu projede düz uçuşta `st.nz ≈ −1`
   (HANDOFF tuzak 5); ilk `duel.py` ham değerin minimumunu aldı — yani
   rapordaki **−8.08** aslında **+8.08 g ÇEKİŞ**ti, izleme listesindeki
   *negatif-g* eşiğiyle (−4.8 g) ilgisi yoktu (kanıt: 800 satırın hepsi
   negatif, en büyüğü −1.47). **Düzeltme:** `g = −st.nz`; `nz_min` (negatif-g
   yönü) ve yeni `nz_max` (tepe çekiş) ayrı izleniyor. Doğrulama: sabit
   smoke senaryosunda `nz_min=−0.47`, `nz_max=+4.52` (eski ham −4.52 ile
   tutarlı).
3. **Öz-denetim kriterim kusurluydu.** "Tüm koşuların kazanma oranı %50'yi
   içermeli" beraberlikleri (%45) hesaba katmıyor — n=400'de sırf bu yüzden
   düşerdi, n=10'da ise GA geniş olduğu için sorun görünmedi. Yerine:
   (a) **geometri simetri kontrolü** (5000 tohum, simülasyonsuz, anlık,
   KESKİN — bu ilk gün olsaydı hatayı koşu yapmadan yakalardı) ve (b)
   **karar verilenlerde mavi payı** (beraberlikler hariç, Wilson GA).
   Ayrıca tam koşu raporuna yerleşik bir "koltuk dengesi" uyarısı eklendi:
   GA 0.5'i içermiyorsa "ÖLÇÜM ARACI TARAF TUTUYOR, sonuçlara güvenme" basıyor.

Küçük düzeltme: "atış/isabet" her savaşın oranının ortalamasıydı
(isabetsiz savaşlar şişiriyordu, 6.3); artık toplam atış / toplam isabet.

**Testler:** `test_duel.py` 11/11 (`bvr/combat/tests` toplamı **69/69**):
`test_9` (koltuk simetrisi, geometri), `test_9b` (ayna başlangıç açı
büyüklüklerini korur), `test_10` (çizim sırası eski tohumları bozmaz). Tuzak
51 gereği üçü de bilerek bozularak sınandı — (A) mavinin yönünü tekrar 0
yapmak, (B) `mirror_scenario`'nun `blue_offset_deg`'i çevirmeyi unutması,
(C) yeni çizimi başa/araya sokmak — her mutasyon KENDİ testini kırdı, dosya
md5 ile geri yüklendi.

**Sonraki adım:** düzeltilmiş araçla tam koşunun YENİDEN yapılması
(~4.5 dk). Yeni tohum→senaryo eşlemesi farklı olduğu için (mavinin yönü
artık rastgele) yukarıdaki sayılarla doğrudan karşılaştırılamaz.

---

## Doğrulama araçları

| Gereksinim grubu | Test |
|---|---|
| INN-01…09 | `scripts/test_inner_loop.py` (16 test) |
| MDL-01 | `scripts/collect_sysid.py` (kapsama raporu) |
| MDL-02…05 | `scripts/compare_models.py` |
| SAF, GUI, SYS-02/03 | `scripts/safety_eval.py -n 100` (bootstrap %95 GA) |
| SYS-04/05 | `scripts/reproduce.py` |


### EVAL-03 — Düzeltilmiş araçla ilk GEÇERLİ tam koşu: truth vs rwr (2026-09-19)

`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --n 200 --workers 22 --csv runs/eval_truth_vs_rwr_v2.csv`
(800 savaş, 264.8 s; ham veri `runs/eval_truth_vs_rwr_v2.csv`, günlük `.log`).
**Not:** `warning_mode` HER İKİ tarafa birden uygulanır ("iki taraf omniscient"
vs "iki taraf RWR"); "mavi RWR'lı, kırmızı değil" karşılaştırması DEĞİL.

| kol | kazanma (mavi galibiyet) | %95 Wilson | kör | hedefsiz | atış/isabet | koltuk (mavi payı) |
|---|---|---|---|---|---|---|
| truth | 0.253 (101/400) | [0.212, 0.297] | 0.18 | 0.43 | 13.0 | 0.49 [0.42, 0.56] OK |
| rwr | 0.223 (89/400) | [0.184, 0.266] | 0.23 | 0.35 | 15.4 | 0.50 [0.43, 0.57] OK |

Sonuç dağılımı truth: mühimmatsız 193 / galibiyet 101 / mağlubiyet 105 /
karşılıklı imha 1; rwr: 222 / 89 / 89 / 0. nz: en kötü negatif-g −3.38
(eşik −4.8, iki kolda aynı), tepe +7.49 g.

**McNemar (400 çift):** yalnız-truth 19, yalnız-rwr 7, uyumlu 374, p=0.029.
**Bağımsızlık kontrolü:** aynı tohumun iki aynası ilişkili olabilir; tohum
başına kümelenince (200 tohum) 18:6, p=0.023 — sonuç değişmedi. İki aynası
birden uyumsuz olan tohum 2/24 (küme etkisi zayıf).

**Yorum (temkinli):**
- Araç artık simetrik: koltuk payı ~0.50 (ilk koşuda 0.70'ti). EVAL-02'nin
  düzeltmeleri çalıştı.
- RWR, kazanma oranını ~3 puan düşürüyor (0.253→0.223) ve fark anlamlı
  (p≈0.03) ama 400 çiftin yalnız 26'sı uyumsuz → etki KÜÇÜK, GA'lar örtüşüyor.
- Mekanizma: uyumsuz çiftlerin 20/26'sı galibiyet↔mühimmatsız; galibiyet↔
  mağlubiyet yalnız 5. Yani RWR "daha çok kaybettirmiyor", füzelerin
  isabete dönüşmesini azaltıyor (kör %18→23, isabet başına atış 13→15.4).
  İki taraf da aynı gecikmeli uyarıyı kullandığı için galibiyet VE mağlubiyet
  birlikte düşüyor (101/105 → 89/89).
- ~%50'si (193/222 of 400) sonuçsuz bitiyor (mühimmat tükendi, kimse
  vurulmadı): sabit 30° crank + betikli komutanla füze verimi düşük. Bu,
  Faz 2.3'ün (geri beslemeli crank) ve Faz 3'ün asıl iyileştirme alanı.
- Sınır: tek model, tek crank (30°), tek senaryo dağılımı; "RWR gecikmesi
  savaşı kötüleştirir" genellemesi yapılmaz. RWR-03'ün n=1 anekdotu artık
  istatistikle destekleniyor ama etki küçük.


### EVAL-03b — Bağımsız inceleme: doğrulama, eklemeler, ertelenenler (2026-09-19)

Bağımsız bir inceleme EVAL-03 sonuçlarını yorumladı. Sayıları CSV'den
(`runs/eval_truth_vs_rwr_v2.csv`) yeniden ürettim — HEPSİ tuttu:

| iddia | doğrulama |
|---|---|
| atış 2695/2744, isabet 208/178 (%7.7/%6.5) | ✅ birebir |
| `tukenme` 1865/1998 (%69/%73), kör %2.7/%3.3, hedefsiz %6.4/%5.1 | ✅ (PAYDA füze sayısı; EVAL-03 tablosundaki kör 0.18/0.23 ve hedefsiz 0.43/0.35 SAVAŞ başına ortalamadır — aynı veri, farklı payda) |
| başlangıç ayrımına göre ≥1 isabet: %80 / %38 / %19 | ✅ (rwr kolu, n=130/122/148) |
| süre ort. ~86 s, en uzun 147 s, tavana dayanan yok | ✅ (truth 86.6/147.2, rwr 86.3/143.3) |
| nz_min<−3 g: 5 koşu; en kötü −3.38 | ✅ |
| `iska` = 0 | ✅ (aşağıda) |
| süre: koşu başına 5.9 s, toplam 78.7 dk CPU | ✅ (39.2 + 39.5 dk) |

**Yapılan eklemeler:**
1. **Kümelenmiş eşleşmiş test ASIL KARAR oldu** (`compare_arms_clustered`).
   Bir senaryonun normal ve aynalı koşusu bağımsız değil; 2n çift yerine n
   senaryo tek gözlem (senaryonun kollardaki galibiyet SAYISI kıyaslanır,
   eşitler uyumlu). Sonuç: 18:6, p=0.023 (koşu düzeyi 19:7, p=0.029 —
   yalnız bilgi olarak basılıyor). Karar değişmedi ama artık araç bunu
   kendisi söylüyor. Yan not: Wilson GA'ları da koşuları bağımsız sayar
   (hafif dar) — rapora not düşüldü; kümelenmiş GA ERTELENDİ.
2. **`iska` zinciri kanıtlandı** (`test_engagement.py::test_10`). Missile
   seviyesinde `iska` zaten vardı (`test_9b`); eksik halka Missile →
   CombatEvent → hedef hayatta idi. Öldürme yarıçapı 2 ft yapılan enerjili
   bir füze (~8 ft ıska, t≈14.7 s'de hedefe VARIYOR) `iska` olayı üretiyor,
   hedef hayatta, `tukenme` yok. Yani `iska=0` "raporlanmıyor" değil —
   bkz. HATA_GUNLUGU H-10.
3. **CSV artık 16 senaryo sütunu içeriyor** (`scn_separation_nm`,
   `scn_aspect_deg`, `scn_blue_offset_deg`, alt/Mach/yakıt/türbülans,
   `scn_initial_ata_blue/red_deg`) — analizde yeniden üretmek gerekmiyor.
   Testler: `test_eval_stats.py` (6 test: Wilson/McNemar bilinen değerler,
   kümeleme, eşit sayım, farklı tohum kümesi reddi, CSV ayna). 5 mutasyon
   (kümeleme kaldır, eşitlik `>=`, CSV aynasız, engagement `iska`→`kor`,
   missile hep `isabet`) HEPSİ yakalandı, md5 geri yüklendi. Toplam **76/76**.

**Asıl bulgu — atış disiplini (Faz 2.3'ün 1. maddesi).** Füzelerin ~%70-73'ü
hedefe varmadan enerjisini tüketiyor; ≥1 isabet oranı başlangıç ayrımıyla
tek yönlü düşüyor (%80→%38→%19). Betikli komutan `can_fire` olur olmaz
(`max_launch_nm=35`) ateş ediyor — 35 nmi'de füze kinematik olarak
yetişemiyor, 4 füze boşa gidiyor, savaş "iki taraf mühimmatsız" bitiyor.
**Dikkat — bu şimdilik GÖZLEMSEL:** ayrım ilk atış menzilinin vekili
(ayrım<35 ise ilk atış başlangıç ayrımında, >35 ise 35 nmi'de), aspect ve
diğer parametrelerle karışık olabilir. Nedensel test = müdahale: atış
kapısını 35 → ~25–30 nmi'ye çek, AYNI 400 senaryoda karşılaştır.
**Önceden yazılmış tahmin (sonuçtan ÖNCE kayda geçti):** atış başına isabet
birkaç kat artar, `muhimmatsiz` oranı belirgin düşer. Tutmazsa (ör. isabet
artar ama kazanma artmaz, ya da kapı çok geç ateşe sokup kaybettirir) bu
da bulgudur. Ölçüm için `run_duel`'a `max_launch_nm` parametresi + eval
CLI bayrağı gerekir (varsayılan = bugünkü davranış, birebir) — kullanıcı
"başlat" deyince kol başına ~2 dk.

**Ertelenen küçük notlar:** (a) İrtifa/Mach/yakıt taraf başına bağımsız
çekiliyor, ayna bunları taşımıyor → ayna sağ/sol önyargısını dengeliyor,
"koltuk avantajını" değil; koltuk dengesi testi geçtiği için sorun yok,
ileride mavi/kırmızı parametre TAKASI ikinci eşleştirme ekseni olabilir.
(b) Kümelenmiş Wilson/bootstrap GA.


### EVAL-04 — Faz 2.3 ÖN ÖLÇÜMÜ: atış kapısı deneyi (tasarım, KOŞU ÖNCESİ kilitlendi)

**Ne yapıyoruz:** Betikli komutan `can_fire` izin verir vermez (yani 35 nmi
Rmax'ta) ateş ediyor; füzelerin ~%70-73'ü hedefe varmadan enerjisini
tüketiyor (EVAL-03b). Deney: komutana "yetki var ama menzil çok uzun, bekle"
diyen bir **atış kapısı** ekleyip bunun gerçekten daha iyi savaş verdirip
vermediğini ölçmek. Bu, Faz 2.3 davranış ağacının ilk düğümü olacak.

**Tasarım (bağımsız incelemeyle kilitlendi):**

| kol | mavi kapı | kırmızı kapı |
|---|---|---|
| A (referans) | yok (35) | yok (35) |
| **B (karar koşusu)** | **25 nmi** | yok (35) |

- **Kapı ASİMETRİK.** İki tarafa birden uygulanırsa iki komutan da aynı anda
  iyileşir; kazanma oranı kapının ÜSTÜNLÜĞÜNÜ göstermez. (İncelemedeki "%50'de
  kalır" ifadesi gevşek: sonuçsuz biten savaşların ~yarısı karara döneceği
  için mavi kazanma oranı YÜKSELİR ama bu üstünlük değil verimlilik işareti —
  yine de "kapı kazandırıyor mu?" sorusunu cevaplamaz.)
- **Birincil ölçüt:** mavi kazanma oranı, A ile B arasında, senaryo düzeyinde
  kümelenmiş eşleşmiş test (EVAL-03b), iki yönlü, α=0.05. Hipotez: B > A.
- **İkincil (mekanizma, AYNI savaşlar içinde mavi↔kırmızı):** atış başına
  isabet, ilk atış menzili, `muhimmatsiz` payı.
- **Birincil kapı değeri ÖNCEDEN SABİT: 25 nmi** (`PRIMARY_GATE_NM`). Başka
  değer (`--gate-nm 30`) KEŞİF sayılır; araç bunu çıktıda işaretler. Birden
  çok değeri deneyip en iyisini raporlamak p-değerini sessizce şişirir.
- **A kolu YENİDEN koşulur** (v2 satırları kullanılmaz): aradan kod/CSV/istatistik
  değişiklikleri geçti; ~2 dk'lık koşu "farklı sürümle karşılaştırma" şüphesini
  tamamen kaldırır.
- **Koltuk dengesi:** A kolunda ~0.5 beklenir (simetrik). B kolu ASİMETRİK
  işaretlenir (`ArmSpec.symmetric`); rapor 0.5 beklemez ve "mavi payının
  yükselmesi kapının etkisidir, ölçüm önyargısı değil" der. Yoksa kendi
  uyarımız bizi yanlış yönlendirirdi.
- **Salvo politikası KARIŞTIRILMAZ.** `max_per_target=2` (hemen iki füze)
  değişmiyor. Sıra: önce kapı, sonra ayrı deney olarak shoot-look-shoot.

**Önceden yazılmış tahmin (sonuçtan ÖNCE):**
1. B'de mavinin atış başına isabeti kırmızınınkinin en az ~2 katı (aynı
   savaşlar içinde, kırmızı 35 nmi'den atmaya devam ediyor).
2. Mavi kazanma oranı A'dan anlamlı yüksek (p<0.05, kümelenmiş).
3. `muhimmatsiz` payı düşer (A'da 222/400).
**Çürütme koşulları (bunlar da bulgudur):** isabet artar ama kazanma
artmazsa → kapı verimi düzeltiyor ama geç atış savunmada bedel ödetiyor
(kırmızının erken füzeleri maviyi kaçışa zorluyor); isabet de artmazsa →
"mesafeden enerji kaybı" açıklaması yetersiz, başka mekanizma aranır
(ör. crank sırasında kilit kaybı, EVAL-03b'deki gözlemsel bağımlılık
başka bir değişkenle karışık). Beklenmedik yön (B < A) ayrıca raporlanır.

**Uygulama (yer seçimi bilinçli):** kapı `Engagement`/`LaunchRules`'ta DEĞİL,
`run_duel` döngüsünde (`fire_gate_nm_blue/red`, varsayılan None = eski davranış
birebir). `LaunchRules` atış YETKİSİDİR; "ne zaman atarım" komutanın kararıdır
ve Faz 3'te PPO'nun "ateş" aksiyonu da `can_fire` yetkisinin ÜSTÜNDE oturacak.
`engagement.py` hiç değişmedi. `DuelResult` 4 yeni alan: kapı değerleri +
ilk atış menzilleri (varsayılan None; CSV kendi kendini açıklar). Eval:
`ArmSpec` (kol = uyarı modu + taraf-bazlı kapı), `--experiment warning|gate`,
`--gate-nm`, CSV'ye `arm` sütunu, `side_efficiency` (pooled, taraf bazlı).

**Doğrulama (koşudan ÖNCE):**
- Regresyon: kapısız `run_duel`, v2 CSV'deki 3 farklı senaryoyu (normal +
  ayna) tüm sonuç alanlarında BİREBİR yeniden üretti.
- Davranış: 30 nmi kafa kafaya senaryoda mavinin ilk atışı 29.25 → 24.99 nmi;
  kırmızınınki 29.25'te DEĞİŞMEDİ; 35/35 kapısı kapısızla özdeş.
- `test_duel_gate.py` 6 test (simülasyonlular model yoksa atlanır). 6 mutasyon
  (kapı hiç yok / rakibin kapısı / ters yön / B simetrik / worker kapıyı
  düşürüyor / birincil değer 25→30) HEPSİ yakalandı, md5 geri yüklendi.
  Toplam **82/82**.
- Bilinen kısıt: füze sonlanma nedenleri (`tukenme` vb.) taraf bazında
  kaydedilmiyor; mekanizma analizi atış-başına-isabet ve ilk atış menziliyle
  yapılır. Not: `runs/eval_truth_vs_rwr_v2.csv` `scn_*` sütunlarından ÖNCE
  üretildi (0 adet) — yalnız yeni koşular bu sütunları taşır.

**Koşu (kullanıcı "başlat" deyince, önce kod incelemesi):**
`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment gate --n 200 --workers 22 --csv runs/eval_gate_25v35.csv`
(800 savaş, ~4.5 dk; A ve B kolu aynı koşuda, aynı kod sürümüyle).


**EVAL-04 eki (kod incelemesinden, koşu ÖNCESİ):**
1. **Kapının kaç senaryoda bağladığı raporlanıyor.** Ayrım 25–40 nmi'den
   çekildiği için 25 nmi kapısı bazı senaryolarda hiçbir şey yapmaz; N/n
   bilinmeden 200 üzerinden hesaplanan fark SEYRELMİŞ olabilir. `DuelResult`'a
   `gate_blocked_ticks_blue/red` (yetki VAR ama komutan bekledi: kaç tik) eklendi;
   rapor "kapı N/n savaşta BAĞLADI" ve "kapının bağladığı senaryolar"
   üzerinde ayrı bir kümelenmiş karşılaştırma (İKİNCİL/KEŞİF — "bağladı" koşul-sonrası
   bir değişken, kilit zamanlamasına/yörüngeye bağlı; birincil karar DEĞİL,
   yalnız etki büyüklüğünü yorumlamak için) basıyor.
2. **"Hiç atamadan öldü" sayacı.** Kapının asıl riski beklerken vurulmak. Rapor,
   atamadan ölenleri "kapı bağlıyken" (kapı yüzünden geç kalma ADAYI) ve "kapıdan
   bağımsız" (ör. kilit hiç kurulmadı) diye ayırıyor; kırmızı için de aynı sayaç
   (kapısız taraf = temel oran). "Aday" çünkü kapının bağlaması ölümün nedeni
   olduğunu KANITLAMAZ — yalnızca kapıdan bağımsız açıklamaları ayıklar.
3. **Test hijyeni:** depo kökünde `pytest.ini` yoktu; eklendi
   (`pythonpath = .`, `testpaths = bvr`, osqp'nin iki bilinen kullanım-dışı
   uyarısı YALNIZ `osqp.interface` modülünden süzülür). Gerçek düello testleri
   7400+ uyarı basıyordu, yeni ve gerçek bir uyarı o yığında kaybolurdu. Filtrenin
   gövde filtresi olmadığı doğrulandı: aynı mesaj başka modülden gelirse ve yeni
   bir `UserWarning` görünmeye devam ediyor.
4. **Testler/mutasyon:** `test_duel_gate.py` 8 test. Sayaçlar için 5 mutasyon:
   tik sayacı artmıyor, "atamadan öldü" `fired==0` şartı düşürülmüş, kapı-bağlı
   ayrımı bozuk, bağlama kümesi kırmızıyı yok sayıyor — 4'ü ilk denemede
   yakalandı; **5.si (kırmızı sayacı maviye yazılıyor) İLK DENEMEDE HAYATTA KALDI**
   çünkü `test_5` kırmızı kapıyı sınıyor ama sayaçlara bakmıyordu. Sayaç iddiası
   `test_5`'e eklendi, mutasyon artık yakalanıyor. Toplam **84/84**.


### EVAL-05 — Atış kapısı deneyi SONUCU: önceden yazılmış tahmin ÇÜRÜTÜLDÜ (2026-09-20)

`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment gate --n 200 --workers 22 --csv runs/eval_gate_25v35.csv`
(800 savaş, 289 s; veri `runs/eval_gate_25v35.csv` — ilk kez 16 `scn_*` sütunu +
`arm` + kapı alanları dahil; günlük `.log`).

| | A (35v35) | B (mavi 25 / kırmızı 35) |
|---|---|---|
| mavi galibiyet | 89 (0.223 [0.184, 0.266]) | 91 (0.228 [0.189, 0.271]) |
| mavi mağlubiyet | 89 | **120** |
| mühimmatsız (sonuçsuz) | 222 | 189 |
| mavi atış başına isabet | %6.5 (89/1379) | **%6.6** (91/1373) |
| kırmızı atış başına isabet | %6.5 (89/1365) | **%8.7** (120/1375) |
| mavi ilk atış menzili (ort.) | 31.7 nmi | 25.0 nmi |
| kapı bağladı | 0/400 | mavi **392/400** savaş (196/200 senaryo, %98) |
| atamadan ölen mavi | 0 | 0 |

**Geçerlilik kontrolleri:** A kolu, EVAL-03'ün `rwr` koluyla 400 savaşın
400'ünde birebir aynı (kod kayması yok). Kapı senaryoların %98'inde bağladı →
sonuç SEYRELMEDİ; "kapı etkisiz kaldı" açıklaması dışlandı.

**Önceden yazılmış tahminler (EVAL-04) — karar:**
| tahmin | sonuç |
|---|---|
| 1. mavi atış başına isabeti kırmızınınkinin ≥~2 katı | ❌ ÇÜRÜTÜLDÜ: %6.6 vs %8.7 (mavi daha DÜŞÜK) |
| 2. mavi kazanma A'dan anlamlı yüksek (p<0.05) | ❌ ÇÜRÜTÜLDÜ: senaryo-kümelenmiş 31:33, **p=0.90** |
| 3. mühimmatsız payı düşer | ⚠️ sayısal olarak evet (222→189), ama yanlış nedenle (aşağıda) |

**Asıl bulgu — "beklerken vurulma" riski GERÇEKLEŞTİ, ama atamadan ölme
biçiminde değil.** Mavi hiç atamadan ölmedi (0), yine de kaybı arttı: A→B
geçişleri: 45 mühimmatsız→galibiyet, 30 galibiyet→**mağlubiyet**, 14
galibiyet→mühimmatsız, 2 mühimmatsız→mağlubiyet, 1 mağlubiyet→galibiyet.
Senaryo düzeyinde mavi kaybı: B'de daha çok olan 25, A'da daha çok olan 1
(p<1e-5; POST-HOC analiz, birincil ölçüt değil — ama etki çok büyük). Kayıp
artışı yakın başlangıç ayrımlarında daha belirgin (<30 nmi: 48→70). Mavinin
B'deki galibiyetleri geç geliyor (ilk isabet ort. 107 s vs A'da 68 s).

**Gözlemsel iddia (EVAL-03b) YENİ sütunlarla doğrulandı ama nedensel çıkmadı.**
A kolunda taraf başına atış-başına-isabet, ilk atış menziline göre: <27 nmi
%17.8, 27–30 %12.3, 30–33 %6.1, ≥33 **%2.8** — ilişki gerçek ve güçlü. Ama
menzili müdahaleyle 25'e çekince mavinin isabeti DEĞİŞMEDİ (%6.5→%6.6).
Demek ki menzil–isabet ilişkisi ya (a) senaryo geometrisiyle karışıktı (yakın
başlayan senaryolar başka bakımlardan da kolay), ya da (b) menzil tek başına
belirleyici değil, aşağıdaki eşleşmeyle iç içe.

**Hipotez (KANITLANMADI, sınanabilir): atış zamanlaması ile kaçış birbirine
bağlı.** A'da iki taraf aynı anda ~31.7 nmi'de atıyor → ikisi de RWR'dan füze
uyarısı alıp kaçışa (crank, SIM2-07) geçiyor → ikisi de KENDİ füzesinin kilidini
sarsıyor ("karşılıklı caydırma"). B'de mavi ~20 s geç atıyor → kırmızı erken
kaçışa zorlanmıyor → kırmızının füzeleri sonuna kadar güdülüyor (kırmızı
isabeti %6.5→%8.7, 89→120 isabet). Yani kapıyı BİR tarafa vermek, o tarafı
rakibin ilk-atış avantajına açıyor. Bu, HATA_GUNLUGU H-05'teki "kaçış
kendi füzeni köreltir" bulgusunun kill-chain düzeyindeki yansıması olabilir.
**Şu anki veriyle AYIRT EDİLEMEZ:** füze sonlanma nedenleri (`kor`, `hedefsiz`,
`tukenme`) taraf bazında kaydedilmiyor.

**Sonuç ve tasarım etkisi (Faz 2.3):** "Ne zaman atarım" kararı yerel bir
menzil eşiği değil; rakibin uyarı/kaçış davranışıyla bağlı. Bu, tez için asıl
değerli çıkarım: RL komutanın öğrenmesi gereken şey tam olarak bu eşleşme.
Kapıyı olduğu gibi (25 nmi, tek taraflı) davranış ağacına KOYMA.

**Sıradaki iki adım (kullanıcı onayına bağlı, sıra önemli):**
1. `DuelResult`'a füze sonlanma sayılarını TARAF bazında ekle (`kor/hedefsiz/
   tukenme/iska`, mavi/kırmızı) — hipotezi ayırt etmenin ön koşulu; küçük,
   mutasyonla sınanır, koşu gerektirmez.
2. Yeni, önceden-yazılmış deney: SİMETRİK kapı (C = 25v25) vs A. Zamanlama
   asimetrisini ortadan kaldırıp "menzil tek başına isabeti artırıyor mu?"
   sorusunu temiz sorar. Bu, yeni bir birincil hipotez (EVAL-05'in sonucundan
   doğdu, aynı verinin ikinci bakışı DEĞİL) — kendi tahminiyle koşulur.
   Simetrik kolda koltuk dengesi ~0.5 yeniden BEKLENİR (`ArmSpec.symmetric`).


### EVAL-06 — Simetrik atış kapısı deneyi (tasarım, KOŞU ÖNCESİ kilitlendi)

**Adım 1 tamam — füze sonlanma nedenleri artık TARAF bazında.** EVAL-05'in
hipotezi ("kaçış rakibin KENDİ füzesini körletir") o gün ayırt edilemedi çünkü
`kor/hedefsiz/iska/tukenme` yalnızca toplam tutuluyordu. `DuelResult`'a 8 alan
eklendi (`blue_/red_ × kor/hedefsiz/iska/tukenme`, ATAN tarafa göre; toplamları
eski toplam alanlara eşit). Sayım saf bir fonksiyona (`tally_missile_end`)
çıkarıldı ki atıf simülasyonsuz sınansın; rapor artık her kolda
"füze sonu (mavi/kırmızı): isabet / kör / hedefsiz / tükenme / ıska /
havada-kaldı" satırlarını basıyor. Regresyon: eski alanlar EVAL-05'in A kolu
satırlarıyla 9 savaşta birebir aynı, taraf toplamı = eski toplam.
`test_duel_side_counts.py` 4 test; 6 mutasyon (rakibe atıf, toplam artmıyor,
hep maviye, isabet de sayılıyor, dönüşte kırmızı→mavi, havada-kaldı hesabı)
HEPSİ yakalandı, md5 geri yüklendi.

**Adım 2 — deney: A (35v35) vs C (İKİ taraf da 25 nmi).** Zamanlama
asimetrisini kaldırır; "menzil TEK BAŞINA isabeti artırıyor mu?" sorusunu
temiz sorar (EVAL-05'te B kolunda mavi geç atınca kırmızının isabeti %6.5→%8.7
çıkmıştı; simetrik kolda bu bozucu yok). Yeni bir birincil hipotez, EVAL-05
sonucundan doğdu — bu yüzden:
- **TAZE tohumlar (2000–2199).** Aynı 200 senaryoyla koşmak, aynı veriye ikinci
  kez bakmak (çift-dalış) olurdu. Araç `SEEN_SEEDS` (1000–1199) ile çakışırsa
  uyarır. A kolu da taze tohumlarla YENİDEN koşulur.
- **Birincil ölçüt** (kazanma oranı DEĞİL — simetrik kolda ~0.5'te kalır ve
  bilgisizdir): senaryo başına TOPLAM İSABET (mavi+kırmızı, ayna dahil),
  senaryo düzeyinde kümelenmiş işaret testi, iki yönlü, α=0.05.
- **İkincil:** atış başına isabet (pooled), sonuçsuz savaş sayısı, taraf
  bazlı füze sonları (kör/tükenme/hedefsiz), koltuk dengesi (simetrik → ~0.5
  BEKLENİR, uyarı devrede), mavi kazanma (beklenti: fark yok).
- **Birincil kapı değeri 25 nmi** (önceden sabit; başka değer KEŞİF).

**Önceden yazılmış tahminler (sonuçtan ÖNCE) ve yorum tablosu:**

| C sonucu (birincil: toplam isabet) | kanıtladığı | sonraki adım |
|---|---|---|
| **Anlamlı ARTAR** (atış başına isabet ≳ 8.5%, ≥ ~1.3×) | Menzil, zamanlama simetrikken gerçekten işe yarıyor → B'nin başarısızlığı **atış-kaçış eşleşmesi/asimetri bedeli** | Komutanın atış kararı rakibin durumuna (füzesi havada mı, uyarıdayım mı) bağlı olmalı; kapıyı koşullu dene |
| **Değişmez** (±1 puan, anlamsız) | Menzil kaldıraç DEĞİL; A'daki %17.8→%2.8 eğimi senaryo geometrisiyle karışıktı | Menzil kapısını bırak; salvo politikası (shoot-look-shoot) ve crank/kaçış tasarımına geç |
| **Anlamlı AZALIR** | Yakından atış daha kötü (ör. kör kalma/kaçınma süresi kısalıyor) | Neden için taraf-bazlı füze sonlarına bak |

Kendi tahminim (kayıtta): **modest artış, atış başına isabet ~%8–10, ~%55
güvenle** — yani eşleşme hipotezi. Bunu kanıt saymıyorum; tablo hangi sonucun
neyi çürüttüğünü önceden bağlıyor.

**Bir uyarı (mekanizma için):** EVAL-05'teki `kor` toplamı füzelerin yalnız
~%3'ü (90/2744). Eşleşme hipotezi yalnız körlük yoluyla işliyorsa isabet
farkının en fazla ~1 puanını açıklar; asıl kanal `tukenme` (füzelerin ~%73'ü)
olabilir — kaçan hedefi kovalayan füze enerji kaybeder. Taraf bazlı sayılar
bunu C koşusunda ayırt edecek.

**Koşu (kullanıcı "başlat" deyince, ~5 dk, 800 savaş):**
`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment gate-sym --seed-start 2000 --n 200 --workers 22 --csv runs/eval_gatesym_25v25.csv`


### EVAL-07 — Simetrik atış kapısı SONUCU: menzil kısmen işe yarıyor, ama asıl varsayım YANLIŞ çıktı (2026-09-20)

`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment gate-sym --seed-start 2000 --n 200 --workers 22 --csv runs/eval_gatesym_25v25.csv`
(taze tohumlar 2000–2199, 800 savaş, 277 s; veri `runs/eval_gatesym_25v25.csv` — ilk kez
taraf bazlı füze sonları dahil).

| | A (35v35) | C (iki taraf 25) | test (senaryo-kümelenmiş) |
|---|---|---|---|
| **toplam isabet** (BİRİNCİL) | 192 | **236** | 10:47, **p=7.5e-7** |
| atış başına isabet (pooled) | %7.0 | %8.3 | — |
| mavi / kırmızı atış başına isabet | %7.2 / %6.9 | %8.3 / %8.3 | — |
| sonuçsuz (mühimmatsız) savaş | 208 | 166 | 45:10, p=2.1e-6 |
| füze **kör** (datalink kaybı) | 82 (%3.0) | **16 (%0.6)** | 24:0, p=1.2e-7 |
| füze **tükenme** (enerji bitti) | %70.8 | **%71.1** | değişmedi |
| mavi kazanma (ikincil) | 0.245 | 0.287 | 35:48, p=0.19 |
| koltuk dengesi (mavi payı) | 0.51 OK | 0.50 OK | — |
| kapı bağladı | — | 200/200 senaryo | — |

**Önceden yazılmış tablo (EVAL-06) — karar:** "Anlamlı ARTAR" satırı: yön ve
anlamlılık ✅ (p=7.5e-7), ama satırın büyüklük eşiği (atış başına ≳%8.5, ≥~1.3×)
❌ — gerçek %8.3 ve 1.19×. Etki GERÇEK ama MÜTEVAZI. (Kendi bahsim %8–10 aralığının
alt ucunda tuttu.) Yani menzil, zamanlama simetrikken işe yarıyor → EVAL-05'teki B
başarısızlığının en az bir kısmı asimetri bedeliydi.

**Asıl bulgu — kazancın mekanizması kör (kor) füzelerin çöküşü, TÜKENME değil.**
Kısa menzilden atınca kör füze oranı %3.0→%0.6 (82→16), isabet oranı +1.3 puan;
tükenme %70.8→%71.1 ile hiç kıpırdamadı. EVAL-06'daki mekanizma uyarım ("kör
yalnız ~%3 → farkın çoğunu açıklayamaz, asıl kanal tükenme olabilir") burada
TERS çıktı: kör kanalı kazancın neredeyse TAMAMINI açıklıyor, tükenme kanalı
menzilden bağımsız.

**EVAL-03b'nin varsayımı ÇÜRÜDÜ:** "füzelerin ~%70'i menzil yüzünden enerji
tüketiyor, kapıyı yaklaştırınca düzelir" — düzelmedi. Menzil–isabet eğimi taze
tohumlarda TEKRARLANDI (ilk atış <27: %12.5, 27–30: %12.2, 30–33: %8.6, ≥33: %3.3)
ama müdahale (35→25) yalnızca +1.3 puan verdi — eğimin büyük kısmı senaryo
geometrisiyle karışık.

**Füze zarfı ölçümü (`scripts/missile_envelope.py`, saniyeler, kilit KUSURSUZ, hedef
düz uçuyor):** füzenin enerji bütçesi ~70 s uçuş; kafa kafaya azami menzil ~30–33
nmi, hedef yana dönünce (phi=90) ~25–27 nmi, kaçınca (phi=120) ~15–20 nmi.
- 35 nmi'de atılan füze kafa kafayaysa BİLE tükenir (63 s) → `LaunchRules.max_launch_nm=35`
  füzenin kendi kinematik menzilinden (~33) UZUN. Yetki ≠ Rmax ≠ NEZ.
- 25 nmi'de atılan füze düz uçan hedefi kafa kafaya 47 s'de, yan hedefi 75 s'de
  vurur — yani gerçek savaştaki %71 tükenme, atış menzilinden değil HEDEFİN
  DÖNMESİNDEN (crank/beam/kaçış) geliyor olabilir. SIM2-09'daki "crank
  sürüklenmesi" (60–90 s'de ATA 55–70°) bununla tutarlı. **HİPOTEZ, KANITLANMADI.**

**Açık kalanlar:** (1) EVAL-05 B kolu (mavi geç atınca kırmızının isabeti %8.7,
mavi kaybı 89→120) TEK koşu, taze tohumda TEKRARLANMADI ve o koşuda taraf bazlı
füze sonları yoktu — eşleşme hipotezi hâlâ açık. (2) Tükenmenin gerçek nedeni
(hedefin kaçışı mı?) ayırt edilmedi. Somut sonraki adım adayları:
(a) `--experiment gate --seed-start 2000` ile B'yi taze tohumda TEKRARLA (yeni kod
gerektirmez; taraf bazlı füze sonları gelir), (b) kaçış rolünü ölç: uyarı modu
`none` (hedef hiç kaçmaz) tanı kolu ekle — tükenme çökerse enerji sorunu
savunma manevrasından geliyor demektir.


### EVAL-08 — EVAL-05 B kolunun TAZE TOHUMDA TEKRARI (tahmin koşu ÖNCESİ kilitlendi)

**Ne/neden:** EVAL-05'te B kolu (mavi 25 / kırmızı 35) kazanmada fark vermedi ama
mavi kaybı 89→120 (senaryo düzeyi 25:1, POST-HOC) ve kırmızının atış başına isabeti
%6.5→%8.7 çıktı; o koşuda taraf bazlı füze sonları YOKTU. Şaşırtıcı bir sonucun
üstüne bir şey kurmadan önce tekrarlanmalı (EVAL-07 açık madde 1). Yeni kod yok:
`--experiment gate --seed-start 2000` (A ve B yeniden koşulur, TAZE tohum 2000–2199;
tohum kümesi EVAL-07'nin C koşusuyla AYNI ama farklı hipotez/kol — A kolu bu kodla
iki kez koşulmuş olacak, birbirini doğrular).

**Bu sefer birincil ölçüt önceden sabit (EVAL-05'te post-hoc'tu):** mavi MAĞLUBİYET
sayısı, A vs B, senaryo düzeyinde kümelenmiş işaret testi (`compare_arms_clustered_metric`
yerine mevcut raporun `mavi kaybı` satırı yoksa CSV'den hesaplanır), iki yönlü, α=0.05.

**Tahmin (sonuçtan ÖNCE):**
1. B'de mavi kaybı A'dan anlamlı YÜKSEK (yön EVAL-05 ile aynı). Kendi bahsim ~%75.
2. Kırmızının atış başına isabeti B'de A'dan yüksek (~+1.5–2 puan); mavinin isabeti
   A ile ~aynı (±0.7 puan).
3. Mavi kazanma A'dan anlamlı FARKLI DEĞİL (p>0.05).
4. (Mekanizma, KEŞİF) Kırmızının kör füze payı B'de A'dan düşük (mavi geç atınca
   kırmızı erken kaçışa zorlanmıyor → kendi füzelerini kilitli tutuyor).

**Yorum tablosu:**
| sonuç | anlamı | sonraki adım |
|---|---|---|
| 1+2 tutar (kayıp artar, kırmızı isabeti artar) | Tek taraflı gecikme BEDEL ödetiyor — atış zamanlaması rakibin kaçışına/uyarısına BAĞLI (asimetri bedeli gerçek) | Atış kararı rakibin durumuna koşullu tasarlanmalı (ör. rakip atmışsa/füzesi havadaysa beklemeyi bırak); kapı davranış ağacına KOŞULSUZ girmez |
| 1 tutmaz (kayıp farkı anlamsız) | EVAL-05 tohum-özgü/şansa bağlıydı; C sonucu (+%23 isabet, asimetri bedeli yok) geçerli | 25 nmi kapısı simetrik uygulanmış hâliyle güvenli; kaçış rolüne (EVAL-07 madde b) geç |
| 1 tutar ama 2 tutmaz | Kayıp artışı isabet oranından değil başka bir yoldan (ör. zamanlama/tükenme) | Taraf bazlı füze sonlarına bak, ayrı mekanizma ara |

**Koşu:**
`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment gate --seed-start 2000 --n 200 --workers 22 --csv runs/eval_gate_rep_2000.csv`
(800 savaş, ~5 dk).


**EVAL-08 SONUCU (2026-09-20)** — `runs/eval_gate_rep_2000.csv`, tohum 2000–2199, 800 savaş, 277 s.
A kolu, EVAL-07'deki A kolunun BİREBİR aynısı çıktı (98/94, tam deterministik).

| | A (35v35) | B (mavi 25 / kırmızı 35) | test (senaryo-kümelenmiş) |
|---|---|---|---|
| **mavi mağlubiyet** (BİRİNCİL) | 94 | **123** | 6:28, **p=2.0e-4** |
| mavi galibiyet | 98 | 89 | 30:29, p=1.0 |
| sonuçsuz savaş | 208 | 188 | 28:8, p=1.2e-3 |
| mavi / kırmızı atış başına isabet (ham) | %7.2 / %6.9 | %6.6 / **%8.9** | — |
| kör füze payı: mavi / kırmızı | %3.4 / %2.7 | %0.7 / **%2.6** | — |
| havada-kaldı (savaş bitince sonuçlanmamış): mavi / kırmızı | %12.9 / %14.1 | **%19.0 / %8.3** | — |
| savaş süresi (ort.) | 86.1 s | 96.9 s | — |

EVAL-05 (1000–1199) + bu tekrar (2000–2199) BİRLEŞİK, 400 senaryo: mavi kaybı
**7:53, p=7.7e-10**. (Not: "kırmızı isabeti" tanım gereği = mavi kaybı; bağımsız kanıt DEĞİL.)

**Tahminler (EVAL-08, koşu öncesi) — karar:** 1 ✅ (mavi kaybı anlamlı yüksek, p=2e-4),
2 ✅ (kırmızı isabeti +2.0 puan; mavi −0.6, ±0.7 içinde), 3 ✅ (kazanma p=1.0),
**4 ❌** (kırmızının kör payı DÜŞMEDİ: %2.7→%2.6). **Yorum tablosunun 1. satırı:
tek taraflı gecikme gerçek bir BEDEL ödetiyor ✅ — ama mekanizma "kaçış–kör füze
eşleşmesi" DEĞİL.** Mavinin kör payı çöktü (%3.4→%0.7) ama bu hiç isabete
dönüşmedi (98→89).

**Mekanizma — hipotezler (KANITLANMADI):**
1. *Atış yarışı + sansür.* Bir isabet düelloyu BİTİRİR; geç atan tarafın havadaki
   füzeleri çözülmeden kesilir. Veri uyumlu: mavinin havada-kalan payı %12.9→19.0,
   kırmızınınki %14.1→8.3; savaş uzuyor (86→97 s). Ham "atış başına isabet" kesilen
   füzeleri payda tutar → geç atan taraf haksız yere kötü görünür.
2. *Sonuca ulaşan füze başına isabet (`hedefsiz` HARİÇ; post-hoc, KEŞİF):* A: mavi %8.8 /
   kırmızı %8.6; **B: mavi %8.7 (DEĞİŞMEDİ) / kırmızı %10.5**; C (EVAL-07): mavi %10.3 /
   kırmızı %10.5. Örüntü: **bir tarafın füzeleri, RAKİP kapılıyken (geç atıyorken)
   daha etkili; kendi kapısı tek başına bir şey yapmıyor** (B'de mavi kendi kapısıyla
   artmadı, C'de rakip de kapılı olunca arttı). Bu örüntüyü AÇIKLAYAN bir mekanizma
   yok; 3 kol, post-hoc — yorum yapmadan kaydediyorum.

**Tasarım etkisi (Faz 2.3):** Atış kapısı (menzil eşiği) davranış ağacına GİRMİYOR.
Tek taraflı bekleme yarışı kaybettirir (ilk atışın ortalaması zaten kilit
menzilinde, 31.7 nmi — komutan yarışı şu an "mümkün olan en erken" kazanıyor);
simetrik kapı sıfır toplamlı yarışta iki tarafa eşit yarar sağlar (C) ama bir
RAKİBE KARŞI üstünlük vermez. Atış disiplini kaldıracı tükendi: kalan adaylar
(a) kaçış/savunma (tükenme %71 menzilden bağımsız; EVAL-07 madde b: uyarı modu
`none` tanı kolu), (b) salvo politikası, (c) algılama/kilit zamanlaması.


### EVAL-09 — Tanı deneyi: "hedef hiç kaçmasa" (tasarım, KOŞU ÖNCESİ kilitlendi)

**Soru:** Füzelerin ~%71'i enerji bitince sonlanıyor ve bu oran atış menzili 35→25 nmi
olunca değişmedi (EVAL-07). Füze zarfı (`scripts/missile_envelope.py`): düz uçan hedefe
25 nmi'den atılan füze yetişir (kafa kafaya 47 s, yan 75 s), 35 nmi'den yetişmez.
**Hipotez (kanıtlanmadı):** enerjiyi hedefin dönmesi/kaçışı tüketiyor. Bunu, kaçışı
KAPATARAK ayırıyoruz — gerçekçi bir politika DEĞİL, mekanizma ayırıcı bir tanı.

**Tasarım — C (RWR-tabanlı kaçış, iki taraf 25 nmi) vs N (HİÇ kaçış yok, iki taraf 25 nmi):**
- Yeni `warning_mode="none"`: iki taraf da tüm savaş boyunca `intercept` (kaçış yok).
  Menzil etkisi ÇIKARILDI (iki kol da 25 nmi'den atar: kinematik olarak ulaşılabilir);
  tek fark kaçış. Bilinmeyen `warning_mode` artık `ValueError` (eskiden yazım hatası
  sessizce `rwr` olarak koşuyordu). Kaçış süresi (`evade_ticks_blue/red`) kaydediliyor.
- **Not — RWR-tabanlı kaçış yalnız füzede değil RADAR KİLİDİ göründüğünde de başlıyor**
  (`kilit` veya `fuze`); `none` ikisini birden kapatır. Hangisinin etkili olduğunu bu
  deney AYIRT ETMEZ (ayrı bir sonraki adım).
- **TAZE tohum 3000–3199** (EVAL-05..08'de 1000–1199 ve 2000–2199 görüldü; araç artık
  ikisiyle de çakışmayı uyarır).
- **Birincil ölçüt SANSÜRE DUYARSIZ:** "en az bir isabetle biten savaş oranı"
  (senaryo düzeyinde kümelenmiş işaret testi, iki yönlü, α=0.05). Neden bu: kaçış yokken
  düello ilk isabette erken biter, kalan füzeler sonuçlanmadan kesilir — `tükenme payı`
  ve isabet SAYISI bu yüzden yanıltıcıdır (EVAL-08 dersi, tuzak 59). Karşılıklı imha 1
  sayılır (2 değil).
- **İkincil / KEŞİF (karar için değil):** ilk isabet zamanı, karşılıklı imha payı,
  toplam atış, kaçış süresi, taraf bazlı füze sonları.

**Referans:** C, EVAL-07'de (tohum 2000–2199) savaşların **%58.5**'inde ≥1 isabet verdi
(115+117+2 / 400). Taze tohumlarda ~%55–62 beklenir.

**Önceden yazılmış tahmin (sonuçtan ÖNCE):** N'de ≥1 isabetle biten savaş oranı **≥%90**
(kendi bahsim, ~%60 güvenle). Gerekçe: düz uçan hedefe 25 nmi'den atılan füze,
kusursuz kilitle bile yetişir (zarf tablosu).

| N sonucu | anlamı | sonraki adım |
|---|---|---|
| **≥ %85** | Füzeleri asıl **savunma manevrası/kaçış** başarısız kılıyor → en büyük kaldıraç savunma politikası | Faz 2.3 odağı: kaçış politikası. Sıradaki deney: tetikleyiciyi ayır (yalnız `fuze` vs `kilit`+`fuze`), `age_s` tabanlı kaçış |
| **%65–85** | Kaçış önemli ama tek neden değil | Kalan nedeni ara (atış-anı geometrisi, güdüm, füze modeli); kaçışı ayrıca tasarla |
| **< %65** (C'ye yakın) | Kaçış füzeleri yenen şey DEĞİL; enerji sorunu başka yerde | Füze modeli/güdüm/pursuit geometrisi (SIM2-08); kaçış tasarımına şimdilik yatırım yapma |

**Uyarı:** N'de iki taraf da aynı anda atıp kaçmadığı için karşılıklı imha payı yüksek
beklenir; bu kazanma-oranı deneyi DEĞİL. Sonucu "kaçmamak daha iyi" diye OKUMA — kaçmamak
kendini de öldürür; ölçtüğümüz şey füzenin kinematik olarak yetişebildiği.

**Koşu (kullanıcı "başlat" deyince, ~5 dk, 800 savaş):**
`python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment evade-diag --seed-start 3000 --n 200 --workers 22 --csv runs/eval_evadediag_25.csv`

**Hazırlık doğrulaması:** varsayılan `rwr` davranışı önceki koşularla 9 savaşta alan alan
birebir aynı; `test_duel_gate.py` 17 teste çıktı; 7 mutasyon (none tanımsız, none yalnız
bir tarafı susturuyor, mod doğrulaması yok, kaçış sayacı taraf değiştirmiş, N etiketli
ama kaçıyor, `duel_had_kill` karşılıklı imhada 2 sayıyor, `total_hits` yalnız maviyi
sayıyor) — **6'sı ilk denemede yakalandı; kaçış sayacının taraf yer değiştirmesi (M4)
ilk denemede hayatta kaldı** çünkü simetrik senaryoda iki taraf birebir aynı sayıyı
veriyordu; asimetrik iki senaryo (seed 1026: mavi>kırmızı, seed 1012: mavi<kırmızı)
eklenince yakalandı. Toplam **97/97**.


**EVAL-09 SONUCU (2026-09-20)** — `runs/eval_evadediag_25.csv`, tohum 3000–3199, 800 savaş, 261 s.

| | C (RWR kaçışı, iki taraf 25) | N (HİÇ kaçış yok, iki taraf 25) | test (senaryo-kümelenmiş) |
|---|---|---|---|
| **≥1 isabetle biten savaş** (BİRİNCİL) | 231/400 (**%57.8**) | **400/400 (%100)** | 0:94, **p=1.0e-28** |
| kaçışta geçen süre (savaş başına, taraf başına) | **97 s** (savaş ort. 101 s) | 0 s | — |
| ilk isabet zamanı (ort.) | 96.9 s | 79.1 s | — |
| füze tükenme payı (ham) | %70–71 | %17.5–18.6 | sansürlü — bkz. not |
| sonuca ulaşan füze başına isabet [isabet/(isabet+tükenme+kör)]: mavi / kırmızı | %10.8 / %9.9 | **%57.9 / %50.8** | — |
| karşılıklı imha | 2 | 22 | — |
| atış toplamı | 2832 | 1948 | — |

**Tahmin (EVAL-09, koşu öncesi):** N'de ≥%90 → **✅ tuttu** (%100). C referansı %58.5 → %57.8 (tutarlı).
**Yorum tablosunun 1. satırı (≥%85): füzeleri asıl SAVUNMA MANEVRASI/KAÇIŞ başarısız kılıyor;
en büyük kaldıraç savunma politikası.** Menzil aynıyken (ikisi de 25 nmi, kinematik olarak
ulaşılabilir) tek fark kaçış: ≥1 isabet oranı %57.8 → %100, sonuca ulaşan füze başına isabet
~%10 → ~%55. Enerji bitmesinin (EVAL-07) nedeni atış menzili değil, hedefin dönmesi/kaçışı.

**Kaçış SÜRESİ bir bulgu:** C kolunda taraf başına savaşın ~%96'sı kaçış modunda geçiyor
(97 s / 101 s). Çünkü kaçış yalnız füze gelince değil RWR'da `kilit` göründüğü anda başlıyor
ve bir daha çıkılmıyor: mevcut betikli komutan fiilen "kilit al, at, sonra SAVAŞ BOYUNCA kaç".
Bu, savaşların ~%42'sinin kimse vurulmadan bitmesinin (mühimmatsız) doğrudan nedeni.

**Sınırlar:** (1) N gerçekçi bir politika DEĞİL — kaçmamak kendini de öldürür (karşılıklı imha
2→22, ilk isabet 97 s→79 s); ölçtüğümüz "füze kinematik olarak yetişebilir mi". (2) `none`,
radar-kilit tetikli kaçışı VE füze tetikli kaçışı BİRLİKTE kapatır; hangisinin etkili olduğu
ayrılmadı. (3) N'de tükenme payı (%17.5) düello erken bittiği için sansürlü (havada-kaldı %35–43);
karar birincil (sansüre duyarsız) ölçüte dayanır.

**⚠ AÇIK ARAÇ UYARISI — N kolunda koltuk dengesi:** karar verilen 378 savaşta mavi payı 0.56
(%95 GA [0.51, 0.61]) → aracın yerleşik uyarısı tetiklendi (diğer 7 simetrik kolda 0.49–0.52).
Araştırma: (a) normal 0.58 ve AYNA 0.54 → geometriden değil, koltuktan; (b) senaryo düzeyinde
mavi-çok-isabet 79 vs kırmızı 53 (p=0.029; C kolunda 42:37, p=0.65); (c) TAM simetrik senaryoda
(aynı irtifa/Mach/yakıt, aspect 0) düello BİREBİR simetrik (aynı anda atış, aynı anda isabet,
karşılıklı imha) → temel döngüde tik-sırası yanlılığı YOK; (d) örneklemdeki enerji dengesizliği
mavi lehine hafif (+0.7σ, anlamsız) ama mavinin kazanmasıyla ilişkisi sıfır/ters (yakıt:
korelasyon −0.23 — hafif uçak kazanıyor); (e) ilk atış menzili mavi=kırmızı (24.9864), atış sayısı
969 vs 979. **Neden BULUNAMADI.** En olası: şans (8 simetrik kol kontrolünün ~%34'ü %5 düzeyinde
bir uyarı verir). ÇÖZÜLMEDİ; replikasyon gerekir (N kolu taze tohumda). Birincil sonuç bundan
ETKİLENMEZ: ölçüt koltuk-bağımsız ("≥1 isabet") ve fark 42 puan (%5'lik bir koltuk yanlılığı
bunu açıklayamaz).

**Tasarım etkisi (Faz 2.3):** Kaçış politikası, betikli komutanın en büyük ve şimdiye dek en az
tasarlanmış parçası: sürekli kaçış savunmada iyi (sağ kalıyor) ama saldırıyı da öldürüyor (kendi
füzesini de). Sonraki adım (onaya bağlı): tetikleyiciyi ayır — yalnız `fuze` (aktif arayıcı)
vs `kilit`+`fuze` (mevcut) vs gecikmeli kaçış (`age_s`/tahmini isabet süresi tabanlı). Ölçüt: bir
taraf varyantı kullanır, diğeri mevcut politikayı (ASİMETRİK; kazanma oranı birincil, EVAL-04
dersi), taze tohum, önceden yazılmış tahmin.


### EVAL-10 — H-15'i kapatma: N kolunun koltuk uyarısı için TAZE TOHUMLU TEKRAR (tahmin koşu ÖNCESİ)

**Soru:** EVAL-09'un N kolunda (hiç kaçış yok) mavi payı 0.56 [0.51, 0.61] çıktı; kod yanlılığı ve
örnekleme dengesizliği elendi, neden bulunamadı (H-15). Şans mı, gerçek koltuk yanlılığı mı?

**Deney:** `evade-diag` TAMAMI taze tohum **4000–4199** ile yeniden (C ve N): hem koltuk uyarısını
hem de EVAL-09'un birincil sonucunu (≥1 isabetle biten savaş) tekrarlar. Yeni kod yok.

**Önceden yazılmış karar kuralı (sonuçtan ÖNCE):**
| N kolunda mavi payı (karar verilen savaşlar) | karar |
|---|---|
| GA 0.5'i içerir VE nokta tahmin < 0.54 | **ŞANS**: EVAL-09 uyarısı tekrarlanmadı → H-15 KAPANIR |
| GA 0.5'i dışlar VE nokta tahmin ≥ 0.54 (tekrar) | **GERÇEK koltuk yanlılığı** (belirlenimci yarış rejiminde) → H-15 AÇIK kalır; ayrıca iki koşu birleşik (800 N savaşı) sayılır ve koltuk-takası (mavi/kırmızı parametre değişimi) tasarlanır |
| arada (ör. 0.54–0.56 ama GA 0.5'i içerir) | Belirsiz; iki koşu birleşik değerlendirilir |
Birincil sonucun tekrarı: N'de ≥1 isabet ≥%95, C'de %52–64 (EVAL-09: %100 / %57.8) — bu
kısım karar kuralının parçası DEĞİL, yalnız tekrar kontrolü.
Kendi bahsim: **şans** (~%65 güvenle) — çünkü tam simetrik senaryoda döngü birebir simetrik.

**Koşu:** `python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment evade-diag --seed-start 4000 --n 200 --workers 22 --csv runs/eval_evadediag_rep_4000.csv` (~5 dk).


**EVAL-10 SONUCU (2026-09-20)** — `runs/eval_evadediag_rep_4000.csv`, tohum 4000–4199, 800 savaş, 261 s.

| | EVAL-09 (3000–3199) | TEKRAR (4000–4199) |
|---|---|---|
| **N kolunda mavi payı** (karar verilen) | 212/378 = **0.561** [0.510, 0.610] ⚠ | 185/377 = **0.491** [0.441, 0.541] ✅ |
| N senaryo düzeyi: mavi-çok-isabet : kırmızı-çok-isabet | 79 : 53 (p=0.029) | 72 : 74 (p=0.93) |
| C kolunda mavi payı | 119/229 = 0.520 | 131/229 = **0.572** [0.507, 0.634] ⚠ |
| ≥1 isabetle biten savaş: C / N | 231/400 (%57.8) / 400/400 (%100) | 229/400 (%57.2) / 400/400 (%100) |

**Karar kuralı (EVAL-10, koşu öncesi): N kolunda GA 0.5'i içeriyor VE nokta tahmin < 0.54 → ŞANS,
H-15 KAPANIR.** Kendi bahsim (şans, ~%65) tuttu. Birincil sonucun tekrarı da tuttu (N %100, C %57.2).

**Dürüst ek:** uyarı N'den C koluna KAYDI (0.572, GA 0.5'i dışlar). 8 BENZERSİZ simetrik
koşunun HEPSİ birleşik (`truth` 1000, `A` 1000, `A` 2000, `C` 2000, `C` 3000, `N` 3000, `C` 4000,
`N` 4000): mavi **1050/2021 = 0.5195 [0.498, 0.541], iki-yönlü p=0.083**; 8 kontrolden ≥2'sinin
%5 düzeyinde uyarma olasılığı 0.057 (gözlenen: 2). Yani veri şansla tutarlı ama ~2 puanlık
küçük bir mavi avantajını TAMAMEN dışlamıyor (GA'nın üst ucu 0.541). Etki büyüklüğü, ölçtüğümüz
tüm karşılaştırmalara göre ihmal edilebilir; ayrıca ESLEŞMİŞ tasarımlarda (A vs B, aynı koltuklar)
sabit bir koltuk yanlılığı iki kolda da aynı kalıp farkta sadeleşir. İZLEME maddesi: yeni bir
simetrik koşu eklendikçe bu birleşik oran güncellenir.


### EVAL-11 — Kaçış tetikleyicisi: "kilitte kaç" ne kadar gecikebilir? (tasarım, KOŞU ÖNCESİ kilitlendi)

**Neden:** EVAL-09: füzeleri asıl kaçış başarısız kılıyor, ama mevcut komutan savaşın ~%96'sını
kaçışta geçiriyor çünkü kaçış RADAR KİLİDİNDE (`kilit`) başlıyor ve bir daha çıkılmıyor. Kaçış
(a) hayatta kalmayı sağlıyor, (b) saldırıyı ve savaşın sonuçlanmasını (~%42 kimse vurulmadan bitiyor)
engelliyor. **Soru: kaçış, kilidin başlangıcından ne kadar sonra başlarsa hayatta kalma bedeli ödenir?**

**Tasarım kararı — "yalnız fuze" yerine TEK PARAMETRELİ doz-yanıt ailesi.** Önceki plan üç ayrı
tetikleyici (`fuze` / `kilit+fuze` / `age_s` gecikmeli) idi. `fuze`-yalnız varyantı büyük ölçüde
ÖNCEDEN BİLİNİYOR: aktif arayıcı ~31 s uçuştan sonra görünür, isabete ~17 s kalır ve füze zarfı
ölçümü (`scripts/missile_envelope.py`) bu mesafede kaçışın füzeyi kurtarmadığını gösteriyor (15 nmi'de
phi=120 bile isabet). Bu yüzden tetikleyiciyi tek parametreye indirdim: **`kilit` teması `T` saniyeden
eskiyse kaç** (`should_evade`); `T=0` = mevcut, `T=∞` = yalnız `fuze`. `age_s` yayıncının İLK
TESPİTİNDEN (arama seviyesinden) beri geçen süredir — kilidin kendi yaşı DEĞİL ama "temas ne kadardır
sürüyor" için makul vekil.

**Kollar (ASİMETRİK; EVAL-04 dersi — kazanma/hayatta kalma rakibe göre ölçülür):**
| kol | mavi kaçışı | kırmızı kaçışı | kapı |
|---|---|---|---|
| A (referans) | T=0 (mevcut) | T=0 | yok (gerçek oyun, 35 nmi) |
| B1 | **T=15 s** | T=0 | yok |
| B2 | **T=∞ (yalnız fuze)** | T=0 | yok |
İki KARŞILAŞTIRMA (B1 vs A, B2 vs A) → **Bonferroni eşiği α=0.025**. Aile önceden sabit {15, ∞};
başka T KEŞİF (araç işaretler). İki komut ayrı koşulur, A kolu iki kez koşulur (belirlenimci → aynı).
**TAZE tohum 5000–5199** (1000–4199 görüldü).

**Birincil ölçüt: MAVİ NET SKOR** (galibiyet +1, mağlubiyet −1; karşılıklı imha ve sonuçsuz 0),
senaryo düzeyinde kümelenmiş işaret testi. Neden kazanma değil: kaçış politikası ağırlıklı olarak
HAYATTA KALMAYI değiştirir (EVAL-05: kazanma ~aynı, kayıp +%30 idi); net skor ikisini birden yakalar.
**İkincil:** mavi galibiyet/mağlubiyet ayrı ayrı, kaçış süresi, taraf bazlı füze sonları, ilk isabet zamanı.
(Asimetrik kolda koltuk dengesi ~0.5 BEKLENMEZ — araç bunu işaretler.)

**Önceden yazılmış tahmin (sonuçtan ÖNCE):**
1. **B2 (yalnız fuze): mavi net skoru A'dan anlamlı DÜŞÜK** (p<0.025), ~%90 güvenle; mavi kaybı A'ya
   göre ≥+%40. (Ön bilgi: yalnız-fuze ≈ "pitbull'a kadar kaçmama".)
2. **B1 (T=15 s): yön NEGATİF (net skor A'dan düşük), ~%65 güvenle; α=0.025'te anlamlı, ~%40.**
   Gerekçe: kaçış ilk tespitten ~15 s sonra başlar (kilit +~3.5 s, ilk atış +~2.5 s; füze isabete
   ~37 s kala) — bu, füzenin enerjisini tüketmesine yetecek yönelme süresinin çoğunu bırakır.

| B1 (T=15 s) sonucu | anlamı | sonraki adım |
|---|---|---|
| net skor **anlamlı düşük** (p<0.025) | Kaçış kilitte BAŞLAMAK ZORUNDA; her gecikme bedel öder | BT kaçışı kilitte tutar; bir sonraki kaldıraç kaçış GEOMETRİSİ (açı) ve kaçıştan ÇIKIŞ |
| **fark anlamsız** | 15 s'lik gecikme BEDELSİZ → ileri baskı için serbest pencere | daha uzun T (ör. 25 s) taraması (KEŞİF) ve "baskı penceresi" tasarımı; asıl kazanç hangi anda ne yapıldığında aranır |
| net skor **anlamlı yüksek** | Erken kaçış boşa; gecikme kazandırıyor | BT'ye kilit-yaşı tabanlı gecikmeli kaçış (T'yi taze tohumda doğrula) |
B2 beklendiği gibi düşükse yalnızca "tamamen geç kaçmak kötü" doğrulanır (kalibrasyon); B2 düşük DEĞİLSE
(net skor A'dan anlamlı farklı değil) bu şaşırtıcı ve önemli bir bulgu olur (kaçış pitbull'dan önce gereksiz).

**Kodlama (doğrulandı):** `should_evade(threat, delay_s)` saf fonksiyon (`fuze` her zaman; `kilit` yaş ≥ T;
diğer hayır); `run_duel(evade_delay_s_blue/red)` (yalnız `warning_mode='rwr'`, aksi ValueError);
`DuelResult.evade_delay_*`; `ArmSpec` gecikme alanları (`symmetric` gecikmeyi de görür);
`--experiment evade-delay --evade-delay-s`; `duel_net_score`. Varsayılan davranış önceki koşularla
9 savaşta alan alan BİREBİR. `test_evade_policy.py` 11 test; 10 mutasyon: **9'u ilk denemede yakalandı,
M8 (worker kırmızının gecikmesini mavininkinden türetiyor) hayatta kaldı** — kapı için yazılan
worker-zinciri testinin gecikme karşılığı eklenince yakalandı. Toplam **108/108**.

**Koşu (kullanıcı "başlat" deyince; 2 komut, ~5 dk her biri, 800 savaş):**
```
python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment evade-delay --evade-delay-s 15 --seed-start 5000 --n 200 --workers 22 --csv runs/eval_evadedelay_15.csv
python -m scripts.eval_commander runs/reward_r3_both/sac_1999968_steps.zip --experiment evade-delay --evade-delay-s inf --seed-start 5000 --n 200 --workers 22 --csv runs/eval_evadedelay_inf.csv
```


**EVAL-11 SONUCU (2026-09-20)** — `runs/eval_evadedelay_15.csv`, `runs/eval_evadedelay_inf.csv`; tohum 5000–5199,
2×800 savaş, ~280 s/koşu. A kolu iki koşuda BİREBİR aynı (belirlenimci).

| | A (T=0, mevcut) | B1 (mavi T=15 s) | B2 (mavi T=∞, yalnız fuze) |
|---|---|---|---|
| mavi galibiyet | 84 | 104 | **258** |
| mavi mağlubiyet | 86 | 92 | **114** |
| **mavi NET SKOR (BİRİNCİL)** | **−2** | **+12** | **+144** |
| net skor testi (senaryo-kümelenmiş, α=0.025) | — | 11:18, p=0.265 ❌ | 23:110, **p=8.4e-15** ✅ |
| mavi galibiyet testi (ikincil) | — | 4:19, p=0.0026 | 17:117, p=1.5e-19 |
| mavi mağlubiyet testi (ikincil) | — | 6:13, p=0.17 | 5:29, **p=3.9e-5** (kayıp ARTTI) |
| mavi atış başına isabet | %6.2 | %7.8 | **%19.9** |
| mavi kör füze payı | %2.6 | %0.5 | %0.2 |
| mavi füze tükenme payı | %74.1 | %71.8 | **%43.1** |
| mavi kaçışta geçen süre | 81.8 s | 68.5 s | **12.6 s** (medyan 15.5) |
| kırmızı atış başına isabet | %6.3 | %6.7 | %8.5 |
| sonuçsuz savaş | 229 | 204 | **27** |

**Tahminler (EVAL-11, koşu öncesi) — karar: İKİSİ DE YANLIŞ.**
1. B2 (yalnız fuze): "mavi net skor anlamlı DÜŞÜK, ~%90 güvenle" → **❌ TAM TERSİ**: net skor −2 → **+144**
   (p=8e-15). Kendi yorum tablomdaki "B2 düşük DEĞİLSE bu şaşırtıcı ve önemli bir bulgu" satırı gerçekleşti —
   üstelik anlamlı ÖNE geçti.
2. B1 (T=15): "yön negatif ~%65" → ❌ yön POZİTİF (+12), birincil ölçütte anlamsız (p=0.265); ikincil kazanma
   testi anlamlı (p=0.0026) ama BİRİNCİL DEĞİL (bir "ikincil"i sonradan öne çıkarmıyorum).
Formal karar: B1 → yorum tablosunun "fark anlamsız → 15 s bedelsiz" satırı; B2 → tabloda öngörülmeyen (güçlü)
üstünlük.

**Ne oluyor (doz–yanıt, tek yönlü ve tutarlı):** kaçışı geciktirdikçe mavinin kazanma sayısı 84 → 104 → 258,
atış başına isabeti %6.2 → %7.8 → %19.9 ve kaçış süresi 82 → 68 → 13 s. Kaybı yalnız 86 → 92 → 114
(hayatta kalma bedeli GERÇEK ama küçük: +28 kayıp, +%33) — kazanılan galibiyet +174. Sonuçsuz savaş 229 → 27.

**Mekanizma (KANITLANMADI, verilerle uyumlu):** (1) Mavi, kırmızı gibi radar kilidinde kaçmayınca hedefe dönük
kalıyor: kör füzeler (%2.6 → %0.2) ve tükenme (%74 → %43) çöküyor — KIRMIZI AYNI kaçış politikasında kalmasına
rağmen. Yani füzelerin enerji kaybı yalnız HEDEFİN kaçışından değil ATICININ kaçışından da geliyor (iki uçak
birbirinden uzaklaşırken füze açılan bir mesafeyi kovalıyor); EVAL-09'daki "kaçış her şeyi belirliyor" okumam
EKSİKTİ — iki taraf birlikte kaçmanın maliyeti bireysel faydasından BÜYÜK. (2) Aktif arayıcı göründükten sonra
(yalnız ~17 s) başlayan kaçış hâlâ ~%80 hayatta bırakıyor (kayıp +%33) → erken kaçışın marjinal hayatta kalma
değeri küçük. **Bu, "hep kaç" dengesinin tek taraflı sapmayla sömürülebilir olduğu anlamına geliyor.**

**TEZ ÖNEMİ (en büyük çıkarım): betikli taban çizgisi ZAYIF/SÖMÜRÜLEBİLİR.** Mevcut komutan ("kilitte kaç")
tek bir parametre değişikliğiyle (kaçışı fuzeye ertele) net skor −2 → +144 ile yenilebiliyor. Faz 4'te
"RL, betikli tabanı geçsin" ölçütü ZAYIF bir tabana karşı olursa anlamsız olur. Taban çizgisi ÖNCE
güçlendirilmeli (Faz 2.3 davranış ağacı) ve RL'nin karşılaştırılacağı rakip, sömürülebilirlik testinden
geçmiş olmalı.

**Uyarılar:** (a) B2 hâlâ gerçekçi bir "sonsuz üstünlük" değil: kaybı %33 artırıyor; kırmızı kaçış geometrisi
sabit (30° crank), aktif arayıcı sonrası daha güçlü kaçış (beam/notch) denenmedi. (b) Sonuç tek füze/tek radar/tek
kaçış modeli içinde geçerli; simülasyon, kaçış manevrasını 30° crank ile temsil ediyor. (c) Asimetrik kolda
mavi payı 0.69 [0.64, 0.74] beklenen bir işaret (mavi bilerek farklı oynuyor), ölçüm önyargısı değil.

**Sıradaki (onaya bağlı):** (1) 3×3 politika matrisi (T ∈ {0, 15, ∞} mavi × kırmızı, taze tohum): T=∞ her
karşıya en iyi yanıt mı? güçlü betikli taban hangisi? (Bonferroni, önceden yazılmış tahmin.) (2) Aktif arayıcı
sonrası kaçış geometrisi (crank vs beam) ile kaybı düşürme. (3) Yeni taban çizgisini (T=∞ ya da matristen çıkan)
Faz 2.3 davranış ağacına yerleştir.


---

## 13. Faz 2.3 hazırlığı, Faz 2.4, tez ve kalibrasyon notları (2026-09-20)

> Bu bölüm 2.3'e BAŞLAMADAN önce yazıldı. Çalışma modu: **öğretici mod** (Claude anlatır, Zahit ürün kodunu
> yazar, Claude kontrol/ölçüm yapar) — aksi belirtilmedikçe. Uzun koşular yine açık "başlat" ister;
> tasarım ve tahmin koşudan ÖNCE yazılır.

### 13.1 Faz 2.3'ten ÖNCE yapılacaklar (kontrol listesi)

| # | iş | kim | durum |
|---|---|---|---|
| 1 | Ön ölçümler EVAL-04…11 | Claude | ✅ bitti |
| 2 | **Füze kalibrasyon ölçümü** (`scripts/missile_envelope.py --sweep`: irtifa × hız × `min_speed_mach`) | Claude | ✅ bitti — bulgular §13.5 |
| 3 | **Kalibrasyon KARARI**: `min_speed_mach=1.5` ve zarf açık kaynaklı mertebelerle uyumlu mu? Dondur mu, değiştir mi? (§13.5) | **Zahit** (kaynak seçimi) | ⬜ 2.3c'den ÖNCE |
| 4 | **Kabul kriterleri ve rakip havuzu R1–R3 TANIMLARI** (koşudan önce yazılacak; non-inferiority marjı dahil, §13.2-F) | **Zahit** + Claude | ⬜ 2.3d'den önce |
| 5 | **Komutan arayüzü**: `Perception` (bilgi sınırı) + `Command`; imzalı crank (şu an yalnız SAĞ) | **Zahit yazar** | ⬜ 2.3a |
| 6 | **`LegacyCommander`**: bugünkü davranışı BİREBİR üretsin (regresyon referansı: EVAL-11 A kolu CSV'leri) | **Zahit yazar** | ⬜ 2.3a |
| 7 | **Notch uygulanabilirlik ölçümü**: radar notch koşulu `elevation ≤ 0` VE `|Vc| < 100 fps` — çok dar pencere; HİÇ denenmedi | Claude (izole ölçüm, `crank_sweep` tarzı) | ⬜ 2.3c'den önce |
| 8 | **CSV şema sürüklenmesi**: eski CSV'lerde `evade_*`/`gate_*`/taraf-bazlı sütunlar yok → analiz betikleri iki biçimi tolere etsin (yardımcı yükleyici) | Claude | ⬜ küçük |
| 9 | **İrtifa-farkında atış kapısı** hipotezi (§13.5): 2.3c'nin ATIŞ düğümünde ölçülecek | Claude ölçer | ⬜ 2.3c |

### 13.2 Faz 2.3 notları

**A. Mimari.** Karar şu an `run_duel` içinde dağınık (`should_evade`, sabit crank, `can_fire` olur olmaz ateş).
Komutan bir NESNE olacak: `Commander.decide(perception) -> Command`. `Perception` komutanın görebildiği HER şey
(tek pencere; yapısal test: komutan modülü `Engagement`/`eng.missiles`/gerçek düşman durumuna erişmesin —
RWR `test_9` gibi kaynak taraması). `LegacyCommander` tabanı koru: EVAL-03…11'in tamamı onunla ölçüldü.

**B. Ağaç kavramları.** Fallback (öncelik), Sequence, Condition/Action, blackboard (=`Perception`), tick (10 Hz).
Öncelik sırası koddaki sıradır. Histerezis: her moda asgari kalış süresi + giriş/çıkış eşik farkı (TAC-08 limit
çevrimi dersi).

**C. Ölçümden düğüme eşleme (ÖLÇÜLMÜŞ olanlar):**
| bulgu | düğüm kararı |
|---|---|
| EVAL-11: aktif arayıcıda (`fuze`) kaç, kilitte değil → net skor −2 → +144 | **Kaçış tetikleyicisi = `fuze`** (bu, ağacın 0. sürümü: `BT_v0`) |
| EVAL-11: kilit gelince hedefe DÖNÜK (`intercept`) kalmak kör füzeyi %2.6→%0.2, tükenmeyi %74→%43 yaptı | **Kilit/atış sırasında CRANK yok; `intercept`** |
| EVAL-08: geç atan yarışı kaybeder | Atış ERTELENMEZ (kilit + yetki → en erken); ertelemeli salvo ÖLÇÜLMEDEN eklenmez |
| SIM2-09: sabit güvenli açı yok, açı+menzil çifti; sağ/sol asimetrik | Kaçış crank'i |ATA| GERİ BESLEMELİ |
| §13.5: füze zarfı irtifaya çok bağlı | Atış kapısı sabit değil, irtifa/hız-farkında (hipotez, ölçülecek) |

**D. ⚠ Başka bir oturumdan gelen tasarım taslağında DOĞRULANAN/DÜZELTİLEN noktalar** (koda ve ölçümlere karşı kontrol edildi):
1. ✅ Notch koşulu doğru: `radar.py`: `elevation_deg <= 0 and |closure_fps| < notch_fps(100)`. Ama `|Vc|<100 fps` ~±4° dar bir geometri
   penceresi (göreli hız ~1600 fps) — uygulanabilirliği ÖLÇÜLMEDİ (madde 7).
2. ❌ **"DESTEK: kendi füzem havadayken CRANK" düğümü ÖLÇÜMLERLE ÇELİŞİYOR.** Eski taban tam olarak bunu yapıyordu (kilitte
   `evade` = 30° crank, savaşın %96'sı) ve EVAL-11'de hedefe dönük (`intercept`) kalan taraf ezici üstün çıktı (füze görününce
   kaçan). Crank'in "F-pole açar / kilidi korur" faydası bu simülasyonda ÖLÇÜLMEDİ; ağaca varsayım olarak girmez, `BT_v0` (intercept
   + fuzede kaç) tabanına EKLENEN bir düğüm olarak (2.3c) test edilir.
3. ⚠ **Kaçış geometrisi**: `pick_target(..., "evade", crank_rad)` her zaman `brg += crank_rad` (yalnız SAĞ). "Notch/drag/imzalı
   crank" yeni sanal-hedef mantığı ister (TAC-08: sanal hedef 5–25 nmi).
4. ⚠ **Bilgi sınırı**: `blue.step(st_red_combat, ...)` gerçek (omniscient) düşman durumunu guidance'a veriyor — radar kilidi
   olmadan da hedefe dönebiliyor. `Perception` KARARLARI sınırlayacak; guidance'ın hedef konumu için gerçek durum kullanması
   BİLİNEN BİR SINIRLAMA olarak tezde yazılır (radar-süzülmüş iz Faz 3+ işi).
5. ⚠ **Salvo/shoot-look-shoot ÖLÇÜLMEDİ** ve EVAL-08 dersiyle çelişebilir (ikinci füzeyi ertelemek yarışı kaybettirebilir).
   `max_per_target=2` `LaunchRules` parametresi; ağaçtaki koşul (ilk füze pitbull olana dek bekle) hipotez — ölç, varsayma.
6. ⚠ **R3 "erken kaçan çekingen" = R1 (`LegacyCommander`, kilitte kaç) ile aynı olabilir.** R3'ü ANLAMLI biçimde ayır (ör. `arama`
   seviyesinde kaç ya da kaçış crank'i daha geniş) ve koşudan önce yaz.
7. ⚠ **"R2'ye anlamlı kaybetmemeli"** bir üstünlük değil DENKLİK iddiasıdır: "anlamlı fark yok" ≠ "eşdeğer". Önceden bir
   non-inferiority marjı (ör. net skor farkı ≥ −δ, %95 GA alt sınırı) yazılmalı. Üç karşılaştırma → Bonferroni α=0.05/3.
8. ⚠ **"Geçişsizlik/taş-kağıt-makas kendi ölçümün" ÖN GÖRÜ, bulgu DEĞİL.** Ölçülen: `fuze-only > kilitte-kaç` (EVAL-11) ve
   `hiç-kaçma vs hiç-kaçma` yazı-tura (EVAL-09). `fuze-only vs hiç-kaçma` ve `hiç-kaçma vs kilitte-kaç` ÖLÇÜLMEDİ; döngü ancak 2.4
   matrisinden sonra iddia edilebilir.

**E. İş sırası:** 2.3a arayüz + `LegacyCommander` (ölçüt: BİREBİR aynı çıktı) → 2.3b `BT_v0` iskeleti + sahte `Perception`
birim testleri (JSBSim'siz) → **2.3b' `BT_v0`, EVAL-11 B2'yi tekrarlamalı (net skor ≈ +144 civarı; DOĞRULAMA)** → 2.3c düğümler tek
tek (imzalı crank geri beslemesi, irtifa-farkında kapı, notch, drag, ertelemeli salvo) — her düğümden sonra AYRI ölçüm → 2.3d havuza karşı
final + belgeler.

**F. Kabul kriterleri (KOŞU ÖNCESİ yazılacak, madde 4):** rakip havuzu R1 (`LegacyCommander`), R2 (hiç kaçmayan), R3 (ayrıştırılmış
erken-kaçan). Yeni ağaç R1 ve R3'ü anlamlı yenmeli, R2'ye karşı non-inferior olmalı; ÜÇÜ de raporlanır (yalnız kazanılan rakibi göstermek
yasak). İkincil: atış başına isabet (sonuca ulaşan füze başına da), `muhimmatsiz` payı, `kor` payı, `nz_min`.

### 13.3 Faz 2.4 notları
- Rakip havuzu **hem erken kaçan hem hiç kaçmayan hem `fuze-only` hem yeni ağaç** içermeli; yoksa "RL tabanı geçti" yine tek bir zayıflığı
  sömürmek olur (EVAL-11 dersi).
- 3×3 politika matrisi (mavi × kırmızı, kaçış gecikmesi ∈ {0, 15, ∞} + `none`) burada: **en iyi yanıt tablosu** + sömürülebilirlik
  (her politikanın havuzdaki en kötü sonucu). Simetrik hücrelerde koltuk dengesi ~0.5 beklenir (izleme: 8 koşu birleşik 0.5195).
- Önceden yazılmış tahminler + Bonferroni; matris DESKRİPTİF (tek bir "kazanan" ilan etmek için yeterli değil, döngü var mı diye bak).
- Faz 4'ün ölçütü (yeniden yazıldı): RL komutanı, **güçlendirilmiş ve sömürülebilirlik testinden geçmiş** betikli havuzun HER üyesine karşı
  (en iyi yanıt dahil) non-inferior/üstün olmalı — "betikliyi geçti" değil.

### 13.4 Tez notları
- **Yöntemsel katkı (savunulabilir):** her deney için önceden yazılmış tahmin + karar kuralı, taze tohum (çift-dalış yok), kümelenmiş
  eşleşmiş test, mutasyonla sınanmış ölçüm aracı, simetri öz-denetimi, sansüre duyarsız ölçüt. Çürütülen tahminler (EVAL-05, 08, 11)
  yöntemin çalıştığının kanıtı.
- **Söylenebilir:** (a) betikli "kilitte kaç" tabanı tek parametreyle sömürülebilir (net −2 → +144, p=8e-15); (b) sabit menzil kapısı
  ortalamada zayıf ama irtifa dilimlerinde etkisi farklı (§13.5); (c) atış zamanlaması ve kaçış birbirine bağlı; (d) tek taraflı geç atmak
  yarışı kaybettirir (7:53, p=8e-10).
- **SÖYLENEMEZ (henüz):** geçişsizlik/taş-kağıt-makas; "fuze-only evrensel olarak en iyi"; füze modeli gerçeğe kalibre; menzil
  kapısı "etkisiz".
- **Sınırlamalar (açık yazılacak):** 3-DOF nokta kütle füze (lofting yok, `iska` neredeyse yok), tek radar/RWR modeli, tek güdüm
  politikası (SIM2-08 sağa-yatık), guidance'a omniscient hedef konumu (§13.2-D4), `min_speed_mach` bir KALİBRASYON DÜĞMESİ (§13.5),
  senaryo dağılımı (irtifa 15–35 kft, Mach 0.75–0.95, ayrım 25–40 nmi) tek bir dağılım.
- **Self-play (Faz 5) gerekçesi:** "betikli havuz sömürülebilir" gözlemi kendi verimizden; geçişsizlik iddiası 2.4 matrisi bittikten SONRA.
- Değişmeyen ilke: aşağıdan yukarı dondur — füze/radar modeli değişirse TÜM EVAL karşılaştırmaları geçersizleşir; kalibrasyon kararı
  2.3c'den ÖNCE verilip dondurulmalı.

### 13.5 KALİBRASYON DÜĞMESİ — füze enerji bütçesi (`MissileConfig`)

**Neden düğme:** fuzelerin ~%71'i `tukenme` ile bitiyor; tüm taktik manzara bu enerji bütçesine asılı. `tukenme`, boost sonrası Mach
`min_speed_mach` (=1.5, "altında manevra kabiliyeti biter") altına inince ilan ediliyor — gerçek bir fiziksel sabit değil bir
KABUL. Düğmeler: `min_speed_mach` (1.5), `boost_s` (9), `boost_thrust_lbf` (3000), `mass_lb` (335), `ref_area_sqft` (0.268),
Cd(Mach) tablosu, `n_pro_nav` (4), `max_g` (30), `pitbull_range_nm` (8), `seeker_fov_deg/range` (30/10), `datalink_memory_s` (5, "denge
parametresi"), `lethal_radius_ft` (30); ayrıca `LaunchRules.max_launch_nm` (35, SABİT). Ölçüm: `python -m scripts.missile_envelope --sweep`
(kusursuz kilit, düz uçan hedef, atıcı ve hedef aynı Mach; 41 s).

**Azami isabet menzili (nmi), kafa kafaya / yan (90°) / kaçan (120°):**
| irtifa | Mach | kafa-kafaya | yan | kaçan | 25 nmi kafa-kafaya |
|---|---|---|---|---|---|
| 15 kft | 0.75 / 0.90 / 1.05 | 20.3 / 22.8 / 25.3 | 16.6 / 18.6 / 20.4 | 12.6 / 13.1 / 13.3 | 0.75, 0.90'da TÜKENME (son Mach 1.50) |
| 25 kft | 0.75 / 0.90 / 1.05 | 29.4 / 32.7 / 36.4 | 24.3 / 26.9 / 29.7 | 18.8 / 19.4 / 19.8 | isabet, son Mach 1.73 / 1.89 / 2.05 |
| 35 kft | 0.75 / 0.90 / 1.05 | 44.0 / 49.0 / 54.0 | 36.7 / 40.5 / 42.5 | 28.7 / 29.6 / 29.9 | isabet, son Mach 2.24 / 2.40 / 2.55 |

**`min_speed_mach` duyarlılığı (25 kft, M0.9), kafa-kafaya / yan / kaçan Rmax:** 0.8 → 57.8/32.9/22.8; 1.0 → 46.0/32.9/22.6;
1.2 → 39.9/31.9/21.8; **1.5 (mevcut) → 32.7/26.9/19.4**; 1.8 → 26.7/22.3/16.6. Eşiği 1.5'ten 1.0'a çekmek kafa-kafaya menzili +%41
artırıyor (yan hedefte +%22).

**Yorumlar:**
1. Zarf İRTİFAYA ÇOK bağlı (kafa-kafaya 22.8 → 32.7 → 49.0 nmi; M0.9), oysa atış yetkisi HER irtifada 35 nmi. Senaryo dağılımı irtifayı
   15–35 kft düzgün çekiyor → savaşların üçte biri füzenin neredeyse işe yaramadığı alçak irtifada.
2. **EVAL-07 yeniden okundu (atıcı irtifa dilimi, % atış; A=35v35 / C=25v25):** <20 kft: isabet 1.0 → 4.3, tükenme 83.8 → 85.1;
   20–30 kft: 7.2 → 8.0, tükenme 71.6 → 72.3; ≥30 kft: 14.0 → 13.3, tükenme 53.1 → 53.8. Yani sabit menzil kapısı "küçük kaldıraç" sonucu
   İRTİFA KARIŞIMININ ORTALAMASIYDI: alçakta 25 nmi bile zarfın dışında (tükenme hâlâ %85), yüksekte kapı zaten gereksiz. **Hipotez (POST-HOC,
   ölçülmedi): atış kapısı sabit değil Rmax(irtifa, hız, aspect)'e oranla olmalı** → 2.3c'de ölçülecek düğüm.
3. Zarf mertebe olarak makul görünüyor (yüksek irtifada ~50 nmi, alçakta ~20 nmi) ama **kaynakla DOĞRULANMADI**; lofting yok (gerçek füze
   daha uzağa gider), `min_speed_mach` bir kabul. Kesin kalibrasyon iddiası YAPILMAZ.
4. **KARAR (madde 3, Zahit):** (a) mevcut değerleri DONDUR ve tezde bir kabul olarak yaz, veya (b) `min_speed_mach`'ı açık kaynak
   menzil mertebeleriyle hizala. Her iki durumda da karar 2.3c'DEN ÖNCE verilip dondurulur — sonra değişirse tüm EVAL sonuçları yeniden
   koşulur (aşağıdan yukarı dondurma ilkesi). Eşiğin `tukenme`ye etkisi büyük: EVAL-09'daki "kaçış kapalı → tükenme %70 → %18"
   bulgusunun büyüklüğü de bu eşiğe bağlı olabilir (yönü değil).

### 13.6 Faz 2.3 — neden yapıyoruz, ne işe yarar, ne bekliyoruz (sade dille)

**Neden?** Elimizdeki betikli komutan ("radar seni kilitleyince kaç") Faz 4'te RL ajanının yeneceği rakip. 8 deneyle gördük ki bu komutan
tek bir ayarla (kaçışı füze görününceye ertele) yenilebiliyor. Zayıf rakibi yenen RL ajanı bir şey kanıtlamaz. Bu yüzden önce GÜÇLÜ ve
SÖMÜRÜLEMEZ bir betikli komutan yazmalıyız.

**Ne işe yarar?** (1) Faz 4'ün "geçilecek eşiği". (2) RL ajanının başlangıç davranışı / davranış klonlama için gösterici. (3) Ölçtüğümüz
kuralların (ne zaman kaç, ne zaman at, hangi açıyla) tek yerde, sınanabilir biçimde toplanması. (4) Tezde "uzman kurallar vs öğrenilmiş
politika" karşılaştırması.

**Ne bekliyoruz?** `BT_v0` (kilit gelince hedefe dön ve at, füze görününce kaç) eski tabanı EVAL-11'deki gibi büyük farkla yenmeli — bu
bizim doğrulamamız. Sonra her düğüm (geri beslemeli crank, irtifa-farkında atış kapısı, notch, drag) ayrı ayrı ölçülüp yalnız İŞE YARAYANLAR
kalır. Kalan ağaç R1/R2/R3 havuzunda hiçbir rakibe karşı sömürülemez olmalı. Bazı düğümler işe YARAMAYABİLİR (EVAL-05/08/11'de tahminlerimiz
üç kez tutmadı); bunu bulgu sayacağız, ağaca eklemeyeceğiz.
