"""
Unit tests for Dual Payload Release Actuator Subsystem
"""
import pytest
from src.avionics.actuator import PayloadReleaseController, PayloadStatus


def test_payload_initial_status():
    actuator = PayloadReleaseController()
    assert actuator.slot_1.status == PayloadStatus.LOADED
    assert actuator.slot_2.status == PayloadStatus.LOADED
    assert actuator.armed_for_release is False
    assert actuator.get_remaining_payload_count() == 2


def test_payload_arming_and_disarming():
    actuator = PayloadReleaseController()
    actuator.arm_mechanism()
    assert actuator.armed_for_release is True
    assert actuator.slot_1.status == PayloadStatus.ARMED
    assert actuator.slot_2.status == PayloadStatus.ARMED

    actuator.disarm_mechanism()
    assert actuator.armed_for_release is False
    assert actuator.slot_1.status == PayloadStatus.LOADED
    assert actuator.slot_2.status == PayloadStatus.LOADED


def test_payload_release_unarmed_rejected():
    actuator = PayloadReleaseController()
    success = actuator.release_payload_for_target("TARGET_A")
    assert success is False
    assert actuator.slot_1.status == PayloadStatus.LOADED


def test_payload_dual_release_sequence():
    actuator = PayloadReleaseController()
    actuator.arm_mechanism()

    # Drop for Target A (Should trigger slot 1 - red payload)
    res_a = actuator.release_payload_for_target("TARGET_A")
    assert res_a is True
    assert actuator.slot_1.status == PayloadStatus.RELEASED
    assert actuator.get_remaining_payload_count() == 1

    # Second drop attempt on Target A should return False (already released)
    res_a2 = actuator.release_payload_for_target("TARGET_A")
    assert res_a2 is False

    # Drop for Target B (Should trigger slot 2 - blue payload)
    res_b = actuator.release_payload_for_target("TARGET_B")
    assert res_b is True
    assert actuator.slot_2.status == PayloadStatus.RELEASED
    assert actuator.get_remaining_payload_count() == 0
