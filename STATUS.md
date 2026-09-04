# Durum ve Devam Notu

> Bu dosya, çalışmaya ara verildiğinde nerede kalındığını ve nasıl devam
> edileceğini tutar. Her oturum sonunda güncellenir.

## Son durum

**Aşama:** 3 — gerçek ölçekte guidance eğitimi **TAMAMLANDI, model SEÇİLDİ**
**Sıradaki:** guidance + kalkan dondurulup BVR altyapısına geçiş

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

## Sonraki faz: BVR altyapısı

1. Radar modeli, füze modeli, çok uçaklı simülasyon
2. Taktik komutan (PPO, 2 Hz) — guidance DONUK
3. İkili kol uçuşu: scripted kanat → MARL
4. Sunum: Tacview/FlightGear videosu, README, LinkedIn

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
