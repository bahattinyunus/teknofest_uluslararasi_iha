"""
TEKNOFEST 2026 Uluslararası İHA - Kara Kutu Tekrar Oynatma ve Regresyon Denetleyicisi
=====================================================================================
Kaydedilmiş CSV uçuş telemetri günlüklerini deterministik olarak adım adım tekrar
oynatarak:
  - 120m AGL tavan irtifa ihlallerini (§8.3.1),
  - Kritik batarya voltaj düşüşlerini (<14.0V),
  - Aşırı hız veya ani dikey düşüş (kırım) anomalilerini,
  - Yük bırakma olaylarının tutarlılığını
denetler ve JSON/Markdown regresyon raporu üretir.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class ReplayAnomaly:
    """Tekrar oynatma sırasında tespit edilen uçuş kuralı veya güvenlik anomalisi."""
    row_index: int
    timestamp: float
    code: str
    severity: str                     # "WARNING" | "CRITICAL"
    message: str


@dataclass
class ReplayAuditResult:
    """Kara kutu tekrar oynatma ve regresyon denetim özeti."""
    source_path: str
    total_rows: int
    duration_s: float
    max_altitude_agl_m: float
    min_battery_v: float
    max_ground_speed_mps: float
    payloads_released: int
    passed_regression: bool
    critical_count: int
    warning_count: int
    anomalies: List[ReplayAnomaly] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class FlightTelemetryReplayer:
    """
    CSV Kara Kutu Telemetri Tekrar Oynatma ve Güvenlik Regresyon Motoru.
    """

    def __init__(
        self,
        max_altitude_agl_m: float = 120.0,
        critical_battery_v: float = 14.0,
        warning_battery_v: float = 14.8,
        max_ground_speed_mps: float = 28.0,
        max_descent_rate_mps: float = 8.0,
    ):
        self.max_altitude_agl_m = float(max_altitude_agl_m)
        self.critical_battery_v = float(critical_battery_v)
        self.warning_battery_v = float(warning_battery_v)
        self.max_ground_speed_mps = float(max_ground_speed_mps)
        self.max_descent_rate_mps = float(max_descent_rate_mps)

    @staticmethod
    def _safe_float(row: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
        for k in keys:
            if k in row and row[k] not in ("", None):
                try:
                    return float(row[k])
                except (ValueError, TypeError):
                    pass
        return default

    def replay_rows(self, rows: List[Dict[str, Any]], source_name: str = "in_memory") -> ReplayAuditResult:
        """Bellekteki telemetri satır listesini regresyon kurallarıyla denetler."""
        anomalies: List[ReplayAnomaly] = []
        max_alt = 0.0
        min_batt = 99.0
        max_spd = 0.0
        first_ts: Optional[float] = None
        last_ts: float = 0.0
        prev_payloads: Optional[int] = None
        payloads_released = 0

        for idx, row in enumerate(rows):
            ts = self._safe_float(row, ["timestamp", "time_s", "t"], float(idx) * 0.1)
            if first_ts is None:
                first_ts = ts
            last_ts = ts

            alt = self._safe_float(row, ["altitude_agl", "alt_agl_m", "altitude"], 0.0)
            spd = self._safe_float(row, ["ground_speed", "ground_speed_mps", "speed"], 0.0)
            vz = self._safe_float(row, ["vz", "vz_mps"], 0.0)
            batt = self._safe_float(row, ["battery_v", "voltage_v"], 16.0)
            pl = int(self._safe_float(row, ["payloads_left", "payloads_remaining"], 2.0))

            max_alt = max(max_alt, alt)
            max_spd = max(max_spd, spd)
            min_batt = min(min_batt, batt)

            if prev_payloads is not None and pl < prev_payloads:
                payloads_released += (prev_payloads - pl)
            prev_payloads = pl

            if alt > self.max_altitude_agl_m:
                anomalies.append(ReplayAnomaly(
                    idx, ts, "CEILING_BREACH", "CRITICAL",
                    f"120m AGL tavan irtifa ihlali: {alt:.1f}m (§8.3.1)"
                ))
            if batt < self.critical_battery_v:
                anomalies.append(ReplayAnomaly(
                    idx, ts, "BATTERY_CRITICAL", "CRITICAL",
                    f"Kritik batarya voltajı: {batt:.2f}V (< {self.critical_battery_v:.1f}V)"
                ))
            elif batt < self.warning_battery_v:
                anomalies.append(ReplayAnomaly(
                    idx, ts, "BATTERY_WARNING", "WARNING",
                    f"Düşük batarya uyarısı: {batt:.2f}V"
                ))
            if spd > self.max_ground_speed_mps:
                anomalies.append(ReplayAnomaly(
                    idx, ts, "OVERSPEED", "WARNING",
                    f"Azami yer hızı aşıldı: {spd:.1f} m/s"
                ))
            if vz > self.max_descent_rate_mps:
                anomalies.append(ReplayAnomaly(
                    idx, ts, "EXCESSIVE_DESCENT", "CRITICAL",
                    f"Kontrolsüz düşüş hızı tespit edildi: vz={vz:.1f} m/s"
                ))

        duration = max(0.0, (last_ts - first_ts)) if first_ts is not None else 0.0
        crit_cnt = sum(1 for a in anomalies if a.severity == "CRITICAL")
        warn_cnt = sum(1 for a in anomalies if a.severity == "WARNING")
        if min_batt == 99.0:
            min_batt = 0.0

        return ReplayAuditResult(
            source_path=source_name,
            total_rows=len(rows),
            duration_s=round(duration, 2),
            max_altitude_agl_m=round(max_alt, 2),
            min_battery_v=round(min_batt, 2),
            max_ground_speed_mps=round(max_spd, 2),
            payloads_released=payloads_released,
            passed_regression=(crit_cnt == 0),
            critical_count=crit_cnt,
            warning_count=warn_cnt,
            anomalies=anomalies,
        )

    def replay_csv(self, csv_path: str) -> ReplayAuditResult:
        """Disk üzerindeki CSV telemetri dosyasını okuyup regresyon denetiminden geçirir."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Telemetri dosyası bulunamadı: {csv_path}")
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return self.replay_rows(rows, source_name=csv_path)
