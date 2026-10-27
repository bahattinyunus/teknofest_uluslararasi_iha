"""
UAV-Architect-Global: Avionics Subsystem
"""
from src.avionics.failsafe import FailsafeManager, FailsafeLevel, AvionicsHealth
from src.avionics.actuator import PayloadReleaseController, PayloadSlot, PayloadStatus

__all__ = [
    "FailsafeManager",
    "FailsafeLevel",
    "AvionicsHealth",
    "PayloadReleaseController",
    "PayloadSlot",
    "PayloadStatus"
]
