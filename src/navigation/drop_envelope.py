"""
TEKNOFEST 2026 Uluslararası İHA - İstatiksel Balistik Bırakma Zarfı ve Güven Motoru
----------------------------------------------------------------------------------
Rüzgar türbülansı, İHA hız gürültüsü, irtifa ölçüm belirsizliği ve servo gecikme
jitter'ını birleştirerek yerde 2B hata elipsi (Covariance Dispersion Ellipse) oluşturur.
Hedef çemberi içine düşme olasılığını (Hit Probability P_hit) hesaplar ve
yalnızca istatistiksel güven sağlandığında bırakma onayı verir.
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional
import math
import numpy as np


@dataclass
class DropEnvelopeStatus:
    predicted_impact_xy: Tuple[float, float]
    miss_distance_m: float
    sigma_major_m: float        # Ana hata ekseni yarıçapı (1-sigma)
    sigma_minor_m: float        # İkincil hata ekseni yarıçapı (1-sigma)
    hit_probability_pct: float  # Hedef çemberine düşme olasılığı (%)
    is_authorized: bool         # Bırakma yetkisi verildi mi?
    recommendation: str         # "RELEASE_AUTHORIZED", "HOLD_APPROACH", "ABORT_GO_AROUND"


class DropEnvelopeCalculator:
    def __init__(
        self,
        scoring_radius_m: float = 10.0,
        min_probability_threshold_pct: float = 80.0,
        sigma_velocity_mps: float = 0.35,
        sigma_altitude_m: float = 0.50,
        sigma_wind_mps: float = 0.80,
        servo_delay_s: float = 0.08
    ):
        self.scoring_radius = scoring_radius_m
        self.prob_threshold = min_probability_threshold_pct
        self.sigma_v = sigma_velocity_mps
        self.sigma_h = sigma_altitude_m
        self.sigma_w = sigma_wind_mps
        self.servo_delay = servo_delay_s

    def calculate_dispersion(
        self,
        time_of_flight_s: float,
        ground_speed_mps: float,
        altitude_m: float
    ) -> Tuple[float, float]:
        """
        Serbest düşüş süresi ve uçuş dinamiklerine göre yerdeki 1-sigma saçılma yarıçaplarını hesaplar.
        """
        tof = max(0.1, time_of_flight_s)

        # Uçuş süresi belirsizliği (irtifa hatasından kaynaklı): dt = dh / sqrt(2*g*h)
        g = 9.80665
        sigma_tof = (self.sigma_h / math.sqrt(max(0.1, 2.0 * g * altitude_m)))

        # İleri eksen saçılması (Sigma X: Hız hatası + Servo gecikmesi + Süre hatası + Rüzgar)
        var_x = (
            (tof * self.sigma_v)**2 +
            (ground_speed_mps * (sigma_tof + self.servo_delay))**2 +
            (tof * self.sigma_w)**2
        )
        sigma_x = math.sqrt(max(0.01, var_x))

        # Yan eksen saçılması (Sigma Y: Yan hız hatası + Yan rüzgar türbülansı)
        var_y = (tof * (self.sigma_v * 0.7))**2 + (tof * self.sigma_w)**2
        sigma_y = math.sqrt(max(0.01, var_y))

        major = max(sigma_x, sigma_y)
        minor = min(sigma_x, sigma_y)
        return float(major), float(minor)

    def calculate_hit_probability(
        self,
        miss_distance_m: float,
        sigma_avg_m: float,
        target_radius_m: float
    ) -> float:
        """
        Dairesel hedef çemberi için 2B Gauss dağılımı üzerinden
        isabet olasılığını hesaplar (Genelleştirilmiş Rayleigh / Rice dağılımı integrali).
        """
        r = max(0.5, target_radius_m)
        s = max(0.2, sigma_avg_m)
        d = miss_distance_m

        # d = 0 için kapalı formül: P = 1 - exp(-r^2 / (2*s^2))
        if d < 0.1:
            prob = 1.0 - math.exp(-(r**2) / (2.0 * (s**2)))
            return float(min(100.0, max(0.0, prob * 100.0)))

        # Ofsetli hedef için Marcum-Q yaklaşımı (1. mertebe seri açılımı)
        # P ≈ exp(-d^2 / (2*s^2)) * (1 - exp(-r^2 / (2*s^2))) * I0(d*r / s^2)
        base_decay = math.exp(-(d**2) / (2.0 * (s**2)))
        circle_factor = 1.0 - math.exp(-(r**2) / (2.0 * (s**2)))

        # Bessel I0(z) yaklaşımı: z = d*r / s^2
        z = (d * r) / (s**2)
        if z < 3.5:
            i0 = 1.0 + (z**2) / 4.0 + (z**4) / 64.0
        else:
            i0 = math.exp(z) / math.sqrt(max(0.1, 2.0 * math.pi * z))

        prob = min(0.999, base_decay * circle_factor * i0)
        return float(min(100.0, max(0.0, prob * 100.0)))

    def evaluate_envelope(
        self,
        impact_xy: Tuple[float, float],
        target_xy: Tuple[float, float],
        time_of_flight_s: float,
        ground_speed_mps: float,
        altitude_m: float
    ) -> DropEnvelopeStatus:
        """
        Anlık bırakma penceresini değerlendirir ve karar üretir.
        """
        dx = impact_xy[0] - target_xy[0]
        dy = impact_xy[1] - target_xy[1]
        miss_distance = math.hypot(dx, dy)

        sigma_maj, sigma_min = self.calculate_dispersion(
            time_of_flight_s=time_of_flight_s,
            ground_speed_mps=ground_speed_mps,
            altitude_m=altitude_m
        )
        sigma_avg = (sigma_maj + sigma_min) / 2.0

        p_hit = self.calculate_hit_probability(
            miss_distance_m=miss_distance,
            sigma_avg_m=sigma_avg,
            target_radius_m=self.scoring_radius
        )

        # Karar mantığı
        is_auth = False
        recommendation = "HOLD_APPROACH"

        if p_hit >= self.prob_threshold and miss_distance <= (self.scoring_radius * 0.4):
            is_auth = True
            recommendation = "RELEASE_AUTHORIZED"
        elif miss_distance > (self.scoring_radius * 1.5):
            recommendation = "ABORT_GO_AROUND"
        else:
            recommendation = "HOLD_APPROACH"

        return DropEnvelopeStatus(
            predicted_impact_xy=(round(impact_xy[0], 2), round(impact_xy[1], 2)),
            miss_distance_m=round(miss_distance, 2),
            sigma_major_m=round(sigma_maj, 2),
            sigma_minor_m=round(sigma_min, 2),
            hit_probability_pct=round(p_hit, 1),
            is_authorized=is_auth,
            recommendation=recommendation
        )
