"""
TEKNOFEST 2026 - Sensor Health, Voting & FDIR Subsystem (Fault Detection, Isolation, Recovery)
Implements Triple Modular Redundancy (TMR) cross-checking, residual analysis,
and automatic sensor isolation to prevent crashes caused by GPS jamming or sensor glitches.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math


class HealthLevel(Enum):
    NOMINAL = "NOMINAL"        # All redundant sensors agree within threshold
    DEGRADED = "DEGRADED"      # One sensor has glitched/failed; backup is active
    CRITICAL = "CRITICAL"      # Redundancy lost or critical disagreement across sources


class FDIRAction(Enum):
    CONTINUE = "CONTINUE"
    WARN_OPERATOR = "WARN_OPERATOR"
    SWITCH_TO_DEAD_RECKONING = "SWITCH_TO_DEAD_RECKONING"
    TRIGGER_RTL = "TRIGGER_RTL"
    EMERGENCY_LAND = "EMERGENCY_LAND"


@dataclass
class SensorChannelStatus:
    name: str
    is_healthy: bool = True
    consecutive_faults: int = 0
    last_fault_reason: str = ""
    last_value: float = 0.0


@dataclass
class FDIRReport:
    timestamp: float
    health_level: HealthLevel
    recommended_action: FDIRAction
    validated_altitude_m: float
    validated_speed_mps: float
    validated_heading_deg: float
    isolated_sensors: List[str] = field(default_factory=list)
    diagnostic_messages: List[str] = field(default_factory=list)


class SensorFusionValidator:
    """
    Multi-sensor cross-validator and isolation engine.
    Ensures avionics integrity for high-stakes competition flight.
    """
    def __init__(self,
                 max_alt_residual_m: float = 2.5,        # max allowed discrepancy between altitude sources
                 max_speed_residual_mps: float = 2.0,    # max allowed velocity residual
                 max_heading_residual_deg: float = 20.0, # max compass vs GPS heading diff
                 fault_latch_count: int = 3):            # consecutive faults to isolate sensor
        self.max_alt_residual_m = max_alt_residual_m
        self.max_speed_residual_mps = max_speed_residual_mps
        self.max_heading_residual_deg = max_heading_residual_deg
        self.fault_latch_count = fault_latch_count

        self.channels: Dict[str, SensorChannelStatus] = {
            "baro_alt": SensorChannelStatus("baro_alt"),
            "lidar_alt": SensorChannelStatus("lidar_alt"),
            "gps_alt": SensorChannelStatus("gps_alt"),
            "gps_speed": SensorChannelStatus("gps_speed"),
            "flow_speed": SensorChannelStatus("flow_speed"),
            "imu_speed": SensorChannelStatus("imu_speed"),
            "mag_heading": SensorChannelStatus("mag_heading"),
            "gps_cog": SensorChannelStatus("gps_cog"),
            "gyro_yaw": SensorChannelStatus("gyro_yaw"),
        }

    def _update_channel_fault(self, channel_name: str, has_fault: bool, reason: str, value: float):
        ch = self.channels[channel_name]
        ch.last_value = value
        if has_fault:
            ch.consecutive_faults += 1
            ch.last_fault_reason = reason
            if ch.consecutive_faults >= self.fault_latch_count:
                ch.is_healthy = False
        else:
            ch.consecutive_faults = max(0, ch.consecutive_faults - 1)
            if ch.consecutive_faults == 0:
                ch.is_healthy = True
                ch.last_fault_reason = ""

    def validate_sensors(self,
                         timestamp: float,
                         baro_alt: Optional[float] = None,
                         lidar_alt: Optional[float] = None,
                         gps_alt: Optional[float] = None,
                         gps_vx: Optional[float] = None,
                         gps_vy: Optional[float] = None,
                         flow_vx: Optional[float] = None,
                         flow_vy: Optional[float] = None,
                         imu_vx: Optional[float] = None,
                         imu_vy: Optional[float] = None,
                         mag_heading: Optional[float] = None,
                         gps_cog: Optional[float] = None,
                         gyro_yaw: Optional[float] = None) -> FDIRReport:
        """
        Executes TMR residual checking across all active sensor channels.
        """
        diagnostics: List[str] = []
        isolated: List[str] = []

        # ---------------- 1. ALTITUDE VALIDATION ----------------
        alt_sources: List[Tuple[str, float]] = []
        if baro_alt is not None:
            alt_sources.append(("baro_alt", baro_alt))
        if lidar_alt is not None:
            alt_sources.append(("lidar_alt", lidar_alt))
        if gps_alt is not None:
            alt_sources.append(("gps_alt", gps_alt))

        validated_alt = 0.0
        if alt_sources:
            vals = [val for _, val in alt_sources]
            median_alt = sorted(vals)[len(vals) // 2]

            for name, val in alt_sources:
                residual = abs(val - median_alt)
                is_fault = residual > self.max_alt_residual_m
                if is_fault:
                    diagnostics.append(f"{name} residual high: {residual:.2f}m > {self.max_alt_residual_m}m")
                self._update_channel_fault(name, is_fault, f"residual {residual:.1f}m", val)

            # Validated alt from healthy sources
            healthy_alts = [val for name, val in alt_sources if self.channels[name].is_healthy]
            validated_alt = sum(healthy_alts) / len(healthy_alts) if healthy_alts else median_alt

        # ---------------- 2. SPEED VALIDATION ----------------
        speed_sources: List[Tuple[str, float]] = []
        if gps_vx is not None and gps_vy is not None:
            speed_sources.append(("gps_speed", math.hypot(gps_vx, gps_vy)))
        if flow_vx is not None and flow_vy is not None:
            speed_sources.append(("flow_speed", math.hypot(flow_vx, flow_vy)))
        if imu_vx is not None and imu_vy is not None:
            speed_sources.append(("imu_speed", math.hypot(imu_vx, imu_vy)))

        validated_speed = 0.0
        if speed_sources:
            s_vals = [s for _, s in speed_sources]
            median_speed = sorted(s_vals)[len(s_vals) // 2]

            for name, s in speed_sources:
                residual = abs(s - median_speed)
                is_fault = residual > self.max_speed_residual_mps
                if is_fault:
                    diagnostics.append(f"{name} residual high: {residual:.2f}m/s > {self.max_speed_residual_mps}m/s")
                self._update_channel_fault(name, is_fault, f"residual {residual:.1f}m/s", s)

            healthy_speeds = [s for name, s in speed_sources if self.channels[name].is_healthy]
            validated_speed = sum(healthy_speeds) / len(healthy_speeds) if healthy_speeds else median_speed

        # ---------------- 3. HEADING VALIDATION ----------------
        hdg_sources: List[Tuple[str, float]] = []
        if mag_heading is not None:
            hdg_sources.append(("mag_heading", mag_heading % 360.0))
        if gps_cog is not None and validated_speed > 1.5:  # COG only valid when moving
            hdg_sources.append(("gps_cog", gps_cog % 360.0))
        if gyro_yaw is not None:
            hdg_sources.append(("gyro_yaw", gyro_yaw % 360.0))

        validated_hdg = 0.0
        if hdg_sources:
            # Circular mean for angle voting
            sin_sum = sum(math.sin(math.radians(deg)) for _, deg in hdg_sources)
            cos_sum = sum(math.cos(math.radians(deg)) for _, deg in hdg_sources)
            mean_hdg = (math.degrees(math.atan2(sin_sum, cos_sum)) + 360.0) % 360.0

            for name, deg in hdg_sources:
                diff = abs((deg - mean_hdg + 180.0) % 360.0 - 180.0)
                is_fault = diff > self.max_heading_residual_deg
                if is_fault:
                    diagnostics.append(f"{name} angular diff high: {diff:.1f} deg > {self.max_heading_residual_deg} deg")
                self._update_channel_fault(name, is_fault, f"angular diff {diff:.1f} deg", deg)

            healthy_hdgs = [deg for name, deg in hdg_sources if self.channels[name].is_healthy]
            if healthy_hdgs:
                h_sin = sum(math.sin(math.radians(d)) for d in healthy_hdgs)
                h_cos = sum(math.cos(math.radians(d)) for d in healthy_hdgs)
                validated_hdg = (math.degrees(math.atan2(h_sin, h_cos)) + 360.0) % 360.0
            else:
                validated_hdg = mean_hdg

        # ---------------- 4. FAULT ISOLATION & ACTION LOGIC ----------------
        isolated = [name for name, ch in self.channels.items() if not ch.is_healthy]
        unhealthy_count = len(isolated)

        if unhealthy_count == 0:
            health_level = HealthLevel.NOMINAL
            action = FDIRAction.CONTINUE
        elif unhealthy_count <= 2:
            health_level = HealthLevel.DEGRADED
            # If GPS speed or GPS alt is faulty, switch to dead reckoning
            if not self.channels["gps_speed"].is_healthy or not self.channels["gps_alt"].is_healthy:
                action = FDIRAction.SWITCH_TO_DEAD_RECKONING
            else:
                action = FDIRAction.WARN_OPERATOR
        else:
            health_level = HealthLevel.CRITICAL
            # Multiple critical channels failed
            if not self.channels["baro_alt"].is_healthy and not self.channels["lidar_alt"].is_healthy:
                action = FDIRAction.EMERGENCY_LAND
            else:
                action = FDIRAction.TRIGGER_RTL

        return FDIRReport(
            timestamp=round(timestamp, 3),
            health_level=health_level,
            recommended_action=action,
            validated_altitude_m=round(validated_alt, 2),
            validated_speed_mps=round(validated_speed, 2),
            validated_heading_deg=round(validated_hdg, 1),
            isolated_sensors=isolated,
            diagnostic_messages=diagnostics
        )

    def reset(self):
        """Resets all fault counters and health statuses."""
        for ch in self.channels.values():
            ch.is_healthy = True
            ch.consecutive_faults = 0
            ch.last_fault_reason = ""
            ch.last_value = 0.0
