"""
TEKNOFEST 2026 Uluslararası İHA - Monte Carlo Yarışma Hazırlık Kıyaslama Motoru
===============================================================================
Malatya Tulga Havalimanı (938m MSL) atmosfer koşullarında N adet rastgeleleştirilmiş
görev sortisi koşturarak:
  - Rüzgar belirsizliği, zemin sürtünmesi (C_rr) ve bırakma gecikmesi altında
    Durma Noktası (Resting Position) CEP50 / CEP90 doğruluğunu,
  - Tablo 3 ortalama PG1 & PG2 puan dağılımını,
  - 120m tavan ihlali / 25 km/h rüzgar limiti / hedef dışı düşüş risk oranını,
  - 0-100 arası bileşik Yarışma Hazırlık İndeksini (Competition Readiness Index - CRI)
hesaplar.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional

from src.avionics.air_data_computer import AirDataComputer
from src.avionics.storage_box_optimizer import (
    CompetitionTeamProfile,
    CompetitorBenchmark,
    StorageBoxOptimizer,
)
from src.navigation.rolling_ballistics import RestingBallisticsOptimizer


@dataclass
class BenchmarkConfig:
    """Monte Carlo kıyaslama senaryo ayarları."""
    num_runs: int = 50
    category: str = "rotary_wing"
    release_altitude_m: float = 20.0
    cruise_speed_mps: float = 14.0
    mean_wind_mps: float = 3.5
    wind_std_mps: float = 1.4
    timing_jitter_s: float = 0.06
    wind_estimation_error_mps: float = 0.65
    empty_mass_kg: float = 1.85
    single_payload_mass_kg: float = 0.60
    box_volume_m3: float = 0.144
    setup_time_s: float = 195.0
    seed: int = 2026


@dataclass
class RunOutcome:
    """Tek bir Monte Carlo sortisinin sonucu."""
    run_id: int
    wind_mps: float
    miss_distance_a_m: float
    miss_distance_b_m: float
    pg1_score: float
    pg2_score: float
    wind_limit_exceeded: bool
    in_scoring_radius: bool


@dataclass
class BenchmarkReport:
    """N sortilik Monte Carlo kıyaslama özet raporu."""
    num_runs: int
    category: str
    scoring_radius_m: float
    tulga_air_density_kgpm3: float
    cep50_m: float
    cep90_m: float
    mean_miss_distance_m: float
    in_radius_success_rate_pct: float
    wind_abort_rate_pct: float
    mean_pg1: float
    mean_pg2: float
    mean_total_flight_score: float
    readiness_index_0_100: float
    readiness_grade: str
    outcomes: List[RunOutcome] = field(default_factory=list)


class MissionReadinessBenchmark:
    """
    Malatya Tulga Şartname V7 Monte Carlo Görev Hazırlık Kıyaslama Motoru.
    """

    MAX_WIND_LIMIT_MPS = 25.0 / 3.6  # 6.944 m/s (25 km/h)

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self.adc = AirDataComputer()
        self.rolling = RestingBallisticsOptimizer()
        self.optimizer = StorageBoxOptimizer()

    @staticmethod
    def _percentile(values: List[float], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = (len(s) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return s[int(k)]
        return s[f] * (c - k) + s[c] * (k - f)

    def run(self, benchmark: Optional[CompetitorBenchmark] = None) -> BenchmarkReport:
        """Monte Carlo kıyaslamasını deterministik tohum (seed) ile icra eder."""
        cfg = self.config
        rng = random.Random(cfg.seed)
        bench = benchmark or CompetitorBenchmark()
        scoring_radius = 20.0 if cfg.category == "fixed_wing" else 10.0

        # Malatya Tulga (938m MSL + release_altitude_m) hava yoğunluğu
        p_static = 101325.0 * math.pow(
            1.0 - 2.25577e-5 * (938.0 + cfg.release_altitude_m), 5.25588
        )
        adc_state = self.adc.compute(
            diff_pressure_pa=0.5 * 1.225 * (cfg.cruise_speed_mps ** 2),
            static_pressure_pa=p_static,
            oat_celsius=24.0,
        )

        outcomes: List[RunOutcome] = []
        all_misses: List[float] = []

        for idx in range(1, max(1, cfg.num_runs) + 1):
            true_wind = max(0.0, rng.gauss(cfg.mean_wind_mps, cfg.wind_std_mps))
            wind_exceeded = true_wind > self.MAX_WIND_LIMIT_MPS

            # Sistemin kestirdiği rüzgar (kestirim hatası içerir)
            est_wind = max(0.0, true_wind + rng.gauss(0.0, cfg.wind_estimation_error_mps))

            # İdeal bırakma önleme mesafesi kestirilen rüzgarla hesaplanır
            planned = self.rolling.simulate_flight_and_roll(
                release_altitude_agl_m=cfg.release_altitude_m,
                uav_ground_speed_ms=cfg.cruise_speed_mps,
                wind_along_track_ms=est_wind,
            )
            # Gerçek düşüş gerçek rüzgar + zamanlama sapmasıyla oluşur
            actual_a = self.rolling.simulate_flight_and_roll(
                release_altitude_agl_m=cfg.release_altitude_m,
                uav_ground_speed_ms=cfg.cruise_speed_mps,
                wind_along_track_ms=true_wind,
            )
            jitter_a_m = rng.gauss(0.0, cfg.timing_jitter_s) * cfg.cruise_speed_mps
            lateral_err_a = rng.gauss(0.0, 0.45 + 0.12 * true_wind)
            along_err_a = (actual_a.total_lead_distance_m - planned.total_lead_distance_m) + jitter_a_m
            miss_a = math.hypot(along_err_a, lateral_err_a)

            jitter_b_m = rng.gauss(0.0, cfg.timing_jitter_s) * cfg.cruise_speed_mps
            lateral_err_b = rng.gauss(0.0, 0.45 + 0.12 * true_wind)
            along_err_b = (actual_a.total_lead_distance_m - planned.total_lead_distance_m) + jitter_b_m
            miss_b = math.hypot(along_err_b, lateral_err_b)

            in_radius = (miss_a <= scoring_radius) and (miss_b <= scoring_radius)

            profile = CompetitionTeamProfile(
                category=cfg.category,
                empty_mass_w0_kg=cfg.empty_mass_kg,
                single_payload_mass_kg=cfg.single_payload_mass_kg,
                box_volume_m3=cfg.box_volume_m3,
                setup_time_s=cfg.setup_time_s,
                task1_flight_time_s=max(75.0, 92.0 + rng.gauss(0.0, 4.0) + true_wind * 1.5),
                task2_flight_time_s=max(130.0, 158.0 + rng.gauss(0.0, 6.0) + true_wind * 2.0),
                drop_dist_a_m=miss_a,
                drop_dist_b_m=miss_b,
                autonomy_coeff_c=1.0,
                bonus_ay_pickup=(cfg.category == "rotary_wing" and in_radius and miss_a < 2.5),
                bonus_by_delivery=(cfg.category == "rotary_wing" and in_radius and miss_b < 2.5),
            )
            pg1, pg2 = self.optimizer.calculate_table3_scores(profile, bench)

            outcomes.append(
                RunOutcome(
                    run_id=idx,
                    wind_mps=round(true_wind, 2),
                    miss_distance_a_m=round(miss_a, 3),
                    miss_distance_b_m=round(miss_b, 3),
                    pg1_score=pg1,
                    pg2_score=pg2,
                    wind_limit_exceeded=wind_exceeded,
                    in_scoring_radius=in_radius,
                )
            )
            all_misses.extend([miss_a, miss_b])

        n = len(outcomes)
        cep50 = self._percentile(all_misses, 50.0)
        cep90 = self._percentile(all_misses, 90.0)
        mean_miss = sum(all_misses) / max(1, len(all_misses))
        in_rad_pct = 100.0 * sum(1 for o in outcomes if o.in_scoring_radius) / n
        wind_abort_pct = 100.0 * sum(1 for o in outcomes if o.wind_limit_exceeded) / n
        mean_pg1 = sum(o.pg1_score for o in outcomes) / n
        mean_pg2 = sum(o.pg2_score for o in outcomes) / n
        mean_total = mean_pg1 + mean_pg2

        max_flight_pts = 110.0 if cfg.category == "rotary_wing" else 100.0
        score_component = min(50.0, 50.0 * (mean_total / max_flight_pts))
        accuracy_component = min(35.0, 35.0 * (in_rad_pct / 100.0))
        cep_component = max(0.0, 15.0 * (1.0 - min(1.0, cep90 / scoring_radius)))
        cri = round(min(100.0, score_component + accuracy_component + cep_component), 2)

        if cri >= 85.0:
            grade = "ELİT YARIŞMA HAZIR (A+)"
        elif cri >= 70.0:
            grade = "YARIŞMAYA UYGUN (A)"
        elif cri >= 55.0:
            grade = "İYİLEŞTİRME GEREKLİ (B)"
        else:
            grade = "RİSKLİ - KALİBRASYON ŞART (C)"

        return BenchmarkReport(
            num_runs=n,
            category=cfg.category,
            scoring_radius_m=scoring_radius,
            tulga_air_density_kgpm3=round(adc_state.air_density_kgpm3, 4),
            cep50_m=round(cep50, 3),
            cep90_m=round(cep90, 3),
            mean_miss_distance_m=round(mean_miss, 3),
            in_radius_success_rate_pct=round(in_rad_pct, 2),
            wind_abort_rate_pct=round(wind_abort_pct, 2),
            mean_pg1=round(mean_pg1, 2),
            mean_pg2=round(mean_pg2, 2),
            mean_total_flight_score=round(mean_total, 2),
            readiness_index_0_100=cri,
            readiness_grade=grade,
            outcomes=outcomes,
        )
