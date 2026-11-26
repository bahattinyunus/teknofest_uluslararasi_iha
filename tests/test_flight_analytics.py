"""
Unit tests for Flight Analytics and 2026 Scoring Subsystem
"""
import pytest
from src.telemetry.analytics import FlightAnalyticsEngine, DropScore, FlightSummary


def test_drop_score_exact_center():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 0 meter miss distance -> 100 points
    score = engine.calculate_drop_score(0.0)
    assert score == 100.0


def test_drop_score_half_radius():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 5.0m miss distance (out of 10m max) -> 50 points
    score = engine.calculate_drop_score(5.0)
    assert score == 50.0


def test_drop_score_out_of_bounds():
    engine = FlightAnalyticsEngine(category="rotary_wing")
    # 12.0m miss distance (> 10m) -> 0 points
    score = engine.calculate_drop_score(12.0)
    assert score == 0.0


def test_fixed_wing_scoring_radius():
    engine = FlightAnalyticsEngine(category="fixed_wing")
    # In fixed wing, radius is 20m. At 10m miss distance -> 50 points
    score = engine.calculate_drop_score(10.0)
    assert score == 50.0


def test_analyze_nonexistent_log():
    engine = FlightAnalyticsEngine()
    summary = engine.analyze_csv_log("non_existent_flight_log.csv")
    assert summary is None


def test_csv_log_parsing(tmp_path):
    csv_file = str(tmp_path / "test_flight.csv")
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("timestamp,state,altitude_agl,ground_speed,vx,vy,vz,battery_v,target_locked,target_type,lead_distance,miss_distance,payloads_left\n")
        f.write("100.0,TAKEOFF,10.0,2.0,2.0,0.0,0.0,16.2,0,NONE,0.0,99.0,2\n")
        f.write("105.0,LOCKING_TARGET_A,25.0,5.0,5.0,0.0,0.0,16.0,1,TARGET_A,3.0,1.5,2\n")
        f.write("110.0,DROPPING_PAYLOAD_1,20.0,3.0,3.0,0.0,0.0,15.8,1,TARGET_A,2.0,2.0,1\n")  # Payload 1 dropped with miss=2.0m
        f.write("115.0,DROPPING_PAYLOAD_2,20.0,3.0,3.0,0.0,0.0,15.5,1,TARGET_B,2.0,1.0,0\n")  # Payload 2 dropped with miss=1.0m
        f.write("120.0,LANDED,0.0,0.0,0.0,0.0,0.0,15.3,0,NONE,0.0,99.0,0\n")

    engine = FlightAnalyticsEngine(category="rotary_wing")
    summary = engine.analyze_csv_log(csv_file)

    assert summary is not None
    assert summary.total_flight_time_s == 20.0
    assert summary.max_altitude_m == 25.0
    assert summary.exceeded_120m_limit is False
    assert len(summary.drop_scores) == 2
    # At 2.0m miss: score = 100 * (1 - 2/10) = 80
    # At 1.0m miss: score = 100 * (1 - 1/10) = 90
    assert summary.drop_scores[0].score_points == 80.0
    assert summary.drop_scores[1].score_points == 90.0
    assert summary.total_mission_score == 170.0
    assert summary.compliance_passed is True

    md = engine.generate_markdown_report(summary)
    assert "170.0 / 200 Puan" in md
    assert "KURAL VE GÖREV UYUMLU" in md
    assert "TÜBİTAK 2026 Şartnamesi Tablo 3 Resmi Puanlama" in md
    assert summary.pg1_score > 0
    assert summary.pg2_score > 0


def test_official_pg1_perfect_score():
    """Tablo 3 Görev 1: 6 + 6 + 6 + 12 = 30 Puan tam başarı testi."""
    res = FlightAnalyticsEngine.evaluate_pg1_breakdown(
        c_autonomy=1.0,
        vol_min=0.08,
        vol_tk=0.08,
        t_min_haz=150.0,
        t_tk_haz=150.0,
        w0_min=2.5,
        w0_tk=2.5,
        t_min_ucus=180.0,
        t_tk_ucus=180.0,
        penalty_points=0.0
    )
    assert res["term_vol_pts"] == 6.0
    assert res["term_haz_pts"] == 6.0
    assert res["term_w0_pts"] == 6.0
    assert res["term_ucus_pts"] == 12.0
    assert res["final_pg1_score"] == 30.0

    score = FlightAnalyticsEngine.calculate_official_pg1(
        c_autonomy=1.0,
        vol_min=0.08,
        vol_tk=0.08,
        t_min_haz=150.0,
        t_tk_haz=150.0,
        w0_min=2.5,
        w0_tk=2.5,
        t_min_ucus=180.0,
        t_tk_ucus=180.0
    )
    assert score == 30.0


def test_official_pg1_semi_autonomous_and_penalties():
    """c=0.7 yarı otonom katsayısı ve ceza puanı kesintisi testi."""
    res = FlightAnalyticsEngine.evaluate_pg1_breakdown(
        c_autonomy=0.7,
        vol_min=0.08,
        vol_tk=0.08,
        t_min_haz=150.0,
        t_tk_haz=150.0,
        w0_min=2.5,
        w0_tk=2.5,
        t_min_ucus=180.0,
        t_tk_ucus=180.0,
        penalty_points=3.0
    )
    # 0.7 * 30 = 21.0 - 3.0 = 18.0
    assert res["raw_score"] == 21.0
    assert res["final_pg1_score"] == 18.0


def test_official_pg2_fixed_wing_perfect_score():
    """Tablo 3 Uluslararası Sabit Kanat: 4/4/4/20/10/20/8 = 70 Puan tam başarı testi."""
    res = FlightAnalyticsEngine.evaluate_pg2_fixed_wing_breakdown(
        c_autonomy=1.0,
        vol_min=0.1,
        vol_tk=0.1,
        t_min_haz=120.0,
        t_tk_haz=120.0,
        w0_min=2.0,
        w0_tk=2.0,
        w_yuk_tk=1.5,
        w_yuk_max=1.5,
        d_4x4_min=0.2,
        d_4x4_tk=0.2,
        d_2x2_min=0.2,
        d_2x2_tk=0.2,
        t_min_ucus=200.0,
        t_tk_ucus=200.0,
        penalty_points=0.0
    )
    assert res["term_vol_pts"] == 4.0
    assert res["term_haz_pts"] == 4.0
    assert res["term_w0_pts"] == 4.0
    assert res["term_wyuk_pts"] == 20.0
    assert res["term_d4x4_pts"] == 10.0
    assert res["term_d2x2_pts"] == 20.0
    assert res["term_ucus_pts"] == 8.0
    assert res["final_pg2_score"] == 70.0


def test_official_pg2_fixed_wing_radius_cutoff():
    """Sabit kanatta 20m üstü atışlar için isabet puanı sıfır olmalıdır."""
    res = FlightAnalyticsEngine.evaluate_pg2_fixed_wing_breakdown(
        c_autonomy=1.0,
        vol_min=0.1,
        vol_tk=0.1,
        t_min_haz=120.0,
        t_tk_haz=120.0,
        w0_min=2.0,
        w0_tk=2.0,
        w_yuk_tk=1.5,
        w_yuk_max=1.5,
        d_4x4_min=0.2,
        d_4x4_tk=20.5,  # > 20m -> 0 puan
        d_2x2_min=0.2,
        d_2x2_tk=25.0,  # > 20m -> 0 puan
        t_min_ucus=200.0,
        t_tk_ucus=200.0,
        penalty_points=0.0
    )
    assert res["term_d4x4_pts"] == 0.0
    assert res["term_d2x2_pts"] == 0.0
    # Kalan terimler: 4 + 4 + 4 + 20 + 8 = 40 Puan
    assert res["final_pg2_score"] == 40.0


def test_official_pg2_rotary_wing_perfect_score_and_bonus():
    """Tablo 3 Uluslararası Döner Kanat: 4/4/4/20/8/12/10(AY+BY)/8 = 80 Puan tam başarı testi."""
    res = FlightAnalyticsEngine.evaluate_pg2_rotary_wing_breakdown(
        c_autonomy=1.0,
        vol_min=0.05,
        vol_tk=0.05,
        t_min_haz=100.0,
        t_tk_haz=100.0,
        w0_min=1.8,
        w0_tk=1.8,
        w_yuk_tk=1.2,
        w_yuk_max=1.2,
        d_altg_min=0.1,
        d_altg_tk=0.1,
        d_ucg_min=0.1,
        d_ucg_tk=0.1,
        t_min_ucus=150.0,
        t_tk_ucus=150.0,
        ay_bonus=1,
        by_bonus=1,
        penalty_points=0.0
    )
    assert res["term_vol_pts"] == 4.0
    assert res["term_haz_pts"] == 4.0
    assert res["term_w0_pts"] == 4.0
    assert res["term_wyuk_pts"] == 20.0
    assert res["term_daltg_pts"] == 8.0
    assert res["term_ducg_pts"] == 12.0
    assert res["bonus_pts"] == 20.0  # AY (10) + BY (10)
    assert res["term_ucus_pts"] == 8.0
    assert res["final_pg2_score"] == 80.0


def test_official_pg2_rotary_wing_partial_bonus():
    """Döner kanat AY=1 (alındı) fakat BY=0 (bırakılamadı) durumunda 10 puan bonus testi."""
    score = FlightAnalyticsEngine.calculate_official_pg2_rotary_wing(
        c_autonomy=1.0,
        vol_min=0.05,
        vol_tk=0.05,
        t_min_haz=100.0,
        t_tk_haz=100.0,
        w0_min=1.8,
        w0_tk=1.8,
        w_yuk_tk=1.2,
        w_yuk_max=1.2,
        d_altg_min=0.1,
        d_altg_tk=0.1,
        d_ucg_min=0.1,
        d_ucg_tk=0.1,
        t_min_ucus=150.0,
        t_tk_ucus=150.0,
        ay_bonus=1,
        by_bonus=0
    )
    # 80 - 10 = 70.0
    assert score == 70.0


def test_official_pg2_rotary_wing_radius_cutoff():
    """Döner kanatta 10m üstü atışlar için isabet puanı sıfır olmalıdır."""
    res = FlightAnalyticsEngine.evaluate_pg2_rotary_wing_breakdown(
        c_autonomy=1.0,
        vol_min=0.05,
        vol_tk=0.05,
        t_min_haz=100.0,
        t_tk_haz=100.0,
        w0_min=1.8,
        w0_tk=1.8,
        w_yuk_tk=1.2,
        w_yuk_max=1.2,
        d_altg_min=0.1,
        d_altg_tk=10.5,  # > 10m -> 0 puan
        d_ucg_min=0.1,
        d_ucg_tk=15.0,  # > 10m -> 0 puan
        t_min_ucus=150.0,
        t_tk_ucus=150.0,
        ay_bonus=0,
        by_bonus=0,
        penalty_points=0.0
    )
    assert res["term_daltg_pts"] == 0.0
    assert res["term_ducg_pts"] == 0.0
    # Kalan terimler: 4 + 4 + 4 + 20 + 8 = 40 Puan
    assert res["final_pg2_score"] == 40.0


def test_calculate_official_pg2_dispatcher():
    """Dispatcher'ın sabit ve döner kanat kategorilerini doğru yönlendirmesi testi."""
    score_fixed = FlightAnalyticsEngine.calculate_official_pg2(
        category="fixed_wing",
        c_autonomy=1.0,
        vol_min=0.1, vol_tk=0.1,
        t_min_haz=120.0, t_tk_haz=120.0,
        w0_min=2.0, w0_tk=2.0,
        w_yuk_tk=1.5, w_yuk_max=1.5,
        d1_min=0.2, d1_tk=0.2,
        d2_min=0.2, d2_tk=0.2,
        t_min_ucus=200.0, t_tk_ucus=200.0
    )
    assert score_fixed == 70.0

    score_rotary = FlightAnalyticsEngine.calculate_official_pg2(
        category="rotary_wing",
        c_autonomy=1.0,
        vol_min=0.05, vol_tk=0.05,
        t_min_haz=100.0, t_tk_haz=100.0,
        w0_min=1.8, w0_tk=1.8,
        w_yuk_tk=1.2, w_yuk_max=1.2,
        d1_min=0.1, d1_tk=0.1,
        d2_min=0.1, d2_tk=0.1,
        t_min_ucus=150.0, t_tk_ucus=150.0,
        ay_bonus=1,
        by_bonus=1
    )
    assert score_rotary == 80.0


def test_calculate_total_competition_score():
    """Tablo 2 Genel Puanlama Tablosu toplam skor ve ceza kesintileri testi."""
    res_sabit = FlightAnalyticsEngine.calculate_total_competition_score(
        video_score=10.0,
        pg1_score=30.0,
        pg2_score=70.0,
        ceza_1=2.0,
        ceza_2=5.0,
        category="fixed_wing"
    )
    # 10 + 30 + 70 - 7 = 103.0 / 110.0
    assert res_sabit["total_score"] == 103.0
    assert res_sabit["max_possible_total"] == 110.0
    assert res_sabit["total_penalties"] == 7.0

    res_doner = FlightAnalyticsEngine.calculate_total_competition_score(
        video_score=10.0,
        pg1_score=30.0,
        pg2_score=80.0,
        ceza_1=5.0,
        ceza_2=10.0,
        category="rotary_wing"
    )
    # 10 + 30 + 80 - 15 = 105.0 / 120.0
    assert res_doner["total_score"] == 105.0
    assert res_doner["max_possible_total"] == 120.0
