"""
TEKNOFEST 2026 Uluslararası İHA - Uçuş ve Görev Telemetri Kaydedici
-------------------------------------------------------------------
Uçuş sırasındaki tüm telemetri parametrelerini, hedef tespitlerini,
balistik bırakma kararlarını ve sistem sağlığını CSV ve JSON formatında
zaman damgalı olarak diske kaydeder.
"""

from typing import Dict, Any, Optional
import os
import json
import csv
import time
from datetime import datetime


class MissionLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(log_dir, f"flight_telemetry_{timestamp_str}.csv")
        self.events_path = os.path.join(log_dir, f"mission_events_{timestamp_str}.jsonl")

        self.csv_file = open(self.csv_path, mode="w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        # Başlık satırı
        self.csv_writer.writerow([
            "timestamp", "state", "altitude_agl", "ground_speed",
            "vx", "vy", "vz", "battery_v", "target_locked",
            "target_type", "lead_distance", "miss_distance", "payloads_left"
        ])
        self.csv_file.flush()

        self.events_file = open(self.events_path, mode="a", encoding="utf-8")
        print(f"[LOGGER] Telemetri günlükleri başlatıldı: {self.csv_path}")

    def log_telemetry_row(
        self,
        state: str,
        altitude_agl: float,
        ground_speed: float,
        vx: float,
        vy: float,
        vz: float,
        battery_v: float,
        target_locked: bool,
        target_type: str,
        lead_dist: float,
        miss_dist: float,
        payloads_left: int
    ):
        now = round(time.time(), 3)
        self.csv_writer.writerow([
            now, state, round(altitude_agl, 2), round(ground_speed, 2),
            round(vx, 2), round(vy, 2), round(vz, 2), round(battery_v, 2),
            int(target_locked), target_type, round(lead_dist, 2),
            round(miss_dist, 2), payloads_left
        ])
        self.csv_file.flush()

    def log_event(self, event_name: str, details: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "event": event_name,
            "details": details
        }
        self.events_file.write(json.dumps(entry) + "\n")
        self.events_file.flush()

    def close(self):
        try:
            self.csv_file.close()
            self.events_file.close()
        except Exception:
            pass
