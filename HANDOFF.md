# Devir Dokümanı — Yeni Oturum İçin

> Bu dosya, projeyi hiç görmemiş bir oturumun (veya kişinin) devam
> edebilmesi için yazıldı. Önce bunu, sonra `ARCHITECTURE.md` ve
> `REQUIREMENTS.md`'yi oku. Anlık durum için `STATUS.md`.

---

## 1. Proje nedir

JSBSim F-16 üzerinde, **kademeli (cascade) kontrol mimarisi** ile otonom
görüş-ötesi (BVR) savaş uçağı. Katmanlar aşağıdan yukarı:

```
JSBSim F-16 FLCS        120 Hz   uçağın kendi fly-by-wire'ı (hazır)
İç döngü (klasik PI)     60 Hz   γ/φ/Mach tutucu            ✅ BİTTİ
Guidance (SAC)           10 Hz   hedef → [φ_cmd, γ_cmd, M_cmd]  ✅ DONDU
Güvenlik filtresi (CBF)  10 Hz   komut yöneticisi           ✅ DONDU
Taktik komutan (PPO)      2 Hz   radar/füze/kaçış/kol uçuşu ⬜ SONRAKİ
```

**BVR savaş katmanı (dikey yığının YANINDA, ayrı bir modül grubu) —
Faz 1.1–1.5 ✅ TAMAMLANDI:** angajman geometrisi, radar (RCS+Doppler+
kilit), füze (3-DOF PN), angajman muhasebesi (atış yetkisi/mühimmat/
olay günlüğü), çok uçaklı simülasyon (1v1 ve 2v2) + Tacview kaydı —
hepsi `bvr/combat/` altında, guidance'tan (yukarıdaki `GuidanceDriver`
üzerinden) tüketiliyor. Ayrıntı: `REQUIREMENTS.md` §RAD/MSL/ENG/SIM2.
Sıradaki: Faz 2 — taktik komutan (PPO, 2 Hz), bkz. §8.

**Amaç ikili:** (a) tez — Koopman tabanlı öğrenilmiş model + CBF güvenlik
filtresi, DMD→EDMD→Deep-Koopman karşılaştırması; (b) portfolyo — çalışan,
Tacview'de gösterilebilir bir BVR demosu.

---

## 2. EN ÖNEMLİ İLKE: katmanları aşağıdan yukarı dondur

Bir alt katman değişirse **üstündeki her şey geçersizleşir ve yeniden
eğitilmesi gerekir.** Bu projede bu kurala uymamak defalarca saatler
kaybettirdi (v5→v9 arası 5 gereksiz eğitim koşusu).

Pratik sonuç:
- Kalkan **eğitim döngüsünün içinde** olduğu için, kalkanı değiştirmek
  guidance'ı geçersiz kılar → kalkan guidance'tan **önce** kesinleşir.
- Guidance dondurulmadan komutan eğitimine **başlanmaz**.

---

## 3. Kilitli kararlar (yeniden tartışılmayacak)

| Konu | Karar | Gerekçe |
|---|---|---|
| Mimari | Kademeli: klasik iç döngü + RL guidance + CBF + RL komutan | Uçtan uca RL en zor uç; literatür ve endüstri kademeli yapar |
| RL komutu | `[φ_cmd, γ_cmd, M_cmd]` — **γ, θ değil** | θ = γ + α; aynı θ farklı hızlarda farklı tırmanış verir |
| CBF yeri | **Dış döngü komutunda** (10 Hz), yüzey komutunda değil | 60 Hz'de bağıl derece yüzünden \|CB\|≈0.01, kalkan işlevsiz |
| Guidance algoritması | **SAC** | Sürekli aksiyon, örneklem verimliliği (JSBSim adımı pahalı) |
| Komutan algoritması | **PPO** | Karma aksiyon uzayı (sürekli + kesikli ateş/hedef) + self-play durağansızlığı |
| Kalkan modeli | `data/models/edmd_physics.pkl` | MDL-08: denetlenebilirlik > doğruluk (sertifikasyon) |
| Model fit | **Offline**, dondurulmuş | Kalıcı uyarım ancak tasarlanmış uyarımla sağlanır |
| Normalizasyon | **Sabit ölçekler** (`state_def.py`), VecNormalize yok | Güvenli küme eğitim boyunca oynamamalı |
| Deep-Koopman | Sadece karşılaştırma satırı | Ek zaman harcanmayacak |
| Yedek politikalı filtre | **Park edildi** | Kritik yolda değil; enerji komutanın ödülünde |
| Kanat uçağı | Önce scripted, sonra MARL | Risk düşük, ikisinin karşılaştırması ayrı sonuç |
| Düşman | Scripted havuz + eski ajan sürümleri (opponent sampling) | AlphaDogfight yaklaşımı |

---

## 4. TUZAKLAR — bunları tekrar keşfetmeye çalışma

Bu bölüm dokümanın en değerli kısmı. Her madde **ölçümle** bulundu.

### Simülasyon
1. **Trim şart.** `run_ic()` + `run()` yeterli değil — trim'siz uçak 60
   saniyede 14–23 bin ft düşüyor. Ölçüldü.
2. **Rüzgâr/türbülans JSBSim reset'inde temizlenmez.** Önceki bölümün
   türbülansı açıkken trim yakınsamaz → worker ölür → `BrokenPipeError`.
   Çözüm: `reset()` başında `set_turbulence(0,0,0)`.
3. **Yakıt trim'den ÖNCE ayarlanmalı** (trim ağırlığa bağlı).
4. **JSBSim F-16'nın kendi FLCS'i var.** `fcs/*-cmd-norm` ham yüzey açısı
   DEĞİL: aileron = yatış *hızı* komutu (1.0 ↔ 180 °/s), elevator =
   *g-yükü* komutu (−1.0 ↔ +9 g, +0.44 ↔ −4 g), içinde α limiter var.
5. **`accelerations/n-pilot-z-norm` düz uçuşta −1.0 okur.** İşaret
   `state_def.state_from_flight` içinde TEK yerde çevriliyor.

### Kontrol / CBF
6. **Bağıl derece.** 0.1 s'lik tek adımda komutun `alt`/`h_dot` üzerindeki
   etkisi gürültü seviyesinde (`B[h_dot, γ_cmd] = −0.0005`, işareti bile
   yanlış). Çözüm: çok adımlı (öngörülü) CBF, `cbf_rows(horizons=...)`.
7. **Zarf hiyerarşisi:** işletme ⊂ **güvenlik** ⊂ sonlandırma ⊂ fiziksel.
   - Güvenlik = işletme olursa filtre sürekli tetiklenir (yatış bariyeri
     müdahaleyi %42'ye çıkarmıştı; kaldırınca %7.5'e düştü).
   - Güvenlik ⊄ sonlandırma olursa filtre **yanlış sayıyı** korur
     (Mach bariyeri 0.40, sonlandırma 0.30 idi).
8. **QP satır ölçeklemesi şart.** Ölçeklenmemiş bariyerlerde satır normları
   4 mertebe farklıydı; OSQP küçük satırları yok sayıyor, 3000 çağrının
   241'inde hata veriyordu. Bariyerler `state_def`'te boyutsuzlaştırılıyor,
   kalkan ayrıca satırları birim norma ölçekliyor ve **otoritesiz satırları
   atıyor** (`hard_deck@1` gibi).
9. **`cbf_rows` önbelleklenmeli.** `A^i` ve `S_i` sabittir; her çağrıda
   yeniden hesaplamak QP'den pahalıydı (800 → 235 µs).
10. **Kalkan eğitim döngüsünde olmalı.** Sonradan takınca: müdahale %62,
    maliyet −%14, erken sonlanma 0→4. Döngü içinde: %21, −%2.8, 0.

### RL / ödül
11. **Gauss şekillendirme uzakta gradyan vermez.** `exp(-(Δh/1000)²)`
    3000 ft hatada 1e-4 → gizli seyrek ödül. Çözüm: **ilerleme** ödülü
    (hata bu adımda ne kadar kapandı, fiziksel max hızla normalize).
12. **Ajan az ağırlıklı kanalı rasyonel olarak yok sayar.** Mach ağırlığı
    0.5 iken tolerans tutturma %30; 0.9 yapınca **%72**.
13. **Ulaşılamaz hedef üretme.** Hedef Mach bağımsız çekiliyordu; 42 kft'te
    taban 0.68 iken 0.55 isteniyordu. Artık irtifaya bağlı + sınırlı
    rastgele yürüyüş.
14. **Komut titremesi.** `w_action_rate=0.05` ödüllerin %1'i kadardı;
    ajan 3 Hz'de bang-bang yapıyordu ve bu **Mach takibini öldürüyordu**
    (yavaş autothrottle hiç oturamıyor). Çözüm: slew sınırı (yapısal) +
    ceza 0.30.


24. **Kabul kriteri ödülde görünmüyorsa öğrenilmez — ve uzun eğitim ZARAR
    verir.** Varış kalitesine bağlı ödül, bölüm getirisinin **%0.26'sıydı**
    (hedef bonusu 16.8/2374; üstelik 10.6'sı koşulsuz). `ep_rew_mean` 1.5M
    adımda doydu; kalan 6.5M adım kriteri kısıtlamayan %99.7'yi optimize
    etti ve yakalama kalitesi 0.540 → 0.316'ya düştü. Bir kriteri
    "önemsiyorsan" ödülde **ölçülebilir bir pay** almalı. Teşhis aracı:
    `scripts/reward_audit.py` — terim terim fiili dağılım.
25. **Şekillendirme çekirdeği toleransla aynı ölçekte olmalı.** `alt_prec_ft`
    1000 iken tolerans ±500'dü: 180 ft hatada ajan ödülün %97'sini zaten
    alıyordu, son 300 ft'i kapatmanın karşılığı yoktu. Ödülün %32.7'si bu
    terimlerdeydi, yani en büyük ikinci blok yanlış şeyi söylüyordu.
26. **SON modeli alma — kabul kriterine göre EN İYİ modeli al.** Bu koşuda
    son model (8M) 2M'deki modelin yarısı kadar iyiydi. `BestByCaptureQuality`
    callback'i 250k adımda bir kriteri ölçüp `sac_best.zip` saklar.

27. **Bir filtrenin KAPSAMINI baştan yaz, yoksa iddiayı fazla büyütürsün.**
    CBF kalkanı 10 Hz'de bir komut yöneticisidir. Ölçüldü: iç döngü komut
    sınırı −2.0 g iken gerçekleşen en kötü geçici **−4.581 g** — farkı komut
    değil, rüzgâr darbesi ve dinamik aşım üretiyor. Kalkan bunu yapısı gereği
    engelleyemez. Savunulabilir cümle: *"komut seviyesinde zarf ihlali üreten
    girdileri filtreler; 60 Hz dinamik/atmosferik geçici aşımları engellemez."*
    Bariyeri sıkmak veya sert moda almak bu kuyruğu KAPATMAZ — ikisi de komut
    seviyesinde çalışır, medyanı iyileştirir, kuyruğa dokunmaz.
28. **"İhlal oranı" ile "ihlalli bölüm sayısı" farklı şeyler söyler.**
    Seçilen modelde kalkanlı/kalkansız oran 0.057 vs 0.275 (5 kat) ama
    ihlalli bölüm 24/150 vs 23/150 (aynı). Doğru yorum: kalkan tehlikeli
    duruma *girmeyi* engellemiyor, girildiğinde **çıkışı kısaltıyor**.
    İkisini birlikte raporlamazsan yanlış hikâye anlatırsın.
29. **Ayrı eğitilmiş iki politikayı kıyaslamak kalkanın etkisini ÖLÇMEZ.**
    `guidance_shield` vs `guidance_noshield` karşılaştırması kalkanın
    etkisiyle politika farkını karıştırıyordu ve SAF-05'i "✅, GA'lar
    örtüşmüyor" göstermişti. AYNI politikayı kalkanlı/kalkansız koşturunca
    fark kayboldu ve iddia geri çekildi. Doğru ablasyon: tek politika, iki
    koşul.
30. **Bir ödül değişikliğinin bedeli tek boyutta olmayabilir.** `r3` kaliteyi
    0.650 → 0.795 çıkardı, verimi 0.864 → 0.833 düşürdü (biliniyordu) VE zarf
    ihlallerini 0.014 → 0.057'ye çıkardı (ölçülmemişti, sonradan bulundu).
    Yeni bir ödül konfigürasyonu seçmeden önce **güvenlik boyutunu da** ölç.

31. **Bir korelasyon gördün diye MEKANIZMAYI bildiğini sanma — bu projede
    ÜÇ KEZ oldu.** (a) "Agresiflik ihlal üretir" sanıldı; ilişki var ama
    zayıf (0.000 → 0.002). (b) "İhlaller varış öncesi hassasiyet
    düzeltmesinden geliyor" denildi — gerekçe, iki kurulum arasındaki tek
    yapısal farkın varış aşaması olmasıydı; `violation_where.py` ile
    ÇÜRÜTÜLDÜ (ihlallerin %2'si yakalama yarıçapının 2 katından yakın,
    medyan menzil tüm adımlarınkiyle aynı). (c) Üçüncü hipotez ölçüldü ve
    doğrulandı: ihlaller **yatık alçalmada** oluşuyor — alçalma 4.3×,
    yatış+alçalma 3.5× zenginleşme. Mekanizma iç döngü formülünde:
    `n = (V·γ̇/g + cos γ)/cos φ`, 55° yatışta 1/cos φ = 1.74.
    **Ders: "tek yapısal fark şu" akıl yürütmesi delil değildir.**
32. **Bir açıklama çürüyünce, ONA DAYANAN kararları da geri al.** nz_min
    referansı 0.042'den 0.001'e indirilmişti; gerekçe "BVR kullanımı stres
    testine benzer" idi ve bu, çürütülen mekanizmaya dayanıyordu. Gerçek
    mekanizma yatık alçalma olunca beklenti TERSİNE döner — BVR'da yatık
    alçalma boldur. Referans düzeltmesi geri alındı, muhafazakâr (yüksek)
    uç kullanılıyor. Çürüyen açıklamayı düzeltip ona dayanan kararı
    bırakmak, sessiz bir hata kaynağıdır.
33. **Açıklayamadığın bir farkı uydurma açıklamayla doldurma.** Stres testi
    ile hedef yakalamalı ortam arasındaki 20 katlık fark HÂLÂ
    açıklanamamıştır ve belgede öyle durmaktadır. İlk iki açıklama denemesi
    de yanlış çıktığı için, üçüncüsünü "makul göründüğü" için yazmak
    aynı hatayı tekrarlamak olurdu.
34. **Pahalı katmanı eğitmeden ÖNCE, onun girdi dağılımını taklit et.**
    Komutanı yeniden eğitmek guidance'tan kat kat pahalı. İç döngüye
    dokunma kararı, komutan eğitilmeden betikli bir komutanla verildi
    (`scripts/stress_commander.py`). Sıralamayı ters kurmak, düzeltme
    maliyetini katlardı.

35. **KOMUTAN ARAYÜZÜ KURALI (TAC-08): sanal hedefi 5–25 nmi'ye koy.**
    Güdüm katmanı yön komutu değil HEDEF NOKTASI anlar. Komutanın yön
    komutunu sanal hedefe çevirirken "hiç varmasın diye uzağa koyayım"
    demek doğal ve YANLIŞ. Ölçüldü: 40 nmi ve ötesinde politika sönümsüz
    limit çevrimine giriyor (yatış std 30–37°, periyot 12.7 s); 25 nmi'de
    std 6.4°, çevrim yok. Eğitim aralığı 3.3–14.8 nmi. Mekanizma: uzak
    hedefte kerteriz uçağın yönüne duyarsız, kurs döngüsünün doğal
    sönümlemesi kayboluyor. Kanıt: yatış–kerteriz gecikmeli korelasyon
    r = −0.949 @ 2.2 s.
36. **Test aracının kendisi ölçümü bozabilir — ve bunu KULLANICI fark etti.**
    `command_hold_test.py` hedefi 200 nmi'ye koyuyordu, yani GUI-11
    sözleşmesi eğitim dağılımının DIŞINDA ölçülmüştü. Kullanıcı Tacview'de
    uçağın sallandığını görüp sordu; ölçünce aracın kusuru çıktı. Araç
    düzeltildi (30 nmi) ve sonuç 14/14 + 14/14 KORUNDU, sapmalar 33 ft'ten
    5–6 ft'e indi. Ders: bir aracın ürettiği koşul, ölçtüğü şeyin geçerlilik
    alanı içinde mi diye sor. Ayrıca **görsel inceleme (Tacview) sayısal
    metriklerin kaçırdığını yakalar** — irtifa ve Mach metrikleri bu
    salınımı hiç göstermiyordu.

37. **JSBSim'de NOKTA KÜTLE de reset arasında kalıcıdır** (türbülans gibi,
    bkz. tuzak 2). `inertia/pointmass-weight-lbs[0]` bir kez yazılırsa
    sonraki `reset()` onu temizlemez. Referans koşuya geçerken açıkça
    sıfırlanmazsa "yüksüz" ölçüm yüklü çıkar. Ayrıca kütle yazıldıktan
    sonra `fdm.run()` çağrılmadan `inertia/weight-lbs` GÜNCELLENMEZ —
    JSBSim kütle özelliklerini adım sırasında yeniden hesaplar.
38. **F-16 modelinde yalnızca pointmass[0] gerçektir.** `[1]`, `[2]`
    yazılabilir ve geri okunabilir ama **kütle dengesine girmez** — sessizce
    etkisiz kalır. Ek yük `[0]`'a eklenmeli ve konumu **birleşik momenti
    koruyacak** şekilde seçilmelidir; aksi halde CG 8.4 inç geriye kayar.
    F-16 gevşek kararlı olduğu için bu, ölçümü yanlı hale getirir.
    (Gerçekte de harici yükler CG'ye yakın asılır — tam bu sebeple.)

39. **"Muhafazakâr sabit" varsayımını, sistemi değiştirdiğinde YENİDEN
    KONTROL ET.** `COMBAT_WEIGHT_LB = 25000` bilerek en ağır durum seçilmiş
    ve Mach tabanı bariyeri ona göre fit edilmişti. 4 AMRAAM eklenince uçak
    25.942 lb oldu ve varsayım sessizce çürüdü — bariyer 10 kft'te
    muhafazakâr olmaktan çıkıp iyimser hale geldi (pay −0.0078 Mach).
    Etki küçük (manevra payı 1.25× → 1.22×) ama **hiç fark edilmeden
    geçebilirdi**: hiçbir test bunu yakalamazdı, çünkü testlerin hepsi
    varsayımın kendisini kullanıyordu. Bir sabitin yanında "muhafazakâr"
    yazıyorsa, sistemi değiştiren her eklemede o iddiayı yeniden ölç.

### BVR savaş katmanı (Faz 1.1–1.5, `bvr/combat/`)
40. **Çoklu-örnek simülasyonda "paylaşılan çerçeve" tek doğruluk kaynağı
    olmalı.** Her `F16Sim`/`GuidanceDriver` kendi `reset()` anını yerel
    (0,0) sanır (JSBSim IC'si böyle çalışır, bkz. tuzak 4-5'in devamı).
    İki uçağı aynı sahneye koymak için `dataclasses.replace()` ile
    `north_ft`/`east_ft`'e SABİT bir ofset eklenip PAYLAŞILAN bir kopya
    üretildi; driver'in kendi iç durumu hiç değişmedi. Bu düzeltme
    `bvr_1v1_smoke.py`, `bvr_2v2_smoke.py` VE `ACMIRecorder` içinde AYRI
    AYRI ama AYNI ilkeyle uygulandı — üçü de tek bir yardımcı fonksiyona
    çıkarılabilirdi, şimdilik kod tekrarı bilerek kabul edildi (küçük, 3
    kopya, davranışı ölçümle doğrulanmış).
41. **Dondurulmuş bir katmanın "eğitime özgü" sandığın parçası aslında
    sözleşmenin kendisi olabilir.** `GuidanceEnv`'den ayrıştırılan
    `GuidanceDriver` ilk sürümde `action_rate_limit` (komut savurma
    sınırı) uygulamıyordu — "bu bir eğitim düzenlileştirmesi, üretimde
    gerekmez" varsayımıyla. Yanlıştı: `GuidanceConfig.action_rate_limit`
    varsayılanı `0.25` (kapalı değil) ve dondurulmuş model TAM DA bu
    filtre ALTINDA kalibre olmuştu. `guidance_driver_smoke.py` ile
    yakalandı (200 adımda ~200 ft irtifa sapması); düzeltince fark <1e-11
    (kayan nokta gürültüsü) düştü. Ders: bir üretim sürücüsü yazarken
    "hangi filtreler eğitime özgü" sorusunu VARSAYMA, orijinal `step()`'in
    HER satırını hesaba kat.
42. **Füze fiziğinin dt-duyarlılığı MONOTONİK DEĞİL.** 6g manevra yapan bir
    hedefe karşı marjinal bir angajmanda dış tik dt=0.1 (10 Hz) ile sonuç
    (isabet/ıska), dt=0.02–0.002 arasındakinden FARKLI çıkabiliyor (bir ara
    dt'de temiz bir ıska, hem daha kaba hem daha ince dt'lerde isabet).
    `scripts/missile_dt_convergence.py` ile ölçüldü (gerçek Python ↔ ayrı
    bir Node.js portu çapraz doğrulamasıyla). Çözüm: füze fiziği dış
    muhasebe adımından bağımsız, kendi içinde N alt-adımla (varsayılan 5 →
    50 Hz) koşuyor (`Engagement.missile_substeps`); radar/muhasebe zaman
    sabitleri saniyeler mertebesinde olduğu için buna ihtiyaç duymuyor.
43. **Çok nesneli telemetride İKİ AYRI hata gizli kalabilir — tek nesneyle
    test etmek ikisini de kaçırır.** `ACMIRecorder`: (a) başlık alanları
    (Name/Type/Color/Pilot) tek bir `bool` bayrakla tutuluyordu — sadece
    İLK yazılan nesne başlık alıyordu, ikinci uçak/her füze isimsiz
    görünüyordu; `set[int]` yapılıp `obj_id` başına izlenerek düzeltildi.
    (b) konum `lon_deg`/`lat_deg`'den (her `F16Sim`'in KENDİ özel orijini)
    değil, `north_ft`/`east_ft`'ten (PAYLAŞILAN muhasebe çerçevesi, bkz.
    tuzak 40) TEK bir referans noktasından türetilmeliydi — aksi halde iki
    ayrı örnekten gelen iki uçak Tacview'de ÇAKIŞIK görünür. Tek-nesneli
    `demo_inner_loop.py` koşusu HİÇBİRİNİ yakalamazdı (tek nesnede hem
    başlık hem çakışma sorunsuz görünür).
44. **"Aynı anı" temsil eden iki değer, MUTLAKA aynı saatten gelmeli — iki
    ayrı sayaçtan değil.** Çok nesneli Tacview kaydında füze/uçak aynı
    tikte kaydediliyordu ama uçak kaydı `FlightState.t`'yi (driver'in İÇ
    saati, ADIM SONRASI, `(k+1)·dt`) kullanıyordu; füze kaydına ise
    betiğin YEREL döngü değişkeni `t = k·dt` (ADIM ÖNCESİ) veriliyordu.
    İkisi aynı anı temsil ediyor sanılıyordu ama 1 dt kaymışlardı. Sonuç:
    dosyada zaman damgaları GERİYE atlıyordu ve yeni fırlatılan bir
    füzenin İLK konumu, atış anındaki değil BİR TİK SONRAKİ uçak
    konumunda görünüyordu. Görünüşte "her ikisi de doğru" olan iki
    hesaplama, kaynakları farklı olduğu için sessizce ayrıştı. Çözüm: füze
    kaydına da uçağın kendi `st.t`'si verildi — TEK saat, iki tüketici.
45. **Bir sonuca TEK bir olası açıklama bulununca aramayı bırakma — bu
    HANDOFF'un kendi tuzak 31'inin bir tekrarıdır.** 1.5c/1.5e'de tüm
    füzeler `"kor"` (datalink kaybı) ile bitiyordu ve "betikli komutan
    her tehditte tam kaçıyor, dengelemiyor" diye yorumlanıp
    **düzeltilmeden** bırakılmıştı — makul bir açıklamaydı ve KISMEN
    doğruydu, ama TEK mekanizma olduğu hiç ölçülmemişti. Bağımsız bir
    incelemede ikinci, bağımsız bir sebep çıktı: kaçış manevrası sabit
    90° (tam beam) idi ve bu, radar gimbal sınırını (60°) aşıp **atıcının
    kendi kilidini** kırıyordu — "kaçıyor" ile "kendi füzeni köreltiyor"
    aynı olayın iki farklı görünümü sanılmıştı, oysa ikincisi ayrı,
    ölçülebilir bir geometrik sınır ihlaliydi. AYRICA üçüncü bir hata daha
    aynı köşede saklanıyordu: `Engagement.fire()`'ın füze kütlesi düşürme
    denemesi gerçek uçuşta hiç çalışmıyordu (sadece mock testte), yani
    "ağırlık modellendi" iddiası da (Faz 2'ye taşınacak not #4) yanlıştı.
    Üçü de tek bir "1.5 tamam" onayının ARKASINDA gizlenmişti. Ders: bir
    olumsuz/beklenmedik sonuca "X çünkü Y" dendiğinde, kabul etmeden önce
    en az bir alternatif mekanizmayı (burada: gimbal/kütle) ELEMEK
    gerekir — özellikle sonuç "zaten öyle olmasını bekliyorduk" gibi
    geliyorsa (burada: "betik basit, tabii ki dengelemiyor" beklentisi
    ikinci bakışı geciktirdi).

46. **Başarısız olamayan test, test değildir — bu projede iki kez yazıldı.**
    (a) HCA değişmez testi: kod `HCA = ATA − AA` hesaplıyordu, test `ATA =
    AA + HCA` diye bakıyordu — ATA 180° yanlış olsa bile geçti (hata
    enjeksiyonuyla kanıtlandı). (b) 1.5a sızıntı testi: iki JSBSim örneği
    AYNI kurulduğu için sızıntı olsa da fark 0 çıkar. Ölçüt: **testi yazınca
    koda kasıtlı hata enjekte et; kırmızıya dönmüyorsa hiçbir şey sınamıyor.**
47. **Mock ile geçen test, gerçek yolda ölü kod olabilir.** `Engagement.fire()`
    kütleyi `setattr(state, "mass_lb", ...)` ile düşürüyordu; mock'ta alan
    vardı, test geçti. Gerçek `FlightState`'te alan yok → `hasattr` sessizce
    False → füze kütlesi canlı simülasyonda HİÇ yoktu (JSBSim 22.859 lb
    kalıyordu, 24.199 olmalıydı). Fiziğe dokunan her şey sonunda **JSBSim'in
    kendi özelliğinden** (`inertia/weight-lbs`) okunarak doğrulanmalı.
48. **Duman testinin kriteri en önemli sonucu içermiyorsa "geçti" denmez.**
    1.5c/1.5e "180 s çökmeden koştu ✅" diye kapatıldı; ama 8/8 ve 16/16 füze
    `kor` idi — isabet → imha → `hedefsiz` yolu canlı simülasyonda hiç
    koşmamıştı. "4 uçak da hayatta" başarı gibi raporlandı. Kural: bir
    entegrasyon testinin en az bir koşusu zincirin son halkasını üretmeli.
49. **Etkili crank sınırı = gimbal − guidance aşımı, gimbal değil.** Radar
    gimbal'i 60°, ama guidance komut edilen yönü aşıyor (50° komut → 65.5°
    tepe ATA, tek gözlem). 90° ve 50° crank kendi füzeni köreltti; 35°
    karşılıklı isabet verdi, 45° karışık. Davranış ağacı "crank 60°" diye
    yazılırsa kendi füzesini sistematik olarak kör eder.

### Ölçüm (en çok hata yapılan yer)
15. **Tepe değeri güvenlik metriği değil.** Tek bir −3.37 g örneği
    "bariyer tutmuyor" gibi görünür; ihlal *oranı* %0.01'di.
16. **Adımlar bağımsız değil.** Uçak bir bölümde kötü duruma girip 200–900
    adım orada kalır. Adım bazlı "%ihlal" etkin örneklemi yüzlerce kat
    abartır. **Birim BÖLÜMDÜR**, belirsizlik bootstrap %95 GA ile verilir.
    Ölçüm: aynı konfigürasyon farklı tohumlarda %0.048–%1.742 (36 kat).
19b. **Değerlendirme BLOĞU başlı başına bir karıştırıcıdır.** Aynı üç
    model, 60 bölümlük iki farklı blokta 0.541/0.571/0.507 ve
    0.664/0.695/0.605 verdi — fark ~0.10, karşılaştırdığımız etkilerle
    aynı mertebede. 40–60 bölüm, bölüm zorluğunu ortalamaya yetmiyor.
    Blok *içi* karşılaştırma geçerli kalır (aynı bölümler), ama **mutlak**
    kabul kararı tek blokta verilemez. Kabul ölçümü artık **n=200**.
    (16 no'lu dersin bir üst seviyesi: birim doğru olsa da SAYISI yetersizse
    sonuç yine kırılgan.)
17. **Güven aralıkları örtüşen iki konfigürasyon arasında fark iddia edilmez.**
18. **Adım-içi tepe** izlenmeli (60 Hz), sadece karar sınırında (10 Hz) değil.
19. **Bariyer muhafazakârlığını ihlal sayma.** Bariyer sabit 25.000 lb
    varsayar; gerçek ağırlık düşükken uçak daha yavaş uçabilir ve bu
    tehlikeli değildir. `stall_marg` (gerçek ağırlık) ile `mach_marg`
    (bariyer) ayrı tutuluyor.

### Altyapı
20. **Konfigürasyon kopyası = sessiz hata.** `GuidanceConfig.shield_horizons`
    kalkanın varsayılanını eziyordu; enerji bariyeri eğitimde hiç aktif
    olmadı ve "çalışmıyor" sonucuna varılmıştı. Artık `None` → tek
    doğruluk kaynağı kalkanın kendisi.
21. **`model_best.pkl` gibi tek dosya kırılgan.** Her model açık isimle
    `data/models/` altına yazılır, config açık yolla seçer.
22. **TensorBoard kaydı bölüm bitişine bağlanmalı.** Paralel ortamlar
    senkron bittiği için SB3 log'u tam o anda boşaltır; sabit aralıklı
    kayıt diske hiç düşmüyordu (9 metrik yerine 30).
23. **Yavaş değişen durumu poly2 kitaplığına ekleme.** Yakıt eklenince
    `yakıt×X` terimleri eşdoğrusal oldu, ridge 1e-2'ye fırladı, EDMD-poly2
    uzun ufukta çöktü (0.155 → 0.246). Fizik kitaplığı etkilenmedi.

---

## 5. Ölçülmüş sonuçlar (referans)

**İç döngü** (4 koşul: 15k/M0.7 … 45k/M1.3) — 16/16 test geçti
- Roll 0→45°: t_r 0.70–0.77 s, aşım %3–17, kalıcı hata 0.07–0.16°
- γ 0→+8°: t_r 1.3–2.4 s, aşım %3.5–10, kalıcı hata ≈0
- Koordineli dönüş 45°/20 s: irtifa değişimi 27–51 ft

**Sistem tanımlama:** 717k geçiş, koşul sayısı 25.6 (kalıcı uyarım ✓)

**Modeller** (1-adım / 20-adım nRMSE, `relift`):
| model | z_dim | H=1 | H=20 |
|---|---|---|---|
| persistence | — | 0.0337 | 0.2878 |
| DMD | 12 | 0.0192 | 0.1453 |
| **EDMD-fizik** ← kalkan bunu kullanıyor | 31 | 0.0178 | 0.1481 |
| EDMD-poly2 | 78 | 0.0176 | 0.2159 |
| Deep-Koopman + kararlılık | 44 | 0.0158 | **0.1030** |

**Kalkan** (100 bölüm, bölüm-başı, %95 GA):
| | kalkansız | kalkanlı |
|---|---|---|
| `nz_min` ihlal % | 0.044 [0.028, 0.063] | **0.008 [0.003, 0.015]** |
| `beta_max` ihlalli bölüm | 4/100 | **0/100** |
| Ödül | 2101 [2028, 2174] | 2106 [2042, 2165] |
| Müdahale / slack / çözücü hatası | — | %17.6 / %4.2 / 159 |

→ `nz` ihlali **5.5× az**, GA'lar örtüşmüyor, **ödül maliyeti sıfır**.

**Ödül** (`scripts/reward_audit.py`): adım [−2.23, +2.80]; ulaşılabilir
tavan ≈3260; ölçülen 2479 (%76).

---

## 6. Dosya haritası

```
bvr/sim/aircraft.py        F-16 sabitleri, FCS sözleşmesi, atmosfer, stall
bvr/sim/jsbsim_bridge.py   trim, yakıt, türbülans, komut, durum
bvr/sim/acmi.py            Tacview kaydı
bvr/control/inner_loop.py  γ→n→elevator, φ→p→aileron, Mach→throttle
bvr/models/state_def.py    durum/girdi tanımı, sabit ölçekler, bariyerler (C,d)
bvr/models/base.py         DynamicsModel ABC + cbf_rows() (çok adımlı DT-CBF)
bvr/models/{dmd,edmd,deep_koopman}.py
bvr/safety/cbf.py          OSQP komut yöneticisi (satır budama + ölçekleme)
bvr/safety/robust.py       model hata marjı (park edildi)
bvr/sysid/{excitation,collect,evaluate}.py
bvr/envs/guidance_env.py   dış döngü RL ortamı (eğitim)
bvr/envs/guidance_shared.py bearing/obs/aksiyon donusumleri (env+driver ORTAK)
bvr/envs/guidance_driver.py dondurulmus guidance'in CANLI (egitim-disi) surucusu
bvr/agents/{train_guidance,scripted_guidance}.py
bvr/config.py              YAML → dataclass (bilinmeyen anahtar = hata)

bvr/combat/geometry.py     ATA/AA/HCA/kapanma/LOS-rate (BVR temel geometri)
bvr/combat/radar.py        RCS+Doppler notch+gimbal+kilit gecikmesi/coast
bvr/combat/missile.py      3-DOF nokta-kutle PN fuze, boost/coast, seeker gate
bvr/combat/engagement.py   atis yetkisi, muhimmat, olay gunlugu, N-ucakli muhasebe

configs/*.yaml             deney tanımları
data/models/*.pkl          açık isimli dinamik modeller
runs/<isim>/config.resolved.yaml   o koşunun TAM ayarları
```

---

## 7. Komutlar

```bash
python scripts/reproduce.py --list        # tüm boru hattı
python scripts/test_inner_loop.py         # iç döngü kabul testi (16)
python scripts/collect_sysid.py --episodes 600
python scripts/compare_models.py          # model karşılaştırma tablosu
python scripts/sweep.py                   # hiperparametre taraması
python scripts/train.py configs/X.yaml --save-buffer
python scripts/mission_eval.py <model.zip> -n 40    # görev metrikleri
python scripts/safety_eval.py -n 100               # güvenlik + GA
python scripts/reward_audit.py <model.zip>         # ödül ayrıştırma
python scripts/demo_inner_loop.py         # Tacview kaydı

# BVR savaş katmanı (Faz 1.1-1.5)
python -m scripts.bvr_1v1_smoke runs/reward_r3_both/sac_1999968_steps.zip \
    --duration 180 --acmi runs/1v1.acmi
python -m scripts.bvr_2v2_smoke runs/reward_r3_both/sac_1999968_steps.zip \
    --duration 180 --acmi runs/2v2.acmi
python -m scripts.missile_dt_convergence   # fuze fizigi dt-yakinsama olcumu
python -m pytest bvr/combat/tests -q       # 46 savas katmani testi

tensorboard --logdir runs/tb
```

---

## 8. Faz 2'ye (taktik komutan) taşınacak tasarım notları

> Bu bölüm Faz 1.1–1.5 BAŞLAMADAN ÖNCE yazılmıştı; artık savaş katmanı
> (geometri/radar/füze/muhasebe/çok-uçaklı-sim) BİTTİ. Aşağıda hangi
> maddenin gerçekleştiği, hangisinin hâlâ Faz 2'nin (taktik komutan)
> önünde durduğu işaretlendi.

1. ⬜ **Gözlem/aksiyon uzayı en baştan 4 uçaklık son durum için
   tasarlanacak**, 1v1'de maskeli. Aksi halde her aşamada sıfırdan eğitim
   gerekir. **Hâlâ Faz 2'nin işi** — guidance'ın kendisi 1v1 gözlem
   uzayında dondu; komutanın gözlem/aksiyon uzayı bu maddeyi ayrıca
   çözecek.
2. ⬜ Komutan **2 Hz** (taktik kararlar saniyeler ölçeğinde). Değişmedi.
3. ⬜ Düşman modeli **tak-çıkar**: 3-DOF nokta-kütle (eğitim, 10–50× ucuz)
   / tam JSBSim (demo). Henüz yazılmadı — 1.5c/1.5e'deki "kırmızı" da
   guidance'ın kendisiyle (aynı dondurulmuş model, ayna hedef) simüle
   edildi, ayrı/basit bir düşman modeli DEĞİL.
4. ✅ **Silah kütlesi eklendi ve ölçüldü — ama İKİ AŞAMADA.** İlk sürümde
   `Engagement.fire()`'ın kütle-düşürme denemesi (`hasattr(state,
   "mass_lb")`) SADECE mock durumlarla (`test_engagement.py`) çalışıyordu;
   gerçek `FlightState`'te böyle bir alan yok, `combat_state` da her adım
   yeniden üretilen bir kopya olduğu için gerçek uçuşta HİÇBİR ETKİSİ
   yoktu — bağımsız bir incelemeyle yakalandı (bkz. tuzak 45). Gerçek
   düzeltme `GuidanceDriver.set_payload()`: `payload_check.py`'nin ölçtüğü
   yöntemle (pointmass[0], CG korunarak) DOĞRUDAN JSBSim'e yazıyor;
   `Aircraft` artık tam mühimmatla (25.942 lb) trim oluyor, her atıştan
   sonra kalan yüke göre ağırlık güncelleniyor.
5. ✅ **Guidance ve kalkan dondurulmuş durumda çalışıyor** —
   `GuidanceDriver` bunun için yazıldı (fizik-sadece, ödül/Gym yok);
   1.5b'de `GuidanceEnv` ile <1e-11 tolerans içinde eşdeğerliği kanıtlandı.
6. ✅ **Gerçek BVR akışı UÇTAN UCA çalıştığı ÖLÇÜLDÜ.** İlk ölçümde tüm
   atışlar `"kor"` (datalink kaybı) ile sonuçlanıyordu ve bu "scriptli
   komutan dengelemiyor" diye yorumlanmıştı — EKSİK yorumdu (bkz. tuzak
   45): asıl sebep sabit 90° kaçışın radar gimbal sınırını (60°) aşıp
   ATICININ KENDİ kilidini kırmasıydı. `--crank-deg 35` düzeltmesiyle
   zincir (tespit→kilit→atış→destek→pitbull→seeker→isabet→imha) 1v1'de
   KARŞILIKLI İMHAYA kadar uçtan uca çalıştı. Crank/notch-beam/drag-abort AYRI,
   isimlendirilmiş taktik davranışlar olarak henüz yok — bunlar tam olarak
   **Faz 2'nin öğrenmesi beklenen şey**, betikli komutandan beklenmiyordu.
7. ✅ **Temel taktik birim iki uçaklı kol; dört uçak = iki kol — 1.5e'de
   DOĞRULANDI.** 2v2 koşusu (4 `GuidanceDriver`, 4 radar, çapraz ateş,
   16 toplam mühimmat) `Engagement`/`Radar`'da HİÇBİR kod değişikliği
   gerektirmedi — ikisi de baştan N-uçaklı tasarlanmıştı. Bu, mimari
   kararın (veri yapısı seviyesinde genellik) ödediği somut bir kanıt.
8. ⬜ **YENİ (1.5b'de fark edildi, henüz çözülmedi):** dondurulmuş guidance
   politikası SABİT HEDEF NOKTALARINA uçmak için eğitildi, düşman uçağa
   değil (`guidance_env.py::_new_waypoint()` biri yakalanana kadar
   değişmeyen sabit bir nokta üretir). 1v1/2v2 betikleri bunu "komutanın
   ürettiği hareketli sanal hedefe" (TAC-08, 5-25 nmi) her tikte yeniden
   hedefleyerek DOLAYLI olarak aşıyor — ama bu, guidance'ın GERÇEKTE
   gördüğü eğitim dağılımının biraz dışında bir kullanım şekli. Faz 2
   komutanı eğitilirken bu dağılım-kayması izlenmeli; eğer sorun çıkarsa
   (ör. agresif manevra yapan hedeflere karşı guidance kalitesi düşerse)
   ilk bakılacak yer burası.
