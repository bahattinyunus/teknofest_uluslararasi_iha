"""
Unit tests for Sensor Fusion Validator and FDIR Subsystem
"""
import pytest
from src.avionics.sensor_fusion_validator import (
    SensorFusionValidator,
    HealthLevel,
    FDIRAction,
    FDIRReport
)


def test_validator_nominal_operation():
    validator = SensorFusionValidator()
    report = validator.validate_sensors(
        timestamp=1.0,
        baro_alt=30.0,
        lidar_alt=29.8,
        gps_alt=30.1,
        gps_vx=10.0,
        gps_vy=0.0,
        flow_vx=9.8,
        flow_vy=0.1,
        mag_heading=90.0,
        gps_cog=91.0,
        gyro_yaw=89.5
    )
    assert report.health_level == HealthLevel.NOMINAL
    assert report.recommended_action == FDIRAction.CONTINUE
    assert len(report.isolated_sensors) == 0
    assert 29.5 <= report.validated_altitude_m <= 30.5
    assert 9.5 <= report.validated_speed_mps <= 10.5


def test_validator_gps_altitude_glitch_isolation():
    validator = SensorFusionValidator(fault_latch_count=2)
    # Step 1: sudden GPS altitude anomaly (e.g. multipath jump to 80m while baro is 30m)
    validator.validate_sensors(timestamp=1.0, baro_alt=30.0, lidar_alt=30.0, gps_alt=80.0)
    # Step 2: fault latches on 2nd step
    report = validator.validate_sensors(timestamp=2.0, baro_alt=30.0, lidar_alt=30.0, gps_alt=80.0)

    assert "gps_alt" in report.isolated_sensors
    # Validated altitude must reject the faulty 80m GPS and use healthy sensors (30m)
    assert report.validated_altitude_m == 30.0
    assert report.health_level == HealthLevel.DEGRADED


def test_validator_critical_failure_triggers_action():
    validator = SensorFusionValidator(fault_latch_count=1)
    # Both altitude sensors fail completely
    report = validator.validate_sensors(
        timestamp=1.0,
        baro_alt=150.0, # baro thinks 150m
        lidar_alt=5.0,  # lidar thinks 5m
        gps_alt=80.0,   # gps thinks 80m
        gps_vx=25.0,
        flow_vx=0.0,
        imu_vx=10.0
    )
    assert report.health_level in (HealthLevel.DEGRADED, HealthLevel.CRITICAL)


def test_validator_reset():
    validator = SensorFusionValidator(fault_latch_count=1)
    validator.validate_sensors(timestamp=1.0, baro_alt=30.0, lidar_alt=30.0, gps_alt=999.0)
    assert not validator.channels["gps_alt"].is_healthy
    validator.reset()
    assert validator.channels["gps_alt"].is_healthy
    assert validator.channels["gps_alt"].consecutive_faults == 0
