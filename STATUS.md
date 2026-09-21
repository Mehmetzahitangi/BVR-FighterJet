# Durum ve Devam Notu

> Bu dosya, çalışmaya ara verildiğinde nerede kalındığını ve nasıl devam
> edileceğini tutar. Her oturum sonunda güncellenir.

## Son durum

**Aşama:** Faz 1.1–1.5 TAMAMLANDI — BVR savaş katmanı (geometri, radar,
füze, angajman muhasebesi, çok uçaklı simülasyon + Tacview) baştan sona
kuruldu ve ölçüldü. Guidance ve kalkan zaten dondurulmuştu; bu fazda
İKİSİNE DE dokunulmadı (`GuidanceDriver` sadece onları TÜKETİYOR).
**Faz 2.0 TAMAMLANDI** (crank → tepe ATA eğrisi, `scripts/crank_sweep.py`
+ `scripts/pursuit_cost.py`). Yol boyunca iki bulgu çıktı, ikisi de kapatıldı:

1. Guidance saf takip (pure pursuit) kullanıyor, LOS dönme hızından (λ̇)
   habersiz — hedef tam karşıdayken bile (be=0) eğitim aralığının İÇİNDE
   ~34° yatış komutu veriyor. Gerçek angajman ölçeğinde maliyeti ölçüldü
   (`pursuit_cost.py`): önemsiz (zaman +2.3%, yol +0.1%, gimbal payı +42°).
   **Karar: guidance/CBF retrain'i ERTELENDİ**, donmuş katmana dokunulmadı.
   (`HATA_GUNLUGU.md` H-06, `REQUIREMENTS.md` SIM2-08)
2. Tam tarama (9 θ × 3 irtifa × 2 Mach + yön kontrolü, 60 koşu), SIM2-07'nin
   tek-noktalı 35° seçimini düzeltti; sonra **bağımsız bir inceleme bu
   düzeltmeyi de düzeltti**: |ATA| geçici bir aşım yapıp oturmuyor, menzil
   kapandıkça büyümeye devam ediyor — yani "tepe ATA" ölçüm penceresi
   uzadıkça büyüyor (60 s'de 30°→51°, 90 s'de 30°→70°). "35 aşıyor, 30
   aşmıyor" hükmü 60 saniyelik pencerenin eseriymiş. **Doğru çerçeve:
   sabit açı sınırı yok, açı+menzil çifti var** — 35° ~9 nmi'ye, 30° ~6
   nmi'ye, 25° ~5 nmi'ye kadar |ATA| < 55°. Ayrıca sağ/sol crank simetrik
   değil (sağ kırma H-06'nın önyargısıyla güçleniyor).
   **`CRANK_DEG_DEFAULT` 35→30**, gerekçe "35 eşiği aşıyor" değil "30,
   kilidi ~3 nmi daha yakına kadar korur"; 1v1/2v2'de doğrulandı (2v2: 4/4
   imha). Faz 2.3 crank'ı sabit açıyla değil geri beslemeyle sürecek.
   (`HATA_GUNLUGU.md` H-05, `REQUIREMENTS.md` SIM2-09)

**Faz 2.1 — RWR modeli TAMAMLANDI** (`bvr/combat/rwr.py`).
Kilitli karar #4'ün ("füze uyarısı RWR ile") ilk uygulaması: betikli
komutan artık kaçış kararını gerçek füze listesinden değil (omniscient,
eski davranış — `--warning truth` ile hâlâ erişilebilir, regresyon
referansı) gerçekçi bir RWR sinyalinden alıyor (`--warning rwr`,
varsayılan; hem 1v1 hem 2v2'de). Uyarı zinciri üç aşamalı: arama → kilit
→ füze (pitbull + arayıcı konisi) — atıştan pitbull'a kadar füzenin
kendisi hiç görünmez, bu BVR'ın bilgi asimetrisinin ta kendisi.

İlk uygulama kod incelemesinden ve 46/46 testten geçti ama bağımsız bir
inceleme, canlı yolu ayrıca ölçünce üç gerçek hata buldu (kuantizasyon
canlı yola hiç ulaşmıyordu, seviye hiç düşmüyordu, "arama" hiç
beslenmiyordu) — üçü de "mekanizma doğru yazılmış ama devrede değil"
türünden, ÜÇÜ de düzeltildi ve izole testlerle + gerçek 1v1/2v2 koşularıyla
doğrulandı. Bağımsız incelemenin ikinci turu iki eksik daha buldu (asıl
"kilit kesilip arama devam eder" senaryosunun testi yoktu; kuantizasyon
hatası bir birim testiyle yakalanamazdı çünkü kablolamadaydı, kaynak-tarama
testi eklendi) — ikisi de tamamlandı. **Üçüncü tur: mutasyon testi**
(kuantizasyonu kapat, füzeyi pitbull yerine atış anından besle) — İKİSİ
DE 10/10'u hiç etkilemedi, çünkü mevcut testler head-on geometri (kerteriz
hep 0°) kullanıyordu ve "atış görünmez" testi atıştan sonra tek tik
ilerliyordu. 2 test daha eklendi, aynı mutasyonlar TEKRAR uygulanıp bu
sefer yakalandığı doğrulandı (dosyalar md5 ile geri yüklendi). `test_rwr.py`
**12/12 geçiyor** (`bvr/combat/tests` toplamı **58/58**). Genel ders
`HANDOFF.md` tuzak 51'e işlendi: "test geçiyor" güvence değildir. Tam
hikaye: `HATA_GUNLUGU.md` H-07, `REQUIREMENTS.md` RWR-01/02/03.

**Bilinen sınırlama:** 2v2'de bir uçağın RWR'ı kendi kanadının radarından
da "kilit" alabilir (radar takım ayrımı yapmıyor, SIM2-06'nın bir uzantısı)
— düzeltilmedi, ölçülen koşularda sonuç bozukluğu gözlenmedi.

**Kullanıcı kendi elinde doğruladı:** `--warning truth` vs `rwr` A/B'sinde
TEK koşuda sonuç değişti (truth: blue hayatta; rwr: karşılıklı imha,
~1.1s'lik gecikme farkı yüzünden) — gerçek ama n=1, istatistik değil
(RWR-03). Bunu ayırt etmek tam olarak Faz 2.2'nin işi.

**Faz 2.2 — değerlendirme düzeneği YAZILDI; ilk koşu geçersizdi, düzeltilmiş koşu TAMAM (EVAL-03).**
`bvr/combat/duel.py` (paylaşılan angajman döngüsü — `bvr_1v1_smoke.py`
buradan çağırıyor, `crank_sweep.py`/`pursuit_cost.py`'nin `pick_target`
import'ları da yeni konuma güncellendi) + `scripts/eval_commander.py`
(rastgele senaryo, aynalama, ortak rastgele sayılar/CRN, Wilson GA,
McNemar). Mimari, istatistik fonksiyonları (bilinen referans değerlerle
doğrulandı) ve `--self-check` (10 tohum × 2 ayna × 2 kol = 40 koşu, HIZLI,
onay gerekmez) TAMAMLANDI ve 3/3 geçti. Yol boyunca küçük ama gerçek bir
tuzak bulundu: `DuelResult`'ın otomatik `__eq__`'i `wall_time_s`'i (asla
aynı çıkmayan duvar-saati süresi) de karşılaştırıyordu, tekrar
üretilebilirlik testini HER ZAMAN yanlış şekilde düşürüyordu — düzeltildi
(`HATA_GUNLUGU.md` H-08). Ayrıca `Aircraft`'ın ölü/rastgele
`seed=abs(hash(name))%1000`'i temizlendi, artık senaryo tohumundan
deterministik türetiliyor. Tam hikaye: `REQUIREMENTS.md` EVAL-01.

**2v2 ayrışmaya karşı korundu (EVAL-01b).** `run_duel()` 1v1'e sabit
kaldı (2v2'ye genişletmek Faz 6'nın işi), ama `bvr_2v2_smoke.py` artık
`Aircraft`/`pick_target`/sabitleri `duel.py`'den import ediyor — kendi
kopyası yok, komutan/crank değişince geride kalamaz. Refaktör öncesi/sonrası
2v2 çıktısı `diff` ile birebir aynı (42 olay). `test_duel.py` (8 test)
kopyanın geri gelmesini kilitliyor, mutasyonla sınandı. `bvr/combat/tests`
toplamı **108/108** (EVAL-02: test_duel 9/9b/10; EVAL-03b: `test_eval_stats.py` 6 + engagement `test_10`; EVAL-04/06: `test_duel_gate.py` 12; `test_duel_side_counts.py` 4). `pytest.ini` eklendi (osqp uyarı gürültüsü süzüldü).

**İlk tam koşu (n=200, 800 savaş, 259 s) yapıldı — ama ÖLÇÜM ARACI
üç yerden hatalıydı (EVAL-02, H-09, tuzak 52).** (1) Koltuk önyargısı:
mavi, aynı modelin kendisine karşı bile karar verilenlerin %70'ini
kazanıyordu (mavi başlangıç |ATA| 8.6° vs kırmızı 30.3°) → mavinin yönü de
artık aynı dağılımdan çekiliyor. (2) `nz_min` işareti ters okunuyordu (ham
`st.nz` düz uçuşta −1) → `g = −st.nz`, `nz_max` eklendi. (3) Öz-denetim
kriteri beraberlikleri saymıyordu → geometri simetri + karar verilenlerde
koltuk payı kontrolü, tam rapora yerleşik uyarı. İlk koşunun sayıları
(truth 0.388 / rwr 0.367, McNemar 13:5, p=0.096 — 400 çiftin yalnız 18'i
uyumsuz) asimetrik dağılımda ölçüldü, **atıf yapılmayacak**.

**Faz 2.2 KAPANDI (EVAL-03, düzeltilmiş araçla tam koşu, 800 savaş).** Koltuk dengesi düzeldi (mavi payı
0.49/0.50). truth 0.253 [0.212, 0.297] vs rwr 0.223 [0.184, 0.266]; senaryo-kümelenmiş eşleşmiş test 18:6,
p=0.023 — RWR'nin bedeli küçük ama gerçek. Savaşların ~%50'si sonuçsuz bitiyor (mühimmat tükendi).
Bağımsız inceleme (EVAL-03b) sayıları doğruladı; araca kümelenmiş test, `iska` zinciri testi ve senaryo
sütunları eklendi (H-10, H-11). Ham veri: `runs/eval_truth_vs_rwr_v2.csv`.

### Faz 2.3 ÖN ÖLÇÜMLERİ (EVAL-04…11) — Faz 2.3'ün KENDİSİ (davranış ağacı komutan) HENÜZ BAŞLAMADI

> `bvr/agents/scripted_commander.py` YOK. Aşağıdakiler, 2.3'ün NASIL tasarlanacağını belirleyen ölçümlerdir.
> (Önceki sürümde bu bölüm yanlışlıkla "Faz 2.3 açıldı" diye etiketlenmişti ve paragraflar iç içe geçmişti.)

| deney | soru | sonuç | davranış ağacına etkisi |
|---|---|---|---|
| EVAL-04/05 | Atış menzil kapısı, TEK taraf (mavi 25 / kırmızı 35) | tahmin ÇÜRÜDÜ: kazanma aynı (p=0.90), mavi kaybı 89→120 (25:1) | Menzil kapısı GİRMEZ |
| EVAL-06/07 | Kapı İKİ tarafa (25v25), taze tohum | toplam isabet +%23 (p=7.5e-7) ama kazanç kör füzelerin çöküşünden, tükenme %71'de DEĞİŞMEDİ (H-13) | Kapı küçük kaldıraç (+1.3 puan) |
| EVAL-08 | EVAL-05 B kolunun taze tohumda tekrarı | tekrarlandı (7:53 birleşik); "kaçış–kör eşleşmesi" mekanizması çürüdü (H-14) | Geç atan yarışı kaybeder |
| EVAL-09/10 | Kaçış tamamen kapalı (tanı) + H-15 kapanışı | ≥1 isabetle biten savaş %57.8 → %100; komutan savaşın %96'sını kaçışta geçiriyor; koltuk uyarısı şans (H-15) | Kaçış, füzeleri yenen ana şey |
| **EVAL-11** | Kaçış tetikleyicisi gecikmesi (T = 0 / 15 s / ∞) | **T=∞ (yalnız aktif arayıcıda kaç): net skor −2 → +144 (p=8e-15)**; kayıp yalnız +%33; iki tahminim de YANLIŞ (H-16) | **Mevcut "kilitte kaç" tabanı SÖMÜRÜLEBİLİR; kaçış tetikleyicisi fuze-tabanlı olmalı** |

**2.3'e girdi olan bulgular:** (1) atış: kilit gelince en erken at, menzil kapısı YOK; (2) kaçış: radar
kilidinde değil aktif arayıcı (fuze) görününce başlat — mevcut taban zayıf; (3) crank: sabit açı yerine
|ATA| geri beslemesi (SIM2-09); (4) kaçış geometrisi (crank vs beam/notch) denenmedi.

**2.3 ÖNCESİ HAZIRLIK YAZILDI:** `REQUIREMENTS.md` §13 (kontrol listesi, 2.3/2.4/tez notları, kalibrasyon düğmesi, 2.3'ün "neden/ne işe yarar/ne bekliyoruz" yazısı). Yeni bulgular: füze zarfı irtifaya çok bağlı (kafa kafaya Rmax 22.8/32.7/49.0 nmi @15/25/35 kft) ve `min_speed_mach=1.5` bir KALİBRASYON DÜĞMESİ (1.0 → 46 nmi); sabit menzil kapısı etkisi irtifa dilimlerinde farklı (H-17). **Çalışma modu: öğretici (Zahit kodu yazar).**

**Sıradaki:** Faz 2.3'ü BAŞLAT (davranış ağacı komutan, `scripted_commander.py`). Betikli-vs-betikli politika
matrisi (T ∈ {0, 15, ∞} × {0, 15, ∞}) Faz 2.4'ün ("rakip varyantları + betikli-vs-betikli tablosu") işidir.
Faz planı: aşağıda "Faz planı (2–7)". PPO komutanı Faz 3'te.

### BVR kararları kilitlendi (2026-09-04)

| # | karar |
|---|---|
| 1 | Füze: **3-DOF nokta kütle + PN** |
| 2 | Radar: **RCS + Doppler/notching dahil** |
| 3 | Altyapı **2v2'ye hazır**, eğitim **1v1**'den |
| 4 | Füze uyarısı **RWR** (MAW değil — BVR'da alev görünmez) |
| 5 | **IRST faz 2'ye ertelendi** (notching'i yener, temel taktiği bozar) |
| 6 | **4 AMRAAM** |
| 7 | **Füze kütlesi modellenecek** — ölçüldü, sözleşme korunuyor |

Ayrıntı ve gerekçeler: `REQUIREMENTS.md` → "BVR fazı — KİLİTLİ KARARLAR".

**Mühimmat kütlesi ölçümü (`scripts/payload_check.py`):** 5 konfigürasyonun
hepsinde **14/14 + 14/14**. En ağır durumda (25.942 lb, eğitim üst sınırının
%5.5 üstünde) en kötü irtifa hatası **109 ft** — referanstan bile küçük.
Guidance yeniden eğitilmeyecek.

**⚠️ Yan bulgu — BVR izleme listesine eklendi.** `COMBAT_WEIGHT_LB = 25000`
bariyerin varsaydığı "en ağır durum"du; 4 AMRAAM + tam yakıt 25.942 lb ile
bunu 942 lb aşıyor. Etki **yalnızca 10 kft'te**: bariyer yüklü uçağı 0.0078
Mach kapsamıyor (15 kft ve üstünde pay rahat). Uçak stall'a girmiyor —
manevra payı 1.25× → 1.22×'e düşüyor. Ayrıca doğrusal fit 10 kft'te
varsayılan ağırlıkta bile 0.0017 kısa kalıyor, yani sorun kısmen fitten
geliyor. **Komutan zamanının önemli kısmını 15 kft altında geçirirse
yeniden değerlendir.** Detay: REQUIREMENTS.md.

### Seçilen model

```
runs/reward_r3_both/sac_1999968_steps.zip
```

Konfigürasyon: `configs/reward/r3_both.yaml` (2M adım, tohum 0)
Kalkan: `data/models/edmd_physics.pkl` (donuk)

### Kabul kriterleri (n=200, 3 tohumda doğrulandı)

| kriter | kabul | tohum 0 | aralık (3 tohum) | |
|---|---|---|---|---|
| GUI-02 seyrüsefer verimi | ≥0.85 | 0.833 | 0.813–0.833 | ❌ |
| GUI-03 varışta irtifa | ≥0.85 | 0.927 | 0.863–0.927 | ✅ |
| GUI-04 varışta mach | ≥0.80 | 0.842 | 0.815–0.845 | ✅ |
| GUI-05 ikisi birden | ≥0.70 | **0.795** | 0.741–0.795 | ✅ |
| GUI-06 erken sonlanma | <%3 | %1 | %0–1 | ✅ |
| GUI-11a komut tutma irtifa | ≥6/7 | **14/14** | üçünde de 14/14 | ✅ |
| GUI-11b komut tutma mach | ≥6/7 | **14/14** | üçünde de 14/14 | ✅ |

Yedide altı. GUI-02 üç tohumda da başarısız — yani konfigürasyonun gerçek
bedeli, gürültü değil. **Eşik gevşetilmedi.**

### Bu turda ne oldu (özet)

1. 8M × 3 tohum eğitim **başarısız**: 2M'dekinden kötü (0.540 → 0.316).
2. Kök neden ölçüldü: kabul kriterine bağlı ödül = getirinin **%0.26'sı**.
   `ep_rew_mean` 1.5M'de doyuyor, kalan adımlar kriteri kısıtlamayan %99.7'yi
   optimize ediyor.
3. Ölçüm sorunu: 60 bölümlük bloklar arası fark ~0.10. Kabul ölçümü n=200.
4. Altı ödül konfigürasyonu denendi (r1–r5 + taban). `r3_both` kazandı.
5. Üç tohumla doğrulandı.

Tam analiz: `REQUIREMENTS.md` → "Ödül–kriter uyumsuzluğu".
Yayınlanan özet sayfa: https://claude.ai/code/artifact/8868b325-322a-4bcb-aaf5-92bda68c239d

### Bu turda eklenen/düzeltilen kod

- `bvr/agents/train_guidance.py` → **`BestByCaptureQuality`**: 250k adımda bir
  kabul kriterini ölçüp `sac_best.zip` saklar. **Asgari bacak şartı vardır** —
  ilk sürümde yoktu ve eğitimin başında 1/1 = 1.000 ölçüp seçim donuyordu.
- `bvr/config.py` → `eval_every`, `eval_n_ep` alanları.
- `scripts/reward_whatif.py` → bir ödül config'ini **denemeden önce** kalite
  payını ölçer (aynı yörüngeler, farklı ağırlıklar).
- `scripts/reward_compare.py` → tüm kontrol noktalarını tarar; `sac_best`'e
  güvenmez.
- `scripts/mission_eval.py --seed0` → tutulan blokta ölçüm.
- `scripts/command_hold_test.py` → **14 dengeli manevra** (2 tutma, 4 tırmanış,
  4 alçalma, 2 hız, 2 birleşik). Eski 7 durumluk küme tırmanışları yetersiz
  örnekliyordu.
- `scripts/safety_eval.py --model --shield-model --no-shield --seed0` → tek
  model modu.

### Güvenlik kalkanı — DONDURULDU

Konfigürasyon (kilitli): `data/models/edmd_physics.pkl` · γ = 0.1 · yumuşak
mod · ufuklar kalkanın kendi varsayılanı · **eğitim döngüsünün içinde**.

Seçilen model üzerinde aynı-politika ablasyonu (150 bölüm):

| | kalkanlı | kalkansız |
|---|---|---|
| toplam ihlal % | 0.057 [0.027, 0.097] | 0.275 [0.027, 0.652] |
| ihlalli bölüm | 24/150 | 23/150 |
| ödül | 2418 [2319, 2512] | 2501 [2401, 2599] |

**Hiçbir bariyerde anlamlı iyileşme gösterilemedi.** Oran 5 kat düşük ama
GA'lar örtüşüyor; ihlalli bölüm sayısı aynı. Kalkan tehlikeli duruma girmeyi
engellemiyor, **çıkışı kısaltıyor**. Ödül maliyeti yok.

Kalkan yine de kalıyor: bedeli yok, döngünün içinde eğitildi (sökülemez) ve
asıl sınavı BVR'da — komutan çok daha agresif komut verecek.

**SAF-10 — kalkanın SINIRI (savunulabilir tek iddia):** komut seviyesinde
zarf ihlali üreten girdileri filtreler; 60 Hz'de gerçekleşen dinamik ve
atmosferik geçici aşımları **engellemez**. Ölçülen en kötü geçici −4.581 g
(0.1 s). "Kalkan zarfı garanti eder" **denemez**.

**Ertelenen düzeltme:** doğru çözüm yeri iç döngüde rüzgâr darbesine karşı g
sınırlama, ya da 60 Hz'de çalışan bir filtre. İkisi de dondurulmuş katmanları
açmayı gerektirir, bu fazın kapsamı dışında.

## BVR ilerlemesi

| faz | ne | durum |
|---|---|---|
| 1.1 | Angajman geometrisi (`bvr/combat/geometry.py`) | ✅ 4/4 test |
| 1.2 | Radar (`bvr/combat/radar.py`) | ✅ 20/20 test |
| 1.2b | Kilit gecikmesi (RAD-09/10/11) | ✅ dahil |
| 1.3 | Füze (PN güdüm, 3-DOF) | ✅ (46 testin bir kısmı; ENG-10: dt-yakınsama için 50 Hz alt-adım) |
| 1.4 | Angajman muhasebesi (atış yetkisi/mühimmat/olay günlüğü) | ✅ |
| 1.5a | İki JSBSim örneği arası sızıntı testi | ✅ sızıntı yok — asimetrik testle doğrulandı (commit'li test hâlâ simetrik, SIM2-07) |
| 1.5b | `guidance_shared` çıkarımı + `GuidanceDriver` (fizik-sadece sürücü) | ✅ `GuidanceEnv` ile <1e-11 eşdeğer |
| 1.5c | İlk uçtan uca 1v1 (`scripts/bvr_1v1_smoke.py`) | ✅ crank 35°: pitbull t=43.3 s, karşılıklı isabet t=62.2 s, 0 kor |
| 1.5d | Tacview çok-nesne kaydı (`ACMIRecorder`) | ✅ |
| 1.5e | 2v2 (`scripts/bvr_2v2_smoke.py`) | ✅ 2 imha; 16 atışın 6'sı `hedefsiz` (overkill), 8'i kor |
| 1.5f | crank açısı + füze kütlesi düzeltmesi (SIM2-07) | ✅ bağımsız olarak doğrulandı (2026-09-11) |

`bvr/combat/tests` toplam **46/46** geçiyor. Ayrıntı ve ölçüm sonuçları:
`REQUIREMENTS.md` → §RAD/MSL/ENG/SIM2.

**Faz 2'ye taşınan girdiler (SIM2-07):**
- **Etkili crank sınırı ölçüldü (Faz 2.0'da kapandı, SIM2-09).** "~40°"
  hipotezi yanlıştı: sabit bir açı sınırı YOK. |ATA| menzil kapandıkça
  büyüdüğü için her açı belli bir menzile kadar güvenli — 35° ~9 nmi'ye,
  30° ~6 nmi'ye, 25° ~5 nmi'ye kadar |ATA| < 55°. `CRANK_DEG_DEFAULT = 30`.
  Faz 2.3'te sabit açı yerine geri besleme (|ATA| eşiği) kullanılacak.
- **Hedef paylaşımı (sorting) → Faz 6.** 2v2'de kanatlar aynı "en yakın
  düşmanı" seçip aynı hedefe yığılıyor — 16 atışın 6'sı boşa. Faz 2 1v1
  olduğu için kol uçuşu fazına bırakıldı.
- **Füze kütlesi canlı yolda uygulanıyor** (`GuidanceDriver.set_payload`):
  kalkışta 24.199 lb, atış başına −335 lb.

**Ayarlanacak denge parametreleri (fiziksel sabit DEĞİL):**
`lock_delay_s = 2.5` ve `coast_s = 4.0` birlikte notching'in gücünü
belirliyor. Gerekçeli başlangıç tahminleri; ajanlar ortaya çıkınca ölçülüp
ayarlanacak. Detay: `REQUIREMENTS.md` → RAD-09/10.
Ayrıca `MissileConfig.datalink_memory_s = 5.0` — 10.0'a çıkarılıp
ÖLÇÜLDÜ (MSL-09), fayda sıfır + gerçek taktik maliyet bulununca 5.0'a
GERİ ALINDI (bkz. HANDOFF.md tuzak 32'nin yeni bir örneği).

**Ertelenen:** yeniden kilitlenme gecikmesi (`reacquire_delay_s`). Gerçek
radarda tekrar kilit sıfırdan aramadan hızlıdır; modelde yok. Notching fazla
güçlü çıkarsa ilk başvurulacak ayar.

**⚠️ DÜZELTİLMİŞ BULGU (SIM2-07) — 1.5c/1.5e'de "hepsi kor" yorumu
EKSİKTİ.** İlk yorum: basit "düşman ateş etti mi anında 90° kaç" kuralı
herkesi anında kaçırıp kendi füzesini desteksiz bırakıyor. Bağımsız bir
inceleme ölçtü ki asıl sebep bu DEĞİL (ya da sadece bu değil): 90°'lik
kaçış, radar gimbal sınırını (60°) aşıp **atıcının kendi kilidini**
kırıyordu. İKİNCİ, ayrı bir hata daha vardı: füze kütlesi (`Engagement.
fire()`'daki deneme) hiçbir zaman gerçek JSBSim durumuna ulaşmıyordu
(`FlightState`'te öyle bir alan yok, `combat_state` her adım yeniden
üretilen bir kopya). İkisi düzeltildi: `--crank-deg` parametresi
(varsayılan 35°) + `GuidanceDriver.set_payload()` (gerçek JSBSim
ağırlığı, `payload_check.py` yöntemiyle). Sonuç: 1v1'de KARŞILIKLI
İSABET (t=62.2s, iki taraf da imha), 2v2'de karışık sonuç (bazı çiftler
isabetle, bazıları hâlâ `"kor"` ile bitiyor). "Füzeni desteklemek için
dönük kalman lazım ama dönük kalırsan sen de hedefsin" ödünleşmesi hâlâ
gerçek ve hâlâ Faz 2'nin işi — ama artık betik bunu GERÇEKTEN test
edebiliyor, önceden gimbal aşımı yüzünden hiç sınanamıyordu. Ayrıntı:
`REQUIREMENTS.md` → SIM2-07.

## ⚠️ BVR'A BAŞLARKEN İLK OKUNACAK: komutan arayüzü kuralı (TAC-08)

**Komutanın yön komutu, sanal hedef olarak 5–25 nmi arasına konacak.
40 nmi ve ötesi YASAK.**

Güdüm katmanı yön komutu anlamaz, **hedef noktası** anlar. Komutanın "şu
yöne dön" komutunu sanal bir hedefe çevirirken "hiç varmasın diye uzağa
koyayım" demek doğaldır ve **yanlıştır**:

| sanal hedef menzili | yatış std | limit çevrimi |
|---|---|---|
| 200 nmi | 37.3° | var (12.7 s) |
| 40 nmi | 30.5° | var (12.4 s) |
| **25 nmi** | **6.4°** | **yok** |
| 15 nmi | 14.4° | yok |
| *eğitim aralığı* | *3.3–14.8 nmi* | — |

Uzak hedefte kerteriz uçağın yönüne duyarsız kalır, kurs döngüsünün doğal
sönümlemesi kaybolur, politika sönümsüz çevrime girer (yatış ±60°, kerteriz
hatası yalnızca ±10°, gecikmeli korelasyon r = −0.949).

Bu, kullanıcının Tacview'de "uçak sürekli sağa sola yatıyor" gözlemi
sayesinde bulundu. `command_hold_test.py` 200 → 30 nmi düzeltildi; GUI-11
**14/14 + 14/14 korundu**, sapmalar 33 ft → 5–6 ft'e indi.

Detay: `REQUIREMENTS.md` → TAC-08.

## Faz planı (2–7)

Sıra değişmedi (2026-09-11 gözden geçirildi). Guidance ve kalkan tüm
fazlarda DONUK.

| faz | ne | çıktı / kabul |
|---|---|---|
| 1 | ~~Savaş katmanı (geometri, radar, füze, muhasebe, çok uçaklı sim)~~ | ✅ Faz 1.1–1.5 |
| **2** | **Betikli taban (öğrenme yok)** | `bvr/agents/scripted_commander.py` + betikli-vs-betikli kazanma oranı |
| 3 | Komutan ortamı (gözlem/aksiyon, 2 Hz, PPO) | Gym ortamı |
| 4 | 1v1 eğitim, betikli rakip havuzuna karşı | betikli komutanı geçmek, güven aralıkları örtüşmeyecek |
| 5 | Self-play (betikli + dondurulmuş eski sürümler havuzu) | — |
| 6 | İkili kol uçuşu: betikli kanat → MARL | hedef paylaşımı (sorting) burada |
| 7 | Sunum: Tacview/FlightGear videosu, README, LinkedIn | — |

**Faz 2 alt adımları** (Faz 1 bulgularıyla genişletildi):

| adım | ne | çıktı |
|---|---|---|
| 2.0 | Crank → tepe ATA eğrisi (izole ölçüm) | ✅ `crank_sweep.py`/`pursuit_cost.py`; komutan sabiti **30°** (gerekçe: 35°'e göre kilidi ~3 nmi daha yakına kadar korur — "35 aşıyor, 30 aşmıyor" ilk hükmü ölçüm penceresinin eseriydi, SIM2-09); SIM2-08 (pure pursuit) bulundu, maliyeti önemsiz, retrain ertelendi |
| 2.1 | **RWR modeli** (spike / atış görünmez / pitbull'da yeni tehdit) + testler | ✅ TAMAMLANDI — `bvr/combat/rwr.py` + 1v1/2v2 bağlantısı + `test_rwr.py` (12/12, mutasyon testiyle doğrulandı); 3 hata bulunup düzeltildi (H-07); kullanıcı smoke ile doğruladı (RWR-03) |
| 2.2 | Değerlendirme düzeneği: rastgele geometri, n=200, Wilson GA + McNemar; kazanç/kayıp/berabere, `kor`, `hedefsiz`, **nz_min** | ✅ KAPANDI — düzeltilmiş araçla tam koşu (EVAL-03): truth 0.253 vs rwr 0.223, p=0.029 |
| 2.3 | Betikli komutan, davranış ağacı (yaklaş, ateş, crank, notch, drag, yeniden gir) | ⬜ **BAŞLAMADI** (`bvr/agents/scripted_commander.py` yok). Ön ölçümler EVAL-04…11 TAMAM ve tasarımı belirledi (yukarıdaki bölüm) |
| 2.4 | Rakip varyantları (agresif / temkinli) + betikli-vs-betikli tablosu | Faz 4'ün geçilecek eşiği, Faz 4–5 rakip havuzu |

**Neden 2.1 (RWR) şart:** kilitli karar #4 "füze uyarısı RWR ile" diyor,
ama RWR hiç yazılmadı. Smoke'lar kaçış kararını **gerçek füze listesinden**
alıyor (`bvr_1v1_smoke.py:160`), yani uçak füzeyi atıldığı anda "görüyor".
Bu, MAW'ı reddetme gerekçemizin ta kendisi. Betikli taban her şeyi bilirse
Faz 4'teki "RL tabanı geçti" karşılaştırması adil olmaz. İkisi AYNI bilgiyi
görmeli.

**Faz 3'e şimdiden işlenen düzeltmeler:**
- Gözlem: "füze durumları" = **kendi füzelerimin durumu + RWR uyarıları**.
  Düşman füzesinin gerçek konumu gözleme GİRMEZ.
- Aksiyon: istikamet komutu 5–25 nmi uzaklığa sanal hedef olarak çevrilir
  (TAC-08); crank açısı Faz 2.0'da ölçülen sınırla kırpılır.

Ayrıntılı devir notları (nelerin bittiği, nelerin Faz 2'yi beklediği):
`HANDOFF.md` §8.

**Guidance katmanının üst katmana verdiği sözleşme:** komut sabit tutulduğunda
irtifa ±184 ft, Mach ±0.019 içinde kalır; salınım yoktur (σ ≤ 33 ft). Komutan
bu sözleşmeye güvenerek tasarlanabilir.

### Stres testi — BVR öncesi son karar (2026-09-03)

**Soru:** komutan devreye girince zarf ihlalleri patlar mı? İç döngüye
BVR'dan önce dokunmalı mıyız?

**Yöntem:** komutan eğitilmeden, komut dağılımı betikli 2 Hz bir komutanla
taklit edildi (`scripts/stress_commander.py`), üç agresiflik seviyesi,
80'er bölüm.

| seviye | komut/bölüm | ihlalli bölüm | nz_min oranı | en kötü |
|---|---|---|---|---|
| nominal | 10.3 | 6/80 | 0.000 [0.000, 0.000] | −3.296 g |
| agresif | 18.3 | 22/80 | 0.001 [0.000, 0.002] | −3.867 g |
| aşırı | 31.4 | 46/80 | 0.002 [0.001, 0.003] | −4.194 g |
| *hedef yakalamalı ortam* | — | 24/150 | *0.042* | *−4.581 g* |

**Karar: hiçbir değişiklik yapılmadan BVR'a geçiliyor.** Eşik (0.084)
hiçbir seviyede aşılmadı — 40 kat marj var.

**İki hipotez kurduk, ikisi de yanlış çıktı — üçüncüsü doğrulandı.**

1. *"Agresiflik → ihlal."* İlişki var ama zayıf (0.000 → 0.002).
2. *"İhlaller varış öncesi hassasiyet düzeltmesinden geliyor."*
   `violation_where.py` ile **çürütüldü**: ihlallerin yalnızca %2'si
   yakalama yarıçapının iki katından yakın; medyan menzili tüm adımların
   medyanıyla neredeyse aynı (6.51 vs 6.04 nmi).
3. *"İhlaller yatık alçalmada oluşuyor."* **Doğrulandı:**

| | ihlal anında | tüm adımlar |
|---|---|---|
| yatış (medyan) | 55.2° | 33.2° |
| uçuş yolu açısı | −6.3° | −0.1° |
| irtifa hatası | −3789 ft (hedefin üstünde) | +78 ft |
| alçalma (γ < −5°) | %59.4 | %13.9 → **4.3×** |
| yatış>45° + alçalma | %35.8 | %10.1 → **3.5×** |

Mekanizma iç döngü formülünde: `n = (V·γ̇/g + cos γ) / cos φ`.
55° yatışta `1/cos φ` çarpanı komutu 1.74 kat büyütür.

**AÇIK SORU:** stres testinin neden 20 kat düşük çıktığı açıklanamadı.
Uydurma bir açıklamayla doldurulmadı.

**Elenen müdahaleler:** bariyeri −2.7'ye çekmek ve sert mod, komut
seviyesinde çalıştıkları için yanlış ilaç. Kalanlar (iç döngü g sınırlama,
60 Hz filtre) dondurulmuş katman açmayı gerektirir ve ölçüm bunu haklı
çıkarmıyor.

**Kararın sınırı:** betikli komutan, öğrenilmiş komutanın yaklaşık
taklididir. Öğrenilmiş bir komutan daha kötü komut dizileri bulabilir.
Karar "sorun yok" değil, **"şimdi müdahale gerekçesi yok"**tur.

### BVR fazında İLK İZLENECEK METRİK

```bash
python scripts/stress_commander.py <model> -n 80 --level agresif
python scripts/safety_eval.py --model <model> -n 150     # ikincil
```

**Referans — MUHAFAZAKÂR (yüksek) uç kullanılır:**

| kurulum | oran | en kötü |
|---|---|---|
| betikli komutan, agresif | 0.001 [0.000, 0.002] | −3.867 g |
| hedef yakalamalı ortam | **0.042 [0.023, 0.062]** | **−4.581 g** |

| izleme eşiği | değer |
|---|---|
| nz_min ihlal oranı | **0.084** |
| en kötü geçici derinlik | **−4.8 g** |

**Referansı 0.001'e indirme kararı GERİ ALINDI.** Gerekçesi "BVR kullanımı
stres testine benzer" idi ve bu, çürütülen mekanizmaya dayanıyordu. Gerçek
mekanizma yatık alçalma olunca beklenti tersine döner: **BVR'da yatık
alçalma boldur** (füze kaçınma, enerji yönetimi, savunma manevraları).
BVR, stres testinden daha iyi değil daha kötü olabilir.

Eşik aşılırsa sırayla değerlendir:
1. Komutanın ödülüne zarf yaklaşma cezası
2. İç döngüde g sınırlama (dondurulmuş katman açılır → guidance yeniden
   ölçülür; GUI-11 korunuyorsa komutan etkilenmez)
3. 60 Hz filtre (mimari değişikliği; SAF-09 gereği guidance yeniden eğitilir)

## İzleme

```bash
tensorboard --logdir runs/tb
```
