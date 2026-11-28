"""
UAV-Architect-Global: Vision Subsystem
"""
from src.vision.detector import (
    VisionDetector,
    TargetDetection,
    TargetType,
    TargetShape,
    TargetColor,
    TargetCategory,
    PayloadColor,
    OFFICIAL_TARGET_SPECS_V7
)
from src.vision.tracker import TargetTracker
from src.vision.camera import CameraInterface
from src.vision.dataset_generator import SyntheticDatasetGenerator
from src.vision.calibration import CameraCalibrator
from src.vision.target_classifier import TargetClassifier, TrackedTarget
from src.vision.multi_target_fusion import (
    MultiTargetFusionTracker,
    FusedTargetTrack,
    TrackStatus
)
from src.vision.optical_flow_odometry import (
    OpticalFlowOdometry,
    OpticalFlowEstimate
)

__all__ = [
    "VisionDetector",
    "TargetDetection",
    "TargetType",
    "TargetShape",
    "TargetColor",
    "TargetCategory",
    "PayloadColor",
    "OFFICIAL_TARGET_SPECS_V7",
    "TargetTracker",
    "CameraInterface",
    "SyntheticDatasetGenerator",
    "CameraCalibrator",
    "TargetClassifier",
    "TrackedTarget",
    "MultiTargetFusionTracker",
    "FusedTargetTrack",
    "TrackStatus",
    "OpticalFlowOdometry",
    "OpticalFlowEstimate"
]
