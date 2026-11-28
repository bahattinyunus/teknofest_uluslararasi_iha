"""
UAV-Architect-Global: Avionics Subsystem
"""
from src.avionics.failsafe import (
    FailsafeManager,
    FailsafeLevel,
    AvionicsHealth,
    VehicleType,
    FailSafeProfile
)
from src.avionics.emergency_recovery import (
    EmergencyRecoveryManager,
    EmergencyStatusReport,
    RecoveryStatus,
    TriggerReason,
    ParachuteParams
)
from src.avionics.actuator import PayloadReleaseController, PayloadSlot, PayloadStatus
from src.avionics.preflight import PreflightChecker, PreflightReport, CheckItem
from src.avionics.power_manager import BatteryPowerManager, PowerStatus
from src.avionics.sensor_fusion_validator import (
    SensorFusionValidator,
    HealthLevel,
    FDIRAction,
    FDIRReport
)
from src.avionics.terrain_following import (
    TerrainFollowingController,
    AltitudeMode,
    TerrainState
)
from src.avionics.air_data_computer import (
    AirDataComputer,
    AirDataState,
    AirspeedAlert
)
from src.avionics.payload_grabber import (
    PayloadGrabberController,
    GrabberState,
    GrabberTelemetry
)
from src.avionics.storage_box_optimizer import (
    StorageBoxOptimizer,
    BoxGeometry,
    StorageBoxSpec,
    BoxValidationResult,
    CompetitionTeamProfile,
    CompetitorBenchmark,
    PayloadTrialRecommendation,
    ScoreOptimizationResult
)
from src.avionics.propulsion_health import (
    PropulsionHealthMonitor,
    PropulsionSnapshot,
    PropulsionHealthReport,
    PropulsionAlertLevel
)

__all__ = [
    "FailsafeManager",
    "FailsafeLevel",
    "AvionicsHealth",
    "VehicleType",
    "FailSafeProfile",
    "EmergencyRecoveryManager",
    "EmergencyStatusReport",
    "RecoveryStatus",
    "TriggerReason",
    "ParachuteParams",
    "PayloadReleaseController",
    "PayloadSlot",
    "PayloadStatus",
    "PreflightChecker",
    "PreflightReport",
    "CheckItem",
    "BatteryPowerManager",
    "PowerStatus",
    "SensorFusionValidator",
    "HealthLevel",
    "FDIRAction",
    "FDIRReport",
    "TerrainFollowingController",
    "AltitudeMode",
    "TerrainState",
    "AirDataComputer",
    "AirDataState",
    "AirspeedAlert",
    "PayloadGrabberController",
    "GrabberState",
    "GrabberTelemetry",
    "StorageBoxOptimizer",
    "BoxGeometry",
    "StorageBoxSpec",
    "BoxValidationResult",
    "CompetitionTeamProfile",
    "CompetitorBenchmark",
    "PayloadTrialRecommendation",
    "ScoreOptimizationResult",
    "PropulsionHealthMonitor",
    "PropulsionSnapshot",
    "PropulsionHealthReport",
    "PropulsionAlertLevel"
]
