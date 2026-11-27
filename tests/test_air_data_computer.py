"""
Unit tests for Air Data Computer (ADC) and Stall Protection Subsystem
"""
import pytest
import math
from src.avionics.air_data_computer import AirDataComputer, AirDataState, AirspeedAlert


def test_adc_sea_level_nominal_computation():
    adc = AirDataComputer(v_stall_mps=9.5, v_ne_mps=30.0)
    # Sea level: P_static = 101325 Pa, OAT = 15 degC (ISA)
    # Dynamic pressure at 15 m/s: 0.5 * 1.225 * 15^2 = 137.81 Pa
    dp = 0.5 * 1.225 * (15.0 ** 2)
    state = adc.compute(diff_pressure_pa=dp, static_pressure_pa=101325.0, oat_celsius=15.0, timestamp=1.0)

    assert abs(state.ias_mps - 15.0) < 0.2
    assert abs(state.tas_mps - 15.0) < 0.2
    assert abs(state.air_density_kgpm3 - 1.225) < 0.01
    assert abs(state.pressure_alt_m - 0.0) < 10.0
    assert state.alert == AirspeedAlert.NOMINAL
    assert state.stall_margin_mps > 5.0


def test_adc_density_altitude_scaling_at_tulga():
    adc = AirDataComputer()
    # Malatya Tulga: elevation ~938m MSL -> P_static ~90500 Pa, OAT = 30 degC (hot day)
    dp = 120.0
    state = adc.compute(diff_pressure_pa=dp, static_pressure_pa=90500.0, oat_celsius=30.0, timestamp=1.0)

    # In thin air, TAS should be higher than IAS
    assert state.tas_mps > state.ias_mps
    assert state.air_density_kgpm3 < 1.15
    assert state.density_alt_m > state.pressure_alt_m
    assert state.mach_number > 0.0


def test_adc_stall_warning_and_critical_detection():
    adc = AirDataComputer(v_stall_mps=9.5)
    p_static = 90500.0
    
    # 1. IAS = 9.0 m/s (below V_stall 9.5 -> STALL_WARNING)
    dp_warning = 0.5 * 1.225 * (9.0 ** 2)
    s_warn = adc.compute(diff_pressure_pa=dp_warning, static_pressure_pa=p_static, timestamp=1.0)
    assert s_warn.alert == AirspeedAlert.STALL_WARNING
    assert s_warn.stall_margin_mps < 0.0

    # 2. IAS = 7.0 m/s (below 85% of V_stall 9.5 -> STALL_CRITICAL)
    dp_crit = 0.5 * 1.225 * (7.0 ** 2)
    s_crit = adc.compute(diff_pressure_pa=dp_crit, static_pressure_pa=p_static, timestamp=2.0)
    assert s_crit.alert == AirspeedAlert.STALL_CRITICAL

    # 3. Stall recovery action test
    rec_pitch, rec_throttle = adc.get_stall_recovery_action(current_pitch_deg=4.0)
    assert rec_pitch <= -8.0
    assert rec_throttle == 1.0


def test_adc_overspeed_detection():
    adc = AirDataComputer(v_ne_mps=30.0)
    # Speed at 32 m/s -> Overspeed
    dp_fast = 0.5 * 1.225 * (32.0 ** 2)
    state = adc.compute(diff_pressure_pa=dp_fast, static_pressure_pa=101325.0, timestamp=1.0)
    assert state.alert == AirspeedAlert.OVERSPEED


def test_adc_pitot_blockage_detection():
    adc = AirDataComputer()
    p_static = 95000.0
    
    # Fast cruise first
    dp_cruise = 0.5 * 1.225 * (16.0 ** 2)
    adc.compute(diff_pressure_pa=dp_cruise, static_pressure_pa=p_static, timestamp=1.0)

    # Sudden zero dynamic pressure drop for multiple cycles -> Blockage
    adc.compute(diff_pressure_pa=0.0, static_pressure_pa=p_static, timestamp=2.0)
    adc.compute(diff_pressure_pa=0.0, static_pressure_pa=p_static, timestamp=3.0)
    st = adc.compute(diff_pressure_pa=0.0, static_pressure_pa=p_static, timestamp=4.0)
    assert st.alert == AirspeedAlert.SENSOR_BLOCKAGE
