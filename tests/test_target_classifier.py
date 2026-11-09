"""
Unit tests for Target Classifier and Multi-Target Tracking Subsystem
"""
import pytest
from src.vision.target_classifier import (
    TargetClassifier,
    TargetType,
    TargetDetection,
    TrackedTarget
)


def test_classify_blue_regular_hexagon():
    classifier = TargetClassifier()
    # Regular hexagon properties: 6 vertices, circularity around 0.907
    # For perimeter = 60, regular hexagon side = 10 -> area = (3*sqrt(3)/2)*100 ~= 259.8
    # circularity = 4 * pi * 259.8 / 3600 ~= 0.9069
    det = classifier.classify_contour(
        vertices=6,
        area=259.8,
        perimeter=60.0,
        color_name="blue",
        bbox=(200, 150, 80, 80)
    )
    assert det.target_type == TargetType.TARGET_A_HEXAGON
    assert det.confidence >= 0.70
    assert det.color_purity == 1.0


def test_classify_red_equilateral_triangle():
    classifier = TargetClassifier()
    # Equilateral triangle: 3 vertices, circularity around 0.605
    # side = 20, perimeter = 60, area = (sqrt(3)/4)*400 ~= 173.2
    # circularity = 4 * pi * 173.2 / 3600 ~= 0.6046
    det = classifier.classify_contour(
        vertices=3,
        area=173.2,
        perimeter=60.0,
        color_name="red",
        bbox=(300, 250, 70, 70)
    )
    assert det.target_type == TargetType.TARGET_B_TRIANGLE
    assert det.confidence >= 0.70
    assert det.color_purity == 1.0


def test_tracking_temporal_confirmation():
    classifier = TargetClassifier(min_confirmation_hits=3)
    det = TargetDetection(
        target_type=TargetType.TARGET_A_HEXAGON,
        confidence=0.85,
        bbox=(200, 200, 50, 50),
        center_norm=(0.1, 0.1),
        num_vertices=6,
        circularity=0.90,
        color_purity=1.0,
        area_px=2000.0
    )

    # Frame 1: track created, not yet confirmed
    tracks = classifier.update_tracks([det])
    assert len(tracks) == 1
    assert not tracks[0].is_confirmed
    assert classifier.get_confirmed_target(TargetType.TARGET_A_HEXAGON) is None

    # Frame 2: hit count 2
    tracks = classifier.update_tracks([det])
    assert not tracks[0].is_confirmed

    # Frame 3: hit count 3 -> confirmed!
    tracks = classifier.update_tracks([det])
    assert tracks[0].is_confirmed
    assert classifier.get_confirmed_target(TargetType.TARGET_A_HEXAGON) is not None


def test_tracking_occlusion_and_pruning():
    classifier = TargetClassifier(min_confirmation_hits=1, max_lost_frames=2)
    det = TargetDetection(
        target_type=TargetType.TARGET_B_TRIANGLE,
        confidence=0.90,
        bbox=(100, 100, 40, 40),
        center_norm=(-0.2, -0.2),
        num_vertices=3,
        circularity=0.60,
        color_purity=1.0,
        area_px=1500.0
    )
    classifier.update_tracks([det])
    assert len(classifier.tracks) == 1

    # Lost frame 1: track kept
    classifier.update_tracks([])
    assert len(classifier.tracks) == 1

    # Lost frame 2: track kept
    classifier.update_tracks([])
    assert len(classifier.tracks) == 1

    # Lost frame 3: exceeds max_lost_frames=2 -> pruned
    classifier.update_tracks([])
    assert len(classifier.tracks) == 0
