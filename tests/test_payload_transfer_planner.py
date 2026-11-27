"""Unit tests for the Payload Transfer Planner (TEKNOFEST Görev 3 Bonus Transfer Planlayıcısı)."""

import pytest
from src.avionics.payload_grabber import PayloadGrabberController
from src.navigation.payload_transfer_planner import (
    PayloadTransferPlanner,
    TransferPhase,
    TransferStatus,
)


class TestPayloadTransferPlanner:
    """Test suite for PayloadTransferPlanner."""

    @pytest.fixture
    def planner(self):
        controller = PayloadGrabberController(grasp_hold_time_s=0.5)
        return PayloadTransferPlanner(
            target_a_xy=(-20.0, 45.0),
            target_b_xy=(25.0, 45.0),
            transit_altitude_m=15.0,
            pickup_hover_altitude_m=0.35,
            drop_hover_altitude_m=1.20,
            acceptance_radius_m=0.40,
            grabber_controller=controller,
        )

    def test_initial_state(self, planner):
        """Verify initial state is STANDBY with zero bonus."""
        status = planner.update(uav_xy=(0.0, 0.0), uav_alt_m=10.0)
        assert status.phase == TransferPhase.STANDBY
        assert status.total_bonus_points == 0
        assert not status.ay_bonus_awarded
        assert not status.by_bonus_awarded
        assert not status.is_active

    def test_start_and_abort(self, planner):
        """Verify start and abort mission transitions."""
        assert planner.start_transfer_mission() is True
        assert planner.phase == TransferPhase.NAVIGATE_TO_TARGET_A

        assert planner.abort_mission() is True
        assert planner.phase == TransferPhase.ABORTED

    def test_full_mission_transfer_cycle(self, planner):
        """Verify complete flight progression from Target A to Target B with +20 points."""
        planner.start_transfer_mission()
        t = 1000.0

        # Phase 1: Transit to Target A (-20.0, 45.0)
        status = planner.update(uav_xy=(0.0, 20.0), uav_alt_m=15.0, timestamp=t)
        assert status.phase == TransferPhase.NAVIGATE_TO_TARGET_A
        assert status.is_active is True

        # Close in on Target A
        status = planner.update(uav_xy=(-19.0, 44.5), uav_alt_m=15.0, timestamp=t)
        assert status.phase == TransferPhase.PRECISION_DESCENT_A

        # Phase 2: Precision Descent at Target A
        status = planner.update(uav_xy=(-20.1, 45.1), uav_alt_m=0.36, timestamp=t)
        assert status.phase == TransferPhase.GRASP_PAYLOAD

        # Phase 3: Grasping (AY Bonus)
        # Advance time by 0.6s to trigger locked load
        status = planner.update(
            uav_xy=(-20.0, 45.0),
            uav_alt_m=0.35,
            contact_switch=True,
            motor_current_ma=900.0,
            timestamp=t + 0.6,
        )
        assert status.phase == TransferPhase.CLIMB_TRANSIT
        assert status.ay_bonus_awarded is True
        assert status.total_bonus_points == 10

        # Phase 4: Climb back to transit altitude
        status = planner.update(uav_xy=(-20.0, 45.0), uav_alt_m=14.0, timestamp=t + 2.0)
        assert status.phase == TransferPhase.NAVIGATE_TO_TARGET_B

        # Phase 5: Transit to Target B (25.0, 45.0)
        status = planner.update(uav_xy=(24.0, 44.5), uav_alt_m=15.0, timestamp=t + 4.0)
        assert status.phase == TransferPhase.PRECISION_DESCENT_B

        # Phase 6: Precision Descent at Target B
        status = planner.update(uav_xy=(25.1, 45.1), uav_alt_m=1.22, timestamp=t + 6.0)
        assert status.phase == TransferPhase.RELEASE_PAYLOAD

        # Phase 7: Release payload and verify completion (BY Bonus)
        status = planner.update(uav_xy=(25.0, 45.0), uav_alt_m=1.20, timestamp=t + 7.0)
        assert status.phase == TransferPhase.COMPLETED
        assert status.by_bonus_awarded is True
        assert status.total_bonus_points == 20
        assert status.is_active is False
