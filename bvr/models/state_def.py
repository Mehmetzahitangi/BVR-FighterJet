"""
MODEL DURUM TANIMI: dinamik modellerin (DMD/EDMD/Deep-Koopman) ve
guvenlik filtresinin (CBF) uzerinde calistigi ortak durum/girdi vektoru.

=============================================================================
MODELLENEN SISTEM NEDIR?
=============================================================================
Ciplak F-16 DEGIL. Modellenen sey KAPALI CEVRIMDIR:

    [ F-16 airframe + JSBSim FLCS + bvr/control/inner_loop.py ]

Girdi u = dis dongunun (RL) verdigi komut  [phi_cmd, gamma_cmd, mach_cmd]
Cikti x = ucusun gozlenen durumu

Bu kritik bir tercihtir. Kapali cevrim sistemi, ciplak airframe'e gore
cok daha dusuk mertebeli, cok daha iyi sonumlenmis ve cok daha az
dogrusalsizdir -- yani Koopman/DMD ile tanimlamasi ciddi olcude daha
kolaydir. Eski mimarinin 60 Hz yuzey seviyesinde yasadigi bagil derece
(relative degree) problemi burada ortadan kalkar: 0.1 saniyelik bir dis
dongu adiminda phi_cmd, phi'yi GERCEKTEN degistirir.

=============================================================================
NEDEN SABIT OLCEKLEME? (ogrenilen/canli istatistik DEGIL)
=============================================================================
Eski kodda gozlem VecNormalize'in CANLI istatistikleriyle olcekleniyor ve
CBF kisitlari da o uzayda kuruluyordu -- yani guvenli kume egitim boyunca
yer degistiriyordu. Burada olcekler bu dosyada SABITTIR:
  - guvenli kume hicbir zaman oynamaz,
  - egitim/degerlendirme/tez sonuclari tekrar uretilebilir,
  - farkli modeller (DMD/EDMD/Koopman) birebir ayni uzayda karsilastirilir.
=============================================================================
"""
from __future__ import annotations

import numpy as np

from ..sim import aircraft as ac

# --- Durum vektoru x (fiziksel birimler) -----------------------------------
X_NAMES = (
    "phi_rad",     # 0  yatis acisi
    "gamma_rad",   # 1  ucus yolu acisi
    "mach",        # 2
    "alt_ft",      # 3
    "alpha_rad",   # 4  hucum acisi      (zarf kisiti)
    "beta_rad",    # 5  yanal kayma      (zarf kisiti)
    "n_eff",       # 6  normal g yuku    (zarf kisiti)
    "p_rads",      # 7  yatis hizi
    "q_rads",      # 8  yunuslama hizi
    "h_dot_fps",   # 9  dikey hiz        (irtifa bariyerinin turevi)
    "fuel_frac",   # 10 yakit orani -> AGIRLIK
)
X_DIM = len(X_NAMES)

# Normalizasyon: z = (x - X_CENTER) / X_SCALE   -> kabaca O(1)
# Yakit orani MODEL DURUMUNA dahildir: agirlik 19.900-23.900 lb arasinda
# degisir ve ivmelenme ~1/kutle ile olceklenir. Agirligi durumda tutmazsak
# model bu %20'lik degisimi ACIKLANAMAYAN VARYANS olarak gorur ve dogrulugu
# duser -- CBF de o modele guveniyor.
X_CENTER = np.array([0.0, 0.0, 0.90, 25000.0, 0.05, 0.0, 1.0, 0.0, 0.0, 0.0, 0.65])
X_SCALE = np.array([1.0, 0.40, 0.40, 12000.0, 0.20, 0.10, 3.0, 1.50, 0.40, 300.0, 0.35])

# --- Girdi vektoru u (dis dongu komutu) ------------------------------------
U_NAMES = ("phi_cmd_rad", "gamma_cmd_rad", "mach_cmd")
U_DIM = len(U_NAMES)
U_CENTER = np.array([0.0, 0.0, 0.90])
U_SCALE = np.array([1.0, 0.40, 0.40])


def state_from_flight(st) -> np.ndarray:
    """FlightState -> model durum vektoru x (fiziksel birimler).

    n_eff isaret duzeltmesi: JSBSim'in n-pilot-z-norm degeri duz ucusta
    -1.0 okur (scripts/id_nz.py ile olculdu); isareti burada TEK YERDE
    cevirilir ki asagidaki hicbir modul bu konvansiyonla ugrasmasin.
    """
    return np.array([
        st.phi_rad, st.gamma_rad, st.mach, st.alt_ft,
        st.alpha_rad, st.beta_rad, -st.nz,
        st.p_rads, st.q_rads, st.h_dot_fps, st.fuel_frac,
    ], dtype=np.float64)


def cmd_to_u(cmd) -> np.ndarray:
    """InnerLoopCommand -> girdi vektoru u (fiziksel birimler)."""
    return np.array([cmd.phi_cmd_rad, cmd.gamma_cmd_rad, cmd.mach_cmd], dtype=np.float64)


def normalize_x(x: np.ndarray) -> np.ndarray:
    return (x - X_CENTER) / X_SCALE


def denormalize_x(z: np.ndarray) -> np.ndarray:
    return z * X_SCALE + X_CENTER


def normalize_u(u: np.ndarray) -> np.ndarray:
    return (u - U_CENTER) / U_SCALE


def denormalize_u(w: np.ndarray) -> np.ndarray:
    return w * U_SCALE + U_CENTER


# --- Zarf kisitlari: h(x) = d - C @ x >= 0 ---------------------------------
# CBF bariyerleri BU fiziksel uzayda tanimlanir. Her satir bir kisittir.
# (Lifting yapan modellerde Psi(x)'in ilk blogu x'in kendisi olacagi icin
#  ayni C matrisi kaldirilan uzayda da gecerli kalir -- bkz. models/base.py)
def envelope_constraints():
    """(C, d, isim_listesi) dondurur.  Guvenli bolge: C @ x <= d

    ONEMLI: her satir kendi KARAKTERISTIK OLCEGINE bolunerek verilir, yani
    h = d - C x BOYUTSUZDUR ve sinira yakinken hepsi O(1) buyukluktedir.

    Neden: olceklenmemis halde alpha satiri radyan (~0.02 mertebesi),
    irtifa satiri feet (~5000 mertebesi) uretir. QP'nin kisit matrisinde
    4 mertebe fark olusur; OSQP bu kosullanmada kucuk satirlari fiilen
    yok sayar ve cozucu sik sik basarisiz olur (olculdu: 3000 cagrinin
    241'inde hata). Satir olcekleme, sayisal kosullanmanin standart
    duzeltmesidir ve bariyerin ANLAMINI degistirmez (h >= 0 kosulu
    pozitif bir sabitle bolununce ayni kalir).
    """
    rows, d, names = [], [], []

    def add(idx_coefs, limit, name, scale):
        r = np.zeros(X_DIM)
        for i, c in idx_coefs:
            r[i] = c
        rows.append(r / scale)
        d.append(limit / scale)
        names.append(name)

    i = {n: k for k, n in enumerate(X_NAMES)}

    add([(i["alpha_rad"], 1.0)], np.radians(ac.ALPHA_MAX_DEG), "alpha_max", 0.20)
    add([(i["alpha_rad"], -1.0)], -np.radians(ac.ALPHA_MIN_DEG), "alpha_min", 0.20)
    add([(i["beta_rad"], 1.0)], np.radians(ac.BETA_MAX_DEG), "beta_max", 0.10)
    add([(i["beta_rad"], -1.0)], np.radians(ac.BETA_MAX_DEG), "beta_min", 0.10)
    add([(i["n_eff"], 1.0)], ac.NZ_MAX, "nz_max", 3.0)
    add([(i["n_eff"], -1.0)], -ac.NZ_MIN, "nz_min", 3.0)
    add([(i["mach"], 1.0)], ac.MACH_MAX, "mach_max", 0.30)
    # MACH TABANI IRTIFAYA BAGLIDIR.
    #   M >= A + B*h      <=>      -M + B*h <= -A
    # Bariyer bu haliyle HALA x'te DOGRUSALDIR; sadece C matrisinin alt
    # sutununa bir katsayi girer. CBF makinesi (ve A^i onbellegi) aynen
    # gecerli kalir.
    #
    # Neden: sabit 0.40 tabani fiziksel olarak yanlisti -- 10 kft'te gercek
    # guvenli taban 0.33, 40 kft'te 0.66. Alcakta gereksiz ihlal uretiyor,
    # yuksekte gercek stall riskini kaciriyordu. Guvenlik metriginin
    # varyansinin buyuk kismi bu kotu tanimli bariyerden geliyordu.
    add([(i["mach"], -1.0), (i["alt_ft"], ac.MACH_FLOOR_B)],
        -ac.MACH_FLOOR_A, "mach_min", 0.30)
    # YATIS ACISI BILEREK BURADA DEGIL.
    # Yatis bir GUVENLIK kisiti degil, ISLETME kisitidir: F-16 ters de
    # ucabilir, yatis kendi basina ucagi kaybettirmez. Zaten dis dongunun
    # aksiyon eslemesi (+-BANK_MAX_DEG) ve ic dongu tarafindan uygulanir.
    # Bariyer kumesine konuldugunda olculen etki: politika aksiyon uzayinin
    # tam sinirinda calistigi icin kalkan SUREKLI tirpanliyordu (mudahale
    # orani %42, bunun buyuk kismi bank satirlari). Guvenlik zarfi, isletme
    # zarfinin DISINDA olmalidir; ayni yere konursa filtre surekli tetiklenir
    # ve gercek tehlikeleri gorunmez kilar.
    #
    # Gercek guvenlik bariyerleri: alpha (stall/departure), beta (departure),
    # Nz (yapisal), Mach (stall / asiri hiz), irtifa tabani.
    # Irtifa tabani: sadece irtifa degil, dikey hizla birlestirilmis bir
    # bariyer kullanilir (h = alt - deck + tau*h_dot). tau, "onumuzdeki
    # tau saniyede nereye varirim" ufkudur; irtifa bariyerinin bagil
    # derecesini 1'e dusuren standart numaradir.
    tau = 5.0
    add([(i["alt_ft"], -1.0), (i["h_dot_fps"], -tau)], -ac.HARD_DECK_FT,
        "hard_deck", 5000.0)

    return np.array(rows), np.array(d), tuple(names)
