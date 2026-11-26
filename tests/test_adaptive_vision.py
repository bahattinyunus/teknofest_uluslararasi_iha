import pytest
import numpy as np
from src.vision.adaptive_vision import AdaptiveLightingNormalizer, LightingMetrics


def test_lighting_analysis_bright_and_dark():
    norm = AdaptiveLightingNormalizer()

    # Çok parlak görüntü (güneş parlaması)
    bright_frame = np.full((100, 100, 3), 245, dtype=np.uint8)
    metrics_bright = norm.analyze_lighting(bright_frame)
    assert metrics_bright.condition == "HARSH_SUNLIGHT"
    assert metrics_bright.mean_brightness > 200.0

    # Çok karanlık görüntü (gölge altı)
    dark_frame = np.full((100, 100, 3), 30, dtype=np.uint8)
    metrics_dark = norm.analyze_lighting(dark_frame)
    assert metrics_dark.condition in ("OVERCAST_SHADOW", "LOW_LIGHT")
    assert metrics_dark.mean_brightness < 45.0


def test_adaptive_hsv_ranges_for_targets():
    norm = AdaptiveLightingNormalizer()

    metrics_harsh = LightingMetrics(mean_brightness=220.0, std_brightness=20.0, glare_ratio=0.3, shadow_ratio=0.01, condition="HARSH_SUNLIGHT")
    metrics_shadow = LightingMetrics(mean_brightness=50.0, std_brightness=15.0, glare_ratio=0.01, shadow_ratio=0.4, condition="OVERCAST_SHADOW")

    # Kırmızı Altıgen (Target A)
    ranges_harsh = norm.get_adaptive_hsv_ranges("TARGET_A", metrics_harsh)
    ranges_shadow = norm.get_adaptive_hsv_ranges("TARGET_A", metrics_shadow)

    assert len(ranges_harsh) == 2
    assert len(ranges_shadow) == 2
    # Güneş parlamasında S_min düşürülür
    assert ranges_harsh[0][0][1] <= ranges_shadow[0][0][1]

    # Mavi Üçgen (Target B)
    blue_harsh = norm.get_adaptive_hsv_ranges("TARGET_B", metrics_harsh)
    blue_shadow = norm.get_adaptive_hsv_ranges("TARGET_B", metrics_shadow)
    assert len(blue_harsh) == 1
    assert blue_harsh[0][0][0] == 100
    assert blue_harsh[0][1][0] == 135


def test_clahe_and_target_preprocessing():
    norm = AdaptiveLightingNormalizer()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Ortaya parlak kırmızı altıgen benzeri kutu çiz
    frame[30:70, 30:70] = [0, 0, 220]  # BGR formatında Kırmızı

    res = norm.preprocess_for_target(frame, "TARGET_A")
    assert "lighting" in res
    assert "mask" in res
    assert res["processed_frame"] is not None
    # Maske içerisinde tespit edilmiş pikseller olmalı
    assert np.count_nonzero(res["mask"]) > 0


def test_normalized_chromaticity_dimensions():
    norm = AdaptiveLightingNormalizer()
    frame = np.random.randint(0, 256, (80, 80, 3), dtype=np.uint8)
    ncc = norm.extract_normalized_chromaticity(frame)
    assert ncc.shape == frame.shape
