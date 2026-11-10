"""
Unit tests for L1 Adaptive Controller & Disturbance Observer Subsystem
"""
import pytest
import math
from src.navigation.l1_adaptive_controller import L1AdaptiveController, DisturbanceState


def test_adaptive_controller_zero_disturbance():
    ctrl = L1AdaptiveController()
    state = ctrl.update(
        timestamp=0.1,
        measured_vel_xyz=(10.0, 0.0, 0.0),
        applied_accel_xyz=(0.0, 0.0, 0.0),
        desired_accel_xyz=(0.0, 0.0, 0.0)
    )
    assert not state.is_severe_turbulence
    assert state.gust_magnitude_mps2 < 1.0


def test_adaptive_controller_constant_wind_gust_rejection():
    ctrl = L1AdaptiveController(obs_gain_l=10.0, obs_gain_kd=15.0)
    # Simulate a sudden lateral wind gust pushing UAV in Y direction (e.g. +2 m/s^2)
    t = 0.0
    vel_y = 0.0
    disturbance_y_applied = 2.0  # m/s^2

    for _ in range(30):
        t += 0.05
        # Physical plant acceleration: a_actual = disturbance_y_applied
        vel_y += disturbance_y_applied * 0.05
        state = ctrl.update(
            timestamp=t,
            measured_vel_xyz=(10.0, vel_y, 0.0),
            applied_accel_xyz=(0.0, 0.0, 0.0),
            desired_accel_xyz=(0.0, 0.0, 0.0)
        )

    # Observer should estimate the positive Y disturbance and produce negative Y compensation
    assert state.dist_y_mps2 > 0.5
    assert state.compensated_ay < 0.0
    assert abs(state.desired_roll_deg) > 0.5


def test_adaptive_controller_severe_turbulence_alert():
    ctrl = L1AdaptiveController(severe_turbulence_thresh=2.5)
    # Feed rapid velocity discrepancy
    ctrl.update(0.1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    state = ctrl.update(0.2, (15.0, 15.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    # High gust magnitude expected
    assert state.gust_magnitude_mps2 > 2.0


def test_adaptive_controller_reset():
    ctrl = L1AdaptiveController()
    ctrl.update(0.1, (5.0, 5.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    ctrl.reset()
    assert ctrl.hat_vx == 0.0
    assert ctrl.hat_dx == 0.0
    assert ctrl.last_timestamp is None
