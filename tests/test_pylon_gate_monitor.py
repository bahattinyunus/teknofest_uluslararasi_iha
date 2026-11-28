"""
TEKNOFEST 2026 - 150m Referans Direkleri Dış Dönüş & ∞ Kapı İzleyici Testleri
"""

import math
from src.navigation.pylon_gate_monitor import PylonGateMonitor, TurnComplianceState


def test_pole_2_outer_turn_authorizes_vision_scan():
    mon = PylonGateMonitor()

    # Başlangıçta tarama yetkisi kapalı
    st0 = mon.update(0.0, 0.0)
    assert st0.pole_2_outer_turn_verified is False
    assert st0.vision_scan_authorized is False

    # 2. direk (-75, 0) etrafında dıştan (x < -75) 180 derece dönüş
    for deg in range(0, 210, 30):
        rad = math.radians(deg)
        x = -75.0 - 20.0 * math.sin(rad)
        y = 20.0 * math.cos(rad)
        mon.update(x, y)

    # Tarama alanına giriş (0, 0) -> yetki açık ve Ceza 2 = 0
    st_scan = mon.update(0.0, 0.0)
    assert st_scan.pole_2_outer_turn_verified is True
    assert st_scan.vision_scan_authorized is True
    assert st_scan.estimated_penalty_2_pts == 0.0


def test_inside_turn_triggers_penalty_2_violation():
    mon = PylonGateMonitor()
    # 2. direğe yaklaş ama x = -60'tan (direğin içinden!) geri doğuya dönüp tarama alanına gir
    for x in [-20.0, -40.0, -60.0, -55.0, -45.0, -30.0]:
        st = mon.update(x, 5.0)

    assert st.compliance_state == TurnComplianceState.INSIDE_TURN_VIOLATION
    assert st.estimated_penalty_2_pts > 0.0
    assert len(st.violations) >= 1


def test_figure_eight_two_laps_and_finish_line():
    mon = PylonGateMonitor(required_figure_eight_laps=2)

    def circle_pole_2():
        for deg in range(0, 210, 30):
            rad = math.radians(deg)
            mon.update(-75.0 - 20.0 * math.sin(rad), 20.0 * math.cos(rad))

    def circle_pole_1():
        for deg in range(0, 210, 30):
            rad = math.radians(deg)
            mon.update(75.0 + 20.0 * math.sin(rad), 20.0 * math.cos(rad))

    # İlk Direk 2 dış dönüşü + 2 tam ∞ turu (P1 -> P2 -> P1 -> P2)
    circle_pole_2()
    circle_pole_1()
    circle_pole_2()
    circle_pole_1()
    circle_pole_2()

    # Bitiş çizgisini geç (x < 0 -> x > 0)
    mon.update(-10.0, 0.0)
    st_fin = mon.update(5.0, 0.0)
    assert st_fin.figure_eight_laps_completed >= 2
    assert st_fin.compliance_state == TurnComplianceState.TASK_1_LAPS_COMPLETE
    assert st_fin.finish_line_crossed is True
