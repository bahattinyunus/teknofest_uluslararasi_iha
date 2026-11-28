"""
Unit tests for CompetitionOptimizer (Weight/CG Shift, Transport Box, Setup Timing, Tablo 3 Sensitivity)
"""
from src.avionics.competition_optimizer import CompetitionOptimizer, MassComponent


def test_weight_and_balance_dual_payload_cg_shift():
    opt = CompetitionOptimizer(category="rotary_wing", cg_x_limits_m=(-0.03, 0.03), cg_y_limits_m=(-0.02, 0.02))
    components = [
        MassComponent("Airframe+Avionics", 1.50, 0.0, 0.0, 0.0),
        MassComponent("4S LiPo 5000mAh", 0.55, 0.01, 0.0, -0.02),
        MassComponent("Payload 1 (Red)", 0.45, 0.03, 0.04, -0.05, is_droppable_payload=True, payload_slot=1),
        MassComponent("Payload 2 (Blue)", 0.45, -0.03, -0.04, -0.05, is_droppable_payload=True, payload_slot=2),
    ]
    report = opt.analyze_weight_and_balance(components)

    assert report["full_load"].total_mass_kg == 2.95
    assert report["full_load"].mtow_compliant is True
    assert report["after_drop_1"].total_mass_kg == 2.50
    assert report["after_drop_1"].cg_shift_from_nominal_mm > 0.0
    assert report["empty"].total_mass_kg == 2.05


def test_mtow_violation_detected():
    opt = CompetitionOptimizer(category="fixed_wing")
    heavy = [MassComponent("Heavy UAV", 4.35, 0.0, 0.0, 0.0)]
    report = opt.analyze_weight_and_balance(heavy)
    assert report["full_load"].mtow_compliant is False


def test_transport_box_cylindrical_vs_prism_rules():
    fixed_opt = CompetitionOptimizer(category="fixed_wing")
    ok_cyl = fixed_opt.audit_transport_box("cylindrical", (0.30, 1.10), single_person_portable=True)
    assert ok_cyl.is_compliant is True
    assert ok_cyl.volume_liters > 70.0

    bad_ellipse = fixed_opt.audit_transport_box("elliptical", (0.30, 1.10))
    assert bad_ellipse.is_compliant is False

    rotary_opt = CompetitionOptimizer(category="rotary_wing")
    ok_prism = rotary_opt.audit_transport_box("rectangular_prism", (0.55, 0.55, 0.35), external_items_count=0)
    assert ok_prism.is_compliant is True

    bad_ext = rotary_opt.audit_transport_box("rectangular_prism", (0.55, 0.55, 0.35), external_items_count=2)
    assert bad_ext.is_compliant is False
    assert bad_ext.external_item_penalty_pts == 4.0


def test_setup_timing_extra_intervention_penalty():
    opt = CompetitionOptimizer(category="rotary_wing")
    # 200s measured + 2 interventions (15s and 20s) -> +15+20 + 2*10 = 55s -> 255s effective
    audit = opt.audit_setup_timing(measured_setup_s=200.0, interventions_s=[15.0, 20.0])
    assert audit.intervention_count == 2
    assert audit.penalty_added_s == 55.0
    assert audit.effective_setup_s == 255.0
    assert audit.within_8min_limit is True

    # Exceeds 480s limit
    over = opt.audit_setup_timing(measured_setup_s=450.0, interventions_s=[25.0])
    assert over.effective_setup_s == 485.0
    assert over.within_8min_limit is False


def test_table3_score_and_sensitivity_analysis():
    opt = CompetitionOptimizer(category="rotary_wing")
    sens = opt.run_sensitivity_analysis({
        "c_autonomy": 1.0,
        "vol_tk": 0.144,
        "vol_min": 0.110,
        "t_haz_tk": 180.0,
        "t_haz_min": 120.0,
        "w0_tk": 2.0,
        "w0_min": 1.6,
        "w_yuk_tk": 1.0,
        "w_yuk_max": 1.6,
        "t_ucus_tk": 150.0,
        "t_ucus_min": 110.0,
        "ay_bonus": False,
        "by_bonus": False
    })
    assert sens["delta_plus_200g_payload"] > 0.0
    assert sens["delta_minus_15pct_box_volume"] > 0.0
    assert sens["delta_enable_g3_bonus"] == 20.0
