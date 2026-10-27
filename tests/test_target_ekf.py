"""
Unit tests for Target Extended Kalman Filter (EKF) Subsystem
"""
import pytest
import numpy as np
from src.navigation.target_ekf import TargetEKF


def test_target_ekf_initialization():
    ekf = TargetEKF()
    assert ekf.initialized is False
    assert ekf.update_count == 0


def test_target_ground_projection_center():
    ekf = TargetEKF()
    # When target is in exact center (norm_offset=(0, 0)) and UAV is level (roll=0, pitch=0, yaw=0)
    # Ground position should match UAV position (0, 0)
    gx, gy = ekf.project_pixel_to_ground(
        norm_offset_xy=(0.0, 0.0),
        uav_pos_xy=(10.0, 20.0),
        altitude_agl=30.0,
        roll_deg=0.0,
        pitch_deg=0.0,
        yaw_deg=0.0
    )
    assert pytest.approx(gx, abs=0.1) == 10.0
    assert pytest.approx(gy, abs=0.1) == 20.0


def test_target_ekf_convergence():
    ekf = TargetEKF()
    # Feed stationary ground target at (5.0, 5.0) multiple times with small noise
    for _ in range(15):
        noise_x = np.random.uniform(-0.1, 0.1)
        noise_y = np.random.uniform(-0.1, 0.1)
        state = ekf.update(
            norm_offset_xy=(0.1 + noise_x, 0.1 + noise_y),
            uav_pos_xy=(0.0, 0.0),
            altitude_agl=20.0,
            roll_deg=0.0,
            pitch_deg=0.0,
            yaw_deg=0.0
        )

    assert state.is_converged is True
    assert state.uncertainty_m < 2.0


def test_target_ekf_reset():
    ekf = TargetEKF()
    ekf.update(norm_offset_xy=(0.2, 0.2), uav_pos_xy=(0.0, 0.0), altitude_agl=20.0)
    assert ekf.initialized is True

    ekf.reset()
    assert ekf.initialized is False
    assert ekf.update_count == 0
