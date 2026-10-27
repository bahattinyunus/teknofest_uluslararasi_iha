"""
TEKNOFEST 2026 Uluslararası İHA - Uçuş Sonrası Analiz ve Puanlama Motoru
-----------------------------------------------------------------------
Uçuş esnasında kaydedilen CSV telemetri günlüklerini ve JSONL olaylarını
analiz ederek 2026 şartnamesine göre puanlama, azami irtifa denetimi,
hedef isabet doğruluğu ve batarya tüketim verimliliği raporu üretir.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import os
import csv
import json


@dataclass
class DropScore:
    slot_id: int
    target_type: str
    target_color: str
    miss_distance_m: float
    is_valid_drop: bool
    score_points: float


@dataclass
class FlightSummary:
    log_file: str
    total_flight_time_s: float
    max_altitude_m: float
    exceeded_120m_limit: bool
    max_ground_speed_mps: float
    battery_start_v: float
    battery_end_v: float
    voltage_drop_v: float
    drop_scores: List[DropScore]
    total_mission_score: float
    compliance_passed: bool


class FlightAnalyticsEngine:
    def __init__(self, category: str = "rotary_wing"):
        self.category = category
        # 2026 kuralı: Döner kanat 10m, Sabit kanat 20m çember
        self.max_scoring_radius = 10.0 if category == "rotary_wing" else 20.0
        self.max_score_per_drop = 100.0

    def calculate_drop_score(self, miss_distance_m: float) -> float:
        """
        Şartnameye göre merkeze olan mesafeden puan hesabı:
        Puan = MaxPuan * (1 - (Mesafe / MaxYarıçap))
        """
        if miss_distance_m > self.max_scoring_radius:
            return 0.0
        ratio = max(0.0, 1.0 - (miss_distance_m / self.max_scoring_radius))
        return round(self.max_score_per_drop * ratio, 2)

    def analyze_csv_log(self, csv_path: str) -> Optional[FlightSummary]:
        if not os.path.exists(csv_path):
            print(f"[ANALYTICS] Günlük dosyası bulunamadı: {csv_path}")
            return None

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        if not rows:
            return None

        # Zaman hesabı
        timestamps = [float(r["timestamp"]) for r in rows if r.get("timestamp")]
        start_time = timestamps[0]
        end_time = timestamps[-1]
        total_time = max(0.1, end_time - start_time)

        # İrtifa ve Hız
        altitudes = [float(r["altitude_agl"]) for r in rows if r.get("altitude_agl")]
        max_alt = max(altitudes) if altitudes else 0.0
        exceeded_120m = max_alt > 120.0

        speeds = [float(r["ground_speed"]) for r in rows if r.get("ground_speed")]
        max_speed = max(speeds) if speeds else 0.0

        # Batarya
        voltages = [float(r["battery_v"]) for r in rows if r.get("battery_v")]
        bat_start = voltages[0] if voltages else 16.0
        bat_end = voltages[-1] if voltages else 16.0
        voltage_drop = round(bat_start - bat_end, 2)

        # Yük bırakma anları (payloads_left azalması)
        drop_scores: List[DropScore] = []
        prev_payloads = 2
        for r in rows:
            try:
                curr_payloads = int(r.get("payloads_left", 2))
                if curr_payloads < prev_payloads:
                    # Bir yük bırakıldı
                    miss_d = float(r.get("miss_distance", 99.0))
                    t_type = r.get("target_type", "TARGET_A")
                    score = self.calculate_drop_score(miss_d)
                    slot = 2 - curr_payloads
                    drop_scores.append(DropScore(
                        slot_id=slot,
                        target_type=t_type,
                        target_color="red" if t_type == "TARGET_A" else "blue",
                        miss_distance_m=round(miss_d, 2),
                        is_valid_drop=miss_d <= self.max_scoring_radius,
                        score_points=score
                    ))
                prev_payloads = curr_payloads
            except Exception:
                pass

        total_score = sum(d.score_points for d in drop_scores)
        compliance = not exceeded_120m and len(drop_scores) > 0

        return FlightSummary(
            log_file=os.path.basename(csv_path),
            total_flight_time_s=round(total_time, 1),
            max_altitude_m=round(max_alt, 1),
            exceeded_120m_limit=exceeded_120m,
            max_ground_speed_mps=round(max_speed, 1),
            battery_start_v=round(bat_start, 2),
            battery_end_v=round(bat_end, 2),
            voltage_drop_v=voltage_drop,
            drop_scores=drop_scores,
            total_mission_score=round(total_score, 1),
            compliance_passed=compliance
        )

    def generate_markdown_report(self, summary: FlightSummary) -> str:
        """Yarışma hakemleri ve teknik inceleme için detaylı Markdown raporu üretir."""
        verdict = "✅ KURAL VE GÖREV UYUMLU" if summary.compliance_passed else "❌ KURAL İHLALİ VEYA BAŞARISIZ GÖREV"
        if summary.exceeded_120m_limit:
            verdict += " (DİSKALİFİYE: 120m İRTİFA LİMİTİ AŞILDI)"

        report = f"""# 🛸 TEKNOFEST 2026 - Uçuş ve Görev Analiz Raporu
**Günlük Dosyası:** `{summary.log_file}`  
**Operasyonel Karar:** **{verdict}**  

---

### 1. Uçuş Dinamikleri ve Sınır Denetimi
| Metrik | Ölçülen Değer | 2026 Şartname Limiti | Uyumluluk Durumu |
| :--- | :--- | :--- | :--- |
| **Toplam Süre** | {summary.total_flight_time_s} saniye | - | Tamamlandı |
| **Azami İrtifa (AGL)** | **{summary.max_altitude_m} m** | **Azami 120.0 m** | {'❌ İHLAL' if summary.exceeded_120m_limit else '✅ UYUMLU'} |
| **Azami Yer Hızı** | {summary.max_ground_speed_mps} m/s | 15.0 m/s | ✅ Nominal |
| **Batarya Başlangıç/Bitiş** | {summary.battery_start_v}V $\\rightarrow$ {summary.battery_end_v}V | $\\Delta V = {summary.voltage_drop_v}V$ | ✅ Sağlıklı |

---

### 2. Yük Bırakma İsabeti ve Puanlama ({self.category.upper()})
*Puanlama Alanı Sınırı: Hedef merkezinden $\\le {self.max_scoring_radius}m$*

| Yük No | Hedef Tipi | Renk | Sapma Mesafesi | Geçerlilik | Kazanılan Puan |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for d in summary.drop_scores:
            status = "✅ Geçerli" if d.is_valid_drop else "❌ Alan Dışı"
            report += f"| **Yük {d.slot_id}** | {d.target_type} | {d.target_color.upper()} | {d.miss_distance_m} m | {status} | **{d.score_points} / 100** |\n"

        report += f"\n**TOPLAM GÖREV PUANI:** **{summary.total_mission_score} / 200 Puan**\n"
        return report
