"""
TEKNOFEST 2026 - Malatya Tulga Monte Carlo Yarışma Hazırlık Kıyaslama Testleri
"""

from src.simulation.mission_benchmark import (
    MissionReadinessBenchmark,
    BenchmarkConfig,
)


def test_rotary_wing_benchmark_report_metrics():
    bench = MissionReadinessBenchmark(BenchmarkConfig(num_runs=30, category="rotary_wing", seed=42))
    rep = bench.run()

    assert rep.num_runs == 30
    assert rep.scoring_radius_m == 10.0
    # Malatya Tulga 938m MSL hava yoğunluğu deniz seviyesinden (1.225) düşük olmalıdır
    assert 0.95 < rep.tulga_air_density_kgpm3 < 1.18
    assert rep.cep50_m <= rep.cep90_m
    assert 0.0 <= rep.in_radius_success_rate_pct <= 100.0
    assert 0.0 <= rep.readiness_index_0_100 <= 100.0
    assert len(rep.outcomes) == 30


def test_fixed_wing_benchmark_deterministic_seed():
    cfg = BenchmarkConfig(num_runs=25, category="fixed_wing", seed=2026)
    rep1 = MissionReadinessBenchmark(cfg).run()
    rep2 = MissionReadinessBenchmark(cfg).run()

    assert rep1.scoring_radius_m == 20.0
    assert rep1.cep50_m == rep2.cep50_m
    assert rep1.mean_total_flight_score == rep2.mean_total_flight_score
    assert rep1.readiness_index_0_100 == rep2.readiness_index_0_100
