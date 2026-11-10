"""
Unit tests for Declarative Mission Playbook & Opportunity Re-planner Subsystem
"""
import pytest
from src.navigation.mission_playbook import (
    MissionPlaybook,
    PlaybookPhase,
    PlaybookStatus
)


def test_playbook_initial_state():
    playbook = MissionPlaybook()
    st = playbook.update((0.0, 0.0, 0.0))
    assert st.current_phase == PlaybookPhase.STANDBY
    assert st.phase_index == 0
    assert not st.opportunity_replan_triggered


def test_playbook_takeoff_advancement():
    playbook = MissionPlaybook(takeoff_alt_m=25.0)
    playbook.current_phase_idx = 1  # TAKEOFF
    playbook._build_phase_waypoints()

    # Reach takeoff altitude
    st = playbook.update((0.0, 0.0, 25.0))
    # Should advance to next phase (TASK_1_FIGURE_EIGHT)
    assert st.current_phase == PlaybookPhase.TASK_1_FIGURE_EIGHT


def test_playbook_dynamic_opportunity_replan():
    playbook = MissionPlaybook()
    # Put into ATTACK_TARGET_A phase
    playbook.current_phase_idx = 4
    playbook._build_phase_waypoints()
    assert playbook.phases[playbook.current_phase_idx] == PlaybookPhase.ATTACK_TARGET_A

    # Target B detected close by (20m away) with mild headwind
    replan = playbook.evaluate_opportunity_replan(
        current_uav_pos=(10.0, 10.0),
        detected_target_type="TARGET_B",
        target_pos=(25.0, 15.0),
        headwind_mps=2.0
    )
    assert replan is True
    # Target B should now precede Target A!
    assert playbook.phases[playbook.current_phase_idx] == PlaybookPhase.ATTACK_TARGET_B


def test_playbook_reset():
    playbook = MissionPlaybook()
    playbook.current_phase_idx = 3
    playbook.reset()
    assert playbook.current_phase_idx == 0
    assert playbook.phases[0] == PlaybookPhase.STANDBY
