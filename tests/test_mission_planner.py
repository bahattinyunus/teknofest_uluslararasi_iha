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
