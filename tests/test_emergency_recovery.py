"""
Unit tests for Autonomous Flight Termination System (FTS) & Emergency Recovery
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi (Madde 9.2 Arıza Emniyet):
- Sabit Kanat: Motor kesildi, tam yukarı irtifa, tam sağ rudder/aileron, tam açık flap, paraşüt.
- Döner Kanat: Yarım gaz kontrollü iniş, RTL KESİNLİKLE YASAK (no RTL).
"""
import pytest
from src.avionics.emergency_recovery import (
    EmergencyRecoveryManager,
    RecoveryStatus,
    TriggerReason
)
from src.avionics.failsafe import VehicleType


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


# ==============================================================================
# Sabit vs Döner Kanat Acil Kurtarma Profil Testleri
# ==============================================================================

def test_sabit_kanat_emergency_recovery_profile():
    """Sabit Kanat Acil Durum / Kırım Kurtarma Profili Testi."""
    rec = EmergencyRecoveryManager(vehicle_type="fixed_wing")
    assert rec.vehicle_type == VehicleType.FIXED_WING

    prof = rec.get_failsafe_profile()
    assert prof["throttle"] == "cut"
    assert prof["pitch"] == "full_up"
    assert prof["rudder"] == "full_right"
    assert prof["aileron"] == "full_right"
    assert prof["flaps"] == "full_down"
    assert prof["rtl_allowed"] is False

    # Tetiklendiğinde raporda komutların doğrulanması
    rep = rec.trigger_failsafe_profile(altitude_agl_m=35.0, timestamp=10.0)
    assert rep.is_triggered is True
    assert rep.status == RecoveryStatus.PARACHUTE_DEPLOYED
    assert rep.throttle_command == "cut"
    assert rep.elevator_pitch == "full_up"
    assert rep.rudder == "full_right"
    assert rep.aileron == "full_right"
    assert rep.flaps == "full_down"
    assert rep.rtl_allowed is False


def test_doner_kanat_emergency_recovery_profile_no_rtl():
    """Döner Kanat Acil Durum Kontrollü Alçalma ve NO RTL Kuralı Testi."""
    rec = EmergencyRecoveryManager(vehicle_type="rotary_wing")
    assert rec.vehicle_type == VehicleType.ROTARY_WING
    assert rec.rtl_allowed is False

    prof = rec.get_failsafe_profile()
    assert prof["throttle"] == "half_throttle_controlled_descent"
    assert prof["throttle_pct"] == 50.0
    assert prof["rtl_allowed"] is False
    assert prof["flaps"] == "none"

    # Failsafe tetiklendiğinde Döner kanat yarım gaz kontrollü inişe geçmelidir (RTL yasak)
    rep = rec.trigger_failsafe_profile(altitude_agl_m=40.0, timestamp=12.0)
    assert rep.is_triggered is True
    assert rep.status == RecoveryStatus.CONTROLLED_DESCENT
    assert rep.throttle_command == "half_throttle_controlled_descent"
    assert rep.rtl_allowed is False

    # Geofence sert sınır ihlalinde kontrollü inişe geçmelidir
    rec_geo = EmergencyRecoveryManager(vehicle_type="rotary_wing")
    rep_geo = rec_geo.evaluate_telemetry(
        timestamp=15.0,
        altitude_agl_m=30.0,
        vz_down_mps=1.0,
        roll_rate_deg_s=5.0,
        pitch_rate_deg_s=5.0,
        yaw_rate_deg_s=5.0,
        accel_magnitude_g=1.0,
        geofence_distance_outside_m=30.0  # > 25m dışarı kaçış
    )
    assert rep_geo.is_triggered is True
    assert rep_geo.status == RecoveryStatus.CONTROLLED_DESCENT
    assert rep_geo.trigger_reason == TriggerReason.GEOFENCE_HARD_BREACH
    assert rep_geo.rtl_allowed is False
