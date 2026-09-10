"""
Bu modülde x=kuzey, y=doğu, z=yukarı. NED DEĞİL. Özellikle ACMİ Kullanırken Dikkat Edin. 
(bvr/sim/jsbsim_bridge.py) her şeyi radyan tutuyor
"""

from typing import Protocol
from math import acos, asin, atan2, cos, sin
import numpy as np
from dataclasses import dataclass


class FlightState(Protocol):
    """Gereken asgari uçuş durumu arayüzü (NEU: North, East, Up).

    Alan adlari ve birimleri bvr/sim/jsbsim_bridge.py:FlightState ile
    birebir eslesir (hepsi radyan) -- gercek FlightState nesnesi
    adaptorsuz olarak bu Protocol'u karsilar.
    """
    north_ft: float
    east_ft: float
    alt_ft: float
    psi_rad: float      # Heading / Rota (0 = Kuzey, +pi/2 = Doğu) [radyan]
    theta_rad: float    # Pitch / Yunuslama [radyan]
    vt_fps: float       # Toplam hız (feet/sec)
    gamma_rad: float    # Uçuş yolu açısı (flight path angle) [radyan]
    beta_rad: float     # Yan kayma açısı (sideslip) [radyan]

@dataclass
class RelativeGeometry:
    range_ft: float
    range_nm: float
    ata_deg: float            # [-180, 180], + sağ
    aa_deg: float             # [-180, 180]
    hca_deg: float            # [-180, 180]
    closure_fps: float        # + yaklaşıyor
    los_rate_radps: float     # Görüş hattı dönme hızı (büyüklük)
    elevation_deg: float      # + hedef yukarıda
    off_boresight_deg: float  # 3D: Burun ekseni ile LOS arası açı [0, 180]

def wrap_to_180(deg: float) -> float:
    """Açıyı [-180, +180] aralığına normalize eder."""
    return (deg + 180.0) % 360.0 - 180.0

def relative_geometry(blue: FlightState, red: FlightState) -> RelativeGeometry:
    """
    İki uçak arasındaki göreli geometrik durumu hesaplar.
    """
    r_menzil = np.array([red.north_ft - blue.north_ft, red.east_ft - blue.east_ft, red.alt_ft - blue.alt_ft])
    range_ft_R = np.linalg.norm(r_menzil)
    if range_ft_R < 1e-6:
        raise ValueError("Iki ucak ayni noktada (range=0). LOS yonu tanımsız")

    nose_blue = np.array([cos(blue.theta_rad) * cos(blue.psi_rad), cos(blue.theta_rad) * sin(blue.psi_rad), sin(blue.theta_rad)])

    velocity_blue = blue.vt_fps * np.array([cos(blue.gamma_rad) * cos(blue.psi_rad + blue.beta_rad), cos(blue.gamma_rad) * sin(blue.psi_rad + blue.beta_rad), sin(blue.gamma_rad)])

    velocity_red =  red.vt_fps *  np.array([cos(red.gamma_rad) * cos(red.psi_rad + red.beta_rad), cos(red.gamma_rad) * sin(red.psi_rad + red.beta_rad), sin(red.gamma_rad)])

    beta_LOS =  atan2(r_menzil[1], r_menzil[0]) # Doğu fark, kuzey farkı, kuzey yönü referans alınarak hesaplanır. Bu, LOS açısıdır (radyan).

    # beta_LOS ve psi_rad ikisi de radyan fark da radyan cikar. wrap_to_180 derece bekledigi icin farki once np.degrees ile dereceye ceviriyoruz.
    ATA = wrap_to_180(np.degrees(beta_LOS - blue.psi_rad))  # ATA = β_LOS − ψ_m 
    AA = wrap_to_180(np.degrees(beta_LOS - red.psi_rad))     # AA = β_LOS − ψ_k
    HCA = wrap_to_180(np.degrees(red.psi_rad - blue.psi_rad))
    #ATA − AA = (β_LOS − ψ_m) − (β_LOS − ψ_k) = ψ_k − ψ_m = HCA

    kapanma_hizi = (velocity_red - velocity_blue) @ (r_menzil / range_ft_R)  # Kapanma hızı, LOS yönünde hız farkı. Sonuç skaler olmalı 
    Vclosure = - kapanma_hizi  # + yaklaşıyor

    LOS_donme_hizi = np.cross(r_menzil, velocity_red - velocity_blue) / (range_ft_R**2)  # LOS dönme hızı, LOS yönünde hız farkı. (r⃗ × v⃗_bağıl) / R²
    LOS_rate = np.linalg.norm(LOS_donme_hizi)  # Görüş hattı dönme hızı (büyüklük)

    elev = asin(r_menzil[2] / range_ft_R) # yükseliş açısı,  asin(Δz / R)

    off_boresight_deg = np.degrees(acos(np.clip(np.dot(nose_blue, r_menzil / range_ft_R), -1.0, 1.0)))  # Burun ekseni ile LOS arası açı [0, 180]


    return RelativeGeometry(
        range_ft=range_ft_R,
        range_nm=range_ft_R / 6076.12,  # Feet to nautical miles
        ata_deg=ATA,
        aa_deg=AA,
        hca_deg=HCA,
        closure_fps=Vclosure,
        los_rate_radps=LOS_rate,
        elevation_deg=np.degrees(elev),
        off_boresight_deg=off_boresight_deg
    )