# BVR F-16 — Mimari

Kademeli (cascade) kontrol mimarisi üzerine kurulu, güvenlik filtreli
pekiştirmeli öğrenme ile otonom savaş uçağı kontrolü.

```
┌─────────────────────────────────────────────────────────────┐
│  TAKTİK KOMUTAN            (gelecek — bvr/tactics/)          │
│  radar · kilit · füze · kaçış                               │
│                    ↓  hedef: (X, Y, irtifa, hız)            │
├─────────────────────────────────────────────────────────────┤
│  GÜVENLİK FİLTRESİ         10 Hz   bvr/safety/               │
│  CBF-QP, model: [DMD | EDMD | Deep-Koopman]  ← TAK-ÇIKAR     │
│                    ↓  düzeltilmiş komut                     │
├─────────────────────────────────────────────────────────────┤
│  DIŞ DÖNGÜ (GUIDANCE)      10 Hz   bvr/envs/ + bvr/agents/   │
│  SAC · hata gözlemi → [φ_cmd, γ_cmd, M_cmd]                 │
│                    ↓                                        │
├─────────────────────────────────────────────────────────────┤
│  İÇ DÖNGÜ (KLASİK)         60 Hz   bvr/control/              │
│  γ→ṅ→n→elevator · φ→p→aileron · M→throttle · β→rudder       │
│                    ↓  fcs/*-cmd-norm                        │
├─────────────────────────────────────────────────────────────┤
│  JSBSim F-16 FLCS         120 Hz   (modelin kendi FBW'si)    │
│  roll rate CAS · g-command + α limiter · yaw damper         │
└─────────────────────────────────────────────────────────────┘
```

## Katman sözleşmeleri

### JSBSim FLCS — `f16.xml`'den okundu, `bvr/sim/aircraft.py`'de belgelendi
`fcs/*-cmd-norm` **ham yüzey açısı değildir**:

| Kanal | Anlamı | Ölçek |
|---|---|---|
| `aileron-cmd-norm` | yatış **hızı** komutu | 1.0 ↔ 180 °/s |
| `elevator-cmd-norm` | **g-yükü** + pitch-rate karışımı | −1.0 ↔ +9 g, +0.44 ↔ −4 g |
| `rudder-cmd-norm` | yaw damper girişi | — |
| `throttle-cmd-norm` | ×2 → pos-norm | 0.5 = askeri güç, >0.5 art yakıcı |

FLCS'in kendi **α limiter'ı** 28–30°'de komutu keser. Bu yüzden ayrıca α limiter yazılmadı.

### İç döngü — `bvr/control/inner_loop.py`
Girdi `[φ_cmd, γ_cmd, M_cmd]`, çıktı FLCS komutları. Pitch kanalı ölçümle doğrulanan kinematik üzerinden kapanır:

```
γ̇ = g (n cos φ − cos γ) / V     →     n_cmd = (V γ̇_cmd/g + cos γ) / cos φ
```

`1/cos φ` = yatış telafisi (45° bankta 1.41 g). Nz zarfı bu komutta doğrudan kırpılır.

### Dış döngü — `bvr/envs/guidance_env.py`
Aksiyon `[-1,1]³` → `[φ_cmd ±80°, γ_cmd ±30°, M_cmd 0.55–1.35]`.
Gözlem: **hata** (yön sin/cos, menzil, irtifa, Mach) + kendi durumu + son aksiyon = 18 boyut.
Ödül sınırlı (~[−1, +2.5]), ilerleme-tabanlı, pozitif terimli.

### Model + güvenlik — `bvr/models/`, `bvr/safety/`
Modellenen sistem **kapalı çevrimdir** (F-16 + FLCS + iç döngü), çıplak uçak değil.
`Psi(x)` **her zaman x ile başlar** (`state-inclusive observables`) — bariyerin kaldırılmış uzaya taşınabilmesi için zorunlu; `base.py` bunu çalışma anında denetler.

Ayrık zamanlı CBF: `h(x⁺) ≥ (1−γ)h(x)` → `G·w ≤ rhs`, `base.cbf_rows()`.

## Kararlar ve gerekçeleri

| Karar | Neden |
|---|---|
| CBF dış döngüde, iç döngüde değil | 60 Hz yüzey seviyesinde bağıl derece yüzünden `\|CB\|≈0.01`; 0.1 s'lik komut adımında otorite gerçek |
| `γ_cmd`, `pitch_cmd` değil | θ = γ + α; aynı θ farklı hızlarda farklı tırmanış. Guidance'ın dili γ'dır |
| SB3 SAC, el yazması değil | Katkı SAC değil; otomatik sıcaklık/grad clipping/tanh düzeltmesi bedava ve doğru |
| Model **offline** fit, online değil | Kalıcı uyarım ancak tasarlanmış uyarımla sağlanır; ayrıca model kalitesi RL'den bağımsız ölçülebilir |
| Sabit ölçekleme, VecNormalize yok | Güvenli küme eğitim boyunca yerinden oynamamalı; sonuçlar tekrar üretilebilir olmalı |
| Trim zorunlu | Trim'siz uçak 60 s'de 20.000 ft düşüyor (ölçüldü) |

## Ölçüm metodolojisi (zor öğrenilmiş dersler)

Bu proje sırasında üç ölçüm hatası yapıldı ve düzeltildi. Üçü de sonuçları
ters yönde etkiliyordu; tezde ayrı bir bölüm hak ediyorlar.

**1. Tepe değeri ≠ güvenlik metriği.**
İlk metrik "en kötü tek örnek" (max/min) idi. 18.000 adımlık bir koşuda tek
bir −3.37 g anlık değeri "bariyer tutmuyor" gibi görünüyordu; oysa n < −3 olan
adım oranı %0.01 (≈2 adım) idi. Doğru metrik **ihlal oranı + şiddeti + süresi**.

**2. Örnekleme frekansı.**
Zarf uç değerleri dış döngü sınırında (10 Hz) ölçülüyordu; iki karar
arasındaki aşımlar görünmüyordu. Artık iç döngü alt adımlarında (60 Hz)
tepe tutuluyor. (Ölçüldü: fark küçük — n_max +0.15 g — ama sıfır değil.)

**3. En önemlisi: bağımsızlık varsayımı yanlıştı.**
Zarf ihlalleri **adım seviyesinde bağımsız olaylar değil**. Uçak bir bölümde
yavaş bir duruma girer ve 200–900 adım orada kalır. Adımları bağımsız sayıp
"% ihlal" hesaplamak, etkin örneklem sayısını yüzlerce kat abartır.

Ölçüm: **aynı politika, aynı kalkan, farklı tohum blokları** →

| tohum | toplam ihlal % | `mach_min` % | `nz_min` % |
|---|---|---|---|
| 10000 | 1.272 | 1.230 | 0.041 |
| 20000 | 0.048 | 0.000 | 0.048 |
| 30000 | 0.907 | 0.868 | 0.033 |
| 40000 | 1.742 | 1.719 | 0.022 |
| 50000 | 0.602 | 0.560 | 0.040 |

**36 kat aralık.** `nz_min` kararlı, `mach_min` tamamen gürültü.

Sonuç: metrik birimi **bölümdür**, adım değil; belirsizlik bölümler üzerinden
**bootstrap güven aralığı** ile verilir; ve güven aralığı örtüşen iki
konfigürasyon arasında fark **iddia edilemez**.

## Yol haritası

| | Adım | Durum |
|---|---|---|
| P0 | İskelet, JSBSim köprüsü, trim, ACMI | ✅ |
| P1 | İç döngü + kabul testi | ✅ 16/16 |
| P2 | Model arayüzü, DMD + EDMD, karşılaştırma | ✅ |
| P3 | Guidance ortamı + SAC | ✅ |
| P4 | CBF komut yöneticisi (eğitim döngüsünde) | ✅ |
| P5 | Deep-Koopman | ⬜ |
| P6 | Robust CBF (model hata sınırı) | ⬜ |
| P7 | Taktik komutan arayüzü | ⬜ |

## Çalıştırma

```bash
python scripts/smoke_trim.py                  # trim doğrulaması
python scripts/test_inner_loop.py             # iç döngü kabul testi (16 test)
python scripts/demo_inner_loop.py             # Tacview + grafik
python scripts/collect_sysid.py --episodes 600
python scripts/compare_models.py              # tez karşılaştırma tablosu
python scripts/train_guidance.py --steps 400000 --envs 12 --tag v1
python scripts/eval_guidance.py --model runs/guidance_v1/sac_final.zip
```
