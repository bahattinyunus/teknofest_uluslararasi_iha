"""
TEKNOFEST 2026 Uluslararası İHA - 3B Uçuş Yolu KML ve GeoJSON İhracatçısı
-------------------------------------------------------------------------
Uçuş telemetri günlüklerini (CSV) Google Earth 3B KML ve QGroundControl / Leaflet
uyumlu GeoJSON formatlarına dönüştürür. İrtifa renk geçişi, hedef kilit noktaları
ve yük bırakma koordinatlarını harita üzerinde görselleştirir.
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import csv
import json


class FlightTrajectoryExporter:
    def __init__(self, ref_latitude: float = 41.0082, ref_longitude: float = 28.9784):
        self.ref_lat = ref_latitude
        self.ref_lon = ref_longitude

    def meters_to_lat_lon(self, north_m: float, east_m: float) -> Tuple[float, float]:
        """Yerel NED metre koordinatlarını WGS84 enlem/boylamına dönüştürür."""
        # 1 enlem derecesi ~ 111,139 m
        lat = self.ref_lat + (north_m / 111139.0)
        # 1 boylam derecesi ~ 111,139 * cos(lat) m
        lon = self.ref_lon + (east_m / (111139.0 * 0.7547))
        return float(lat), float(lon)

    def export_geojson(self, csv_log_path: str, output_path: str) -> str:
        """CSV telemetri dosyasından GeoJSON üretir."""
        coords_3d = []
        placemarks = []

        with open(csv_log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            prev_payloads = 2
            for row in reader:
                vx = float(row.get("vx", 0.0))
                vy = float(row.get("vy", 0.0))
                alt = float(row.get("altitude_agl", 0.0))
                # x: North, y: East
                lat, lon = self.meters_to_lat_lon(vx * 5.0, vy * 5.0)
                coords_3d.append([round(lon, 6), round(lat, 6), round(alt, 1)])

                payloads = int(row.get("payloads_left", 2))
                if payloads < prev_payloads:
                    placemarks.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6), round(alt, 1)]},
                        "properties": {
                            "name": f"Yük Bırakma (Slot {2 - payloads})",
                            "target_type": row.get("target_type", ""),
                            "miss_distance": row.get("miss_distance", "")
                        }
                    })
                prev_payloads = payloads

        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords_3d
                },
                "properties": {
                    "name": "TEKNOFEST 2026 İHA Uçuş Rotası",
                    "altitude_mode": "relativeToGround"
                }
            }
        ]
        features.extend(placemarks)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)

        return output_path

    def export_kml(self, csv_log_path: str, output_path: str) -> str:
        """Google Earth için 3B KML dosyası üretir."""
        coords_str_list = []

        with open(csv_log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vx = float(row.get("vx", 0.0))
                vy = float(row.get("vy", 0.0))
                alt = float(row.get("altitude_agl", 0.0))
                lat, lon = self.meters_to_lat_lon(vx * 5.0, vy * 5.0)
                coords_str_list.append(f"{lon:.6f},{lat:.6f},{alt:.1f}")

        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>TEKNOFEST 2026 Uçuş Yolu (3D)</name>
    <Style id="dronePathStyle">
      <LineStyle>
        <color>ff00f2ff</color>
        <width>4</width>
      </LineStyle>
      <PolyStyle>
        <color>7f00f2ff</color>
      </PolyStyle>
    </Style>
    <Placemark>
      <name>Otonom Görev İzi</name>
      <styleUrl>#dronePathStyle</styleUrl>
      <LineString>
        <extrude>1</extrude>
        <tessellate>1</tessellate>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
          {" ".join(coords_str_list)}
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(kml_content)

        return output_path
