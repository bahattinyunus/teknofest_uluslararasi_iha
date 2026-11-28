"""
Unit tests for Web Ground Control Station (Web GCS) Subsystem
TÜBİTAK TEKNOFEST 2026 Uluslararası İHA V7 Specification Alignment:
- Malatya Tulga Havalimanı (38.34694° N, 38.24444° E, 938m MSL)
- 200x300m flight area, 150m poles, 30x100m scan area
- Sabit Kanat vs Döner Kanat target toggle & fail-safe profiles
- Official Tablo 3 PG1 & PG2 score calculators
"""
import urllib.request
import json
import time
import pytest
from src.web_gcs.server import WebGCSServer


@pytest.fixture(scope="module")
def gcs_server():
    server = WebGCSServer(host="127.0.0.1", port=8899, core_instance=None, category="rotary_wing")
    server.start_background()
    time.sleep(0.15)
    yield server
    server.stop()


def test_web_gcs_html_dashboard(gcs_server):
    with urllib.request.urlopen("http://127.0.0.1:8899/") as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "UAV-ARCHITECT-GLOBAL" in html
        assert "radarCanvas" in html
        assert "Malatya Tulga" in html
        assert "200m x 300m" in html or "200x300m" in html
        assert "150m" in html
        assert "30x100m" in html
        assert "TABLO 3" in html
        assert "DÖNER KANAT" in html
        assert "SABİT KANAT" in html
        assert "120m AGL" in html


def test_web_gcs_telemetry_endpoint(gcs_server):
    with urllib.request.urlopen("http://127.0.0.1:8899/api/telemetry") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, dict)
        assert data["venue"] == "Malatya Tulga Havalimanı (LTAO)"
        assert data["coordinates"]["lat"] == 38.34694
        assert data["coordinates"]["lon"] == 38.24444
        assert data["coordinates"]["alt_msl_m"] == 938.0
        assert "category" in data
        assert "altitude_agl" in data
        assert "ground_speed" in data
        assert "wind_speed" in data
        assert "battery_v" in data


def test_web_gcs_field_config_endpoint(gcs_server):
    with urllib.request.urlopen("http://127.0.0.1:8899/api/field_config") as resp:
        assert resp.status == 200
        config = json.loads(resp.read().decode("utf-8"))
        assert config["venue_name"] == "Malatya Tulga Havalimanı (LTAO)"
        assert config["flight_area"]["width_m"] == 200.0
        assert config["flight_area"]["length_m"] == 300.0
        assert config["flight_area"]["has_buffer_zone"] is False
        assert config["poles"]["distance_m"] == 150.0
        assert config["scan_area"]["width_m"] == 30.0
        assert config["scan_area"]["length_m"] == 100.0
        assert config["targets"]["rotary_wing"]["scoring_radius_m"] == 10.0
        assert config["targets"]["fixed_wing"]["scoring_radius_m"] == 20.0
        assert config["targets"]["rotary_wing"]["target_a"]["shape"] == "regular_hexagon"
        assert config["targets"]["fixed_wing"]["target_a"]["shape"] == "square"


def test_web_gcs_category_toggle(gcs_server):
    # Set to fixed wing
    req = urllib.request.Request(
        "http://127.0.0.1:8899/api/command",
        data=json.dumps({"command": "SET_CATEGORY", "category": "fixed_wing"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "SUCCESS"
        assert res["category"] == "fixed_wing"

    assert gcs_server.category == "fixed_wing"

    # Reset back to rotary wing
    req = urllib.request.Request(
        "http://127.0.0.1:8899/api/command",
        data=json.dumps({"command": "SET_CATEGORY", "category": "rotary_wing"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "SUCCESS"
        assert res["category"] == "rotary_wing"

    assert gcs_server.category == "rotary_wing"


def test_web_gcs_commands(gcs_server):
    commands = [
        "START_MISSION_1",
        "START_MISSION_2",
        "DROP_PAYLOAD_1",
        "DROP_PAYLOAD_2",
        "RTL",
        "DEPLOY_PARACHUTE"
    ]
    for cmd in commands:
        req = urllib.request.Request(
            "http://127.0.0.1:8899/api/command",
            data=json.dumps({"command": cmd}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "SUCCESS"
            assert res["command"] == cmd


def test_web_gcs_official_score_calculators(gcs_server):
    # 1. Test PG1 calculation endpoint
    pg1_req = urllib.request.Request(
        "http://127.0.0.1:8899/api/score/pg1",
        data=json.dumps({
            "c": 1.0,
            "vol_ratio": 1.0,
            "haz_ratio": 1.0,
            "w0_ratio": 1.0,
            "ucus_ratio": 1.0,
            "penalty": 0.0
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pg1_req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["pg1_score"] == 30.0
        assert res["max_score"] == 30.0

    # 2. Test PG2 Fixed-Wing score calculation endpoint
    pg2_f_req = urllib.request.Request(
        "http://127.0.0.1:8899/api/score/pg2_fixed",
        data=json.dumps({
            "c": 1.0,
            "vol_ratio": 1.0,
            "haz_ratio": 1.0,
            "w0_ratio": 1.0,
            "wyuk_ratio": 1.0,
            "d_4x4": 0.05,
            "d_2x2": 0.05,
            "ucus_ratio": 1.0,
            "penalty": 0.0
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pg2_f_req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["pg2_fixed_score"] == 70.0
        assert res["max_score"] == 70.0

    # 3. Test PG2 Rotary-Wing score calculation endpoint
    pg2_r_req = urllib.request.Request(
        "http://127.0.0.1:8899/api/score/pg2_rotary",
        data=json.dumps({
            "c": 1.0,
            "vol_ratio": 1.0,
            "haz_ratio": 1.0,
            "w0_ratio": 1.0,
            "wyuk_ratio": 1.0,
            "d_altg": 0.05,
            "d_ucg": 0.05,
            "ay_bonus": 1,
            "by_bonus": 1,
            "ucus_ratio": 1.0,
            "penalty": 0.0
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pg2_r_req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["pg2_rotary_score"] == 80.0
        assert res["max_score"] == 80.0


def test_web_gcs_export_endpoints(gcs_server):
    # Test GeoJSON export
    with urllib.request.urlopen("http://127.0.0.1:8899/api/export/geojson") as resp:
        assert resp.status == 200
        geo = json.loads(resp.read().decode("utf-8"))
        assert geo["type"] == "FeatureCollection"
        assert len(geo["features"]) >= 2

    # Test CSV export
    with urllib.request.urlopen("http://127.0.0.1:8899/api/export/csv") as resp:
        assert resp.status == 200
        csv_text = resp.read().decode("utf-8")
        assert "timestamp" in csv_text
        assert "alt_agl_m" in csv_text

    # Test Referee Report export
    with urllib.request.urlopen("http://127.0.0.1:8899/api/export/report") as resp:
        assert resp.status == 200
        report = json.loads(resp.read().decode("utf-8"))
        assert report["organization"] == "TÜBİTAK TEKNOFEST 2026"
        assert report["rules_compliance"]["ceiling_under_120m"] is True
        assert report["rules_compliance"]["power_cut_under_2s"] is True


def test_web_gcs_security_and_pylon_endpoints(gcs_server):
    with urllib.request.urlopen("http://127.0.0.1:8899/api/security") as resp:
        assert resp.status == 200
        sec = json.loads(resp.read().decode("utf-8"))
        assert sec["encryption_active"] is True
        assert sec["anomaly_level"] == "NOMINAL"

    with urllib.request.urlopen("http://127.0.0.1:8899/api/pylon_gate") as resp:
        assert resp.status == 200
        pg = json.loads(resp.read().decode("utf-8"))
        assert "compliance_state" in pg
        assert "pole_2_outer_turn_verified" in pg


def test_web_gcs_propulsion_and_attempts_endpoints(gcs_server):
    with urllib.request.urlopen("http://127.0.0.1:8899/api/propulsion") as resp:
        assert resp.status == 200
        prop = json.loads(resp.read().decode("utf-8"))
        assert prop["alert_level"] == "NOMINAL"
        assert "hover_throttle_margin_pct" in prop

    with urllib.request.urlopen("http://127.0.0.1:8899/api/attempts") as resp:
        assert resp.status == 200
        att = json.loads(resp.read().decode("utf-8"))
        assert att["attempts_remaining"] == 4
        assert "tactical_recommendation" in att
