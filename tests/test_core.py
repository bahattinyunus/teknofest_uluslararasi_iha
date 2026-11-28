"""
Integration tests for ArchitectCore
"""
import pytest
from src.main_brain.core import ArchitectCore
from src.navigation.mission_planner import MissionState


def test_core_initialization_and_single_step():
    core = ArchitectCore(mode="simulation", task=2)
    assert core.status == "HAZIR"

    core.start_mission()
    assert core.status == "OPERASYONEL"
    assert core.running is True

    # Run one step
    step_info = core.step()
    assert "state" in step_info
    assert "altitude_agl" in step_info
    assert "payloads_remaining" in step_info
    assert step_info["payloads_remaining"] == 2
    assert step_info["link_security"] == "SECURE"
    assert "pylon_active" in step_info
    assert "pylon_inner_turn_risk" in step_info

    core.stop_mission()
    assert core.running is False
