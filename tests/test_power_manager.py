"""
Unit tests for Battery Power and Energy Management Subsystem
"""
import pytest
from src.avionics.power_manager import BatteryPowerManager, PowerStatus


def test_power_manager_initial_full_battery():
    mgr = BatteryPowerManager(nominal_capacity_mah=5000.0, cell_count=4)
    # 16.8V full battery (4.20V/cell)
    status = mgr.update(voltage_v=16.8, current_a=1.5, distance_to_home_m=20.0)

    assert status.cell_voltage_v == 4.20
    assert status.state_of_charge_pct > 90.0
    assert status.is_pnr_reached is False
    assert status.throttle_limit_factor == 1.0


def test_power_manager_pnr_threshold_detection():
    mgr = BatteryPowerManager(nominal_capacity_mah=5000.0, cell_count=4)
    # Depleted battery (13.6V ~ 3.40V/cell) and far from home (300m)
    status = mgr.update(voltage_v=13.6, current_a=15.0, distance_to_home_m=300.0, headwind_mps=3.0)

    assert status.cell_voltage_v == 3.40
    assert status.state_of_charge_pct < 15.0
    assert status.is_pnr_reached is True
    assert status.throttle_limit_factor < 1.0


def test_power_manager_rtl_energy_scaling_with_headwind():
    mgr = BatteryPowerManager()
    e_calm = mgr.calculate_rtl_energy(distance_to_home_m=200.0, headwind_mps=0.0)
    e_wind = mgr.calculate_rtl_energy(distance_to_home_m=200.0, headwind_mps=4.0)

    assert e_wind > e_calm


def test_power_manager_reset():
    mgr = BatteryPowerManager()
    mgr.update(voltage_v=15.5, current_a=12.0)
    assert mgr.consumed_wh > 0.0

    mgr.reset()
    assert mgr.consumed_wh == 0.0
    assert mgr.consumed_mah == 0.0
