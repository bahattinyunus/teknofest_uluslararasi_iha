"""
TEKNOFEST 2026 - Optik Akış Görsel Odometri (OpticalFlowOdometry) Testleri
"""

import numpy as np
from src.vision.optical_flow_odometry import OpticalFlowOdometry


def test_optical_flow_detects_known_translation():
    rng = np.random.default_rng(2026)
    base_img = rng.integers(0, 255, size=(240, 320), dtype=np.uint8)
    # 10 piksel sağa (x+), 4 piksel aşağı (y+) kaydırılmış ikinci kare
    shifted = np.roll(np.roll(base_img, shift=10, axis=1), shift=4, axis=0)

    vo = OpticalFlowOdometry(hfov_deg=85.0, process_size=(160, 120), ema_alpha=1.0)
    est1 = vo.update(base_img, altitude_agl_m=20.0, dt_s=0.05)
    assert est1.valid is False  # İlk karede referans kurulur

    est2 = vo.update(shifted, altitude_agl_m=20.0, dt_s=0.05)
    assert est2.valid is True
    assert est2.quality_score > 0.3
    # 320x240 -> 160x120 ölçeklemede shift_x ~ +5.0 px, shift_y ~ +2.0 px
    assert abs(est2.pixel_shift_xy[0] - 5.0) < 0.8
    assert abs(est2.pixel_shift_xy[1] - 2.0) < 0.8
    # Pozitif sahne kayması -> negatif yer hızı
    assert est2.vy_mps < 0.0
    assert est2.vx_mps < 0.0


def test_optical_flow_reset_clears_state():
    vo = OpticalFlowOdometry()
    img = np.zeros((120, 160), dtype=np.uint8)
    vo.update(img, altitude_agl_m=15.0)
    vo.reset()
    est = vo.update(img, altitude_agl_m=15.0)
    assert est.valid is False
