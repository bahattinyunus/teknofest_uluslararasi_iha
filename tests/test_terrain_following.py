"""
Unit tests for Laser Terrain Following & Landing Flare Controller Subsystem
"""
import pytest
from src.avionics.terrain_following import (
    TerrainFollowingController,
    AltitudeMode,
    TerrainState
)


def test_terrain_following_nominal_cruise():
    ctrl = TerrainFollowingController(target_cruise_agl_m=30.0)
    state = ctrl.update(
        timestamp=1.0,
        raw_laser_range_m=30.0,
        roll_deg=0.0,
        pitch_deg=0.0
    )
    assert state.mode == AltitudeMode.HOLD_AGL
    assert not state.is_ground_proximity_alert
    assert not state.is_touchdown_confirmed
    assert abs(state.climb_rate_cmd_mps) < 1.0


def test_terrain_following_roll_pitch_compensation():
    ctrl = TerrainFollowingController(target_cruise_agl_m=30.0)
    # UAV is banked at 45 deg roll. Slanted laser range is ~42.42m
    # Projected true vertical altitude = 42.42 * cos(45 deg) = 30.0m
    state = ctrl.update(
        timestamp=1.0,
        raw_laser_range_m=42.42,
        roll_deg=45.0,
        pitch_deg=0.0
    )
    assert 29.0 <= state.filtered_agl_m <= 31.0


def test_terrain_following_landing_flare_transition():
    ctrl = TerrainFollowingController(flare_altitude_m=2.0, touchdown_threshold_m=0.2)
    # 1. Approach descent at 5m
    st1 = ctrl.update(1.0, raw_laser_range_m=5.0, roll_deg=0.0, pitch_deg=0.0, is_landing_commanded=True)
    assert st1.mode == AltitudeMode.APPROACH_DESCENT

    # 2. Descend smoothly into Flare (< 2.0m)
    for i in range(10):
        st2 = ctrl.update(1.1 + i * 0.1, raw_laser_range_m=1.5, roll_deg=0.0, pitch_deg=0.0, is_landing_commanded=True)
    assert st2.mode == AltitudeMode.FLARE
    assert st2.climb_rate_cmd_mps < 0.0  # gentle downward rate

    # 3. Touchdown at 0.15m
    for i in range(10):
        st3 = ctrl.update(2.1 + i * 0.1, raw_laser_range_m=0.15, roll_deg=0.0, pitch_deg=0.0, is_landing_commanded=True)
    assert st3.mode == AltitudeMode.TOUCHDOWN
    assert st3.is_touchdown_confirmed


def test_terrain_following_reset():
    ctrl = TerrainFollowingController()
    ctrl.update(1.0, 5.0, 0.0, 0.0, is_landing_commanded=True)
    ctrl.reset(initial_agl=30.0)
    assert ctrl.filtered_agl == 30.0
    assert ctrl.mode == AltitudeMode.HOLD_AGL
