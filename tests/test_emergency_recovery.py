import pytest
from src.avionics.emergency_recovery import EmergencyRecoveryManager, RecoveryStatus, TriggerReason


def test_recovery_nominal_no_trigger():
    rec = EmergencyRecoveryManager()
    rep = rec.evaluate_telemetry(
        timestamp=1.0,
        altitude_agl_m=30.0,
        vz_down_mps=0.5,
        roll_rate_deg_s=15.0,
        pitch_rate_deg_s=10.0,
        yaw_rate_deg_s=12.0,
        accel_magnitude_g=1.1
    )
    assert rep.is_triggered is False
    assert rep.status == RecoveryStatus.ARMED
    assert rep.trigger_reason == TriggerReason.NONE


def test_tumble_spin_triggers_recovery():
    rec = EmergencyRecoveryManager(max_angular_rate_deg_s=180.0)
    rep = rec.evaluate_telemetry(
        timestamp=2.0,
        altitude_agl_m=28.0,
        vz_down_mps=2.0,
        roll_rate_deg_s=210.0,  # 180°/s limitini aşan vril / spin
        pitch_rate_deg_s=20.0,
        yaw_rate_deg_s=15.0,
        accel_magnitude_g=1.5
    )
    assert rep.is_triggered is True
    assert rep.status == RecoveryStatus.PARACHUTE_DEPLOYED
    assert rep.trigger_reason == TriggerReason.UNCONTROLLED_SPIN


def test_excessive_dive_triggers_recovery():
    rec = EmergencyRecoveryManager(max_dive_rate_mps=12.0)
    rep = rec.evaluate_telemetry(
        timestamp=3.0,
        altitude_agl_m=25.0,
        vz_down_mps=15.5,  # 12 m/s üstünde kontrolsüz dik dalış
        roll_rate_deg_s=10.0,
        pitch_rate_deg_s=10.0,
        yaw_rate_deg_s=5.0,
        accel_magnitude_g=1.2
    )
    assert rep.is_triggered is True
    assert rep.trigger_reason == TriggerReason.CRITICAL_DESCENT_RATE


def test_manual_gcs_trigger():
    rec = EmergencyRecoveryManager()
    rep = rec.trigger_manual_override(altitude_agl_m=20.0, timestamp=4.0)
    assert rep.is_triggered is True
    assert rep.status == RecoveryStatus.PARACHUTE_DEPLOYED
    assert rep.trigger_reason == TriggerReason.MANUAL_GCS_COMMAND


def test_parachute_drift_prediction():
    rec = EmergencyRecoveryManager(uav_mass_kg=2.6)
    # 30m AGL irtifadan 4 m/s rüzgar altında süzülüş
    drift_m, ttg_s, d_dir = rec.predict_touchdown_drift(
        current_altitude_agl_m=30.0,
        wind_speed_mps=4.0,
        wind_direction_deg=90.0  # Doğudan esen rüzgar Batıya sürükler (270°)
    )
    assert ttg_s > 4.0  # Paraşütle iniş süresi ~ 5-8 sn olmalı
    assert drift_m > 15.0  # Rüzgarla sürüklenme mesafesi
    assert d_dir == 270.0
