"""
Unit tests for Camera Calibration Subsystem
"""
import os
import pytest
import numpy as np
from src.vision.calibration import CameraCalibrator


def test_default_camera_matrix_and_fov():
    calib = CameraCalibrator(image_size=(1280, 720))
    fov_x, fov_y = calib.get_fov()

    # Default is roughly 85 degrees horizontal FOV
    assert pytest.approx(fov_x, abs=2.0) == 85.0
    assert 40.0 < fov_y < 65.0
    assert calib.is_calibrated is False


def test_undistort_with_coefficients():
    cam_matrix = np.array([
        [800.0, 0.0, 640.0],
        [0.0, 800.0, 360.0],
        [0.0, 0.0, 1.0]
    ])
    dist_coeffs = np.array([-0.2, 0.05, 0.0, 0.0, 0.0])
    calib = CameraCalibrator(camera_matrix=cam_matrix, dist_coeffs=dist_coeffs, image_size=(1280, 720))

    assert calib.is_calibrated is True
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    undistorted = calib.undistort(frame)

    assert undistorted is not None
    assert undistorted.shape == (720, 1280, 3)


def test_undistort_uncalibrated_passthrough():
    calib = CameraCalibrator(image_size=(640, 480))
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 120
    out = calib.undistort(frame)
    assert np.array_equal(frame, out)


def test_save_and_load_calibration(tmp_path):
    save_file = str(tmp_path / "camera_calib.json")
    cam_matrix = np.array([
        [900.0, 0.0, 640.0],
        [0.0, 900.0, 360.0],
        [0.0, 0.0, 1.0]
    ])
    dist_coeffs = np.array([-0.15, 0.03, 0.0, 0.0, 0.0])
    calib = CameraCalibrator(camera_matrix=cam_matrix, dist_coeffs=dist_coeffs, image_size=(1280, 720))

    calib.save_calibration(save_file)
    assert os.path.exists(save_file)

    loaded = CameraCalibrator.load_calibration(save_file)
    assert loaded.is_calibrated is True
    assert pytest.approx(loaded.camera_matrix[0, 0], abs=1e-2) == 900.0
