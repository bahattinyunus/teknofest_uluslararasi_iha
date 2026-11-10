"""
Unit tests for Blackbox Telemetry Mission Debriefing Engine
"""
import pytest
import os
from src.telemetry.debrief_engine import MissionDebriefEngine, DebriefMetrics


def test_debrief_nonexistent_file():
    engine = MissionDebriefEngine()
    metrics = engine.analyze_log_file("nonexistent_flight_log.csv")
    assert metrics is None


def test_debrief_valid_csv_log(tmp_path):
    log_file = tmp_path / "test_telemetry.csv"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("timestamp,altitude_agl,ground_speed,voltage_v,roll_deg,pitch_deg,payloads_left,mission_state,miss_dist\n")
        f.write("0.0,0.0,0.0,16.8,0.0,0.0,2,TAKEOFF,0.0\n")
        f.write("5.0,28.0,12.0,16.4,2.0,1.0,2,SEARCHING,0.0\n")
        f.write("10.0,30.0,14.0,16.1,4.0,2.0,1,DROPPING,0.45\n")
        f.write("15.0,30.0,10.0,15.8,1.0,0.5,0,DROPPING,0.80\n")
        f.write("20.0,0.0,0.0,15.5,0.0,0.0,0,LANDED,0.0\n")

    engine = MissionDebriefEngine()
    metrics = engine.analyze_log_file(str(log_file))
    assert metrics is not None
    assert metrics.total_flight_time_s == 20.0
    assert metrics.battery_start_v == 16.8
    assert metrics.battery_end_v == 15.5
    assert metrics.max_ground_speed_mps == 14.0
    assert metrics.drop_events_detected == 2

    # Check Markdown report generation
    report = engine.generate_markdown_report(metrics, str(log_file))
    assert "TEKNOFEST 2026 Görev Analiz" in report
    assert "Bırakma # | Zaman (s)" in report
    assert "16.8V" in report
