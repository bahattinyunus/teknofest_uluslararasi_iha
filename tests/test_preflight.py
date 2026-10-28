"""
Unit tests for Preflight Diagnostics & Checklist Subsystem
"""
import pytest
from src.avionics.preflight import PreflightChecker, PreflightReport


def test_preflight_checker_standalone():
    checker = PreflightChecker(core_instance=None)
    report = checker.run_all_checks()

    assert report.total_count == 10
    assert report.passed_count == 10
    assert report.overall_status == "GO_FOR_TAKEOFF"
    assert report.duration_s < 2.0


def test_preflight_checker_items_content():
    checker = PreflightChecker(core_instance=None)
    report = checker.run_all_checks()

    item_names = [item.name for item in report.items]
    assert "120M_GEOFENCE_CEILING" in item_names
    assert "BATTERY_POWER" in item_names
    assert "MAVLINK_HEARTBEAT" in item_names
    assert "PAYLOAD_ACTUATORS" in item_names
