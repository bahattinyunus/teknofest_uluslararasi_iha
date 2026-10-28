"""
Unit tests for Autonomous Go-Around & Approach Manager
"""
import pytest
from src.navigation.approach_manager import ApproachManager, ApproachPhase


def test_ideal_inbound_heading_headwind():
    mgr = ApproachManager()
    # If wind is coming from North (0 deg) -> Inbound heading should be North (0 + 180 = 180 deg South-facing, or directly against wind)
    # Wind blowing from 90 deg (East) -> Headwind approach flying East towards 90 deg
    heading = mgr.calculate_ideal_inbound_heading(90.0)
    assert heading == 270.0


def test_final_release_run_trigger():
    mgr = ApproachManager()
    # UAV approaching target at 10m distance with 0 angle error
    cmd = mgr.evaluate_approach(
        uav_pos_xy=(0.0, 0.0),
        target_pos_xy=(10.0, 0.0),
        uav_heading_deg=0.0,
        wind_direction_deg=180.0,
        miss_distance_m=0.5,
        hit_probability_pct=92.0,
        is_closing_in=True
    )

    assert cmd.phase == ApproachPhase.FINAL_RELEASE_RUN
    assert cmd.should_abort_drop is False
    assert cmd.target_speed_mps <= 4.0


def test_overshoot_triggers_go_around():
    mgr = ApproachManager()
    mgr.current_phase = ApproachPhase.FINAL_RELEASE_RUN

    # Target is moving away (not closing in) and distance is 15m (overshoot)
    cmd = mgr.evaluate_approach(
        uav_pos_xy=(20.0, 0.0),
        target_pos_xy=(0.0, 0.0),
        uav_heading_deg=0.0,
        wind_direction_deg=0.0,
        miss_distance_m=12.0,
        hit_probability_pct=30.0,
        is_closing_in=False
    )

    assert cmd.phase == ApproachPhase.GO_AROUND_CLIMB
    assert cmd.should_abort_drop is True
    assert cmd.target_altitude_m > mgr.approach_altitude
    assert cmd.reposition_waypoints is not None
    assert len(cmd.reposition_waypoints) >= 2
