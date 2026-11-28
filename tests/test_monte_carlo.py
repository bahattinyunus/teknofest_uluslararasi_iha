"""
Unit tests for MonteCarloDropSimulator (CEP50, R95, Hit Probability)
"""
from src.simulation.monte_carlo import MonteCarloDropSimulator, MonteCarloConfig


def test_monte_carlo_rotary_wing_nominal_high_hit_rate():
    cfg = MonteCarloConfig(
        num_trials=150,
        seed=42,
        category="rotary_wing",
        release_altitude_m=18.0,
        ground_speed_mps=10.0,
        wind_gust_std_mps=0.8
    )
    sim = MonteCarloDropSimulator(cfg)
    res = sim.run()

    assert res.num_trials == 150
    assert res.scoring_radius_m == 10.0
    assert 0.0 <= res.cep50_m <= res.r95_m <= res.max_error_m
    assert res.hit_probability_pct >= 95.0
    assert len(res.radial_errors_m) == 150


def test_monte_carlo_higher_wind_increases_cep50():
    sim = MonteCarloDropSimulator()
    calm = sim.run(MonteCarloConfig(num_trials=120, seed=7, wind_gust_std_mps=0.3, altitude_noise_std_m=0.2))
    gusty = sim.run(MonteCarloConfig(num_trials=120, seed=7, wind_gust_std_mps=3.5, altitude_noise_std_m=1.0))

    assert gusty.cep50_m > calm.cep50_m
    assert gusty.r95_m > calm.r95_m


def test_monte_carlo_fixed_wing_20m_radius():
    cfg = MonteCarloConfig(num_trials=100, seed=99, category="fixed_wing", release_altitude_m=25.0, ground_speed_mps=18.0)
    res = MonteCarloDropSimulator(cfg).run()
    assert res.scoring_radius_m == 20.0
    assert res.hit_probability_pct >= 90.0
