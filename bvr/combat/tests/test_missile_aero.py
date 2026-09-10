"""
Faz 1.3 Adım 1: Atmosfer ve Cd(M) modellerinin doğrulama testleri
"""

import math
import pytest
from bvr.combat.missile import atmosphere, drag_coefficient

def test_atmosphere_sea_level():
    # Deniz seviyesinde standart referanslar
    rho, sos = atmosphere(0.0)
    assert math.isclose(rho, 0.0023769, rel_tol=1e-4)
    assert math.isclose(sos, 1116.45, rel_tol=1e-3)


def test_atmosphere_30k_ft():
    # 30.000 ft irtifada elle çıkarılan referans:
    # a = 994.67 fps, rho = 0.0008907 slug/ft^3
    rho, sos = atmosphere(30000.0)
    assert math.isclose(sos, 994.67, rel_tol=1e-3)
    assert math.isclose(rho, 0.0008893, rel_tol=1e-3)

def test_atmosphere_stratosphere_isothermal():
    # 36.089 ft üstünde sıcaklık sabit (izotermal) kalmalı, ses hızı düşmemeli
    _, sos_36k = atmosphere(36089.0)
    _, sos_45k = atmosphere(45000.0)
    assert math.isclose(sos_36k, sos_45k, rel_tol=1e-4)

def test_drag_transonic_peak():
    # Cd eğrisinde tepe noktası kesinlikle Mach 1.1 - 1.2 civarında olmalı
    cd_subsonic = drag_coefficient(0.7)
    cd_transonic = drag_coefficient(1.15)
    cd_supersonic = drag_coefficient(2.5)

    assert cd_subsonic == 0.25
    assert cd_transonic == 0.72
    assert cd_transonic > cd_subsonic
    assert cd_transonic > cd_supersonic
    assert cd_supersonic > cd_subsonic


def test_drag_interpolation():
    # Mach 0.9 için [0.8, 1.0] aralığında tam orta nokta (0.25 + 0.55)/2 = 0.40
    cd_09 = drag_coefficient(0.9)
    assert math.isclose(cd_09, 0.40, abs_tol=1e-4)