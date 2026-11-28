"""
TEKNOFEST 2026 - İtki, ESC Termal & Titreşim Sağlık İzleyici Testleri
"""

from src.avionics.propulsion_health import (
    PropulsionHealthMonitor,
    PropulsionSnapshot,
    PropulsionAlertLevel,
)


def test_nominal_propulsion_at_tulga_altitude():
    mon = PropulsionHealthMonitor()
    rep = mon.evaluate(PropulsionSnapshot(
        motor_rpms=[7200.0, 7220.0, 7180.0, 7210.0],
        esc_temps_c=[52.0, 54.0, 51.5, 53.0],
        throttle_pct=52.0,
        air_density_kgpm3=1.06,
        vibration_rms_mps2=2.5,
    ))
    assert rep.alert_level == PropulsionAlertLevel.NOMINAL
    assert rep.thermal_derating_factor == 1.0
    assert rep.suspected_fault_motor_idx is None
    assert rep.hover_throttle_margin_pct > 25.0


def test_esc_overheat_thermal_derating_and_critical_alert():
    mon = PropulsionHealthMonitor()
    rep_warn = mon.evaluate(PropulsionSnapshot(
        motor_rpms=[7500.0, 7500.0, 7500.0, 7500.0],
        esc_temps_c=[72.0, 88.0, 74.0, 73.0],
        throttle_pct=55.0,
    ))
    assert rep_warn.alert_level == PropulsionAlertLevel.WARNING
    assert rep_warn.thermal_derating_factor < 1.0

    rep_crit = mon.evaluate(PropulsionSnapshot(
        motor_rpms=[7500.0, 7500.0, 7500.0, 7500.0],
        esc_temps_c=[75.0, 98.0, 76.0, 75.0],
        throttle_pct=55.0,
    ))
    assert rep_crit.alert_level == PropulsionAlertLevel.CRITICAL
    assert rep_crit.thermal_derating_factor <= 0.70


def test_motor_rpm_asymmetry_and_vibration_fault_isolation():
    mon = PropulsionHealthMonitor()
    rep = mon.evaluate(PropulsionSnapshot(
        motor_rpms=[7400.0, 7420.0, 4800.0, 7380.0],
        esc_temps_c=[55.0, 56.0, 68.0, 55.0],
        throttle_pct=60.0,
        vibration_rms_mps2=31.0,
    ))
    assert rep.alert_level == PropulsionAlertLevel.CRITICAL
    assert rep.suspected_fault_motor_idx == 2
    assert rep.rpm_asymmetry_pct >= 25.0
