"""
Unit tests for Vision Detection and Tracking Subsystem
"""
import pytest
import cv2
import numpy as np

from src.vision.detector import VisionDetector, TargetType, TargetShape, TargetColor
from src.vision.tracker import TargetTracker
from src.vision.camera import CameraInterface


def test_synthetic_camera_generation():
    cam = CameraInterface(source="synthetic", width=640, height=480)
    ret, frame = cam.read_frame()
    assert ret is True
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    cam.release()


def test_detector_finds_targets_in_synthetic_frame():
    cam = CameraInterface(source="synthetic", width=1280, height=720)
    detector = VisionDetector()

    ret, frame = cam.read_frame()
    assert ret is True

    detections = detector.detect(frame)
    assert len(detections) >= 1

    # Should detect Target A (Blue Hexagon) or Target B (Red Triangle)
    types_found = {d.target_type for d in detections}
    assert (TargetType.TARGET_A in types_found) or (TargetType.TARGET_B in types_found)
    cam.release()


def test_hexagon_shape_classification():
    detector = VisionDetector()
    # Create an image with an ideal regular hexagon
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    center = (200, 200)
    radius = 60
    angles = np.linspace(0, 2 * np.pi, 7)[:-1]
    pts = np.array([
        [int(center[0] + radius * np.cos(a)), int(center[1] + radius * np.sin(a))]
        for a in angles
    ], dtype=np.int32)

    # Blue color: BGR (220, 100, 20) -> HSV falls in blue
    cv2.fillPoly(img, [pts], (220, 100, 20))

    detections = detector.detect(img)
    assert len(detections) >= 1
    det = detections[0]
    assert det.color == TargetColor.BLUE
    assert det.shape == TargetShape.HEXAGON
    assert det.target_type == TargetType.TARGET_A


def test_triangle_shape_classification():
    detector = VisionDetector()
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    tri_pts = np.array([
        [200, 120],
        [140, 260],
        [260, 260]
    ], dtype=np.int32)

    # Red color: BGR (20, 20, 220)
    cv2.fillPoly(img, [tri_pts], (20, 20, 220))

    detections = detector.detect(img)
    assert len(detections) >= 1
    det = detections[0]
    assert det.color == TargetColor.RED
    assert det.shape == TargetShape.TRIANGLE
    assert det.target_type == TargetType.TARGET_B


def test_tracker_smoothing():
    tracker = TargetTracker(alpha=0.5)
    cam = CameraInterface(source="synthetic", width=640, height=480)
    detector = VisionDetector()

    ret, frame = cam.read_frame()
    detections = detector.detect(frame)

    # First update
    target1 = tracker.update(detections)
    assert target1 is not None
    assert tracker.locked is True

    # Second update
    target2 = tracker.update(detections)
    assert target2 is not None

    # Empty detections - should tolerate missing frames up to threshold
    target_missing = tracker.update([])
    assert target_missing is not None
    cam.release()


def test_fixed_wing_square_shape_classification():
    detector = VisionDetector()
    # 4x4m Blue Square Target for Fixed Wing
    img_blue = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.rectangle(img_blue, (150, 150), (250, 250), (220, 100, 20), -1)

    dets_blue = detector.detect(img_blue)
    assert len(dets_blue) >= 1
    assert dets_blue[0].color == TargetColor.BLUE
    assert dets_blue[0].shape == TargetShape.SQUARE
    assert dets_blue[0].target_type == TargetType.TARGET_A

    # 2x2m Red Square Target for Fixed Wing
    img_red = np.zeros((400, 400, 3), dtype=np.uint8)
    cv2.rectangle(img_red, (150, 150), (250, 250), (20, 20, 220), -1)

    dets_red = detector.detect(img_red)
    assert len(dets_red) >= 1
    assert dets_red[0].color == TargetColor.RED
    assert dets_red[0].shape == TargetShape.SQUARE
    assert dets_red[0].target_type == TargetType.TARGET_B


def test_v7_target_specs_and_expected_payload():
    detector = VisionDetector()
    specs_fixed = detector.get_target_specs("fixed_wing")
    assert specs_fixed["scoring_radius_m"] == 20.0
    assert specs_fixed["target_a"]["dimensions_m"] == (4.0, 4.0)
    assert specs_fixed["target_a"]["payload_color"] == "red"
    assert specs_fixed["target_b"]["dimensions_m"] == (2.0, 2.0)
    assert specs_fixed["target_b"]["payload_color"] == "blue"

    specs_rotary = detector.get_target_specs("rotary_wing")
    assert specs_rotary["scoring_radius_m"] == 10.0
    assert specs_rotary["target_a"]["side_length_m"] == 2.0
    assert specs_rotary["target_a"]["payload_color"] == "red"
    assert specs_rotary["target_b"]["side_length_m"] == 1.0
    assert specs_rotary["target_b"]["payload_color"] == "blue"

    from src.vision.detector import PayloadColor
    assert detector.get_expected_payload(TargetType.TARGET_A) == PayloadColor.RED
    assert detector.get_expected_payload(TargetType.TARGET_B) == PayloadColor.BLUE
    assert detector.get_scoring_radius(TargetType.TARGET_A, "fixed_wing") == 20.0
    assert detector.get_scoring_radius(TargetType.TARGET_A, "rotary_wing") == 10.0


def test_v7_category_filtering():
    # Frame containing both Fixed Wing (Blue Square) and Rotary Wing (Blue Hexagon)
    frame = VisionDetector.generate_synthetic_frame(category="all", add_noise=False)

    # 1. Fixed Wing detector should only pick up fixed wing targets
    det_fixed = VisionDetector(category="fixed_wing")
    res_fixed = det_fixed.detect(frame)
    assert any(d.category == "fixed_wing" for d in res_fixed)
    assert not any(d.category == "rotary_wing" for d in res_fixed)

    # 2. Rotary Wing detector should only pick up rotary wing targets
    det_rotary = VisionDetector(category="rotary_wing")
    res_rotary = det_rotary.detect(frame)
    assert any(d.category == "rotary_wing" for d in res_rotary)
    assert not any(d.category == "fixed_wing" for d in res_rotary)

    # 3. All category detector should detect both
    det_all = VisionDetector(category="all")
    res_all = det_all.detect(frame)
    categories_found = {d.category for d in res_all}
    assert "fixed_wing" in categories_found
    assert "rotary_wing" in categories_found


def test_fixed_wing_cross_validation_area_ratio():
    # Generate frame with 4x4m Blue square and 2x2m Red square
    frame = VisionDetector.generate_synthetic_frame(category="fixed_wing", add_noise=False)
    det_fixed = VisionDetector(category="fixed_wing")
    results = det_fixed.detect(frame)

    assert len(results) >= 2
    types = {d.target_type for d in results}
    assert TargetType.TARGET_A in types
    assert TargetType.TARGET_B in types

    det_a = [d for d in results if d.target_type == TargetType.TARGET_A][0]
    det_b = [d for d in results if d.target_type == TargetType.TARGET_B][0]

    # Target A (4x4m) must be larger than Target B (2x2m)
    assert det_a.area > det_b.area
    # Cross-validation flag should be True
    assert det_a.cross_validated is True
    assert det_b.cross_validated is True
    assert det_a.scoring_radius_m == 20.0
    assert det_b.scoring_radius_m == 20.0
    assert det_a.payload_color == "red"
    assert det_b.payload_color == "blue"


def test_physical_dimension_estimation_with_altitude():
    detector = VisionDetector(category="fixed_wing")
    # Simulate a 100px square at 35m AGL
    bbox = (200, 200, 100, 100)
    area = 10000.0
    frame_dims = (1280, 720)
    altitude = 35.0

    phys = detector.estimate_physical_dimensions(bbox, area, frame_dims, altitude)
    assert "width_m" in phys
    assert "height_m" in phys
    assert "area_m2" in phys
    assert phys["width_m"] > 0
    assert phys["height_m"] > 0
    assert phys["area_m2"] > 0


def test_hud_rendering_with_v7_metadata():
    detector = VisionDetector(category="all")
    frame = VisionDetector.generate_synthetic_frame(category="all", add_noise=False)
    detections = detector.detect(frame)
    assert len(detections) >= 1

    hud = detector.draw_hud(frame, detections, locked_target=detections[0])
    assert hud is not None
    assert hud.shape == frame.shape

