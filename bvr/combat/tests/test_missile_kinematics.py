"""
Faz 1.3 Adım 2: Füzenin güdümsüz balistik kinematiği ve motor aşamaları testleri.
"""

import numpy as np
import pytest
from bvr.combat.missile import Missile, MissileConfig


class MockLaunchState:
    def __init__(self, pos_ft: list[float], vel_fps: list[float]):
        self.pos_ft = np.array(pos_ft, dtype=float)
        self.vel_fps = np.array(vel_fps, dtype=float)


def test_5_boost_bitince_hiz_azalmaya_baslamali():
    # 30.000 ft irtifada, 900 fps başlangıç hızıyla düz atış
    cfg = MissileConfig(boost_s=9.0, boost_thrust_lbf=3000.0, mass_lb=335.0)
    launch = MockLaunchState(pos_ft=[0.0, 0.0, 30000.0], vel_fps=[900.0, 0.0, 0.0])
    
    missile = Missile(cfg, launch, target_id="hedef_1")
    dt = 0.1

    # Boost aşaması boyunca (0 -> 8.9 saniye) uçur
    speed_history = []
    time_points = []
    
    # Hedef füzenin çok uzağında olsun ki pitbull/çarpma tetiklenmesin
    dummy_target_pos = np.array([500000.0, 0.0, 30000.0])
    dummy_target_vel = np.array([0.0, 0.0, 0.0])

    t = 0.0
    while t <= 12.0:
        state = missile.update(dt, dummy_target_pos, dummy_target_vel, datalink_ok=True)
        speed = float(np.linalg.norm(state.vel_fps))
        speed_history.append(speed)
        time_points.append(t)
        t += dt

    # 1. Motor yanarken (boost) füze ivmelenmeli
    idx_1s = int(1.0 / dt)
    idx_8s = int(8.0 / dt)
    assert speed_history[idx_8s] > speed_history[idx_1s]

    # 2. Boost bitiş noktası (t = 9.0s) civarında tepe hız görülmeli
    idx_9s = int(9.0 / dt)
    idx_11s = int(11.0 / dt)
    
    # 9. saniyedeki hız, 11. saniyedeki hızdan kesinlikle büyük olmalı (Kriter 5)
    assert speed_history[idx_9s] > speed_history[idx_11s]
    assert state.phase == "coast"