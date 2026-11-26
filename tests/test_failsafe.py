"""
Unit tests for Avionics Failsafe and Health Monitoring Subsystem
TÜBİTAK TEKNOFEST 2026 V7 Şartnamesi (Madde 9.2 Arıza Emniyet) Doğrulaması:
- Sabit Kanat: Motor kesildi, tam yukarı irtifa, tam sağ rudder/aileron, tam açık flap.
- Döner Kanat: Yarım gaz kontrollü iniş, RTL KESİNLİKLE YASAK (no RTL).
"""
import time
import pytest
from src.avionics.failsafe import (
    FailsafeManager,
    FailsafeLevel,
    AvionicsHealth,
    VehicleType,
    FailSafeProfile
)


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


# ==============================================================================
# 2026 Şartnamesi Madde 9.2 Sabit vs Döner Fail-Safe Profil Testleri
# ==============================================================================

def test_sabit_kanat_exact_failsafe_profile():
    """
    Sabit Kanat Profili:
    - Motor durdurulmalı (cut throttle, 0%)
    - İrtifa dümeni tam yukarı (full elevator up, +100%)
    - İstikamet ve kanatçık tam sağ (full rudder and aileron right, +100%)
    - Varsa flaplar tam aşağı (full flaps down, +100%)
    """
    mgr = FailsafeManager(vehicle_type="fixed_wing")
    assert mgr.vehicle_type == VehicleType.FIXED_WING

    prof = mgr.get_failsafe_profile()
    assert prof.throttle == "cut"
    assert prof.throttle_pct == 0.0
    assert prof.pitch == "full_up"
    assert prof.pitch_pct == 100.0
    assert prof.rudder == "full_right"
    assert prof.rudder_pct == 100.0
    assert prof.aileron == "full_right"
    assert prof.aileron_pct == 100.0
    assert prof.flaps == "full_down"
    assert prof.flaps_pct == 100.0

    # PWM Kanalları: CH1=2000, CH2=2000, CH3=1000, CH4=2000, CH5=2000
    assert prof.pwm_channels[1] == 2000  # Aileron tam sağ
    assert prof.pwm_channels[2] == 2000  # Elevator tam yukarı
    assert prof.pwm_channels[3] == 1000  # Throttle motor kesildi
    assert prof.pwm_channels[4] == 2000  # Rudder tam sağ
    assert prof.pwm_channels[5] == 2000  # Flap tam aşağı

    cmd = mgr.get_actuator_commands()
    assert cmd["throttle"] == "cut"
    assert cmd["flaps"] == "full_down"


def test_doner_kanat_exact_failsafe_profile_no_rtl():
    """
    Döner Kanat Profili:
    - İHA'nın yarım gazla (half throttle) kontrollü inişi sağlanmalı (descent)
    - Kesinlikle RTL yapılmamalıdır (NO RTL - rtl_allowed = False)!
    """
    mgr = FailsafeManager(vehicle_type="rotary_wing")
    assert mgr.vehicle_type == VehicleType.ROTARY_WING
    assert mgr.rtl_allowed is False

    prof = mgr.get_failsafe_profile()
    assert prof.throttle == "half_throttle_controlled_descent"
    assert prof.throttle_pct == 50.0
    assert prof.rtl_allowed is False
    assert prof.pitch == "neutral"
    assert prof.rudder == "neutral"
    assert prof.aileron == "neutral"
    assert prof.flaps == "none"

    # PWM Kanalları: CH1=1500, CH2=1500, CH3=1500 (half throttle descent)
    assert prof.pwm_channels[1] == 1500
    assert prof.pwm_channels[2] == 1500
    assert prof.pwm_channels[3] == 1500  # Yarım gaz kontrollü iniş
    assert prof.pwm_channels[4] == 1500

    cmd = mgr.get_actuator_commands()
    assert cmd["rtl_allowed"] is False
    assert cmd["throttle_pct"] == 50.0


def test_doner_kanat_evaluation_strictly_no_rtl():
    """
    Döner kanatta irtifa aşımı veya haberleşme kaybında RTL yerine
    daima CONTROLLED_DESCENT tetiklenmelidir.
    """
    mgr = FailsafeManager(vehicle_type="rotary_wing")

    # İrtifa aşımı senaryosu (> 120m)
    health_alt = AvionicsHealth(
        voltage_v=15.5,
        current_a=12.0,
        altitude_agl_m=122.0,
        distance_from_home_m=50.0,
        last_heartbeat_time=time.monotonic(),
        satellites_visible=12,
        ekf_healthy=True
    )
    level, reason = mgr.evaluate(health_alt)
    assert level == FailsafeLevel.CONTROLLED_DESCENT
    assert level != FailsafeLevel.RTL_REQUIRED
    assert "RTL Yasak" in reason
    assert mgr.failsafe_triggered is True
    assert mgr.active_profile.rtl_allowed is False
    assert mgr.active_profile.throttle_pct == 50.0

    # Heartbeat timeout senaryosu
    health_hb = AvionicsHealth(
        voltage_v=15.5,
        current_a=10.0,
        altitude_agl_m=30.0,
        distance_from_home_m=30.0,
        last_heartbeat_time=time.monotonic() - 6.0,
        satellites_visible=12,
        ekf_healthy=True
    )
    level_hb, reason_hb = mgr.evaluate(health_hb)
    assert level_hb == FailsafeLevel.CONTROLLED_DESCENT
    assert level_hb != FailsafeLevel.RTL_REQUIRED
    assert "RTL Yasak" in reason_hb


def test_failsafe_config_initialization():
    """Konfigürasyon sözlüğünden otomatik kategori tespiti testi."""
    cfg_rotary = {
        "competition": {"category": "rotary_wing"},
        "failsafe": {"max_altitude_agl_m": 120.0}
    }
    mgr = FailsafeManager(config=cfg_rotary)
    assert mgr.vehicle_type == VehicleType.ROTARY_WING
    assert mgr.rtl_allowed is False

    cfg_fixed = {
        "competition": {"category": "fixed_wing"},
        "failsafe": {"modes": {"fixed_wing": {"rtl_allowed": True}}}
    }
    mgr_fixed = FailsafeManager(config=cfg_fixed)
    assert mgr_fixed.vehicle_type == VehicleType.FIXED_WING
    assert mgr_fixed.rtl_allowed is True
