"""
TEKNOFEST 2026 Uluslararası İHA - İtki, ESC Termal ve Titreşim Sağlık İzleyici
===============================================================================
Malatya Tulga Havalimanı (938m MSL, Eylül ayı 30-38°C saha sıcaklığı) yüksek
yoğunluk irtifasında (density altitude ~1600-1900m) motor/ESC aşırı ısınmasını,
itki marjı kaybını, pervane balanssızlığını ve tek motor arızasını uçuş sırasında
erken tespit eden aviyonik sağlık modülü.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PropulsionAlertLevel(Enum):
    NOMINAL = "NOMINAL"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class PropulsionSnapshot:
    """Anlık motor/ESC ve titreşim telemetri ölçümü."""
    motor_rpms: List[float]
    esc_temps_c: List[float]
    throttle_pct: float
    air_density_kgpm3: float = 1.06
    vibration_rms_mps2: float = 1.2
    bus_current_a: float = 18.0
    timestamp: float = 0.0


@dataclass
class PropulsionHealthReport:
    """İtki sistemi sağlık, termal derating ve titreşim analiz raporu."""
    alert_level: PropulsionAlertLevel
    density_thrust_ratio: float           # sigma = rho / 1.225
    hover_throttle_margin_pct: float      # Kalan itki marjı (%)
    max_esc_temp_c: float
    thermal_derating_factor: float        # 1.0 = tam güç, <1.0 = termal kısıtlama
    rpm_asymmetry_pct: float              # Motorlar arası maksimum RPM sapması (%)
    vibration_rms_mps2: float
    suspected_fault_motor_idx: Optional[int]
    diagnostics: List[str] = field(default_factory=list)


class PropulsionHealthMonitor:
    """
    Yoğunluk irtifası itki kaybı, ESC termal koruma, RPM simetri ve
    IMU titreşim RMS tabanlı pervane/motor sağlık izleyicisi.
    """

    ISA_SEA_LEVEL_DENSITY = 1.225

    def __init__(
        self,
        esc_caution_c: float = 70.0,
        esc_warning_c: float = 85.0,
        esc_critical_c: float = 95.0,
        vib_warning_mps2: float = 15.0,
        vib_critical_mps2: float = 28.0,
        rpm_asymmetry_warn_pct: float = 12.0,
        rpm_asymmetry_crit_pct: float = 25.0,
    ):
        self.esc_caution_c = esc_caution_c
        self.esc_warning_c = esc_warning_c
        self.esc_critical_c = esc_critical_c
        self.vib_warning_mps2 = vib_warning_mps2
        self.vib_critical_mps2 = vib_critical_mps2
        self.rpm_asymmetry_warn_pct = rpm_asymmetry_warn_pct
        self.rpm_asymmetry_crit_pct = rpm_asymmetry_crit_pct
        self.latest_report: Optional[PropulsionHealthReport] = None

    def evaluate(self, snap: PropulsionSnapshot) -> PropulsionHealthReport:
        diagnostics: List[str] = []
        severity = 0  # 0=NOMINAL, 1=CAUTION, 2=WARNING, 3=CRITICAL

        # 1. Yoğunluk irtifası itki oranı (sigma = rho / rho_0)
        sigma = max(0.5, min(1.15, snap.air_density_kgpm3 / self.ISA_SEA_LEVEL_DENSITY))
        effective_max_throttle = 100.0 * sigma
        hover_margin = max(0.0, effective_max_throttle - snap.throttle_pct)

        if hover_margin < 15.0:
            severity = max(severity, 3)
            diagnostics.append(
                f"KRİTİK İTKİ MARJI: Yoğunluk irtifası (sigma={sigma:.2f}) nedeniyle kalan marj %{hover_margin:.1f}!"
            )
        elif hover_margin < 25.0:
            severity = max(severity, 1)
            diagnostics.append(f"Düşük itki marjı (%{hover_margin:.1f}, sigma={sigma:.2f}).")

        # 2. ESC Sıcaklık & Termal Derating
        max_temp = max(snap.esc_temps_c) if snap.esc_temps_c else 25.0
        if max_temp >= self.esc_critical_c:
            thermal_derating = 0.65
            severity = max(severity, 3)
            diagnostics.append(f"KRİTİK ESC AŞIRI ISINMA: {max_temp:.1f}°C (>= {self.esc_critical_c:.0f}°C)!")
        elif max_temp >= self.esc_warning_c:
            thermal_derating = 0.82
            severity = max(severity, 2)
            diagnostics.append(f"UYARI: ESC sıcaklığı yüksek ({max_temp:.1f}°C), termal güç kısıtlaması aktif.")
        elif max_temp >= self.esc_caution_c:
            thermal_derating = 0.94
            severity = max(severity, 1)
            diagnostics.append(f"DİKKAT: ESC sıcaklığı yükseliyor ({max_temp:.1f}°C).")
        else:
            thermal_derating = 1.0

        # 3. Çoklu Motor RPM Simetrisi & Tek Motor Arıza Tespiti
        rpm_asymmetry_pct = 0.0
        fault_idx: Optional[int] = None
        if len(snap.motor_rpms) >= 2:
            mean_rpm = sum(snap.motor_rpms) / len(snap.motor_rpms)
            if mean_rpm > 500.0:
                deviations = [abs(r - mean_rpm) / mean_rpm * 100.0 for r in snap.motor_rpms]
                rpm_asymmetry_pct = max(deviations)
                worst_idx = deviations.index(rpm_asymmetry_pct)
                if rpm_asymmetry_pct >= self.rpm_asymmetry_crit_pct:
                    severity = max(severity, 3)
                    fault_idx = worst_idx
                    diagnostics.append(
                        f"KRİTİK MOTOR ASİMETRİSİ: Motor #{worst_idx + 1} sapması %{rpm_asymmetry_pct:.1f}!"
                    )
                elif rpm_asymmetry_pct >= self.rpm_asymmetry_warn_pct:
                    severity = max(severity, 2)
                    fault_idx = worst_idx
                    diagnostics.append(
                        f"UYARI: Motor #{worst_idx + 1} RPM sapması %{rpm_asymmetry_pct:.1f} (pervane/ESC kontrolü)."
                    )

        # 4. IMU Titreşim RMS Analizi
        if snap.vibration_rms_mps2 >= self.vib_critical_mps2:
            severity = max(severity, 3)
            diagnostics.append(
                f"KRİTİK TİTREŞİM: {snap.vibration_rms_mps2:.1f} m/s² (pervane kırığı/gevşek motor şüphesi)!"
            )
        elif snap.vibration_rms_mps2 >= self.vib_warning_mps2:
            severity = max(severity, 2)
            diagnostics.append(
                f"UYARI: Yüksek gövde titreşimi ({snap.vibration_rms_mps2:.1f} m/s²), EKF sapma riski."
            )

        if not diagnostics:
            diagnostics.append("İtki, ESC termal ve titreşim parametreleri nominal.")

        level_map = {
            0: PropulsionAlertLevel.NOMINAL,
            1: PropulsionAlertLevel.CAUTION,
            2: PropulsionAlertLevel.WARNING,
            3: PropulsionAlertLevel.CRITICAL,
        }
        report = PropulsionHealthReport(
            alert_level=level_map[severity],
            density_thrust_ratio=round(sigma, 4),
            hover_throttle_margin_pct=round(hover_margin, 2),
            max_esc_temp_c=round(max_temp, 2),
            thermal_derating_factor=round(thermal_derating, 3),
            rpm_asymmetry_pct=round(rpm_asymmetry_pct, 2),
            vibration_rms_mps2=round(snap.vibration_rms_mps2, 2),
            suspected_fault_motor_idx=fault_idx,
            diagnostics=diagnostics,
        )
        self.latest_report = report
        return report
