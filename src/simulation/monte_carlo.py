"""
TEKNOFEST 2026 Uluslararası İHA - Monte Carlo Balistik Dağılım & Görev Güvenilirlik Simülatörü
==============================================================================================
Malatya Tulga Havalimanı (938m MSL) atmosferik koşullarında yüzlerce stokastik yük
bırakma denemesi koşturarak gerçek havacılık istatistikleri üretir:
- CEP50 (Circular Error Probable %50)
- R95 (%95 Kapsama Yarıçapı)
- Ortalama & Maksimum Radyal Sapma
- Şartname Puanlama Çemberi İçinde İsabet Olasılığı (Döner: <= 10m, Sabit: <= 20m)
- Rüzgar belirsizliği, irtifa sensör gürültüsü, servo gecikme titreşimi (jitter) ve
  zemin yuvarlanma sürtünmesi (C_rr) varyasyonu modellemesi
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math
import random


@dataclass
class MonteCarloConfig:
    """Monte Carlo stokastik balistik dağılım parametreleri."""
    num_trials: int = 200
    seed: int = 2026
    category: str = "rotary_wing"         # "rotary_wing" (10m) | "fixed_wing" (20m)
    release_altitude_m: float = 20.0
    altitude_noise_std_m: float = 0.45
    ground_speed_mps: float = 14.0
    speed_noise_std_mps: float = 0.40
    mean_wind_xy_mps: Tuple[float, float] = (3.0, 1.0)
    wind_gust_std_mps: float = 1.2
    release_latency_mean_s: float = 0.06
    release_latency_std_s: float = 0.02
    payload_mass_kg: float = 0.50
    drag_coeff_cd: float = 0.47
    cross_section_m2: float = 0.00785
    air_density_kgpm3: float = 1.116      # Malatya Tulga 938m MSL standart hava yoğunluğu
    rolling_friction_mu: float = 0.35
    rolling_friction_std: float = 0.05


@dataclass
class MonteCarloResult:
    """Monte Carlo simülasyonu istatistiksel çıktı raporu."""
    num_trials: int
    category: str
    scoring_radius_m: float
    cep50_m: float
    r95_m: float
    mean_error_m: float
    std_error_m: float
    max_error_m: float
    hit_probability_pct: float            # Puanlama çemberi içinde kalma yüzdesi
    bullseye_2m_probability_pct: float    # 2m yarıçap içine tam isabet yüzdesi
    mean_bias_xy_m: Tuple[float, float]
    radial_errors_m: List[float] = field(default_factory=list)


class MonteCarloDropSimulator:
    """
    RK4 / Analitik sürüklemeli düşüş + zemin yuvarlanması üzerinde stokastik
    Monte Carlo dağılım analizi yapan doğrulama motoru.
    """

    GRAVITY = 9.80665

    def __init__(self, config: Optional[MonteCarloConfig] = None):
        self.config = config or MonteCarloConfig()

    def _simulate_single_drop(
        self,
        alt_m: float,
        vx0: float,
        vy0: float,
        wind_x: float,
        wind_y: float,
        rho: float,
        mu_roll: float,
        dt: float = 0.02
    ) -> Tuple[float, float]:
        """Tek bir düşüş + zemin yuvarlanma yörüngesini sayısal olarak entegre eder."""
        m = max(0.05, self.config.payload_mass_kg)
        cd = self.config.drag_coeff_cd
        area = self.config.cross_section_m2
        k_drag = 0.5 * rho * cd * area / m

        x, y, z = 0.0, 0.0, max(1.0, alt_m)
        vx, vy, vz = vx0, vy0, 0.0

        # Serbest düşüş fazı (Euler-Midpoint / RK2)
        t = 0.0
        while z > 0.0 and t < 30.0:
            rvx = vx - wind_x
            rvy = vy - wind_y
            rvz = vz
            rel_speed = math.sqrt(rvx * rvx + rvy * rvy + rvz * rvz)

            ax = -k_drag * rel_speed * rvx
            ay = -k_drag * rel_speed * rvy
            az = -self.GRAVITY - k_drag * rel_speed * rvz

            vx += ax * dt
            vy += ay * dt
            vz += az * dt
            x += vx * dt
            y += vy * dt
            z += vz * dt
            t += dt

        # Zemin temas sonrası yuvarlanma (Şartname Madde 8.3.3 Durma Noktası)
        # Çarpma anında yatay hızın %35'i yuvarlanmaya dönüşür (restitution/friction kaybı)
        v_horiz = math.hypot(vx, vy)
        if v_horiz > 0.1 and mu_roll > 0.05:
            v_roll = 0.35 * v_horiz
            roll_dist = (v_roll ** 2) / (2.0 * mu_roll * self.GRAVITY)
            x += (vx / v_horiz) * roll_dist
            y += (vy / v_horiz) * roll_dist

        return (x, y)

    def run(self, config: Optional[MonteCarloConfig] = None) -> MonteCarloResult:
        """
        Nominal hedefe göre nişan alınmış bırakma noktasından N adet stokastik
        deneme koşturur ve CEP50 / R95 / isabet olasılığı metriklerini üretir.
        """
        cfg = config or self.config
        rng = random.Random(cfg.seed)
        scoring_radius = 10.0 if cfg.category == "rotary_wing" else 20.0

        # 1. Nominal (beklenen) durma noktasını hesapla -> İHA bu noktaya göre nişan alır
        nom_x, nom_y = self._simulate_single_drop(
            alt_m=cfg.release_altitude_m,
            vx0=cfg.ground_speed_mps,
            vy0=0.0,
            wind_x=cfg.mean_wind_xy_mps[0],
            wind_y=cfg.mean_wind_xy_mps[1],
            rho=cfg.air_density_kgpm3,
            mu_roll=cfg.rolling_friction_mu
        )
        # Nominal servo gecikmesi kadar ileri kayma
        nom_x += cfg.ground_speed_mps * cfg.release_latency_mean_s

        errors_x: List[float] = []
        errors_y: List[float] = []
        radial_errors: List[float] = []

        # 2. Stokastik denemeleri çalıştır
        for _ in range(max(10, cfg.num_trials)):
            alt_sample = max(2.0, rng.gauss(cfg.release_altitude_m, cfg.altitude_noise_std_m))
            spd_sample = max(1.0, rng.gauss(cfg.ground_speed_mps, cfg.speed_noise_std_mps))
            wx_sample = rng.gauss(cfg.mean_wind_xy_mps[0], cfg.wind_gust_std_mps)
            wy_sample = rng.gauss(cfg.mean_wind_xy_mps[1], cfg.wind_gust_std_mps)
            lat_sample = max(0.0, rng.gauss(cfg.release_latency_mean_s, cfg.release_latency_std_s))
            mu_sample = max(0.10, rng.gauss(cfg.rolling_friction_mu, cfg.rolling_friction_std))

            rx, ry = self._simulate_single_drop(
                alt_m=alt_sample,
                vx0=spd_sample,
                vy0=0.0,
                wind_x=wx_sample,
                wind_y=wy_sample,
                rho=cfg.air_density_kgpm3,
                mu_roll=mu_sample
            )
            rx += spd_sample * lat_sample

            ex = rx - nom_x
            ey = ry - nom_y
            err_r = math.hypot(ex, ey)

            errors_x.append(ex)
            errors_y.append(ey)
            radial_errors.append(round(err_r, 3))

        sorted_err = sorted(radial_errors)
        n = len(sorted_err)
        cep50 = sorted_err[int(0.50 * (n - 1))]
        r95 = sorted_err[int(0.95 * (n - 1))]
        mean_err = sum(sorted_err) / n
        var_err = sum((e - mean_err) ** 2 for e in sorted_err) / n
        std_err = math.sqrt(var_err)

        hits = sum(1 for e in sorted_err if e <= scoring_radius)
        bullseyes = sum(1 for e in sorted_err if e <= 2.0)

        return MonteCarloResult(
            num_trials=n,
            category=cfg.category,
            scoring_radius_m=scoring_radius,
            cep50_m=round(cep50, 3),
            r95_m=round(r95, 3),
            mean_error_m=round(mean_err, 3),
            std_error_m=round(std_err, 3),
            max_error_m=round(sorted_err[-1], 3),
            hit_probability_pct=round((hits / n) * 100.0, 2),
            bullseye_2m_probability_pct=round((bullseyes / n) * 100.0, 2),
            mean_bias_xy_m=(round(sum(errors_x) / n, 3), round(sum(errors_y) / n, 3)),
            radial_errors_m=radial_errors
        )
