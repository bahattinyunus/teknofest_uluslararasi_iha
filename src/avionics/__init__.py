"""
UAV-Architect-Global: Avionics Subsystem
"""
from src.avionics.failsafe import FailsafeManager, FailsafeLevel, AvionicsHealth
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
