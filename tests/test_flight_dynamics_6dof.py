import math
import pytest
from src.simulation.flight_dynamics import FlightDynamics6DOF, AircraftState6DOF, ControlInputs, AircraftAeroParams


def test_steady_level_flight_lift_balances_weight():
    sim = FlightDynamics6DOF()
    # 18 m/s sabit hızda, hafif gaz ile bir adım simüle et
    ctrl = ControlInputs(throttle=0.50, elevator_rad=-0.02)
    st = sim.step(ctrl, dt=0.02)

    # Düşey hız aşırı patlamamalı, kontrollü kalmalıdır
    assert abs(st.w) < 1.5
    assert st.u > 15.0


def test_thrust_increases_airspeed():
    sim = FlightDynamics6DOF()
    st_initial = sim.state.u

    # Tam gaz ver (%100)
    ctrl = ControlInputs(throttle=1.0, elevator_rad=0.0)
    for _ in range(25):  # 0.5 saniye
        st = sim.step(ctrl, dt=0.02)

    # İleri hız artmış olmalı
    assert st.u > st_initial


def test_elevator_produces_pitch_moment():
    sim = FlightDynamics6DOF()
    # Negatif elevatör (yukarı çekiş) -> pozitif yunuslama momenti (pitch up)
    ctrl = ControlInputs(throttle=0.5, elevator_rad=-0.15)
    for _ in range(10):  # 0.2 saniye
        st = sim.step(ctrl, dt=0.02)

    # q (pitch rate) veya theta artmış olmalıdır
    assert st.q > 0.0 or st.theta > 0.0


def test_ground_collision_clamping():
    # Yere yakın (pos_d = -0.5m) ve aşağı düşen (w = 5.0m/s) uçak
    init = AircraftState6DOF(pos_d=-0.1, w=5.0)
    sim = FlightDynamics6DOF(initial_state=init)
    ctrl = ControlInputs(throttle=0.0)
    st = sim.step(ctrl, dt=0.05)

    # Zemin kısıtı devreye girmeli (pos_d <= 0.0)
    assert st.pos_d <= 0.0
    assert st.w == 0.0
