# Teknik Notlar — Terimler, Konular ve Proje Günlüğü

> İki bölümlü bir referans. **Bölüm A** projede geçen her teknik terimi ve
> araştırılacak konuyu toplar. **Bölüm B** projeyi sırasıyla nasıl kurduğumuzu
> anlatır — "önce şunu yaptım, bunun için şu dosyayı yazdım" diye anlatabilmek
> için.
>
> İşaretler: ✅ kullanıldı ve çalışıyor · ⚠️ denendi, sonuç zayıf ·
> 📋 gelecek fazda · 🔬 araştırılacak

---

# BÖLÜM A — TERİMLER VE KONULAR

## A1. Uçuş dinamiği ve simülasyon

| terim | ne demek | projede |
|---|---|---|
| **JSBSim** | Açık kaynak uçuş dinamiği motoru (FDM). Uçağın aerodinamiğini, motorunu, kütle dağılımını diferansiyel denklemlerle çözer. | ✅ F-16 modeli, 120 Hz |
| **FDM** (Flight Dynamics Model) | Uçağın fiziğini hesaplayan katman. Kontrol yasası değil, uçağın kendisi. | ✅ |
| **FLCS** (Flight Control System) | Uçağın kendi uçuş kontrol bilgisayarı. F-16 *fly-by-wire*'dır: pilot yüzeyleri değil, **komut** verir. | ✅ JSBSim içinde |
| **Trim** | Uçağı dengeli uçuş durumuna oturtma. Kuvvetler ve momentler sıfırlanır. | ✅ zorunlu — trimsiz uçak 60 s'de 14–23 bin ft kaybediyordu |
| **α (hücum açısı)** | Kanat kirişi ile bağıl rüzgâr arasındaki açı. Çok büyürse **stall**. | ✅ limit 22°, sonlandırma 26° |
| **β (yana kayma açısı)** | Uçağın burnu ile gidiş yönü arasındaki yatay açı. | ✅ limit 10°, sonlandırma 15° |
| **γ (uçuş yolu açısı)** | Uçağın gerçekte tırmandığı/alçaldığı açı. **θ = γ + α** | ✅ dış döngünün komut ettiği büyüklük |
| **θ (pitch/yunuslama açısı)** | Burnun ufka göre açısı. γ ile karıştırılmamalı. | — |
| **φ (bank/yatış açısı)** | Kanatların yatıklığı. | ✅ limit 80° |
| **n / nz (yük faktörü)** | Uçağa etkiyen g kuvveti. 1 g = düz uçuş. | ✅ +9 g / −3 g |
| **q̄ (dinamik basınç)** | ½ρV². Kontrol yüzeylerinin etkinliğini belirler. | ✅ gain scheduling burada |
| **Mach** | Ses hızına oranla hız. İrtifaya göre değişir. | ✅ 0.55–1.35 |
| **Tacview / ACMI** | Uçuş kaydı görselleştirme aracı ve dosya formatı. | ✅ `bvr/sim/acmi.py` |
| 🔬 **Gain scheduling** | Kontrol kazançlarını uçuş şartına (q̄, Mach) göre değiştirme. Araştır: neden tek sabit kazanç yetmez. | ✅ iç döngüde |

## A2. Klasik kontrol (iç döngü)

| terim | ne demek | projede |
|---|---|---|
| **PID / PI** | Oransal-İntegral-Türev denetleyici. Hata → düzeltme. | ✅ PI kullanıldı, D yok |
| **Kp / Ki** | Oransal ve integral kazançlar. Kp anlık hataya, Ki birikmiş hataya tepki verir. | ✅ |
| **Kalıcı durum hatası** (steady-state error) | Sistem oturduğunda kalan hata. Sadece Kp ile sıfırlanmaz — **Ki gerekir**. | ✅ yatışta 3.1° hata vardı, integral eklendi |
| **Anti-windup** | İntegral teriminin doyma sırasında şişip kontrolü ele geçirmesini önleme. | ✅ koşullu integrasyon |
| **Integral-near-null** | İntegrali yalnızca hedefe yakınken çalıştırma (sızıntılı integratör). | ✅ yatış çıkışında +14° aşım görülünce eklendi |
| **ζ (sönümleme oranı)** | Sistemin salınım karakteri. ζ<1 salınımlı, ζ≈0.7 ideal. | ✅ autothrottle'da %30 aşımı düzeltmek için hesaplandı: ζ = Kp√k / (2√Ki) |
| **Kinematik ters çevirme** | İstenen γ̇'dan gereken n'i çıkarma: **n = (V·γ̇/g + cos γ) / cos φ** | ✅ |
| **Bank kompanzasyonu** | `1/cos φ` terimi. 45° yatışta düz uçuş için 1.41 g gerekir. | ✅ |
| **Basamak yanıtı testi** | Ani komut verip sistemin nasıl oturduğunu ölçme. | ✅ 16/16 test |
| 🔬 **Kaskad (cascade) kontrol** | İç içe kontrol döngüleri; iç döngü hızlı, dış döngü yavaş. Araştır: neden iç döngü dıştan **5–10 kat hızlı** olmalı. | ✅ mimarinin temeli |
| 🔬 **Bağıl derece** (relative degree) | Girdinin çıktıyı kaç türev sonra etkilediği. Yüksekse tek adımlık kontrol yetkisi yok denecek kadar azdır. | ⚠️ CBF'te sorun çıkardı |

## A3. Sistem tanılama (system identification)

| terim | ne demek | projede |
|---|---|---|
| **Sysid** | Sistemin girdi-çıktı verisinden matematiksel modelini çıkarma. | ✅ 717k geçiş |
| **Kalıcı uyarım** (persistent excitation) | Verinin modeli belirlemeye yetecek kadar "zengin" olması. Tek frekans yetmez. | ✅ koşul sayısı 25.6 ile doğrulandı |
| **Koşul sayısı** (condition number) | Matrisin ne kadar iyi koşullandığı. Büyükse çözüm gürültüye duyarlı. | ✅ PE tanısı olarak kullanıldı |
| **Multisine** | Birden çok frekansın toplamı olan uyarım sinyali. | ✅ |
| **3-2-1-1 çok basamaklı** | Havacılıkta standart sysid manevrası; geniş bant uyarım verir. | ✅ |
| **Chirp** | Frekansı zamanla süpüren sinyal. | ✅ |
| **Ridge regresyon** | En küçük kareler + L2 cezası. Aşırı uyumu ve kötü koşullanmayı engeller. | ✅ |
| **Artık (residual/delta) regresyon** | `x⁺ − x`'i tahmin etmek. Ridge cezası A'yı sıfıra değil **birim matrise** çeker — dinamik sistemler için doğru olan bu. | ✅ önemli detay |
| 🔬 **Train/test sızıntısı** | Eğitim ve test verisinin aynı tohumlardan gelmesi. Sonuçları olduğundan iyi gösterir. | ✅ tohum blokları ayrıldı |

## A4. Koopman operatör teorisi ⭐ (tezin katkı iddiası)

| terim | ne demek | projede |
|---|---|---|
| **Koopman operatörü** | Doğrusal olmayan bir sistemi, **sonsuz boyutlu ama DOĞRUSAL** bir uzayda temsil etme fikri. Durumlar yerine *gözlemlenebilirler* üzerinde çalışır. | ⭐ teorik temel |
| **Gözlemlenebilir** (observable) | Durumun bir fonksiyonu, ψ(x). Doğru seçilirse dinamik doğrusallaşır. | ✅ |
| **DMD** (Dynamic Mode Decomposition) | En basit Koopman yaklaşımı: `x⁺ ≈ A x + B u`. Doğrusal. | ✅ taban model |
| **EDMD** (Extended DMD) | Durumu bir gözlemlenebilir sözlüğüyle **yükseltip** orada doğrusal model kurma. | ✅ **seçilen model** |
| **Sözlük/kitaplık** (library) | Gözlemlenebilir kümesi. Projede: `physics` (sin, cos, q̄, çarpımlar), `poly2` (ikinci derece polinomlar). | ✅ `physics` seçildi |
| **Deep Koopman** | Gözlemlenebilirleri elle seçmek yerine bir autoencoder ile **öğrenme**. | ⚠️ daha doğru ama seçilmedi |
| **Durum-içeren gözlemlenebilir** (state-inclusive) | ψ(x)'in ilk n bileşeni x'in kendisi olmalı — yoksa `C·x` biçimindeki bariyerler yükseltilmiş uzaya taşınamaz. | ✅ kritik tasarım kararı |
| **Spektral ceza** | Öğrenilen A'nın özdeğerlerini birim çember içinde tutma → kararlılık. | ✅ `deep_koopman_stable` |
| 🔬 **Denetlenebilirlik vs doğruluk** | Deep Koopman daha doğruydu ama EDMD-fizik seçildi: her terim fiziksel bir büyüklüğe karşılık geliyor. **Sertifikasyonda doğruluktan çok bu önemli.** | ✅ MDL-08 kararı |

## A5. Kontrol bariyer fonksiyonları (CBF) ⭐

| terim | ne demek | projede |
|---|---|---|
| **CBF** (Control Barrier Function) | Sistemi güvenli kümede tutmayı **matematiksel olarak** garantileyen kısıt. h(x) ≥ 0 güvenli bölge. | ⭐ |
| **Ayrık zamanlı CBF** | `h(x⁺) ≥ (1−γ)·h(x)`. Güvenlik payının adım başına en fazla γ oranında azalmasına izin verir. | ✅ |
| **γ (CBF gevşeklik parametresi)** | Küçük → muhafazakâr, büyük → serbest. | ✅ 0.1 |
| **Çok adımlı / öngörülü CBF** | `h(x_{k+i}) ≥ (1−γ)^i h(x_k)`. Tek adımda yetkisi olmayan yavaş durumlar için. | ✅ ufuklar (1,5,10,20,50,150,300) |
| **Komut yöneticisi** (command governor) | Filtreyi yüzey seviyesinde değil, **komut** seviyesinde uygulama. | ✅ mimari kararı |
| **QP** (Quadratic Program) | Karesel amaç + doğrusal kısıt. CBF filtresi bir QP olarak çözülür. | ✅ OSQP |
| **OSQP** | Hızlı QP çözücü. | ✅ 0.24 ms |
| **Slack değişkeni** | Kısıt sağlanamazsa "biraz ihlal et ama cezasını öde". Sert modda yoktur. | ✅ yumuşak mod |
| **Boyutsuz bariyer** | Her bariyer satırını karakteristik ölçeğine bölme. Koşullanmayı 925× → 1× düzeltti. | ✅ |
| **Satır budama** | Komut yetkisi olmayan (‖G‖ küçük) kısıtları atma. | ✅ |
| **ZOH** (Zero-Order Hold) | Komutun adımlar arasında sabit tutulduğu varsayımı. | ✅ |
| **Zarf hiyerarşisi** | işletme ⊂ emniyet ⊂ sonlandırma ⊂ fiziksel. Bariyer **sonlandırmanın içinde** olmalı. | ✅ SAF-08 |
| ⚠️ **Kalkanın sınırı** | 10 Hz komut filtresi, 60 Hz'de gerçekleşen dinamik/atmosferik geçici aşımı **engelleyemez**. Ölçülen en kötü: −4.581 g. | ⚠️ SAF-10 |
| 🔬 **Gürbüz (robust) CBF** | Model hatasına karşı pay bırakma. | 📋 park edildi |
| 🔬 **Yedek politika filtresi** | Güvenli bir "kaçış" politikasının varlığını kısıt olarak kullanma. | 📋 plandan çıkarıldı |

## A6. Pekiştirmeli öğrenme

| terim | ne demek | projede |
|---|---|---|
| **RL** | Ödülü maksimize eden politikayı deneme-yanılma ile öğrenme. | ✅ |
| **SAC** (Soft Actor-Critic) | Sürekli aksiyon, örneklem-verimli, **otomatik entropi** ayarlı off-policy algoritma. | ✅ güdüm katmanı |
| **PPO** (Proximal Policy Optimization) | On-policy; karma aksiyon uzayı ve self-play'de daha kararlı. | 📋 taktik komutan |
| **On-policy / off-policy** | Off-policy eski verilerden öğrenebilir (replay buffer), on-policy öğrenemez. | ✅ |
| **Replay buffer** | Geçmiş deneyimlerin saklandığı havuz. SAC'ın gerçek "devam"ı bunsuz olmaz. | ✅ 1M geçiş |
| **Aktör / Kritik** | Aktör aksiyonu üretir, kritik onu değerlendirir. | ✅ |
| **Entropi katsayısı (α)** | Keşif miktarı. `auto` olunca kendi kendine ayarlanır. | ✅ 0.045'te oturdu |
| **γ (indirim çarpanı)** | Geleceğin bugüne değeri. 0.99 → ~10 s ufuk, 0.995 → ~20 s. | ✅ 0.995 |
| **Ödül şekillendirme** (reward shaping) | Seyrek ödülü yoğunlaştırma. | ✅ ilerleme ödülü |
| **Potansiyel tabanlı şekillendirme** | Optimal politikayı **değiştirmediği ispatlanmış** şekillendirme biçimi. | 🔬 araştır |
| ⚠️ **Ödül–kriter uyumsuzluğu** | Kabul kriterinin ödüldeki payı %0.26 idi → kritik onu çözemiyor, uzun eğitim **zarar veriyor**. | ⚠️ bu projenin ana bulgusu |
| **Domain randomization** | Eğitimde koşulları rastgeleleştirme (rüzgâr, türbülans, yakıt) → gerçekliğe dayanıklılık. | ✅ |
| **Guvenli RL (Safe RL)** | Kalkan **eğitim döngüsünün içinde** olmalı, sonradan takılmamalı. | ✅ SAF-09 |
| 🔬 **MARL** (Multi-Agent RL) | Çok ajanlı öğrenme. | 📋 kol uçuşu |
| 🔬 **Self-play / opponent sampling** | Ajanı kendi eski sürümlerine karşı eğitme; durağan olmama (non-stationarity) sorunu. | 📋 |
| 🔬 **Curriculum learning** | Kolaydan zora sıralı eğitim. | 📋 |

## A7. Ölçüm metodolojisi ⭐ (en çok hata yapılan yer)

| terim | ne demek | projede |
|---|---|---|
| **Bootstrap güven aralığı** | Veriden tekrar tekrar örnekleyerek belirsizlik tahmini. | ✅ %95 GA |
| **İstatistiksel birim** | Neyin bağımsız örnek sayıldığı. Adımlar bağımsız **değildir** — birim **bölümdür**. | ✅ |
| **Örtüşen GA kuralı** | Güven aralıkları örtüşüyorsa fark **iddia edilmez**. | ✅ projede 3 kez uygulandı |
| **Blok etkisi** | Farklı 60 görevlik değerlendirme setleri ~0.10 farklı sonuç verdi. Örneklem n=200'e çıkarıldı. | ✅ |
| **Ablasyon** | Bir bileşeni çıkarıp etkisini ölçme. **Aynı politika**, iki koşul — ayrı eğitilmiş iki politika değil. | ✅ |
| **Seçim yanlılığı** | Test kümesinde model seçmek. Tutulan blokta doğrulama gerekir. | ✅ |
| **Tohum varyansı** | Aynı ayar farklı rastgele tohumla farklı sonuç verir. Tek koşuya dayanan iddia savunulamaz. | ✅ 3 tohum |
| **Adım-içi tepe** | Karar noktaları arasında (60 Hz) gerçekleşen aşımları yakalama. | ✅ |
| **Vekil ölçüt** (proxy metric) | Asıl istediğinin yerine geçen ölçüt. Yanıltabilir. | ✅ |
| 🔬 **Post-hoc metrik değişikliği** | Sonucu gördükten sonra metriği değiştirmek. Yapılacaksa **gerekçesi kayda geçmeli**. | ✅ GUI-07'de yapıldı, yazıldı |
| **Çürüyen açıklamaya dayanan kararı geri alma** | Bir açıklama ölçümle çürüdüğünde, ONA DAYANAN kararlar da geri alınmalı. nz_min referansı çürütülen bir mekanizmaya dayanarak düşürülmüştü; mekanizma çürüyünce referans da geri alındı. | ✅ yapıldı |
| **Açıklanamayan farkı boş bırakma cesareti** | Stres testi ile normal ortam arasındaki 20 katlık fark açıklanamadı ve belgede öyle duruyor. İki açıklama denemesi yanlış çıktıktan sonra üçüncüsünü "makul göründüğü" için yazmak aynı hatayı tekrarlamak olurdu. | ✅ boş bırakıldı |
| **Referansın temsil geçerliliği** | Bir izleme metriğinin referansı, **gelecekteki kullanıma benzeyen** bir kurulumda ölçülmeli. Hedef yakalamalı ortamda ölçülen nz_min (0.042), varış düzeltmesiyle şişkindi; komutan hedef kovalamayacağı için BVR'da yanlış temel. Stres testi 20 kat düşük verdi. | ✅ referans düzeltildi |

## A8. BVR — savaş katmanı ✅ (Faz 1.1–1.5 bitti) / betikli taban 📋 (Faz 2) / öğrenen komutan 📋 (Faz 3–6)

**Kilitli kararlar:** füze 3-DOF+PN · radar RCS+Doppler · 2v2'ye hazır altyapı ·
RWR (MAW değil) · IRST ertelendi · 4 AMRAAM · füze kütlesi modellenecek

**Durum:** aşağıdaki tablo BVR fazı BAŞLAMADAN ÖNCE terimler sözlüğü olarak
yazılmıştı (durum sütunu o zamanki tahmindi). Geometri/radar/füze/muhasebe/
çok-uçaklı-sim artık `bvr/combat/` altında YAZILDI ve ÖLÇÜLDÜ — ayrıntı
Adım 17'de. Taktik komutan (PPO, self-play, kredi atama) satırları hâlâ 📋.

| terim | ne demek | durum |
|---|---|---|
| **BVR** (Beyond Visual Range) | Görüş ötesi hava muharebesi. | 📋 |
| **AIM-120 AMRAAM** | F-16'nın standart BVR füzesi. ~335 lb, aktif radar güdümlü. | ✅ karar |
| **Oransal seyrüsefer (PN)** | Füze güdüm yasası: `a = N·V·λ̇`. Füze, **görüş hattının dönme hızıyla** orantılı ivmelenir. LOS dönmüyorsa çarpışma rotasındasın. | ✅ karar |
| **LOS dönme hızı** (λ̇) | PN'in tek girdisi. Sıfıra yakınsa çarpışma kaçınılmaz. | 🔬 |
| **N (seyrüsefer sabiti)** | Genelde 3–5. Büyük N daha agresif ama daha çok enerji harcar. | 🔬 |
| **Radar menzil denklemi** | `R ∝ ⁴√(P·G²·λ²·σ)` — **dördüncü dereceden**. RCS yarıya inince menzil sadece %16 düşer. | ✅ karar |
| **RCS** (radar kesit alanı, σ) | Hedefin radar görünürlüğü; **açıya göre büyük ölçüde değişir** (burun-açık vs yan). | ✅ karar |
| **Doppler ve notching** | Radar, kapanma hızı ~0 olan hedefi yer yankısından ayıramaz. 90°'ye dönmek ("beam/notch") kilidi kırar. **BVR'ın temel taktiği.** | ✅ karar |
| **Tarama tekrar ziyaret süresi** | Radarın bir noktaya tekrar bakma süresi. ±60°/4 bar ~5–6 s, ±30°/2 bar ~1.5–2 s, ±10°/1 bar <1 s. | ✅ RAD-09 |
| **M-of-N tespit** | Radar tek dönüşle kilit kurmaz; yanlış alarm elemek için ör. 3 taramada 2 tespit arar. Kilit ~2 tarama periyodu sürer. | ✅ RAD-09 |
| **Kilit gecikmesi** | Aramadan kilide geçiş, 2.5 s. ✅ uygulandı. **Fiziksel sabit değil, DENGE PARAMETRESİ** — `coast_s` ile birlikte notching'in gücünü belirler, ajanlar çıkınca ölçülüp ayarlanacak. | ⚠️ ayarlanacak |
| **Coast (kilit hafızası)** | Temas kesilince kilidin sürdüğü süre, 4.0 s. ✅ uygulandı. Notch'u kaç saniye tutman gerektiğini bu belirler. | ⚠️ ayarlanacak |
| 📋 **Yeniden kilitlenme** | Gerçek radarda tekrar kilit, sıfırdan aramadan hızlıdır (anten nereye bakacağını bilir). Modelde **yok** — coast bitince tam sıfırlama. `reacquire_delay_s < lock_delay_s` olarak eklenebilir. | 📋 ertelendi |
| **TWS vs STT** | Track-While-Scan birden çok hedefi izler ama zayıf kilit; Single Target Track tek hedefe sürekli aydınlatma — karşı tarafın RWR'ı ikisini **farklı görür**. | 📋 |
| **Etkili crank sınırı** | Sabit bir açı DEĞİL, menzile bağlı: |ATA| menzil kapandıkça büyür, her açı belli bir menzile kadar güvenli (35° ~9 nmi, 30° ~6 nmi, 25° ~5 nmi; eşik 55°). Sağ/sol simetrik değil (SIM2-08 önyargısı). | ✅ ölçüldü (Faz 2.0, SIM2-09) |
| **Hedef paylaşımı (sorting)** | Kol uçuşunda kanatların farklı düşmanları seçmesi. Yoksa ikisi aynı hedefe yığılır — 2v2'de 16 atışın 6'sı `hedefsiz`. | 📋 Faz 6 |
| **Overkill** | Zaten düşecek hedefe fazladan mühimmat harcamak. `hedefsiz` sonucu bunu ölçüyor. | 📋 Faz 6 |
| **Basamak cevabı / aşım** | Komut aniden sıçrayınca sistemin tepkisi; aşım = tepe − komut. Crank sınırını bu belirliyor (50° komut → 65.5°). | 📋 Faz 2.0 |
| **Spike** | RWR'ın "biri seni kilitledi" uyarısı. Atış anı RWR'da GÖRÜNMEZ; füze pitbull'a geçince yeni tehdit olarak belirir. | 📋 Faz 2.1 |
| **Betikli taban (baseline)** | RL'in geçmesi gereken kural tabanlı rakip. Zemin olmadan "RL iyi" iddiası anlamsız. | 📋 Faz 2.3 |
| **RWR** (Radar Warning Receiver) | Radar aydınlatmasını tespit eder. BVR'da füze uyarısı **buradan** gelir. | ✅ karar |
| ⚠️ **MAW** (Missile Approach Warning) | Füze alevini IR/UV ile görür. **BVR'da işe yaramaz** — AMRAAM 8-10 s yanar, kalan 50+ km'yi süzülür. | ❌ elendi |
| 📋 **IRST** | Pasif kızılötesi arama-takip. **Notching'i yenmez** → temel taktiği bozar. | 📋 faz 2 |
| **Pk** (Probability of Kill) | Füzenin vurma olasılığı; menzil, açı ve hedef enerjisine bağlı. | 📋 |
| **NEZ** (No Escape Zone) | Hedefin kaçamayacağı menzil bandı. | 🔬 |
| **F-pole / A-pole** | Füze uçarken menzil geometrisi ölçütleri. Crank ederken F-pole korunur. | 🔬 |
| **Crank** | Radar kilidini korurken menzil açmak için ~50° dönüş. | 🔬 |
| **Notch / Beam** | 90°'ye dönüp Doppler filtresine yakalanmamak. | 🔬 |
| **Drag / Abort** | Angajmandan tamamen çıkmak. | 🔬 |
| **Davranış Ağacı** (Behavior Tree) | Modüler karar yapısı; FSM'den daha iyi kompoze olur, öncelik sırası doğal. Kırmızı takım için. | ✅ karar |
| 🔬 **PPO** | On-policy; karma aksiyon uzayı ve self-play için SAC'tan uygun. | 📋 |
| 🔬 **Karma aksiyon uzayı** | Sürekli (yön/irtifa/hız) + kesikli (ateş/hedef/mod) birlikte. | 📋 |
| 🔬 **Self-play / rakip örnekleme** | Durağan olmama, döngüsel baskınlık (taş-kağıt-makas). | 📋 |
| 🔬 **CTDE** | Centralized Training, Decentralized Execution — MARL standardı. | 📋 |
| 🔬 **Kredi atama** | Çok ajanlıda hangi ajanın katkısı olduğunu ayırma. | 📋 |

**Referans projeler:** [BVRGym](https://github.com/xcwoid/BVRGym) (JSBSim F-16 + PN füze,
[makale](https://arxiv.org/pdf/2403.17533)) · [LAG](https://github.com/liuqh16/LAG)
(kırmızı/mavi, self-play) · [propNav](https://github.com/gedeschaines/propNav)
(saf Python 3-DOF PN füze) · [MIT 16.070 PN projesi](https://web.mit.edu/16.070/www/project/PG_missile_navigation.pdf)

> Bunlar **kopyalanmayacak, okunup kendimiz yazacağız** — EDMD-fizik'i
> Deep-Koopman'a tercih etme gerekçesiyle aynı: denetlenebilirlik. Ayrıca
> tez katkısı olarak "ortamı kurdum ve doğruladım" ile "başkasının ortamını
> kullandım" arasında büyük fark var. Bakma amacı **doğrulama**: bizim
> sayılarımız onlarınkine yakın mı?

---

# BÖLÜM B — PROJEYİ SIRASIYLA NASIL KURDUK

> Anlatım sırası **gerçek geliştirme sırası**dır. Her adımda: ne yaptık, neden,
> hangi dosya.

## Adım 0 — Mimari kararı

Eskiden **uçtan uca RL** vardı: ajan doğrudan kontrol yüzeylerini sürüyordu.
Terk edildi. Yerine **kaskad mimari**:

```
JSBSim FLCS        120 Hz   uçağın kendi kontrol bilgisayarı
klasik PI iç döngü  60 Hz   γ, φ, Mach tut
RL güdüm (SAC)      10 Hz   nereye gideceğine karar ver
CBF güvenlik kalkanı 10 Hz  tehlikeli komutu düzelt
taktik komutan       2 Hz   (gelecek faz)
```

**Neden:** üç zor bileşeni aynı anda devreye almak, hangisinin bozuk olduğunu
ayrıştırmayı imkânsız kılıyordu. Katmanlar **aşağıdan yukarı** kurulur ve
her biri kabul kriterlerini geçtikten sonra **dondurulur**.

Kilitlenen kararlar: CBF iç döngüde değil **dış döngü komutlarında**;
aksiyon `[φ_cmd, γ_cmd, mach_cmd]` (θ değil **γ** — çünkü θ = γ + α ve
θ-tut hıza bağlı tırmanış verir); Koopman modeli **çevrimdışı** fit edilir;
RL için SB3 SAC (kendi SAC'ımız değil).

## Adım 1 — Simülasyon temeli

**`bvr/sim/aircraft.py`** — F-16 sabitleri ve FCS komut sözleşmesi için tek
doğruluk kaynağı. Buradaki kritik keşif: JSBSim'de
`fcs/aileron-cmd-norm` yüzey açısı **değil, yuvarlanma HIZI** komutudur
(1.0 ↔ 180°/s); `fcs/elevator-cmd-norm` g yükü + yunuslama hızı karışımıdır
ve [−1, +0.44] aralığına kırpılır. Bunu bilmeden yazılan kontrolcü çalışmaz.

**`bvr/sim/jsbsim_bridge.py`** — JSBSim sarmalayıcı. Sıralama önemli:
önce türbülansı sıfırla (JSBSim reset'leri arasında **kalıcı** ve trimi
bozuyor), sonra yakıtı ayarla (trim ağırlığa bağlı), sonra `run_ic()`,
sonra trim.

**`scripts/smoke_trim.py`** — trimin çalıştığını doğrulayan ilk test.
Trimsiz uçak 60 saniyede 14–23 bin ft düşüyordu; trimle sapma 12–76 ft'e indi.

## Adım 2 — FCS'nin gerçekte ne yaptığını ölçme

**`scripts/id_fcs.py`** ve **`scripts/id_nz.py`** — dokümantasyona güvenmek
yerine komut → tepki ilişkisini **ölçtük**. `ROLL_RATE_NORM_GAIN = 0.31821`
gibi sabitler buradan çıktı.

## Adım 3 — İç döngü (klasik kontrol)

**`bvr/control/inner_loop.py`** — dört kanal:
- **γ → ṅ → n → elevator**: kinematik ters çevirme
  `n = (V·γ̇/g + cos γ)/cos φ`, sonra n hatasına PI
- **φ → p → aileron**: yatış açısından yuvarlanma hızı komutu
- **Mach → throttle**: autothrottle
- **β → rudder**: koordinasyon

Yaşanan sorunlar ve çözümleri:
- Yatışta **3.1° kalıcı hata** → sınırlı yetkili integratör
- Yatış çıkışında **+14° aşım** → integral-near-null (sadece hedefe yakınken)
- Autothrottle'da **%30 aşım** → ζ = Kp√k/(2√Ki) hesaplandı, Kp 4→10, Ki 0.3→0.5

**`scripts/test_inner_loop.py`** — 16 kabul testi (basamak yanıtı, oturma
süresi, aşım, kalıcı hata). **16/16 geçti**, katman donduruldu.

**`scripts/demo_inner_loop.py`** — Tacview görselleştirmesi.

## Adım 4 — Veri toplama ve sistem tanılama

**`bvr/sysid/excitation.py`** — uyarım sinyalleri: multisine, rastgele
basamak, 3-2-1-1, chirp. Amaç **kalıcı uyarım**: veri, modeli belirlemeye
yetecek kadar zengin olmalı.

**`bvr/sysid/collect.py`**, **`scripts/collect_sysid.py`** — 717 bin geçiş
toplandı. **`bvr/sysid/evaluate.py`** kalıcı uyarımı koşul sayısıyla
doğruladı: **25.6** (iyi).

## Adım 5 — Koopman modelleri ⭐

**`bvr/models/state_def.py`** — 11 boyutlu durum:
`(φ, γ, Mach, irtifa, α, β, n, p, q, ḣ, yakıt)`. **Sabit** ölçekleme
(canlı istatistik değil). `envelope_constraints()` bariyerleri
**boyutsuz** döndürür.

**`bvr/models/base.py`** — ortak taban. `_fit_linear()` **artık regresyon**
yapar: `Z⁺ − Z = A_d·Z + B·W`, sonra `A = I + A_d`. Böylece ridge cezası
A'yı sıfıra değil **birim matrise** çeker.

**`bvr/models/dmd.py`** (taban) → **`bvr/models/edmd.py`** (fizik/poly2
kitaplıkları) → **`bvr/models/deep_koopman.py`** (autoencoder).

**`scripts/fit_model.py`**, **`scripts/compare_models.py`** — hepsi eğitilip
karşılaştırıldı. Sonuç: Deep Koopman **daha doğru**, ama
**EDMD-fizik seçildi** — her terim fiziksel bir büyüklüğe karşılık geliyor,
denetlenebilir. Sertifikasyon bağlamında doğruluktan önemli.

Ters sonuç: yakıt durumu eklenince **EDMD-poly2 çöktü** (0.155 → 0.246) —
yavaş değişen durum, ikinci derece terimlerde eşdoğrusallık yaratıyor.

## Adım 6 — CBF güvenlik kalkanı ⭐

**`bvr/safety/cbf.py`** — OSQP tabanlı komut filtresi.

Karşılaşılan üç ciddi sorun:
1. **Bağıl derece**: tek adımlık ufukta `B[ḣ, γ_cmd] = −0.0005` ve işareti
   yanlış → **çok adımlı ufuklar** eklendi
2. **QP koşullanması**: bariyerler arası 925× ölçek farkı, 3000 çağrının
   241'inde çözücü hatası → **boyutsuz bariyer + satır normalizasyonu +
   budama** → hata %0.05'e indi
3. **Yatış bariyeri** %42 müdahale yapıyordu → çünkü o bir **işletme**
   kısıtı, emniyet kısıtı değil. Kaldırıldı → %7.5

**`bvr/safety/robust.py`** — gürbüz pay; park edildi.

## Adım 7 — RL ortamı ve güdüm ajanı

**`bvr/envs/guidance_env.py`** — 19 boyutlu gözlem, 3 boyutlu aksiyon.
Gözlem: hatalar (sin/cos kerteriz hatası, menzil, irtifa/Mach hatası) +
kendi durumu + **son UYGULANAN komut** + yakıt.

**`bvr/agents/train_guidance.py`** — SB3 SAC eğitimi, 12 paralel ortam.

**`bvr/agents/scripted_guidance.py`** — klasik güdüm, karşılaştırma tabanı.
SAC onu geçti: 2101 [2028, 2174] vs 1915 [1798, 2021].

**`bvr/config.py`** — YAML tabanlı deney tanımı. Bilinmeyen anahtarda
**hata fırlatır** (yazım hatası koruması). Çözümlenmiş config koşu dizinine
yazılır — hangi ayarla üretildiği kalıcı olarak izlenebilir.

## Adım 8 — Ödül tasarımı ve titreme

İlk ödül (**v1**) Gauss şekillendirme kullanıyordu: `exp(−(Δh/1000)²)`.
3000 ft hatada değer 1e-4 → **gizli seyrek ödül**, uzakta gradyan yok.

**v2** ilerleme ödülü ekledi: "bu adımda hata ne kadar kapandı", fiziksel
maksimumla normalize. Her uzaklıkta gradyan var.

**Komut titremesi**: ajan 3 Hz'de bang-bang yapıyordu, adımların %63'ünde
işaret değiştiriyordu ve bu **Mach takibini öldürüyordu**. Tacview'de
gözle görülüyordu. Çözüm: yapısal **slew limiti** + ağırlaştırılmış ceza.
Mach toleransı %18.9 → %82.

**`scripts/reward_audit.py`** — ödülün teorik aralığı, ulaşılabilir tavanı
ve politikanın fiilen nereden puan topladığı.

## Adım 9 — Ölçüm krizinin çözümü ⭐

Aynı konfigürasyon farklı tohum bloklarında **%0.048 – %1.742** ihlal verdi
(**36 kat**). Sebep: zarf ihlalleri adım seviyesinde **bağımsız değil** —
uçak kötü duruma girip 200–900 adım orada kalıyor.

**Üç iddia geri çekildi.** Metrikler yeniden yazıldı: birim **bölüm**,
belirsizlik **bootstrap %95 GA**, adım-içi tepe 60 Hz'de izlenir.

**`scripts/safety_eval.py`** — bölüm başına ihlal + bootstrap GA.
**`scripts/mission_eval.py`** — görev metrikleri (bacak yakalama, seyrüsefer
verimi, yakalama kalitesi, izleme RMSE).

Eski `is_success` tanımı ("bölümde ≥3 hedef") **fiziksel tavanın üstündeydi**:
180 s × ~900 ft/s = 26.7 deniz mili, hedefler ortalama 9 nmi → dümdüz uçsa
bile ~3. Ulaşılamaz eşiğe göre "%15 başarı" raporlanıyordu.

## Adım 10 — Hiperparametre taraması

**`scripts/sweep.py`** — 9 konfigürasyon, tek faktör değişimi.

**Pahalıya öğrenilen ders:** tarama önce "hedef/bölüm"e göre seçiyordu ve
`s2_smooth` kazanmıştı — dört metrikte birinci. Ama **kabul kriteri** varış
kalitesiydi ve orada `s2_smooth` **en kötüydü** (0.330 vs 0.589).
7.3 saatlik eğitim yanlış konfigürasyonla koştu.
→ **Seçim ölçütü kabul kriteriyle aynı olmalıdır.**

Ters sonuç: slew sınırını **sıkmak** (`s3_slew`) en kötü koşuydu.
Düzgünlüğü **ödülle teşvik etmek** işe yarıyor, **komut yetkisini kısarak
dayatmak** zarar veriyor.

## Adım 11 — Büyük eğitim ve başarısızlığı ⭐

8M adım × 3 tohum, ~7 saat. Sonuç **2M'dekinden kötü**: 0.540 → 0.316.

Teşhis (**`scripts/reward_audit.py`**): bölüm getirisi 2374 puan.
Hedefe varış bonusu 16.8 (%0.7) ve bunun 10.6'sı **koşulsuz**.
→ **Kabul kriterine bağlı ödül = 6.2 puan = %0.26.**

Kritik bunu gürültüde çözemiyor. Ödül 1.5M'de doyuyor, kalan 6.5M adım
kriteri kısıtlamayan %99.7'yi optimize ediyor.

## Adım 12 — Ödül düzeltmesi

**`scripts/reward_whatif.py`** — bir ödül ayarını **denemeden önce** kalite
payını hesaplar (aynı yörüngeler, farklı ağırlıklar). 3.5 saati boşa
harcamamak için.

Altı konfigürasyon (`configs/reward/`):

| ayar | değişiklik | kalite | verim | komut tutma |
|---|---|---|---|---|
| taban | — | 0.650 | 0.864 ✅ | 10/14 · 10/14 |
| r1 | çekirdek 500/0.05 | 0.510 ⚠️ | 0.854 | 9/14 · 12/14 |
| r2 | hedef ödülü 60 | 0.758 | 0.860 ✅ | 11/14 · 14/14 |
| **r3** | ikisi + ilerleme 0.4 | **0.795** | 0.833 ❌ | **14/14 · 14/14** |
| r4 | ilerleme 0.3 | 0.814 | 0.816 ❌ | 14/14 · 10/14 |
| r5 | ilerleme 0.7 | 0.545 | 0.855 ✅ | 0/14 · 14/14 |

**Üç öğrenilen:**
- **Parçalar toplanmıyor.** r1 tek başına zarar verdi — çekirdek daralınca
  uzakta gradyan sıfırlanıyor, baştaki hata geri geliyor. Bonusla birlikte
  faydalı.
- **İnterpolasyon çalışmıyor.** r5 (0.7) ara sonuç vermedi; nitel olarak
  farklı bir davranış üretti (her koşulda sabit +910 ft yüksek uçma).
- **İki metrik farklı sıralama verebilir.** Görev metriğine göre r2,
  arayüz sözleşmesine göre r3 kazanıyordu.

**`scripts/command_hold_test.py`** — üst katmana verilen **asıl sözleşme**:
"komutu sabit tutarsam kalıcı hata ne?" 14 dengeli manevra (2 tutma,
4 tırmanış, 4 alçalma, 2 hız, 2 birleşik). İlk sürüm 7 durumluydu ve
tırmanışları yetersiz örnekliyordu.

**`BestByCaptureQuality`** callback'i (`train_guidance.py` içinde) —
son modeli almak yanlış; kabul kriterine göre en iyisini sakla.
İlk sürümünde **küçük payda hatası** vardı: eğitimin başında 1/1 = 1.000
ölçüp donuyordu. Asgari bacak şartı eklendi.

## Adım 13 — Tohum doğrulaması ve dondurma

`r3` iki ek tohumla eğitildi, üçü n=200 ile ölçüldü:

| tohum | kalite | verim | komut tutma |
|---|---|---|---|
| 0 | 0.795 [0.751, 0.836] | 0.833 | 14/14 · 14/14 |
| 1 | 0.759 [0.712, 0.806] | 0.813 | 14/14 · 14/14 |
| 2 | 0.741 [0.693, 0.786] | 0.825 | 14/14 · 14/14 |

Üçü de eşiği geçti; yayılım 0.054 (8M deneyinde 0.212 idi).
Komut tutma **üçünde de 14/14** → tohum şansı değil, **yapısal**.

**`scripts/violation_depth.py`** — kalkanın sınırını ölçtü: ihlaller anlık
sıçrama (medyan 0.15 g aşım, 0.1 s) ama en kötü geçici **−4.581 g**.
Mekanizma: iç döngü komut sınırı −2.0 g iken gerçekleşen −4.58 g; farkı
komut değil **rüzgâr darbesi ve dinamik aşım** üretiyor.

→ **SAF-10**: kalkan komut seviyesinde çalışır, 60 Hz geçici aşımı
engelleyemez. *"Kalkan zarfı garanti eder" denemez.*

**Seçilen model:** `runs/reward_r3_both/sac_1999968_steps.zip`
Yedi kriterin altısı geçti; seyrüsefer verimi (0.833 vs 0.85) **sağlanmadı**
olarak raporlandı — eşik gevşetilmedi.

---

## Adım 14 — BVR öncesi stres testi ve dondurma kararı

Kalkanı ve güdümü dondurmadan önce bir soru kaldı: **komutan devreye girince
zarf ihlalleri patlar mı?**

Bu sorunun sırası önemli. İç döngüye dokunmak güdümü, güdümü değiştirmek de
(sözleşme bozulursa) komutanı yeniden eğitmeyi gerektirir. Komutanı yeniden
eğitmek güdümden kat kat pahalı. Yani **iç döngü kararı, komutana yatırım
yapmadan önce verilmeli.**

Ama komutanı eğitmeden komut dağılımını bilemeyiz — o yüzden **taklit ettik**:
`scripts/stress_commander.py`, 2 Hz'de betikli agresif komutlar üretir
(sert dönüşler, büyük irtifa basamakları, sert hız değişimleri), üç
agresiflik seviyesinde.

| seviye | ihlalli bölüm | nz_min oranı | en kötü |
|---|---|---|---|
| nominal | 6/80 | 0.000 | −3.296 g |
| agresif | 22/80 | 0.001 | −3.867 g |
| aşırı | 46/80 | 0.002 | −4.194 g |
| *hedef yakalamalı ortam* | 24/150 | *0.042* | *−4.581 g* |

### Sonuç: uçak sağlam, ama "hiç aşmadı" değil

En vahşi seviyede bile ihlal oranı **0.002**; dur eşiği **0.084** idi.
**40 kat marj** var.

> Dikkat: ihlaller **oldu**. Aşırı seviyede 80 bölümün 46'sında en az bir
> ihlal, en kötüsü −4.194 g. Doğru ifade: ihlaller **nadir ve çok kısa**
> (medyan 0.1 saniye), oran eşiğin çok altında.

**Karar: iç döngüye dokunulmadı, ajanlar baştan eğitilmedi.**

### Üç hipotez, iki yanlış — ve bu kısım asıl ders

**Hipotez 1: "Agresiflik ihlal üretir."** İlişki var ama zayıf
(0.000 → 0.001 → 0.002).

**Hipotez 2: "İhlaller varış öncesi hassasiyet düzeltmesinden geliyor."**
Ajanın hedefe tam oturmak için son anda burnunu sertçe aşağı ezdiği
düşünüldü — kırmızı ışıkta son anda fren yapan şoför gibi. Gerekçe: iki
kurulum arasındaki tek yapısal fark varış aşamasıydı.

**Ölçüldü ve ÇÜRÜTÜLDÜ** (`scripts/violation_where.py`):

| menzil bandı | ihlal oranı | kat |
|---|---|---|
| 3k – 6k ft | 0.00018 | 0.5× |
| 6k – 15k | 0.00029 | 0.7× |
| 15k – 30k | 0.00023 | 0.6× |
| 30k – 60k | 0.00069 | 1.7× |
| 60k+ | 0.00017 | 0.4× |

İhlallerin medyan menzili 6.51 nmi, tüm adımların medyanı 6.04 nmi —
neredeyse aynı. İhlallerin yalnızca **%2'si** yakalama yarıçapının iki
katından yakın. **Varış anında yığılma yok. "Son saniye paniği" diye bir
şey yokmuş.**

**Hipotez 3: "İhlaller yatık alçalmada oluşuyor."** Bu sefer önce ölçüldü:

| | ihlal anında | tüm adımlar |
|---|---|---|
| yatış (medyan) | **55.2°** | 33.2° |
| uçuş yolu açısı | **−6.3°** | −0.1° |
| irtifa hatası | **−3789 ft** (hedefin üstünde) | +78 ft |
| alçalma (γ < −5°) | %59.4 | %13.9 → **4.3×** |
| yatış>45° + alçalma | %35.8 | %10.1 → **3.5×** |

**DOĞRULANDI.** Uçak hedefin üstünde kalmış, dönerken aynı anda alçalıyor.
Mekanizma iç döngü formülünde açık:

```
n = (V·γ̇/g + cos γ) / cos φ
```

`1/cos φ` çarpanı 55° yatışta komutu **1.74 kat** büyütür. Alçalma zaten
negatif tarafa gidiyorsa yatıklık negatif g'yi derinleştirir.

### Doğrulama boşluğu kapatıldı — ve iç döngü aklandı

İhlallerin yatık alçalmada oluştuğu anlaşılınca fark edildi ki iç döngünün
**16 kabul testinin hepsi kanat düzdü**. En çok ihlal üreten çalışma noktası
hiç sınanmamıştı. İki grup eklendi:

| grup | koşul | en kötü nz | sonuç |
|---|---|---|---|
| 5 · yatık alçalma | φ=55°, γ=−8° | −2.81 g | 6/6 ✅ |
| 6 · ani ters dönüş | φ=70°, γ +10°→−20° | −2.70 g | 6/6 ✅ |

**28/28 geçti** — ortamın alt köşesi (10 kft / M0.60) dahil.

**Beklenmedik sonuç: iç döngü sorumlu değil.** Temiz komutlarla sürüldüğünde
bariyeri hiç aşmıyor; 70° yatışta anlık 30°'lik γ tersine dönüşü bile −2.70
g'de kalıyor. Ama ortamda sakin havada −3.76 g ölçülmüştü.

Yani derin negatif g, basamak yanıtından değil **ajanın sürekli değişen
komut akışından** geliyor: dış döngü 10 Hz'de komut yeniliyor, uçak hiç
oturmuş bir duruma gelmiyor, ardışık komutlar birikiyor. Tek basamaklı
hiçbir test bunu üretmez.

Bu, müdahale seçeneklerini yeniden sıraladı: iç döngüyü yeniden ayarlamak
(A) artık **zayıf** bir seçenek — döngü zaten 28/28 geçiyor, ayarı bozuk
değil.

### Açık kalan soru — uydurma açıklamayla doldurulmadı

Stres testinin neden 20 kat düşük çıktığı **hâlâ açıklanamadı**. İki
açıklama denemesi de yanlış çıktığı için üçüncüsünü "makul göründüğü" için
yazmak aynı hatayı tekrarlamak olurdu.

**Bunun pratik sonucu: referans düzeltmesi GERİ ALINDI.** Referansı
0.042'den 0.001'e indirme gerekçesi "BVR kullanımı stres testine benzer"
idi ve bu, çürütülen mekanizmaya dayanıyordu. Gerçek mekanizma yatık
alçalma olunca beklenti **tersine döner**: BVR'da yatık alçalma boldur
(füze kaçınma, enerji yönetimi, savunma manevraları). BVR, stres testinden
daha iyi değil **daha kötü** olabilir. İzlemede muhafazakâr (yüksek) uç
kullanılıyor: oran 0.042, derinlik −4.581 g, eşik 0.084.

**Kararın sınırı (dürüst kayıt):** betikli komutan, öğrenilmiş bir komutanın
yaklaşık taklididir. Öğrenilmiş bir komutan rastgele betiklerin bulamayacağı
komut dizileri keşfedebilir. Karar **"sistem savaşa tam hazır" değil**,
**"şimdi müdahale etmek için gerekçe yok"**tur.


---

## Adım 15 — Tacview gözlemi bir test aracı hatasını ortaya çıkardı

Kullanıcı `test_model.py` ile üç senaryo koşturdu ve Tacview'de **uçağın
sürekli sağa sola yattığını** fark etti. Sayısal metrikler bunu
göstermiyordu — irtifa ±50 ft, Mach toleransta.

Log incelenince yatış açısının +40° ile −68° arasında, **12.7 saniyelik**
düzenli bir çevrimle salındığı görüldü.

**İlk hipotez (yanlış):** "ajan irtifayı yatışla trimliyor." Ölçüldü:
yatış–dikey hız korelasyonu yalnızca −0.171. **Çürütüldü.**

**İkinci hipotez (doğrulandı):** sönümsüz kurs takip döngüsü. Yatış ile
kerteriz hatası arasında **2.2 s gecikmeyle r = −0.949**; yatış ±60°
salınırken kerteriz hatası yalnızca ±10°.

**Kök neden test aracındaydı.** `--hold` modu sanal hedefi **200 deniz
mili** uzağa koyuyordu; eğitim aralığı ise **3.3–14.8 nmi**. Uzak hedefte
kerteriz uçağın yönüne duyarsız kalır ve kurs döngüsünün doğal sönümlemesi
kaybolur.

| hedef menzili | yatış std | çevrim |
|---|---|---|
| 200 nmi | 37.3° | 12.7 s |
| 40 nmi | 30.5° | 12.4 s |
| **25 nmi** | **6.4°** | **yok** |
| 15 nmi | 14.4° | yok |

**Düzeltmeler:** `command_hold_test.py` 200 → 30 nmi; `test_model.py`'ye
`--target-range` ve `--schedule` (zaman içinde değişen komut dizisi) eklendi.

**Sonuç değişmedi, güçlendi:** GUI-11 sözleşmesi doğru mesafede yeniden
ölçüldü — **14/14 + 14/14 korundu**, kalıcı rejim sapmaları 33 ft'ten
5–6 ft'e indi.

**Kalıcı çıktı — TAC-08:** komutanın yön komutu sanal hedef olarak
**5–25 nmi** arasına konacak. Bu, BVR arayüzü yazılırken düşülecek doğal
bir tuzağı ("hiç varmasın diye uzağa koyayım") önceden kapatıyor.

---

## Adım 16 — BVR öncesi son ölçüm: mühimmat kütlesi

Kararlar kilitlendikten sonra tek açık soru kaldı: **4 AMRAAM (+1.340 lb)
eklenince dondurulmuş guidance katmanı sözleşmesini hâlâ tutuyor mu?**

JSBSim'den ölçülen gerçek ağırlıklar boş+pilot 17.630 lb, yakıt %30 →
19.722, yakıt %100 → 24.602. Tam yakıt + tam mühimmat **25.942 lb**, yani
eğitim üst sınırının **%5.5 üstünde** — dondurulmuş bir katmanı eğitim
dağılımının dışına çıkarmak, bu projede üç kez tuzağa düşülen tam o şey.

`scripts/payload_check.py` yazıldı, 5 konfigürasyon × 14 manevra:

| konfigürasyon | ağırlık | irtifa | mach |
|---|---|---|---|
| referans (0 füze, %60) | 21.813 lb | 14/14 | 14/14 |
| 0 füze, %100 | 24.602 lb | 14/14 | 14/14 |
| 4 füze, %30 | 21.062 lb | 14/14 | 14/14 |
| 4 füze, %60 | 23.153 lb | 14/14 | 14/14 |
| **4 füze, %100** | **25.942 lb** | **14/14** | **14/14** |

**Hepsi geçti**, ağırlıkla bozulma arasında eğilim yok; en ağır durumda
irtifa hatası referanstan bile küçük (109 vs 161 ft). Sebep: guidance zaten
4.880 lb'lik bir ağırlık bandında eğitilmişti (domain randomization) —
1.340 lb ek yük o bandın %27'si kadar bir genişleme. Ayrıca ağırlık,
yunuslama tepkisini yavaşlattığı için tutma açısından zararsız.

**İkinci satırı bilerek koydum:** yakıt etkisini füze etkisinden ayırmak
için. Sadece son satır bozulsaydı sebep dağılım dışına çıkmak olurdu;
24.602'de de bozulma başlasaydı sorun ağırlığın kendisi olurdu. İkisi
farklı sonuç doğururdu.

**İki JSBSim tuzağı çıktı:** nokta kütle de `reset()` arasında kalıcı
(türbülans gibi — ilk ölçümde "yüksüz referans" yüklü çıktı), ve F-16
modelinde yalnızca `pointmass[0]` kütle dengesine giriyor (`[1]` sessizce
etkisiz). Kütleyi `[0]`'a eklerken konumu birleşik momenti koruyacak şekilde
seçmek gerekti, yoksa CG 8.4 inç geriye kayıyor.

---

## Adım 17 — BVR savaş katmanı: geometri, radar, füze, muhasebe, çok uçaklı sim

Kilitli kararlardan sonra beş alt adımda (`bvr/combat/`) yazıldı, her biri
bir öncekinin üzerine dondurularak: geometri (Faz 1.1) → radar (1.2) →
füze (1.3) → angajman muhasebesi (1.4) → çok uçaklı simülasyon + Tacview
(1.5a–e). Toplam **46/46 test**, tamamı `bvr/combat/tests/` altında.

**Geometri (1.1):** ATA/AA/HCA/kapanma hızı/LOS dönme hızı — radar ve
füzenin İKİSİNİN de üzerine kurulduğu ortak sözleşme. Tek gerçek tuzak:
tautolojik test riski (HCA'yı hesaplayıp aynı formülle doğrulamak hiçbir
şey kanıtlamaz) — testler bağımsız geometrik senaryolarla (bilinen açı
üreten uçuş durumları) yazıldı.

**Radar (1.2):** 4. kök menzil denklemi + açıya bağlı RCS (kuyruk 4 m²,
yan 50 m², burun 2 m² — bu 25 katlık fark BVR'ın temel taktiğinin
kaynağı) + Doppler notch + gimbal + kilit-kurma/coast durum makinesi.
`lock_delay_s`/`coast_s` **fiziksel sabit değil, DENGE PARAMETRESİ** —
ajanlar ortaya çıkınca ölçülüp ayarlanacak (RAD-09/10). Tasarım kararı
baştan `target_id` sözlüğüyle ÇOK HEDEFLİYDİ (docstring: "ileride kol
uçuşu 2v2 gibi senaryolar için") — bu karar 1.5e'de karşılığını ödedi:
2v2'ye geçerken radar kodunda TEK SATIR değişmedi.

**Füze (1.3):** 3-DOF nokta-kütle, gerçek Oransal Seyrüsefer (`a = N·V·λ̇`),
boost/coast fazları, datalink hafızası (kilit kesilince bir süre son
bilinen konum/hızla güdülmeye devam), seeker gate (pitbull sonrası kendi
kilidi). **Ölçülen bulgu:** dt-duyarlılığı MONOTONİK DEĞİL — 6g manevra
yapan hedefe karşı marjinal bir angajmanda 10 Hz dış tik ile sonuç
(isabet/ıska) daha ince/kaba dt'lerdekinden farklı çıkabiliyor
(`missile_dt_convergence.py`, gerçek Python ↔ Node.js portu çapraz
doğrulaması). Çözüm: füze fiziği dışarıdan bağımsız 50 Hz'de (5 alt-adım)
koşuyor (ENG-10).

**Angajman muhasebesi (1.4):** atış yetki hiyerarşisi (mühimmat →
doygunluk → menzil → kilit), kütle düşüşü (335 lb/füze), olay günlüğü.
`Engagement`/`Radar`, hiçbir yerde "tam 2 uçak" varsaymayacak şekilde
(genel `dict`/`list` üzerinden) yazıldı — bu genellik bedelsiz değildi
(daha soyut kod) ama 1.5e'de N-uçaklı genişlemeyi BEDAVA yaptı.

**Çok uçaklı simülasyon + Tacview (1.5a–e):** en çok tuzak burada çıktı,
çünkü ilk kez BİRDEN FAZLA `F16Sim`/`GuidanceDriver` örneği AYNI ANDA,
AYNI SAHNEDE çalıştırıldı:
- 1.5a: iki bağımsız `F16Sim`'in birbirini kirletmediği ölçüldü (60 s'de
  4.43 ft sürüklenme, ikisinde de aynı — sızıntı yok).
- 1.5b: `GuidanceEnv`'in fizik kısmı `guidance_shared.py`'ye çıkarılıp
  eğitim-dışı hafif bir sürücüye (`GuidanceDriver`) taşındı. İlk sürüm
  komut savurma sınırını (`action_rate_limit`) unuttu — "eğitime özgü"
  sanılmıştı, aslında dondurulmuş modelin kalibre olduğu sözleşmenin
  parçasıydı. `guidance_driver_smoke.py` ile yakalandı (200 adımda ~200 ft
  sapma → düzeltince <1e-11).
- 1.5c: ilk uçtan uca 1v1 — 180 s çökmeden koştu, tüm füzeler karşılıklı
  kaçış yüzünden `"kor"` (datalink kaybı) oldu. Kod hatası değil: basit
  betikli komutanın "düşman ateş etti mi anında 90° kaç" kuralı, iki
  tarafın da neredeyse eşzamanlı ateş ettiği bir senaryoda HERKESİ
  kaçırıp herkesin kendi füzesini desteksiz bırakmasına yol açıyor.
- 1.5d: Tacview kaydı çok nesneli hale getirildi. İKİ hata bulundu: (a)
  başlık alanları tek `bool` bayrakla tutuluyordu (sadece ilk nesne isim
  alıyordu), (b) konum her `F16Sim`'in KENDİ özel orijininden değil,
  PAYLAŞILAN `north_ft`/`east_ft` çerçevesinden okunmalıydı — aksi halde
  iki uçak Tacview'de çakışık görünürdü. ÜÇÜNCÜ, daha ince bir hata da
  buradan çıktı: füze/uçak kaydına verilen iki "zaman" değeri (uçağın
  kendi `st.t`'si vs betiğin yerel `k*dt` sayacı) aynı anı temsil ettiği
  SANILIYORDU ama 1 tik kaymışlardı — yeni fırlatılan bir füze, atış
  anındaki değil bir tik SONRAKİ uçak konumunda görünüyordu. Ders: "aynı
  anı" temsil eden iki değer aynı saatten gelmeli.
- 1.5e: 2v2 — 4 uçak, 4 radar, 16 mühimmat. `Engagement`/`Radar`'da SIFIR
  kod değişikliği gerekti; tek yeni mantık betik (komutan) seviyesindeydi
  (en yakın canlı düşmanı seç, takım-çaprazı ateş döngüsü).

**Açık kalan risk (1.5b'de fark edildi, henüz kapatılmadı):** dondurulmuş
guidance politikası SABİT HEDEF NOKTALARINA uçmak için eğitildi
(`guidance_env.py::_new_waypoint()`), hareketli bir düşman uçağına değil.
1v1/2v2 betikleri bunu her tikte hedefi yeniden hesaplayarak dolaylı
aşıyor ama bu, eğitim dağılımının biraz dışında bir kullanım. Faz 2
(taktik komutan) eğitilirken izlenecek ilk şüpheli.

Ayrıntı ve tüm sayısal ölçümler: `REQUIREMENTS.md` → §RAD/MSL/ENG/SIM2.
Tuzakların tam listesi: `HANDOFF.md` → TUZAKLAR §"BVR savaş katmanı".

---

## Adım 18 — İlk uçtan uca koşu: sıfır isabet, iki gizli hata

Faz 1.5'in smoke testleri 180 saniye çökmeden koştu ve "tamam" diye
işaretlendi. Bağımsız bir denetimde görüldü ki **hiçbir füze isabet
etmemişti** — 1v1'de 8/8, 2v2'de 16/16 `kor`. Zincirin son halkası
(isabet → imha → `hedefsiz`) canlı simülasyonda hiç koşmamıştı.

İlk yorum "betik her tehditte tam kaçıyor, Faz 2'nin işi" idi. Ölçüm, başka
iki mekanizma buldu:

**1) Crank açısı radar gimbal'ini aşıyordu.** Betik 90° kırıyordu; kendi
radar kilidin gimbal'de (60°) coast'suz anında kopuyor, füzen körleşiyordu.
Daha şaşırtıcısı: 50° bile yetmedi — guidance komut edilen yönü aşıyor ve
ATA 65.5°'ye çıkıyor.

| crank | sonuç |
|---|---|
| 90° | kilit ATA −61°'de düştü, hepsi `kor` |
| 50° | tepe ATA 65.5°, hepsi `kor` |
| 45° | karışık |
| **35°** | **karşılıklı isabet** |

**2) Füze kütlesi canlı yolda hiç yoktu.** `Engagement.fire()` kütleyi
`mass_lb` alanına yazıyordu; test mock'unda o alan vardı, gerçek
`FlightState`'te yoktu. Kod sessizce hiçbir şey yapmıyordu. Düzeltme
doğrudan JSBSim'e yazıyor: kalkışta 24.199 lb, atış başına −335 lb.

Düzeltmeden sonra 1v1: pitbull t=43.3 s, **karşılıklı isabet t=62.2 s**,
0 `kor`.

**Ders:** "X çünkü Y" yorumuna "başka bir Z de aynı sonucu üretir mi?" diye
sorulmadan "düzeltilmiyor" denmeyecek. Ayrıca iki eski ders tekrarlandı:
başarısız olamayan test (1.5a simetrik kurulum) ve mock ile geçen ölü kod.

---

## Projeyi anlatırken vurgulanacak üç şey

0. **Hipotezini ölçümden ÖNCE yaz, yanlış çıkınca da sil değil kaydet.**
   Bu projede dört kez oldu; ikisi: uzun eğitimin işe yarayacağını sandık (yaramadı, sebebi
   ödül–kriter uyumsuzluğu çıktı); komutanın zarf ihlallerini patlatacağını
   sandık (patlatmadı, asıl kaynak varış düzeltmesiymiş). İkisinde de
   **gözlem doğru, çıkarım yanlıştı**. Bu kayıtlar projenin zayıflığı değil,
   yöntemin kanıtı.

1. **Katmanlı kurulum ve dondurma disiplini.** Her katman kendi kabul
   kriterlerini geçtikten sonra donduruldu. Üç zor bileşeni aynı anda
   devreye almanın teşhisi imkânsızlaştırdığını önceki denemeden biliyorduk.

2. **Ölçüm metodolojisinin kendisi bir katkı.** Bootstrap GA, bölüm-birimli
   istatistik, örtüşen aralıkta iddia etmeme kuralı, aynı-politika ablasyonu,
   tohum doğrulaması. Üç iddia bu yüzden geri çekildi — ve bu, projenin
   zayıflığı değil **titizliğinin kanıtı**.

3. **Ödül–kriter uyumsuzluğu bulgusu.** "Uzun eğitim neden zarar verdi"
   sorusunun ölçülmüş cevabı: kabul kriteri getirinin %0.26'sıydı.
   Genellenebilir bir ders — RL sistemlerinde önemsediğin şey ödülde
   **ölçülebilir bir pay** almalı.

---

## Dosya haritası (hızlı referans)

```
bvr/sim/aircraft.py          F-16 sabitleri, FCS komut sözleşmesi
bvr/sim/jsbsim_bridge.py     JSBSim sarmalayıcı, trim, türbülans
bvr/sim/acmi.py              Tacview kaydı
bvr/control/inner_loop.py    klasik PI iç döngü (γ, φ, Mach, β)
bvr/sysid/excitation.py      uyarım sinyalleri
bvr/sysid/collect.py         veri toplama
bvr/sysid/evaluate.py        kalıcı uyarım doğrulaması
bvr/models/state_def.py      11-boyutlu durum, zarf bariyerleri
bvr/models/base.py           model tabanı, CBF satır üretimi
bvr/models/dmd.py            DMD (taban)
bvr/models/edmd.py           EDMD (SEÇİLEN: physics kitaplığı)
bvr/models/deep_koopman.py   Deep Koopman (karşılaştırma)
bvr/safety/cbf.py            OSQP tabanlı CBF kalkanı
bvr/safety/robust.py         gürbüz pay (park edildi)
bvr/envs/guidance_env.py     RL ortamı, ödül fonksiyonu (eğitim)
bvr/envs/guidance_shared.py  bearing/obs/aksiyon donusumleri (env+driver ORTAK)
bvr/envs/guidance_driver.py  dondurulmus guidance'in CANLI (egitim-disi) surucusu
bvr/agents/train_guidance.py SAC eğitimi + BestByCaptureQuality
bvr/agents/scripted_guidance.py  klasik güdüm (taban)
bvr/config.py                YAML deney tanımı

bvr/combat/geometry.py       ATA/AA/HCA/kapanma/LOS-rate
bvr/combat/radar.py          RCS+Doppler notch+gimbal+kilit/coast (cok hedefli)
bvr/combat/missile.py        3-DOF PN fuze, boost/coast, datalink hafizasi, seeker gate
bvr/combat/engagement.py     atis yetkisi, muhimmat, olay gunlugu (N-ucakli)

scripts/smoke_trim.py        trim doğrulaması
scripts/id_fcs.py            FCS komut ölçümü
scripts/id_nz.py             yük faktörü ölçümü
scripts/test_inner_loop.py   16 kabul testi
scripts/collect_sysid.py     sysid veri toplama
scripts/fit_model.py         model eğitimi
scripts/compare_models.py    DMD/EDMD/DeepKoopman karşılaştırma
scripts/train.py             eğitim giriş noktası
scripts/sweep.py             hiperparametre taraması
scripts/mission_eval.py      görev metrikleri
scripts/safety_eval.py       zarf ihlali + kalkan ablasyonu
scripts/command_hold_test.py ARAYÜZ SÖZLEŞMESİ (14 manevra)
scripts/violation_depth.py   ihlal derinliği ve süresi
scripts/reward_audit.py      ödül dağılımı
scripts/reward_whatif.py     denemeden önce tahmin
scripts/reward_compare.py    ödül ayarları karşılaştırma
scripts/diagnose_policy.py   politika teşhisi
scripts/margin_sweep.py      gürbüz pay taraması
scripts/reproduce.py         tekrar üretilebilirlik
scripts/test_model.py        ELLE TEST: hedef + anlik deger, adim adim
scripts/stress_commander.py  agresif betikli komutanla stres testi
scripts/violation_where.py   ihlaller NEREDE olusuyor (menzil/yatis/alcalma)
scripts/two_jsbsim_smoke.py  iki F16Sim orneginin birbirini kirletmedigi testi (1.5a)
scripts/guidance_driver_smoke.py  GuidanceDriver <-> GuidanceEnv fizik esdegerligi (1.5b)
scripts/guidance_driver_dual_hold_test.py  iki esanli surucu kontaminasyon testi (1.5b)
scripts/missile_dt_convergence.py  fuze fizigi dt-yakinsama olcumu (ENG-10)
scripts/payload_check.py     muhimmat kutlesinin guidance sozlesmesini bozmadigi testi
scripts/bvr_1v1_smoke.py     uctan uca 1v1 angajman + Tacview kaydi (1.5c/1.5d)
scripts/bvr_2v2_smoke.py     uctan uca 2v2 angajman + Tacview kaydi (1.5e)
```

### Elle test etmek için

```bash
# Sabit komut ver, oturmasını izle
python scripts/test_model.py runs/reward_r3_both/sac_1999968_steps.zip \
    --hold 25000 0.90 --from 30000 0.80

# Serbest uçuş + Tacview kaydı
python scripts/test_model.py <model> --acmi runs/test.acmi --every 20

# Kalkansız karşılaştırma
python scripts/test_model.py <model> --no-shield

# BVR savaş katmanı: uctan uca 1v1/2v2 + Tacview kaydi
python -m scripts.bvr_1v1_smoke runs/reward_r3_both/sac_1999968_steps.zip \
    --duration 180 --acmi runs/1v1.acmi
python -m scripts.bvr_2v2_smoke runs/reward_r3_both/sac_1999968_steps.zip \
    --duration 180 --acmi runs/2v2.acmi
```

Diğer belgeler: `ARCHITECTURE.md` (katman sözleşmeleri) ·
`REQUIREMENTS.md` (40+ gereksinim + RAD/MSL/ENG/SIM2, kriter → ölçüm → durum) ·
`HANDOFF.md` (50 maddelik tuzak listesi) · `STATUS.md` (anlık durum) ·
`HATA_GUNLUGU.md` ("bu bir hata mı?" araştırmalarının kısa kaydı)
