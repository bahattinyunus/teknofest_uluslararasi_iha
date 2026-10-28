"""
Unit tests for Flight Trajectory KML & GeoJSON Exporter
"""
import os
import json
import pytest
from src.telemetry.geo_export import FlightTrajectoryExporter


def test_meters_to_lat_lon():
    exporter = FlightTrajectoryExporter(ref_latitude=41.0082, ref_longitude=28.9784)
    lat, lon = exporter.meters_to_lat_lon(100.0, 50.0)

    assert lat > 41.0082
    assert lon > 28.9784


def test_export_geojson_and_kml(tmp_path):
    csv_file = str(tmp_path / "test_geo.csv")
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("timestamp,state,altitude_agl,ground_speed,vx,vy,vz,battery_v,target_locked,target_type,lead_distance,miss_distance,payloads_left\n")
        f.write("1.0,TAKEOFF,10.0,2.0,2.0,1.0,0.0,16.2,0,NONE,0.0,99.0,2\n")
        f.write("2.0,LOCKING_TARGET_A,25.0,4.0,4.0,2.0,0.0,16.0,1,TARGET_A,3.0,1.5,1\n")
        f.write("3.0,LANDED,0.0,0.0,0.0,0.0,0.0,15.8,0,NONE,0.0,99.0,0\n")

    exporter = FlightTrajectoryExporter()
    geojson_out = str(tmp_path / "flight.geojson")
    kml_out = str(tmp_path / "flight.kml")

    exporter.export_geojson(csv_file, geojson_out)
    exporter.export_kml(csv_file, kml_out)

    assert os.path.exists(geojson_out)
    assert os.path.exists(kml_out)

    with open(geojson_out, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 2

    with open(kml_out, "r", encoding="utf-8") as f:
        kml_str = f.read()
        assert "<kml" in kml_str
        assert "<coordinates>" in kml_str
