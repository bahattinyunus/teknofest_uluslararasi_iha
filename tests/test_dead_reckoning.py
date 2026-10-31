"""
Unit tests for Dead Reckoning and GPS-Denied Navigation Subsystem
"""
import pytest
from src.navigation.dead_reckoning import DeadReckoningNavigator, DeadReckoningState


def test_dead_reckoning_gps_reliable_sync():
    dr = DeadReckoningNavigator(min_satellites=6)
    state = dr.update(
        gps_pos_xy=(10.0, 20.0),
        gps_vel_xy=(4.0, 1.0),
        satellites_visible=12,
        flow_rad_s_xy=(0.0, 0.0),
        altitude_agl_m=25.0,
        body_accel_xy=(0.0, 0.0),
        heading_deg=0.0
    )

    assert state.gps_active is True
    assert state.navigation_source == "GPS_EKF"
    assert state.pos_x_m == 10.0
    assert state.pos_y_m == 20.0
    assert state.vel_x_mps == 4.0
    assert state.vel_y_mps == 1.0
    assert state.drift_error_m <= 0.5


def test_dead_reckoning_gps_loss_switches_to_optical_flow():
    dr = DeadReckoningNavigator(min_satellites=6)
    # 1. Reliable GPS init
    dr.update(
        gps_pos_xy=(0.0, 0.0),
        gps_vel_xy=(0.0, 0.0),
        satellites_visible=10,
        flow_rad_s_xy=(0.0, 0.0),
        altitude_agl_m=10.0,
        body_accel_xy=(0.0, 0.0),
        heading_deg=0.0
    )

    # 2. GPS Loss (sats = 3, gps_pos = None)
    # Optical flow = 0.2 rad/s forward at 10m altitude -> 2.0 m/s forward
    state = dr.update(
        gps_pos_xy=None,
        gps_vel_xy=None,
        satellites_visible=3,
        flow_rad_s_xy=(0.2, 0.0),
        altitude_agl_m=10.0,
        body_accel_xy=(0.0, 0.0),
        heading_deg=0.0,
        dt=0.5
    )

    assert state.gps_active is False
    assert state.navigation_source == "OPTICAL_FLOW_DEAD_RECKONING"
    assert state.vel_x_mps > 1.2
    assert state.pos_x_m > 0.5
    assert state.drift_error_m > 0.5


def test_dead_reckoning_reset():
    dr = DeadReckoningNavigator()
    dr.update(
        gps_pos_xy=(5.0, 5.0),
        gps_vel_xy=(1.0, 1.0),
        satellites_visible=10,
        flow_rad_s_xy=(0.0, 0.0),
        altitude_agl_m=5.0,
        body_accel_xy=(0.0, 0.0),
        heading_deg=0.0
    )
    assert dr.is_initialized is True

    dr.reset(init_x=0.0, init_y=0.0)
    assert dr.is_initialized is False
    assert dr.pos_x == 0.0
    assert dr.accumulated_drift == 0.0
