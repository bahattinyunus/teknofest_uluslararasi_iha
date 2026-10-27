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
