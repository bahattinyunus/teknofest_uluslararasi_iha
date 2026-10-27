"""
Unit tests for Web Ground Control Station (Web GCS) Subsystem
"""
import urllib.request
import json
import pytest
from src.web_gcs.server import WebGCSServer


def test_web_gcs_endpoints():
    server = WebGCSServer(host="127.0.0.1", port=8888, core_instance=None)
    server.start_background()

    try:
        # Test GET /
        with urllib.request.urlopen("http://127.0.0.1:8888/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "UAV-ARCHITECT-GLOBAL" in html
            assert "radarCanvas" in html

        # Test GET /api/telemetry
        with urllib.request.urlopen("http://127.0.0.1:8888/api/telemetry") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert isinstance(data, dict)

        # Test POST /api/command
        req = urllib.request.Request(
            "http://127.0.0.1:8888/api/command",
            data=json.dumps({"command": "RTL"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "SUCCESS"
            assert res["command"] == "RTL"
    finally:
        server.stop()
