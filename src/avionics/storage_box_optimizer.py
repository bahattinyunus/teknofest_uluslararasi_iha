"""
TEKNOFEST 2026 Uluslararası İHA - Muhafaza Kutusu ve Tablo 3 Puan Optimizasyon Motoru
======================================================================================
Şartname Referansları:
  - Madde 8.3.4 (Muhafaza Kutusu):
      * Sabit Kanat : Dairesel kesitli SİLİNDİRİK kutu (V = pi * r^2 * h), elips YASAK!
      * Döner Kanat : Dikdörtgen veya kare PRİZMA kutu (V = a * b * c).
      * Dış ölçüler esas alınır; tutma sapı, kulp ve tekerlek hacme dahil edilmez.
      * Tek kişi tarafından taşınabilir olmalı; GCS ve RC hariç tüm parçalar kutuda olmalı.
  - Madde 8.3.5 (Süre & Ek Müdahale Cezası):
      * t_haz <= 480s (8 dk); güç verme/kesme harici her müdahale: delta_t + 10s ceza.
  - Madde 9.3.1 (MTOW):
      * Yükler dahil Azami Kalkış Ağırlığı <= 4.0 kg.
  - Madde 11.1 (Tablo 3 Resmi Puanlama Formülleri):
      * PG1, PG2_Sabit, PG2_Döner hesaplamaları, marjinal duyarlılık türevleri
        (dP/dW0, dP/dW_yuk, dP/dVol, dP/dt_haz) ve 2 adet izinli yük ağırlığı denemesi
        (allowed_weight_trials = 2) için optimal yük çifti önericisi.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class BoxGeometry(Enum):
    CYLINDRICAL = "cylindrical"
    RECTANGULAR_PRISM = "rectangular_prism"


@dataclass
class StorageBoxSpec:
    """Muhafaza kutusu dış ölçüleri ve fiziksel özellikleri."""
    category: str                           # "rotary_wing" | "fixed_wing"
    geometry: BoxGeometry
    # Prizma için (a, b, c) metre cinsinden; silindir için (diameter_1_m, diameter_2_m, height_m)
    dim_a_m: float
    dim_b_m: float
    dim_c_m: float
    portable_by_single_person: bool = True
    all_parts_inside_box: bool = True
    external_items_count: int = 0
    box_empty_mass_kg: float = 1.8


@dataclass
class BoxValidationResult:
    """Muhafaza kutusu şartname uyumluluk raporu."""
    is_compliant: bool
    volume_m3: float
    estimated_penalty_1_pts: float
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CompetitionTeamProfile:
    """Takımın fiziksel ve operasyonel parametreleri."""
    category: str                           # "rotary_wing" | "fixed_wing"
    empty_mass_w0_kg: float                 # Yüksüz İHA ağırlığı W0
    single_payload_mass_kg: float           # 1 adet faydalı yük kütlesi (toplam 2 özdeş yük taşınır)
    box_volume_m3: float                    # Muhafaza kutusu hacmi Vol_tk
    setup_time_s: float                     # Ölçülen kurulum süresi
    extra_interventions_s: List[float] = field(default_factory=list)  # Güç harici müdahale süreleri
    task1_flight_time_s: float = 95.0
    task2_flight_time_s: float = 165.0
    drop_dist_a_m: float = 1.5              # Hedef A (Mavi Altıgen / 4x4 Kare) durma mesafesi
    drop_dist_b_m: float = 1.2              # Hedef B (Kırmızı Üçgen / 2x2 Kare) durma mesafesi
    autonomy_coeff_c: float = 1.0           # 1.0 tam otonom, 0.7 yarı otonom
    bonus_ay_pickup: bool = False           # Döner kanat Görev 3: Altıgenden yük alma (+10)
    bonus_by_delivery: bool = False         # Döner kanat Görev 3: Üçgene bırakma (+10)
    penalty_pts: float = 0.0


@dataclass
class CompetitorBenchmark:
    """Yarışmadaki en iyi rakip referans değerleri (Tablo 3 normalizasyon payları)."""
    vol_min_m3: float = 0.10
    t_min_haz_s: float = 120.0
    w0_min_kg: float = 1.40
    w_yuk_max_kg: float = 1.80              # Toplam 2 yük kütlesi (ör. 2 x 900g)
    t_min_ucus_g1_s: float = 75.0
    t_min_ucus_g2_s: float = 130.0
    d_target_a_min_m: float = 0.5
    d_target_b_min_m: float = 0.5


@dataclass
class PayloadTrialRecommendation:
    """Şartname §8.3.2 uyarınca izin verilen 2 farklı yük denemesi için optimal çift."""
    conservative_total_payload_kg: float
    aggressive_total_payload_kg: float
    max_legal_total_payload_kg: float
    expected_g2_conservative: float
    expected_g2_aggressive: float
    rationale: str


@dataclass
class ScoreOptimizationResult:
    """Tablo 3 skor tahmini, marjinal duyarlılıklar ve stratejik iyileştirme önerisi."""
    mtow_kg: float
    mtow_compliant: bool
    effective_setup_time_s: float
    setup_time_compliant: bool
    predicted_pg1: float
    predicted_pg2: float
    predicted_total_flight_score: float
    sensitivities: Dict[str, float]         # Birim iyileştirme başına puan kazancı
    payload_recommendation: PayloadTrialRecommendation
    top_engineering_lever: str


class StorageBoxOptimizer:
    """
    TEKNOFEST 2026 Muhafaza Kutusu Doğrulayıcı ve Tablo 3 Puan Optimizasyon Motoru.
    """

    MAX_MTOW_KG = 4.0
    MAX_SETUP_TIME_S = 480.0
    EXTRA_INTERVENTION_PENALTY_S = 10.0

    def validate_storage_box(self, spec: StorageBoxSpec) -> BoxValidationResult:
        """Muhafaza kutusunu Şartname Madde 8.3.4 kurallarına göre doğrular."""
        violations: List[str] = []
        warnings: List[str] = []

        if spec.dim_a_m <= 0 or spec.dim_b_m <= 0 or spec.dim_c_m <= 0:
            violations.append("Kutu dış ölçüleri pozitif olmalıdır.")
            return BoxValidationResult(False, 0.0, 5.0, violations, warnings)

        if spec.category == "fixed_wing":
            if spec.geometry != BoxGeometry.CYLINDRICAL:
                violations.append(
                    "Sabit Kanat kategorisinde muhafaza kutusu dairesel kesitli SİLİNDİRİK olmak zorundadır (§8.3.4)."
                )
            # Dairesel kesit kontrolü: dim_a_m ve dim_b_m iki eksen çapı olarak değerlendirilir
            if abs(spec.dim_a_m - spec.dim_b_m) > 0.005:
                violations.append(
                    f"Sabit Kanat silindirik kutuda elips kesit KESİNLİKLE YASAKTIR "
                    f"(Çap X={spec.dim_a_m:.3f}m != Çap Y={spec.dim_b_m:.3f}m)."
                )
            radius = 0.5 * (spec.dim_a_m + spec.dim_b_m) / 2.0
            volume_m3 = math.pi * (radius ** 2) * spec.dim_c_m
        else:
            if spec.geometry != BoxGeometry.RECTANGULAR_PRISM:
                violations.append(
                    "Döner Kanat kategorisinde muhafaza kutusu dikdörtgen veya kare PRİZMA olmalıdır (§8.3.4)."
                )
            volume_m3 = spec.dim_a_m * spec.dim_b_m * spec.dim_c_m

        if not spec.portable_by_single_person:
            violations.append("Muhafaza kutusu tek (1) kişi tarafından taşınabilir olmalıdır.")

        penalty_1 = 0.0
        if not spec.all_parts_inside_box or spec.external_items_count > 0:
            penalty_1 = min(5.0, max(1.0, float(spec.external_items_count) * 1.5))
            warnings.append(
                f"Kutu harici parça tespit edildi ({spec.external_items_count} adet): "
                f"Ceza Puanı 1 tahmini = -{penalty_1:.1f} puan (§8.3.4)."
            )

        if volume_m3 > 0.25:
            warnings.append(
                f"Kutu hacmi yüksek ({volume_m3:.4f} m³); Tablo 3 Vol_min/Vol_tk çarpanında puan kaybı yaratır."
            )

        return BoxValidationResult(
            is_compliant=(len(violations) == 0),
            volume_m3=round(volume_m3, 5),
            estimated_penalty_1_pts=round(penalty_1, 2),
            violations=violations,
            warnings=warnings,
        )

    def compute_effective_setup_time(self, measured_setup_s: float, extra_interventions_s: List[float]) -> float:
        """Ek müdahale cezasını (her müdahale süresi + 10s) hesaplar (§8.3.5)."""
        penalty_total = sum(max(0.0, dt) + self.EXTRA_INTERVENTION_PENALTY_S for dt in extra_interventions_s)
        return measured_setup_s + penalty_total

    def calculate_table3_scores(
        self,
        team: CompetitionTeamProfile,
        bench: CompetitorBenchmark,
    ) -> Tuple[float, float]:
        """Tablo 3 resmi formüllerine göre (PG1, PG2) puanlarını hesaplar."""
        t_haz = max(1.0, self.compute_effective_setup_time(team.setup_time_s, team.extra_interventions_s))
        vol_ratio = min(1.0, bench.vol_min_m3 / max(1e-4, team.box_volume_m3))
        haz_ratio = min(1.0, bench.t_min_haz_s / t_haz)
        w0_ratio = min(1.0, bench.w0_min_kg / max(0.1, team.empty_mass_w0_kg))
        t_g1_ratio = min(1.0, bench.t_min_ucus_g1_s / max(1.0, team.task1_flight_time_s))
        t_g2_ratio = min(1.0, bench.t_min_ucus_g2_s / max(1.0, team.task2_flight_time_s))

        pg1 = team.autonomy_coeff_c * (
            6.0 * vol_ratio + 6.0 * haz_ratio + 6.0 * w0_ratio + 12.0 * t_g1_ratio
        ) - team.penalty_pts
        pg1 = max(0.0, pg1)

        total_payload_kg = 2.0 * max(0.0, team.single_payload_mass_kg)
        w_yuk_ratio = min(1.0, total_payload_kg / max(0.05, bench.w_yuk_max_kg))

        if team.category == "fixed_wing":
            max_r = 20.0
            d_a_ratio = (
                min(1.0, bench.d_target_a_min_m / max(0.05, team.drop_dist_a_m))
                if team.drop_dist_a_m <= max_r
                else 0.0
            )
            d_b_ratio = (
                min(1.0, bench.d_target_b_min_m / max(0.05, team.drop_dist_b_m))
                if team.drop_dist_b_m <= max_r
                else 0.0
            )
            pg2 = team.autonomy_coeff_c * (
                4.0 * vol_ratio
                + 4.0 * haz_ratio
                + 4.0 * w0_ratio
                + 20.0 * w_yuk_ratio
                + 10.0 * d_a_ratio
                + 20.0 * d_b_ratio
                + 8.0 * t_g2_ratio
            ) - team.penalty_pts
        else:
            max_r = 10.0
            d_a_ratio = (
                min(1.0, bench.d_target_a_min_m / max(0.05, team.drop_dist_a_m))
                if team.drop_dist_a_m <= max_r
                else 0.0
            )
            d_b_ratio = (
                min(1.0, bench.d_target_b_min_m / max(0.05, team.drop_dist_b_m))
                if team.drop_dist_b_m <= max_r
                else 0.0
            )
            ay_val = 1.0 if team.bonus_ay_pickup else 0.0
            by_val = 1.0 if team.bonus_by_delivery else 0.0
            pg2 = team.autonomy_coeff_c * (
                4.0 * vol_ratio
                + 4.0 * haz_ratio
                + 4.0 * w0_ratio
                + 20.0 * w_yuk_ratio
                + 8.0 * d_a_ratio
                + 12.0 * d_b_ratio
                + 10.0 * (ay_val + by_val)
                + 8.0 * t_g2_ratio
            ) - team.penalty_pts

        pg2 = max(0.0, pg2)
        return round(pg1, 3), round(pg2, 3)

    def recommend_payload_trials(
        self,
        team: CompetitionTeamProfile,
        bench: CompetitorBenchmark,
        safety_margin_kg: float = 0.08,
    ) -> PayloadTrialRecommendation:
        """
        Şartname Madde 8.3.2 uyarınca izin verilen 2 farklı yük denemesi için
        MTOW <= 4.0 kg kısıtı altında güvenli + agresif yük ağırlığı çiftini önerir.
        """
        max_legal_total = max(0.0, self.MAX_MTOW_KG - team.empty_mass_w0_kg - safety_margin_kg)
        aggressive_total = round(min(max_legal_total, max(bench.w_yuk_max_kg, max_legal_total)), 3)
        conservative_total = round(max(0.20, aggressive_total * 0.72), 3)

        cons_profile = CompetitionTeamProfile(**{**team.__dict__, "single_payload_mass_kg": conservative_total / 2.0})
        aggr_profile = CompetitionTeamProfile(**{**team.__dict__, "single_payload_mass_kg": aggressive_total / 2.0})

        _, g2_cons = self.calculate_table3_scores(cons_profile, bench)
        _, g2_aggr = self.calculate_table3_scores(aggr_profile, bench)

        rationale = (
            f"1. Deneme (Güvenli): {conservative_total*1000:.0f}g toplam yük (2x{conservative_total*500:.0f}g) ile "
            f"yüksek manevra marjı ve skor garantisi ({g2_cons:.1f} puan). "
            f"2. Deneme (Agresif): {aggressive_total*1000:.0f}g toplam yük (2x{aggressive_total*500:.0f}g) ile "
            f"4.0 kg MTOW sınırında maksimum W_yuk katsayısı ({g2_aggr:.1f} puan)."
        )
        return PayloadTrialRecommendation(
            conservative_total_payload_kg=conservative_total,
            aggressive_total_payload_kg=aggressive_total,
            max_legal_total_payload_kg=round(max_legal_total, 3),
            expected_g2_conservative=g2_cons,
            expected_g2_aggressive=g2_aggr,
            rationale=rationale,
        )

    def optimize_team_strategy(
        self,
        team: CompetitionTeamProfile,
        bench: Optional[CompetitorBenchmark] = None,
    ) -> ScoreOptimizationResult:
        """
        Takımın MTOW, kurulum süresi, Tablo 3 puanlarını ve sonlu fark (sensitivity)
        analiziyle en yüksek getiri sağlayan mühendislik iyileştirmesini hesaplar.
        """
        bench = bench or CompetitorBenchmark()
        mtow = team.empty_mass_w0_kg + 2.0 * team.single_payload_mass_kg
        eff_setup = self.compute_effective_setup_time(team.setup_time_s, team.extra_interventions_s)

        base_g1, base_g2 = self.calculate_table3_scores(team, bench)
        base_total = base_g1 + base_g2

        # Marjinal duyarlılık analizleri (gerçekçi mühendislik iyileştirme adımları)
        # 1) Boş ağırlığı 100g azaltma
        p_w0 = CompetitionTeamProfile(**{**team.__dict__, "empty_mass_w0_kg": max(0.5, team.empty_mass_w0_kg - 0.10)})
        g1_w0, g2_w0 = self.calculate_table3_scores(p_w0, bench)
        gain_w0_100g = round((g1_w0 + g2_w0) - base_total, 3)

        # 2) Toplam faydalı yükü 100g artırma (MTOW içinde ise)
        can_add_payload = (mtow + 0.10) <= self.MAX_MTOW_KG
        if can_add_payload:
            p_wy = CompetitionTeamProfile(**{**team.__dict__, "single_payload_mass_kg": team.single_payload_mass_kg + 0.05})
            g1_wy, g2_wy = self.calculate_table3_scores(p_wy, bench)
            gain_payload_100g = round((g1_wy + g2_wy) - base_total, 3)
        else:
            gain_payload_100g = 0.0

        # 3) Kutu hacmini %10 küçültme
        p_vol = CompetitionTeamProfile(**{**team.__dict__, "box_volume_m3": max(0.01, team.box_volume_m3 * 0.90)})
        g1_vol, g2_vol = self.calculate_table3_scores(p_vol, bench)
        gain_box_10pct = round((g1_vol + g2_vol) - base_total, 3)

        # 4) Kurulum süresini 30 saniye hızlandırma
        p_haz = CompetitionTeamProfile(**{**team.__dict__, "setup_time_s": max(20.0, team.setup_time_s - 30.0)})
        g1_haz, g2_haz = self.calculate_table3_scores(p_haz, bench)
        gain_setup_30s = round((g1_haz + g2_haz) - base_total, 3)

        sensitivities = {
            "empty_mass_minus_100g_pts": gain_w0_100g,
            "payload_plus_100g_pts": gain_payload_100g,
            "box_volume_minus_10pct_pts": gain_box_10pct,
            "setup_time_minus_30s_pts": gain_setup_30s,
        }
        top_lever = max(sensitivities, key=sensitivities.get)
        payload_rec = self.recommend_payload_trials(team, bench)

        return ScoreOptimizationResult(
            mtow_kg=round(mtow, 3),
            mtow_compliant=(mtow <= self.MAX_MTOW_KG),
            effective_setup_time_s=round(eff_setup, 2),
            setup_time_compliant=(eff_setup <= self.MAX_SETUP_TIME_S),
            predicted_pg1=base_g1,
            predicted_pg2=base_g2,
            predicted_total_flight_score=round(base_total, 3),
            sensitivities=sensitivities,
            payload_recommendation=payload_rec,
            top_engineering_lever=top_lever,
        )
