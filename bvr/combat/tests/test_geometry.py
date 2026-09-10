import math
import random
from dataclasses import dataclass
from bvr.combat.geometry import relative_geometry, wrap_to_180

@dataclass
class MockFlightState:
    north_ft: float
    east_ft: float
    alt_ft: float
    psi_rad: float
    theta_rad: float = 0.0
    vt_fps: float = 900.0
    gamma_rad: float = 0.0
    beta_rad: float = 0.0

def test_durum_1():
    # Mavi (0,0) yön 0, 900 fps | Kırmızı (60000,0) yön 180, 900 fps
    b = MockFlightState(0, 0, 0, psi_rad=0, vt_fps=900)
    r = MockFlightState(60000, 0, 0, psi_rad=math.pi, vt_fps=900)
    res = relative_geometry(b, r)
    
    assert math.isclose(res.range_ft, 60000, rel_tol=1e-4)
    assert math.isclose(res.ata_deg, 0, abs_tol=1e-4)
    assert math.isclose(abs(res.aa_deg), 180, abs_tol=1e-4)
    assert math.isclose(abs(res.hca_deg), 180, abs_tol=1e-4)
    assert math.isclose(res.closure_fps, 1800, abs_tol=1e-4)
    assert math.isclose(res.los_rate_radps, 0, abs_tol=1e-4)
    assert math.isclose(res.off_boresight_deg, abs(res.ata_deg), abs_tol=1e-4)

def test_durum_2():
    # Mavi (0,0) yön 0, 900 fps | Kırmızı (60000,0) yön 0, 800 fps
    b = MockFlightState(0, 0, 0, psi_rad=0, vt_fps=900)
    r = MockFlightState(60000, 0, 0, psi_rad=0, vt_fps=800)
    res = relative_geometry(b, r)
    
    assert math.isclose(res.range_ft, 60000, rel_tol=1e-4)
    assert math.isclose(res.ata_deg, 0, abs_tol=1e-4)
    assert math.isclose(res.aa_deg, 0, abs_tol=1e-4)
    assert math.isclose(res.hca_deg, 0, abs_tol=1e-4)
    assert math.isclose(res.closure_fps, 100, abs_tol=1e-4)
    assert math.isclose(res.los_rate_radps, 0, abs_tol=1e-4)
    assert math.isclose(res.off_boresight_deg, abs(res.ata_deg), abs_tol=1e-4)

def test_durum_3():
    # Mavi (0,0) yön 0, 900 fps | Kırmızı (60000,0) yön 90, 900 fps
    b = MockFlightState(0, 0, 0, psi_rad=0, vt_fps=900)
    r = MockFlightState(60000, 0, 0, psi_rad=math.pi / 2, vt_fps=900)
    res = relative_geometry(b, r)
    
    assert math.isclose(res.range_ft, 60000, rel_tol=1e-4)
    assert math.isclose(res.ata_deg, 0, abs_tol=1e-4)
    assert math.isclose(res.aa_deg, -90, abs_tol=1e-4)
    assert math.isclose(res.hca_deg, 90, abs_tol=1e-4)
    assert math.isclose(res.closure_fps, 900, abs_tol=1e-4)
    assert math.isclose(res.los_rate_radps, 0.015, abs_tol=1e-4)
    assert math.isclose(res.off_boresight_deg, abs(res.ata_deg), abs_tol=1e-4)

def test_durum_4_degismez_kontrolu():
    # 500 rastgele konfigürasyonda ATA = AA + HCA (mod 360) doğrulaması
    for _ in range(500):
        b = MockFlightState(
            north_ft=random.uniform(-100000, 100000),
            east_ft=random.uniform(-100000, 100000),
            alt_ft=random.uniform(5000, 40000),
            psi_rad=random.uniform(-math.pi, math.pi),
            vt_fps=random.uniform(400, 1200)
        )
        r = MockFlightState(
            north_ft=random.uniform(-100000, 100000),
            east_ft=random.uniform(-100000, 100000),
            alt_ft=random.uniform(5000, 40000),
            psi_rad=random.uniform(-math.pi, math.pi),
            vt_fps=random.uniform(400, 1200)
        )
        res = relative_geometry(b, r)
        fark = wrap_to_180(res.ata_deg - (res.aa_deg + res.hca_deg))
        assert abs(fark) < 1e-5


def test_durum_5_off_boresight_irtifa():
    # Mavi (0,0,0) yön 0, düz uçuş | Kırmızı 10000 ft kuzeyde VE 10000 ft
    # daha yüksekte, aynı yön/hız. Elle hesap:
    #   R = 10000*sqrt(2) ~= 14142.14 ft
    #   elevation = asin(10000/R) = 45 deg
    #   off_boresight = burun (yatay, theta=0) ile LOS (45 derece yukarı)
    #                   arasındaki açı = 45 deg -- ATA (0)'dan FARKLI
    b = MockFlightState(0, 0, 0, psi_rad=0, vt_fps=900)
    r = MockFlightState(10000, 0, 10000, psi_rad=0, vt_fps=900)
    res = relative_geometry(b, r)

    assert math.isclose(res.range_ft, 10000 * math.sqrt(2), rel_tol=1e-4)
    assert math.isclose(res.ata_deg, 0, abs_tol=1e-4)
    assert math.isclose(res.elevation_deg, 45, abs_tol=1e-4)
    assert math.isclose(res.off_boresight_deg, 45, abs_tol=1e-4)
    # İrtifa farkı olduğunda off_boresight artık abs(ata_deg)'e eşit DEĞİL
    # önceki testlerde (elev=0, theta=0) bu eşitlik şans eseri tutuyordu bu yüzden ekledik.
    assert not math.isclose(res.off_boresight_deg, abs(res.ata_deg), abs_tol=1e-4)
    assert math.isclose(res.closure_fps, 0, abs_tol=1e-4)
    assert math.isclose(res.los_rate_radps, 0, abs_tol=1e-4)