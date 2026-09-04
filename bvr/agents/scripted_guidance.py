"""
KLASIK GUDUM YASASI (RL'siz baseline).

Neden gerekli:
1. ODUL SAGLAMASI. Bir odul fonksiyonunun "iyi" olmasi, iyi bir
   politikanin yuksek odul almasiyla dogrulanir. Elle yazilmis makul bir
   politika bile negatif odul aliyorsa, hata ajanda degil ODULDEDIR.
   Bu kontrol yapilmadan RL egitmek, kor ucustur.
2. TEZ KARSILASTIRMASI. "RL, klasik gudume gore ne kazandiriyor?" sorusu
   sorulacaktir. Cevabi olmayan bir RL calismasi zayiftir.
3. KALKAN (CBF) DEGERLENDIRMESI. Kalkanin marjinal katkisi, kalkansiz RL
   ve klasik gudum tabanlarina gore olculur.

Yasa (oransal gudum + irtifa/hiz tutucu):
    phi_cmd   = K_psi * yon_hatasi                (hedefe don)
    gamma_cmd = K_h * irtifa_hatasi / V           (irtifa hatasini kapat)
    mach_cmd  = hedef Mach
Hepsi zarf sinirlarina kirpilir. Ogrenme yok, hafiza yok.
"""
from __future__ import annotations

import math

import numpy as np

from ..sim import aircraft as ac


class ScriptedGuidance:
    """GuidanceEnv gozleminden dogrudan aksiyon ureten klasik kontrolcu.

    Gozlem duzeni bvr/envs/guidance_env.py::_obs ile ayni olmak zorundadir:
        0,1 : sin/cos(yon hatasi)
        2   : menzil / 50000
        3   : irtifa hatasi / 5000
        4   : Mach hatasi / 0.30
        6   : gamma / 0.40
    """

    def __init__(self, k_psi: float = 1.6, k_alt: float = 1.1,
                 k_gamma_damp: float = 0.35,
                 mach_lo: float = 0.55, mach_hi: float = 1.35):
        self.k_psi = k_psi
        self.k_alt = k_alt
        self.k_gamma_damp = k_gamma_damp
        # Aksiyon uzayi MUTLAK Mach komutu tasiyor; hedefi gozlemden geri
        # kurmak icin ortamla ayni eslemeyi kullanmak zorundayiz.
        self.mach_lo = mach_lo
        self.mach_hi = mach_hi

    def predict(self, obs, deterministic: bool = True):
        o = np.asarray(obs, dtype=np.float64).reshape(-1)
        psi_err = math.atan2(o[0], o[1])                 # rad, (-pi, pi]
        alt_err_ft = o[3] * 5000.0
        mach_err = o[4] * 0.30
        gamma = o[6] * 0.40

        # --- Yatis: yon hatasiyla orantili, zarfta kirpili ---
        phi_cmd = self.k_psi * psi_err
        phi_max = math.radians(ac.BANK_MAX_DEG)
        phi_cmd = float(np.clip(phi_cmd, -phi_max, phi_max))

        # --- Ucus yolu: irtifa hatasini kapat, gamma sonumlemesi ile ---
        # 5000 ft hata -> ~15 derece tirmanis; sonumleme asimi engeller.
        gam_cmd = self.k_alt * (alt_err_ft / 5000.0) * math.radians(15.0)
        gam_cmd -= self.k_gamma_damp * gamma
        gam_max = math.radians(ac.GAMMA_MAX_DEG)
        gam_cmd = float(np.clip(gam_cmd, -gam_max, gam_max))

        # --- Hiz: hedef Mach'i gozlemden geri kur, aksiyon uzayina esle ---
        #   o[12] = (mach - 0.90)/0.40   ve   o[4] = (tgt - mach)/0.30
        mach_now = o[12] * 0.40 + 0.90
        tgt_mach = mach_now + mach_err
        span = max(self.mach_hi - self.mach_lo, 1e-6)
        a2 = float(np.clip(2.0 * (tgt_mach - self.mach_lo) / span - 1.0, -1.0, 1.0))

        a0 = phi_cmd / phi_max
        a1 = gam_cmd / gam_max
        return np.array([a0, a1, a2], dtype=np.float32), None
