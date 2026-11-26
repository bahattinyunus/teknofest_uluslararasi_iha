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
    "TerrainState"
]
