"""
TEKNOFEST 2026 - Muhafaza Kutusu Doğrulayıcı ve Tablo 3 Puan Optimizasyonu Testleri
"""

import math
import pytest
from src.avionics.storage_box_optimizer import (
    StorageBoxOptimizer,
    StorageBoxSpec,
    BoxGeometry,
    CompetitionTeamProfile,
    CompetitorBenchmark,
)


def test_rotary_wing_prism_box_validation():
    opt = StorageBoxOptimizer()
    spec = StorageBoxSpec(
        category="rotary_wing",
        geometry=BoxGeometry.RECTANGULAR_PRISM,
        dim_a_m=0.60,
        dim_b_m=0.60,
        dim_c_m=0.40,
    )
    res = opt.validate_storage_box(spec)
    assert res.is_compliant is True
    assert abs(res.volume_m3 - 0.144) < 1e-4
    assert res.estimated_penalty_1_pts == 0.0


def test_fixed_wing_cylinder_valid_and_ellipse_rejected():
    opt = StorageBoxOptimizer()
    valid_cyl = StorageBoxSpec(
        category="fixed_wing",
        geometry=BoxGeometry.CYLINDRICAL,
        dim_a_m=0.35,
        dim_b_m=0.35,
        dim_c_m=1.20,
    )
    res_ok = opt.validate_storage_box(valid_cyl)
    assert res_ok.is_compliant is True
    expected_vol = math.pi * (0.175 ** 2) * 1.20
    assert abs(res_ok.volume_m3 - expected_vol) < 1e-4

    # Elips kesit kesinlikle yasak
    ellipse_cyl = StorageBoxSpec(
        category="fixed_wing",
        geometry=BoxGeometry.CYLINDRICAL,
        dim_a_m=0.40,
        dim_b_m=0.25,
        dim_c_m=1.20,
    )
    res_bad = opt.validate_storage_box(ellipse_cyl)
    assert res_bad.is_compliant is False
    assert any("elips" in v.lower() for v in res_bad.violations)


def test_extra_intervention_setup_time_penalty():
    opt = StorageBoxOptimizer()
    # 2 müdahale (15s ve 5s) -> (15+10) + (5+10) = 40s ceza
    eff = opt.compute_effective_setup_time(180.0, [15.0, 5.0])
    assert eff == pytest.approx(220.0)


def test_table3_score_and_mtow_optimization():
    opt = StorageBoxOptimizer()
    profile = CompetitionTeamProfile(
        category="rotary_wing",
        empty_mass_w0_kg=1.80,
        single_payload_mass_kg=0.60,
        box_volume_m3=0.144,
        setup_time_s=180.0,
        bonus_ay_pickup=True,
        bonus_by_delivery=True,
    )
    bench = CompetitorBenchmark()
    res = opt.optimize_team_strategy(profile, bench)

    assert res.mtow_kg == pytest.approx(3.0)
    assert res.mtow_compliant is True
    assert res.setup_time_compliant is True
    assert 0.0 < res.predicted_pg1 <= 30.0
    assert 0.0 < res.predicted_pg2 <= 80.0
    assert res.payload_recommendation.aggressive_total_payload_kg <= 4.0 - 1.80
    assert res.top_engineering_lever in res.sensitivities


def test_fixed_wing_scoring_radius_cutoff():
    opt = StorageBoxOptimizer()
    bench = CompetitorBenchmark()
    inside = CompetitionTeamProfile(
        category="fixed_wing",
        empty_mass_w0_kg=1.9,
        single_payload_mass_kg=0.5,
        box_volume_m3=0.115,
        setup_time_s=160.0,
        drop_dist_a_m=4.0,
        drop_dist_b_m=3.0,
    )
    outside = CompetitionTeamProfile(**{**inside.__dict__, "drop_dist_a_m": 25.0, "drop_dist_b_m": 25.0})
    _, g2_in = opt.calculate_table3_scores(inside, bench)
    _, g2_out = opt.calculate_table3_scores(outside, bench)
    assert g2_in > g2_out
