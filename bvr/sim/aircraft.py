"""
F-16C sabitleri ve JSBSim FCS komut sozlesmesi.

Bu dosya "uctak ne kadar cekebilir" ve "fcs/*-cmd-norm gercekte ne demek"
sorularinin TEK dogruluk kaynagidir. Kontrolcu, limiter, CBF ve ortam
hepsi buradaki degerleri okur; hicbir yerde sihirli sayi olmaz.

Kaynak: JSBSim 1.3.0 aircraft/f16/f16.xml (FCS kanallari birebir okundu).
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# 1. JSBSim F-16 FCS KOMUT SOZLESMESI
# ---------------------------------------------------------------------------
# Bu model bir fly-by-wire CAS'tir; fcs/*-cmd-norm ham yuzey acisi DEGILDIR.
#
# ROLL  : fcs/aileron-cmd-norm  = normalize yatis HIZI komutu.
#         f16.xml -> fcs/roll-rate-norm = 0.31821 * p  (p: rad/s)
#         Komut ile p karsilastirilip PID ile kapatilir => cmd 1.0 <-> p_max.
ROLL_RATE_NORM_GAIN = 0.31821                     # f16.xml pure_gain
P_CMD_MAX_RADS = 1.0 / ROLL_RATE_NORM_GAIN        # 3.1425 rad/s
P_CMD_MAX_DEGS = math.degrees(P_CMD_MAX_RADS)     # ~180 deg/s

# PITCH : fcs/elevator-cmd-norm = g-yuku + pitch-rate karisimi komutu.
#         ISARET: NEGATIF komut = burun YUKARI = POZITIF G.
#         f16.xml clipto -> [-1.0, +0.44]  ("100% up = 9G, 44% down = -4G")
ELEVATOR_CMD_MIN = -1.0       # tam cekis  -> +9 G
ELEVATOR_CMD_MAX = 0.44       # tam itis   -> -4 G
PITCH_RATE_NORM_GAIN = 6.2    # fcs/pitch-rate-norm = 6.2 * q
G_LOAD_NORM_GAIN = 0.020      # fcs/g-load-norm  = 0.020 * (Nz - cos(theta)cos(phi))

# YAW   : fcs/rudder-cmd-norm -> yaw damper + yanal ivme geri beslemeli PID.
#         Normal ucusta 0 birakilir; FCS koordinasyonu kendisi saglar.

# THROTTLE: fcs/throttle-cmd-norm -> gain 2 -> fcs/throttle-pos-norm [0..2]
#         0.0  = rolanti
#         0.5  = ASKERI GUC (military / 100% kuru itki)
#         >0.5 = ART YAKICI bolgesi (itki burada SICRAR -> PID titreyebilir)
#         1.0  = tam art yakici
THROTTLE_MIL = 0.5
THROTTLE_AB_MIN = 0.5         # bu esigin ustunde AB devrede

# ---------------------------------------------------------------------------
# 2. UCUS ZARFI (CBF bariyerleri ve limiter bu degerleri kullanir)
# ---------------------------------------------------------------------------
# Not: FLCS zaten alpha'yi ~30 derecede kesiyor (f16.xml elevator-scheduler).
# Buradaki ALPHA_MAX_DEG onun ALTINDA tutulur ki bizim katmanimiz once devreye
# girsin ve FLCS'in sert kesmesi hic tetiklenmesin.
ALPHA_MAX_DEG = 22.0          # calisma limiti (FLCS sert limiti 30 deg)
ALPHA_MIN_DEG = -8.0
BETA_MAX_DEG = 10.0           # yanal kayma (departure onleme)

NZ_MAX = 9.0                  # yapisal + FLCS pozitif g limiti
NZ_MIN = -3.0                 # calisma limiti (FLCS -4 g'ye izin verir)

MACH_MAX = 2.0
# GUVENLIK bariyeri icin Mach TABANI. Ortamin sonlandirma esiginden (0.30)
# BELIRGIN SEKILDE YUKARIDA olmalidir: bariyer, sonlanma sinirinin DISINDA
# kalirsa filtre yanlis sayiyi korur -- olculdu, kalkan acikken 3 ek
# low_mach sonlanmasi bundan cikti. Kural: guvenlik zarfi her zaman
# sonlandirma zarfinin ICINDE.
MACH_MIN = 0.40
QBAR_MAX_PSF = 2133.0         # ~800 KEAS dinamik basinc limiti (yapisal)

ALT_MIN_FT = 1000.0           # mutlak zemin (bolum sonlandirma)
ALT_MAX_FT = 55000.0          # servis tavani ustu
HARD_DECK_FT = 5000.0         # guvenlik tabani (CBF bariyeri burada)
TERM_DECK_FT = 3000.0         # bolum sonlandirma tabani -- bariyerin ALTINDA,
                              # yoksa bariyerin marji sifir olur

BANK_MAX_DEG = 80.0           # dis dongu komut zarfi
GAMMA_MAX_DEG = 30.0          # ucus yolu acisi komut zarfi
GAMMA_MIN_DEG = -30.0

# ---------------------------------------------------------------------------
# 3. FIZIKSEL SABITLER / OLCEKLER
# ---------------------------------------------------------------------------
G_FPS2 = 32.174               # yercekimi (ft/s^2)
FT_PER_M = 3.280839895
KTS_PER_FPS = 0.5924838
# JSBSim f16.xml'den okundu: 2 x 3486 lb dahili tank.
MAX_FUEL_LBS = 6972.0
EMPTY_WEIGHT_LB = 17400.0     # f16.xml empty-weight
#: Agirlik araligi: 17.600 (bos tank) ... 24.600 lb (tam dahili yakit)

# Gozlem olcekleme icin SABIT bolenler.
# VecNormalize gibi canli istatistik KULLANILMAZ: guvenli kume ve gozlem
# uzayi egitim boyunca yerinden oynamamali (eski mimarinin hatasi buydu).
OBS_SCALE = {
    "alt_ft": 30000.0,
    "alt_err_ft": 5000.0,
    "mach": 1.0,
    "mach_err": 0.3,
    "angle_rad": 1.0,          # aci degerleri zaten ~O(1) radyan
    "rate_rads": 2.0,
    "gamma_rad": 0.6,
    "heading_err_rad": math.pi,
    "range_ft": 100000.0,
}


def qbar_psf(mach: float, alt_ft: float) -> float:
    """Yaklasik dinamik basinc (kazanc cizelgeleme icin, ISA standart atmosfer).

    Kazanc cizelgelemesinin sebebi: aerodinamik moment ~ qbar ile olcekler.
    15 kft / M0.5 ile 45 kft / M1.5 arasinda qbar ~10x degisir; sabit kazancli
    bir PID birinde tembel, digerinde salinimli olur.
    """
    # ISA troposfer + alt stratosfer yogunlugu (slug/ft^3)
    if alt_ft < 36089.0:
        theta = 1.0 - 6.87559e-6 * alt_ft
        rho = 0.00237717 * theta ** 4.2561
        a_fps = 1116.45 * math.sqrt(theta)
    else:
        rho = 0.00070613 * math.exp(-(alt_ft - 36089.0) / 20806.0)
        a_fps = 968.08
    v_fps = mach * a_fps
    return 0.5 * rho * v_fps * v_fps


def atmos(alt_ft):
    """ISA atmosfer: (rho [slug/ft^3], ses hizi [ft/s]). NumPy dizisi kabul eder.

    EDMD ozellik kitapligi bunlari kullanir: dinamik basinc qbar = 0.5*rho*V^2
    ve gercek hiz V = mach * a. Ucagin dinamigi bu iki buyukluge kuvvetle
    baglidir; onlari ozellik olarak vermek, dogrusal modelin irtifa/Mach
    kuplajini yakalamasini saglar.
    """
    import numpy as _np
    alt = _np.asarray(alt_ft, dtype=_np.float64)
    trop = alt < 36089.0
    theta = _np.clip(1.0 - 6.87559e-6 * alt, 1e-3, None)
    rho_t = 0.00237717 * theta ** 4.2561
    a_t = 1116.45 * _np.sqrt(theta)
    rho_s = 0.00070613 * _np.exp(-(alt - 36089.0) / 20806.0)
    a_s = _np.full_like(alt, 968.08)
    return _np.where(trop, rho_t, rho_s), _np.where(trop, a_t, a_s)


# --- Stall (perdovme) hizi ve IRTIFAYA BAGLI Mach tabani ------------------
WING_AREA_SQFT = 300.0        # F-16 kanat alani
#: BARIYER icin kullanilan agirlik. Bilerek EN AGIR durum secilir
#: (bos agirlik + tam dahili yakit ~ 24.400 lb, yuvarlanmis 25.000).
#: Gerekce: gercek agirlik yakit yandikca DUSER, stall Mach'i da duser;
#: en agir durumu varsaymak bariyeri her zaman GUVENLI tarafta tutar ve
#: -- kritik olarak -- bariyeri x'te DOGRUSAL birakir (agirligi durum
#: vektorune sokmak gerekmez).
#: Olcum: 20.000 lb'de gercek stall Mach 25 kft'te 0.318, 25.000 lb'de
#: 0.355 -- yani bariyer hafif yakitta ~0.04 Mach muhafazakar.
COMBAT_WEIGHT_LB = 25000.0
CL_MAX = 1.2                  # temiz konfigurasyon, maksimum tasima katsayisi


def stall_mach(alt_ft, n_load=1.0, weight_lb=COMBAT_WEIGHT_LB):
    """1g (veya n_load g) stall Mach sayisi.

        V_stall = sqrt( 2 n W / (rho S CLmax) ),   M = V / a(h)

    Neden gerekli: sabit bir Mach tabani FIZIKSEL OLARAK YANLISTIR.
    10 kft'te F-16 rahatca M0.30 ucar; 40 kft'te ayni Mach zaten stall
    altidir. Sabit 0.40 tabani alcakta gereksiz kati, yuksekte yetersizdi
    -- ve guvenlik metriginin varyansinin buyuk kismi bu kotu tanimli
    bariyerden geliyordu.
    """
    import numpy as _np
    rho, a = atmos(alt_ft)
    v = _np.sqrt(2.0 * n_load * weight_lb / (rho * WING_AREA_SQFT * CL_MAX))
    return v / a


#: Manevra pay carpani: 1g stall'in bu kati, "guvenli en dusuk hiz" sayilir.
#: 1.25 -> yaklasik 1.56 g'ye kadar stall'siz manevra imkani.
STALL_MARGIN_FACTOR = 1.25

#: Bariyer icin DOGRUSAL yaklasim:  M_floor(h) = MACH_FLOOR_A + MACH_FLOOR_B * h
#: (fit asagidaki dogrulama betiginde uretildi; bariyerin dogrusal kalmasi
#:  CBF makinesinin degismeden calismasini saglar)
MACH_FLOOR_A = 0.2139
MACH_FLOOR_B = 1.107e-5


def mach_floor(alt_ft):
    """Bariyerde kullanilan dogrusal Mach tabani."""
    return MACH_FLOOR_A + MACH_FLOOR_B * alt_ft


def true_stall_mach(alt_ft, weight_lb):
    """GERCEK agirlikla stall Mach -- OLCUM icin (bariyer icin degil).

    Bariyer muhafazakar sabit agirlik kullanir (dogrusallik icin).
    Bir ihlali RAPORLARKEN ise gercek agirligi kullanmak dogrudur:
    hafif yakitla ucak, bariyerin izin verdiginden daha yavas ucabilir ve
    bu tehlikeli DEGILDIR. Aksi halde filtrenin kasitli muhafazakarligini
    "ihlal" diye sayar ve metrigi sisiririz.
    """
    return stall_mach(alt_ft, n_load=1.0, weight_lb=weight_lb)
