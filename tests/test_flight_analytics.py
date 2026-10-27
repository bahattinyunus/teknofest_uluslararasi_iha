"""
Unit tests for Flight Analytics and 2026 Scoring Subsystem
"""
import pytest
from src.telemetry.analytics import FlightAnalyticsEngine, DropScore, FlightSummary


def test_drop_score_exact_center():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 0 meter miss distance -> 100 points
    score = engine.calculate_drop_score(0.0)
    assert score == 100.0


def test_drop_score_half_radius():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 5.0m miss distance (out of 10m max) -> 50 points
    score = engine.calculate_drop_score(5.0)
    assert score == 50.0


def test_drop_score_out_of_bounds():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 12.0m miss distance (> 10m) -> 0 points
    score = engine.calculate_drop_score(12.0)
    assert score == 0.0


def test_fixed_wing_scoring_radius():
    engine = FlightAnalyticsEngine(category="fixed_wing")
    # In fixed wing, radius is 20m. At 10m miss distance -> 50 points
    score = engine.calculate_drop_score(10.0)
    assert score == 50.0


def test_analyze_nonexistent_log():
    engine = FlightAnalyticsEngine()
    summary = engine.analyze_csv_log("non_existent_flight_log.csv")
    assert summary is None


def test_csv_log_parsing(tmp_path):
    csv_file = str(tmp_path / "test_flight.csv")
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("timestamp,state,altitude_agl,ground_speed,vx,vy,vz,battery_v,target_locked,target_type,lead_distance,miss_distance,payloads_left\n")
        f.write("100.0,TAKEOFF,10.0,2.0,2.0,0.0,0.0,16.2,0,NONE,0.0,99.0,2\n")
        f.write("105.0,LOCKING_TARGET_A,25.0,5.0,5.0,0.0,0.0,16.0,1,TARGET_A,3.0,1.5,2\n")
        f.write("110.0,DROPPING_PAYLOAD_1,20.0,3.0,3.0,0.0,0.0,15.8,1,TARGET_A,2.0,2.0,1\n")  # Payload 1 dropped with miss=2.0m
        f.write("115.0,DROPPING_PAYLOAD_2,20.0,3.0,3.0,0.0,0.0,15.5,1,TARGET_B,2.0,1.0,0\n")  # Payload 2 dropped with miss=1.0m
        f.write("120.0,LANDED,0.0,0.0,0.0,0.0,0.0,15.3,0,NONE,0.0,99.0,0\n")

    engine = FlightAnalyticsEngine(category="rotary_wing")
    summary = engine.analyze_csv_log(csv_file)

    assert summary is not None
    assert summary.total_flight_time_s == 20.0
    assert summary.max_altitude_m == 25.0
    assert summary.exceeded_120m_limit is False
    assert len(summary.drop_scores) == 2
    # At 2.0m miss: score = 100 * (1 - 2/10) = 80
    # At 1.0m miss: score = 100 * (1 - 1/10) = 90
    assert summary.drop_scores[0].score_points == 80.0
    assert summary.drop_scores[1].score_points == 90.0
    assert summary.total_mission_score == 170.0
    assert summary.compliance_passed is True

    md = engine.generate_markdown_report(summary)
    assert "170.0 / 200 Puan" in md
    assert "KURAL VE GÖREV UYUMLU" in md
