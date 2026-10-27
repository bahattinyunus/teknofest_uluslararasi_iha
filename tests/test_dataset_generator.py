"""
Unit tests for Synthetic Dataset Generator & Telemetry Visualizer
"""
import os
import shutil
import pytest
from src.vision.dataset_generator import SyntheticDatasetGenerator
from src.telemetry.visualizer import TelemetryVisualizer


def test_synthetic_sample_generation():
    gen = SyntheticDatasetGenerator(width=640, height=480)
    frame, annotations = gen.generate_sample()

    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert isinstance(annotations, list)


def test_synthetic_batch_generation(tmp_path):
    output_dir = str(tmp_path / "test_synth")
    gen = SyntheticDatasetGenerator(output_dir=output_dir, width=640, height=480)
    res_dir = gen.generate_batch(count=3)

    assert os.path.exists(os.path.join(res_dir, "images"))
    assert os.path.exists(os.path.join(res_dir, "labels"))
    assert os.path.exists(os.path.join(res_dir, "data.yaml"))

    images = os.listdir(os.path.join(res_dir, "images"))
    assert len(images) == 3


def test_telemetry_visualizer_hud_formatting():
    vis = TelemetryVisualizer()
    hud = vis.render_hud_text(
        state="LOCKING_TARGET_A",
        altitude_m=20.5,
        ground_speed_mps=4.2,
        heading_deg=180.0,
        pitch_deg=2.0,
        roll_deg=-3.0,
        battery_v=15.6,
        wind_speed_mps=3.5,
        wind_dir_deg=45.0,
        target_locked=True,
        target_name="TARGET_A",
        miss_dist_m=0.85,
        payloads_left=2,
        failsafe_status="NOMINAL"
    )

    assert "UAV-ARCHITECT-GLOBAL" in hud
    assert "LOCKING_TARGET_A" in hud
    assert "15.60 V" in hud
    assert "TARGET_A" in hud
