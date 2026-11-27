"""Unit tests for the Gust Alleviation & Wind Shear Controller (NASA F-Factor)."""

import pytest
from src.navigation.gust_alleviation import (
    GustAlleviationController,
    ShearHazardLevel,
    GustCompensationOutput,
)


class TestGustAlleviationController:
    """Test suite for GustAlleviationController."""

    @pytest.fixture
    def controller(self):
        return GustAlleviationController(
            k_roll_gust=1.25,
            k_pitch_gust=0.95,
            f_factor_threshold=0.13,
            wind_speed_limit_mps=6.94,
        )

    def test_initial_update_nominal(self, controller):
        """Verify initial update returns zero corrections."""
        out = controller.update(wind_vx=0.0, wind_vy=0.0, wind_vz=0.0, timestamp=100.0)
        assert isinstance(out, GustCompensationOutput)
        assert out.delta_roll_cmd == 0.0
        assert out.delta_pitch_cmd == 0.0
        assert out.hazard_level == ShearHazardLevel.NOMINAL
        assert out.go_around_recommended is False

    def test_lateral_gust_roll_compensation(self, controller):
        """Verify positive lateral wind acceleration produces negative roll corrective command."""
        controller.update(wind_vx=0.0, wind_vy=0.0, timestamp=100.0)
        # Lateral wind step: +2.0 m/s in 0.1s -> acc_y = 20.0 m/s^2 (clamped to max -15 deg roll)
        out = controller.update(wind_vx=0.0, wind_vy=2.0, timestamp=100.1)
        assert out.delta_roll_cmd < 0.0
        assert out.delta_roll_cmd >= -15.0

    def test_nasa_f_factor_wind_shear_warning(self, controller):
        """Verify rapid longitudinal wind drop + severe downdraft triggers WARNING_SHEAR and Go-Around."""
        controller.update(wind_vx=5.0, wind_vy=0.0, wind_vz=0.0, airspeed_mps=15.0, timestamp=100.0)
        # Downdraft of -3.0 m/s and sudden loss of headwind -> F factor >> 0.13
        out = controller.update(
            wind_vx=1.0,
            wind_vy=0.0,
            wind_vz=-3.0,
            airspeed_mps=15.0,
            in_release_run=True,
            timestamp=100.2,
        )
        assert out.hazard_level == ShearHazardLevel.WARNING_SHEAR
        assert out.delta_throttle > 0.0  # Throttle boost to overcome downdraft
        assert out.go_around_recommended is True  # Go-around triggered on release run!

    def test_spec_wind_limit_emergency(self, controller):
        """Verify wind exceeding 25 km/h (6.94 m/s) triggers EMERGENCY_GUST."""
        controller.update(wind_vx=0.0, wind_vy=0.0, timestamp=100.0)
        out = controller.update(wind_vx=7.5, wind_vy=2.0, timestamp=100.5)
        assert out.hazard_level == ShearHazardLevel.EMERGENCY_GUST

    def test_reset(self, controller):
        """Verify controller state reset."""
        controller.update(wind_vx=3.0, wind_vy=2.0, timestamp=100.0)
        controller.reset()
        assert controller.last_wind_vec is None
        assert controller.last_time is None
