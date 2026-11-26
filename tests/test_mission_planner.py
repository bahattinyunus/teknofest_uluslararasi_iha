"""
Unit tests for Mission Planner and FSM State Machine
"""
import pytest
from src.navigation.mission_planner import MissionPlanner, MissionState, MissionTask


def test_planner_initialization():
    planner = MissionPlanner()
    assert planner.state == MissionState.IDLE
    assert planner.payloads_dropped == 0


def test_task_1_transition_sequence():
    planner = MissionPlanner()
    planner.set_task(MissionTask.TASK_1_COORDINATION)
    planner.transition_to(MissionState.TAKEOFF)

    # Reaching altitude transitions to Figure 8
    state = planner.update(
        altitude_agl=26.0,
        target_a_detected=False,
        target_a_locked=False,
        target_b_detected=False,
        target_b_locked=False,
        ballistics_ready=False,
        failsafe_triggered=False
    )
    assert state == MissionState.FIGURE_EIGHT_NAV


def test_task_2_payload_search_and_drop_sequence():
    planner = MissionPlanner()
    planner.set_task(MissionTask.TASK_2_DUAL_PAYLOAD)
    planner.transition_to(MissionState.SEARCHING_TARGET_A)

    # Target A detected
    state = planner.update(
        altitude_agl=30.0,
        target_a_detected=True,
        target_a_locked=False,
        target_b_detected=False,
        target_b_locked=False,
        ballistics_ready=False,
        failsafe_triggered=False
    )
    assert state == MissionState.LOCKING_TARGET_A

    # Target A locked and ballistics ready
    state = planner.update(
        altitude_agl=20.0,
        target_a_detected=True,
        target_a_locked=True,
        target_b_detected=False,
        target_b_locked=False,
        ballistics_ready=True,
        failsafe_triggered=False
    )
    assert state == MissionState.DROPPING_PAYLOAD_1


def test_failsafe_state_interruption():
    planner = MissionPlanner()
    planner.transition_to(MissionState.SEARCHING_TARGET_A)

    state = planner.update(
        altitude_agl=30.0,
        target_a_detected=False,
        target_a_locked=False,
        target_b_detected=False,
        target_b_locked=False,
        ballistics_ready=False,
        failsafe_triggered=True
    )
    assert state == MissionState.EMERGENCY_FAILSAFE

def test_v7_150m_pole_navigation_and_outer_turn_verification():
    planner = MissionPlanner(config={"pole_distance_m": 150.0, "required_figure_eight_laps": 1})
    planner.set_task(MissionTask.TASK_1_COORDINATION)
    planner.transition_to(MissionState.FIGURE_EIGHT_NAV)

    # 1. Fly to Pole 2 outer side (x = 80 > 75)
    planner.update(altitude_agl=30.0, uav_pos_xy=(80.0, 5.0))
    assert planner.pole_2_outer_turn_verified is True
    assert planner.pole_inner_turn_penalty == 0

    # 2. Cross center (x = 0, y = 0)
    planner.update(altitude_agl=30.0, uav_pos_xy=(0.0, 2.0))
    assert planner.center_crossing_verified is True

    # 3. Fly to Pole 1 outer side (x = -80 < -75)
    planner.update(altitude_agl=30.0, uav_pos_xy=(-80.0, -5.0))
    assert planner.pole_1_outer_turn_verified is True

    # 4. Return to center (x = 0) to complete the lap
    state = planner.update(altitude_agl=30.0, uav_pos_xy=(2.0, 0.0))
    assert planner.figure_eight_laps_completed >= 1
    # Once lap completed and verified, it transitions to RETURN_TO_LAUNCH
    assert state == MissionState.RETURN_TO_LAUNCH


def test_pole_inner_turn_penalty_ceza_2():
    planner = MissionPlanner(config={"pole_distance_m": 150.0})
    planner.set_task(MissionTask.TASK_1_COORDINATION)
    planner.transition_to(MissionState.FIGURE_EIGHT_NAV)

    # Approach Pole 2 but abort and cut inside (turn back without reaching x >= 75)
    planner.update(altitude_agl=30.0, uav_pos_xy=(40.0, 0.0))
    planner.update(altitude_agl=30.0, uav_pos_xy=(68.0, 5.0))
    planner.update(altitude_agl=30.0, uav_pos_xy=(60.0, 10.0))  # Turned back early!

    assert planner.pole_inner_turn_penalty == 10  # Ceza 2 applied


def test_v7_mission_summary_report():
    planner = MissionPlanner(config={"pole_distance_m": 150.0})
    summary = planner.get_v7_mission_summary()
    assert summary["pole_distance_m"] == 150.0
    assert summary["pole_1_xy"] == (-75.0, 0.0)
    assert summary["pole_2_xy"] == (75.0, 0.0)
    assert summary["scan_area"] == "30.0m x 100.0m"
