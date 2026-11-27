"""Unit tests for the Referee Report Generator (Official TEKNOFEST 2026 Audit Engine)."""

import pytest
from src.telemetry.referee_report_generator import (
    RefereeReportGenerator,
    RefereeAuditVerification,
)


class TestRefereeReportGenerator:
    """Test suite for RefereeReportGenerator."""

    @pytest.fixture
    def generator(self):
        return RefereeReportGenerator(team_name="TEST-UAV-TEAM")

    @pytest.fixture
    def nominal_telemetry(self):
        return [
            {"timestamp": 0.0, "alt_agl_m": 15.0, "ground_speed_mps": 14.0, "wind_speed_mps": 3.0, "pos_x": 0.0, "pos_y": 10.0},
            {"timestamp": 60.0, "alt_agl_m": 25.0, "ground_speed_mps": 16.0, "wind_speed_mps": 3.5, "pos_x": 50.0, "pos_y": 40.0},
            {"timestamp": 120.0, "alt_agl_m": 20.0, "ground_speed_mps": 15.0, "wind_speed_mps": 4.0, "pos_x": -30.0, "pos_y": -20.0},
            {"timestamp": 180.0, "alt_agl_m": 0.0, "ground_speed_mps": 0.0, "wind_speed_mps": 2.0, "pos_x": 0.0, "pos_y": 0.0},
        ]

    def test_nominal_audit_generation(self, generator, nominal_telemetry):
        """Verify nominal flight audit passes without DQ risk."""
        audit = generator.generate_audit(
            category="rotary_wing",
            task_number=2,
            c_autonomy=1.0,
            flight_telemetry_points=nominal_telemetry,
            setup_duration_s=210.0,
            target_a_miss_m=0.35,
            target_b_miss_m=0.45,
            ay_bonus=True,
            by_bonus=True,
        )
        assert isinstance(audit, RefereeAuditVerification)
        assert audit.team_name == "TEST-UAV-TEAM"
        assert audit.ceiling_breached is False
        assert audit.geofence_breached is False
        assert audit.disqualification_risk is False
        assert len(audit.dq_reasons) == 0
        assert audit.calculated_score > 0.0
        assert audit.max_possible_score == 80.0
        assert len(audit.telemetry_hash) > 0

    def test_ceiling_breach_detection(self, generator, nominal_telemetry):
        """Verify exceeding 120m AGL raises disqualification risk."""
        breached_telemetry = list(nominal_telemetry)
        breached_telemetry.append({
            "timestamp": 90.0,
            "alt_agl_m": 125.4,  # Over 120m ceiling!
            "ground_speed_mps": 15.0,
            "wind_speed_mps": 3.0,
            "pos_x": 10.0,
            "pos_y": 10.0,
        })
        audit = generator.generate_audit(
            category="rotary_wing",
            task_number=2,
            c_autonomy=1.0,
            flight_telemetry_points=breached_telemetry,
        )
        assert audit.ceiling_breached is True
        assert audit.disqualification_risk is True
        assert any("120m" in r for r in audit.dq_reasons)
        assert audit.calculated_score == 0.0  # DQ score zeroed out

    def test_geofence_breach_detection(self, generator, nominal_telemetry):
        """Verify straying outside 200x300m boundary raises geofence breach."""
        breached_telemetry = list(nominal_telemetry)
        breached_telemetry.append({
            "timestamp": 100.0,
            "alt_agl_m": 25.0,
            "ground_speed_mps": 15.0,
            "wind_speed_mps": 3.0,
            "pos_x": 175.0,  # Exceeds +150m boundary
            "pos_y": 20.0,
        })
        audit = generator.generate_audit(
            category="fixed_wing",
            task_number=2,
            c_autonomy=1.0,
            flight_telemetry_points=breached_telemetry,
        )
        assert audit.geofence_breached is True
        assert audit.disqualification_risk is True
        assert any("Geofence" in r for r in audit.dq_reasons)

    def test_html_report_rendering(self, generator, nominal_telemetry):
        """Verify HTML report includes team name, hash, and official styling."""
        audit = generator.generate_audit(
            category="rotary_wing",
            task_number=2,
            c_autonomy=1.0,
            flight_telemetry_points=nominal_telemetry,
        )
        html = generator.render_html_report(audit)
        assert "<!DOCTYPE html>" in html
        assert "TEST-UAV-TEAM" in html
        assert audit.telemetry_hash in html
        assert "TÜBİTAK TEKNOFEST 2026" in html
