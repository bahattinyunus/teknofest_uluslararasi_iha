"""Unit tests for the Payload Grabber Controller mechanism (TEKNOFEST Görev 3 Bonus Payload Transfer)."""

import pytest
import time
from src.avionics.payload_grabber import (
    PayloadGrabberController,
    GrabberState,
    GrabberTelemetry,
)


class TestPayloadGrabberController:
    """Test suite for PayloadGrabberController subsystem."""

    @pytest.fixture
    def grabber(self):
        """Create a fresh grabber controller instance."""
        return PayloadGrabberController(
            pwm_open=1100,
            pwm_close=1900,
            grasp_hold_time_s=1.0,
        )

    def test_initial_state(self, grabber):
        """Verify initial disarmed state."""
        assert grabber.state == GrabberState.DISARMED
        assert grabber.current_pwm == 1100
        assert not grabber.payload_secured
        assert not grabber.ay_bonus_eligible
        assert not grabber.by_bonus_eligible

    def test_arm_and_disarm(self, grabber):
        """Verify arming and disarming transitions."""
        assert grabber.arm() is True
        assert grabber.state == GrabberState.OPEN
        assert grabber.current_pwm == 1100

        assert grabber.disarm() is True
        assert grabber.state == GrabberState.DISARMED

    def test_grasp_sequence_with_contact(self, grabber):
        """Verify successful grasp when contact microswitch and elapsed time confirm."""
        grabber.arm()
        now = 1000.0
        assert grabber.trigger_grasp(timestamp=now) is True
        assert grabber.state == GrabberState.GRASPING
        assert grabber.current_pwm == 1900

        # Step 1: Still grasping, only 0.5s elapsed
        telem = grabber.update_sensors(
            current_ma=900.0,
            contact_switch=True,
            optical_presence=True,
            timestamp=now + 0.5,
        )
        assert telem.state == GrabberState.GRASPING

        # Step 2: 1.2s elapsed (> grasp_hold_time_s) -> LOCKED_LOAD
        telem = grabber.update_sensors(
            current_ma=950.0,
            contact_switch=True,
            optical_presence=True,
            timestamp=now + 1.2,
        )
        assert telem.state == GrabberState.LOCKED_LOAD
        assert telem.payload_secured is True
        assert telem.ay_bonus_eligible is True

    def test_release_sequence(self, grabber):
        """Verify grasp followed by successful release."""
        grabber.arm()
        now = 1000.0
        grabber.trigger_grasp(timestamp=now)
        grabber.update_sensors(
            current_ma=950.0,
            contact_switch=True,
            optical_presence=True,
            timestamp=now + 1.2,
        )
        assert grabber.state == GrabberState.LOCKED_LOAD

        # Release payload
        assert grabber.trigger_release(timestamp=now + 2.0) is True
        assert grabber.state == GrabberState.RELEASED
        assert grabber.current_pwm == 1100
        assert grabber.by_bonus_eligible is True
        assert grabber.payload_secured is False
        assert grabber.cycles_completed == 1

    def test_overcurrent_protection(self, grabber):
        """Verify overcurrent triggers fault and opens jaws."""
        grabber.arm()
        grabber.trigger_grasp(timestamp=1000.0)

        # Trigger overcurrent fault (> OVERCURRENT_LIMIT_MA = 1600.0)
        telem = grabber.update_sensors(
            current_ma=1800.0,
            contact_switch=False,
            optical_presence=False,
            timestamp=1000.5,
        )
        assert telem.state == GrabberState.FAULT
        assert grabber.current_pwm == 1100  # Jaws open for safety
        assert not telem.payload_secured

    def test_telemetry_generation(self, grabber):
        """Verify telemetry dataclass values."""
        grabber.arm()
        telem = grabber.get_telemetry()
        assert isinstance(telem, GrabberTelemetry)
        assert telem.state == GrabberState.OPEN
        assert telem.servo_pwm_us == 1100
        assert telem.cycles_completed == 0
