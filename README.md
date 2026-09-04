# Otonom BVR Savaş Pilotu — F-16 / JSBSim

Kademeli (cascade) kontrol mimarisi üzerine kurulu, **Koopman tabanlı öğrenilmiş
dinamik model + Kontrol Bariyer Fonksiyonu (CBF) güvenlik filtresi** ile
pekiştirmeli öğrenme tabanlı savaş uçağı kontrolü.

Ayrıntılı mimari ve tasarım gerekçeleri: **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## Fikir

Uçak kontrolünü tek bir uçtan uca RL bloğuna yıkmak yerine, endüstri
standardı olan **kademeli** yapıyı kurarız:

```
Taktik komutan (gelecek)  →  hedef: nereye, hangi irtifa, hangi hız
        ↓
Güvenlik filtresi (CBF)   →  komutu zarf içine projekte et      10 Hz
        ↓
Dış döngü (SAC)           →  [φ_cmd, γ_cmd, M_cmd]              10 Hz
        ↓
İç döngü (klasik PI)      →  levye ve gaz komutları             60 Hz
        ↓
JSBSim F-16 FLCS          →  uçağın kendi fly-by-wire'ı        120 Hz
```

RL yalnızca **ne manevra yapılacağına** karar verir; manevranın nasıl
gerçekleştirileceği klasik, ispatlanabilir kontrolün işidir.

## Tez katkısı

Güvenlik filtresinin ihtiyaç duyduğu dinamik model **tak-çıkar** bir arayüzün
arkasındadır. Aynı RL, aynı CBF, aynı veri üzerinde üç model karşılaştırılır:

**DMD** (taban çizgisi) → **EDMD** (genişletilmiş / Koopman) → **Deep-Koopman**

## Durum

| | Adım | Durum |
|---|---|---|
| P0 | İskelet, JSBSim köprüsü, trim, Tacview | ✅ |
| P1 | İç döngü + basamak yanıtı kabul testi | ✅ 16/16 |
| P2 | Model arayüzü, DMD + EDMD karşılaştırması | ✅ |
| P3 | Guidance ortamı + SAC | ✅ |
| P4 | CBF komut yöneticisi (eğitim döngüsünde) | ✅ |
| P5 | Deep-Koopman | ⬜ |
| P6 | Robust CBF (model hata sınırı) | ⬜ |
| P7 | Taktik komutan | ⬜ |

### Şu ana kadarki ölçümler

**İç döngü** (4 uçuş koşulu: 15k/M0.7 … 45k/M1.3)

| Test | Sonuç |
|---|---|
| Roll basamağı 0→45° | t_r 0.7–0.8 s, aşım %3–17, kalıcı hata 0.07–0.16° |
| γ basamağı 0→+8° | t_r 1.3–2.4 s, aşım %3–10, kalıcı hata ≈0° |
| Mach basamağı +0.15 | kalıcı hata 0.0001–0.006 |
| Koordineli dönüş 45° / 20 s | irtifa değişimi 27–51 ft |

**Dinamik modeller** (717k eğitim / 239k doğrulama geçişi, 1-adım nRMSE)

| Model | z_dim | nRMSE | Beceri (persistence'a göre) |
|---|---|---|---|
| DMD | 11 | 0.0234 | 40.6 % |
| EDMD-fizik | 30 | 0.0216 | 45.2 % |
| EDMD-poly2 | 66 | 0.0193 | 50.9 % |
| EDMD-fizik+poly2 | 85 | **0.0188** | **52.3 %** |

**Güvenlik / performans** — 100 bölüm × 180 s, bölüm-başı ortalama,
%95 bootstrap güven aralığı (metodoloji için [ARCHITECTURE.md](ARCHITECTURE.md))

Son konfigürasyon (irtifaya bağlı stall bariyeri, bariyer-başına ufuk):

| | Toplam ihlal % | %95 GA | Ödül | %95 GA |
|---|---|---|---|---|
| Klasik güdüm | 1.224 | [0.56, 2.07] | 1915 | [1798, 2021] |
| SAC (kalkansız) | 0.946 | [0.30, 1.76] | **2101** | [2028, 2174] |
| SAC + enerji-farkında CBF | 1.814 | [0.61, 3.32] | 2099 | [1999, 2190] |

Kararlı alt-metrikler:

| | `beta_max` ihlalli bölüm | `nz_min` ihlalli bölüm | Çözücü hatası |
|---|---|---|---|
| SAC (kalkansız) | 4/100 | 33/100 | — |
| SAC + CBF | **0/100** | **20/100** | **233** (önce 3313) |

**Kanıtlanmış:** SAC > klasik güdüm (ödül); kalkan `beta` ihlallerini sıfırlıyor
ve `nz` ihlalli bölüm sayısını üçte bir azaltıyor; kalkanın ödül maliyeti artık
**sıfır** (2099 vs 2101).

**Kanıtlanmamış:** kalkanın `mach_min` (enerji) ihlallerine etkisi. Uzun ufuklu
enerji bariyeri denendi ve **işe yaramadı** — açıklaması aşağıda.

> **Açık problem — ZOH varsayımı uzun ufukta geçersiz.** Filtre "bu komutu 30
> saniye TUTARSAM güvende miyim?" diye sorar. Ama ajan komutu her 0.1 saniyede
> değiştirir. 2 saniyede bu varsayım savunulabilir, 30 saniyede anlamsız: hafif
> bir tırmanışı tutmak güvenlidir, ama art arda tırmanış komutları enerjiyi
> bitirir ve filtre bunu hiç görmez. Doğru çözüm, uzun ufukta tutulan komut
> yerine bir **yedek politika** (backup controller / terminal safe set)
> varsaymaktır — MPC tabanlı güvenlik filtrelerinin standart yapısı.

## Kurulum

```bash
conda create -n bvr_ai python=3.10 -y
conda activate bvr_ai
pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128
pip install -r requirements.txt
```

## Çalıştırma

```bash
python scripts/smoke_trim.py
python scripts/test_inner_loop.py
python scripts/demo_inner_loop.py
python scripts/collect_sysid.py --episodes 600
python scripts/compare_models.py
python scripts/train_guidance.py --steps 1000000 --envs 12 --tag v2
python scripts/eval_guidance.py --model scripted
python scripts/eval_guidance.py --model runs/guidance_v2/sac_final.zip
```

## Teknoloji

JSBSim 1.3 · PyTorch (cu128) · Stable-Baselines3 SAC · CVXPY/cvxpylayers (P4) ·
Tacview ACMI · TensorBoard

`legacy/` altında önceki (Faz 3 / Faz 4) uygulama arşivlenmiştir.

## Okuma listesi

* [Hierarchical RL for Air Combat at DARPA's AlphaDogfight Trials](https://arxiv.org/pdf/2105.00990)
* [A Deep RL Control Approach for High-Performance Aircraft](https://link.springer.com/article/10.1007/s11071-023-08725-y)
* [Autonomous Dogfight Decision-Making with Automatic Opponent Sampling](https://www.mdpi.com/2226-4310/12/3/265)
* [Dogfight Simulation of Autonomous Swarm UAVs Based on MARL](https://www.sciepublish.com/article/pii/955)
