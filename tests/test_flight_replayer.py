"""
TEKNOFEST 2026 - Kara Kutu Tekrar Oynatma ve Regresyon Denetleyicisi Testleri
"""

import json
from src.telemetry.flight_replayer import FlightTelemetryReplayer


def test_replayer_nominal_flight_passes_regression():
    replayer = FlightTelemetryReplayer()
    rows = [
        {"timestamp": 0.0, "altitude_agl": 0.0, "ground_speed": 0.0, "vz": 0.0, "battery_v": 16.4, "payloads_left": 2},
        {"timestamp": 10.0, "altitude_agl": 35.0, "ground_speed": 15.0, "vz": 0.0, "battery_v": 15.8, "payloads_left": 2},
        {"timestamp": 25.0, "altitude_agl": 20.0, "ground_speed": 12.0, "vz": 0.3, "battery_v": 15.4, "payloads_left": 1},
        {"timestamp": 40.0, "altitude_agl": 20.0, "ground_speed": 12.0, "vz": 0.2, "battery_v": 15.1, "payloads_left": 0},
    ]
    res = replayer.replay_rows(rows)
    assert res.passed_regression is True
    assert res.critical_count == 0
    assert res.payloads_released == 2
    assert res.max_altitude_agl_m == 35.0
    parsed = json.loads(res.to_json())
    assert parsed["passed_regression"] is True


def test_replayer_detects_ceiling_and_battery_critical_breaches(tmp_path):
    csv_file = tmp_path / "breach_log.csv"
    csv_file.write_text(
        "timestamp,altitude_agl,ground_speed,vz,battery_v,payloads_left\n"
        "0.0,10.0,5.0,0.0,16.0,2\n"
        "5.0,126.5,18.0,0.0,13.6,2\n"
        "10.0,50.0,12.0,11.2,13.4,2\n",
        encoding="utf-8",
    )
    replayer = FlightTelemetryReplayer()
    res = replayer.replay_csv(str(csv_file))
    assert res.passed_regression is False
    codes = {a.code for a in res.anomalies}
    assert "CEILING_BREACH" in codes
    assert "BATTERY_CRITICAL" in codes
    assert "EXCESSIVE_DESCENT" in codes
