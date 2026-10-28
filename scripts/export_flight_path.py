"""
TEKNOFEST 2026 - 3B Uçuş Yolu Dışa Aktarıcı (KML & GeoJSON)
===========================================================
Uçuş telemetri loglarını Google Earth (KML) ve QGroundControl (GeoJSON)
harita dosyalarına dönüştürür.
"""

import sys
import os
import glob
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.telemetry.geo_export import FlightTrajectoryExporter


def main():
    parser = argparse.ArgumentParser(description="Uçuş Yolu KML/GeoJSON İhracatçısı")
    parser.add_argument("--log", help="CSV log dosyası yolu (varsayılan: en son)")
    parser.add_argument("--format", choices=["kml", "geojson", "both"], default="both")
    args = parser.parse_args()

    log_path = args.log
    if not log_path:
        csv_files = glob.glob(os.path.join("logs", "*.csv"))
        if not csv_files:
            print("[ERROR] 'logs/' dizininde CSV dosyası bulunamadı.")
            return
        log_path = max(csv_files, key=os.path.getctime)

    print(f"🗺️ Uçuş Yolu Haritası Çıkarılıyor: {log_path}")
    exporter = FlightTrajectoryExporter()
    base_name = os.path.splitext(log_path)[0]

    if args.format in ("kml", "both"):
        kml_out = base_name + ".kml"
        exporter.export_kml(log_path, kml_out)
        print(f"✅ Google Earth 3B KML Dosyası: {kml_out}")

    if args.format in ("geojson", "both"):
        geojson_out = base_name + ".geojson"
        exporter.export_geojson(log_path, geojson_out)
        print(f"✅ QGroundControl / Leaflet GeoJSON Dosyası: {geojson_out}")


if __name__ == "__main__":
    main()
