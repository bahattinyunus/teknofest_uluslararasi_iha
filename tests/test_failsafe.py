"""
Unit tests for Avionics Failsafe and Health Monitoring Subsystem
"""
import time
import pytest
from src.avionics.failsafe import FailsafeManager, FailsafeLevel, AvionicsHealth


def test_failsafe_nominal_state():
    mgr = FailsafeManager()
    health = AvionicsHealth(
        voltage_v=15.8,
        current_a=12.0,
        altitude_agl_m=35.0,
        distance_from_home_m=50.0,
        last_heartbeat_time=time.monotonic(),
        satellites_visible=14,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health)
    assert level == FailsafeLevel.NOMINAL
    assert mgr.failsafe_triggered is False


def test_failsafe_altitude_limit_violation():
    mgr = FailsafeManager()
    # 2026 rule: max 120m AGL
    health = AvionicsHealth(
        voltage_v=15.5,
        current_a=12.0,
        altitude_agl_m=125.0,  # Exceeded 120m!
        distance_from_home_m=50.0,
        last_heartbeat_time=time.monotonic(),
        satellites_visible=12,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health)
    assert level == FailsafeLevel.RTL_REQUIRED
    assert mgr.failsafe_triggered is True
    assert "İrtifa Limiti Aşıldı" in reason


def test_failsafe_critical_battery():
    mgr = FailsafeManager()
    health = AvionicsHealth(
        voltage_v=13.8,  # Below 14.0V critical threshold
        current_a=18.0,
        altitude_agl_m=40.0,
        distance_from_home_m=60.0,
        last_heartbeat_time=time.monotonic(),
        satellites_visible=12,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health)
    assert level == FailsafeLevel.RTL_REQUIRED
    assert mgr.failsafe_triggered is True
    assert "DÜŞÜK BATARYA" in reason


def test_failsafe_emergency_battery():
    mgr = FailsafeManager()
    health = AvionicsHealth(
        voltage_v=12.9,  # Below 13.2V emergency threshold
        current_a=20.0,
        altitude_agl_m=40.0,
        distance_from_home_m=60.0,
        last_heartbeat_time=time.monotonic(),
        satellites_visible=12,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health)
    assert level == FailsafeLevel.LAND_IMMEDIATELY
    assert mgr.failsafe_triggered is True


def test_failsafe_heartbeat_timeout():
    mgr = FailsafeManager()
    health = AvionicsHealth(
        voltage_v=15.5,
        current_a=10.0,
        altitude_agl_m=30.0,
        distance_from_home_m=30.0,
        last_heartbeat_time=time.monotonic() - 5.0,  # 5 seconds stale
        satellites_visible=12,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health)
    assert level == FailsafeLevel.RTL_REQUIRED
    assert mgr.failsafe_triggered is True
    assert "HABERLEŞME KESİLDİ" in reason
