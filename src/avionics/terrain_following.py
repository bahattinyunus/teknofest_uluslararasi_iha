"""
TEKNOFEST 2026 - Laser Terrain Following & Touchdown Flare Controller
Maintains tight Above-Ground-Level (AGL) altitude during search and release runs,
compensating for vehicle pitch/roll tilt, and executes gentle flare landing.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import math


class AltitudeMode(Enum):
    HOLD_AGL = "HOLD_AGL"        # Precision cruise/search AGL hold
    TERRAIN_FOLLOW = "TERRAIN_FOLLOW" # Tracking undulating ground
    APPROACH_DESCENT = "APPROACH_DESCENT"
    FLARE = "FLARE"              # Exponential deceleration before ground contact
    TOUCHDOWN = "TOUCHDOWN"      # Confirmed ground contact


@dataclass
class TerrainState:
    mode: AltitudeMode
    filtered_agl_m: float
    raw_range_m: float
    target_agl_m: float
    climb_rate_cmd_mps: float
    is_ground_proximity_alert: bool
    is_touchdown_confirmed: bool


class TerrainFollowingController:
    """
    Precision laser rangefinder processor and vertical velocity controller.
    Compensates for gimbal / body tilt and governs autonomous landing flare.
    """
    def __init__(self,
                 target_cruise_agl_m: float = 30.0,
                 flare_altitude_m: float = 2.0,
                 touchdown_threshold_m: float = 0.20,
                 max_climb_rate_mps: float = 2.5,
                 max_descent_rate_mps: float = 2.0,
                 flare_decay_gain: float = 0.45):
        self.target_cruise_agl = target_cruise_agl_m
        self.flare_altitude = flare_altitude_m
        self.touchdown_threshold = touchdown_threshold_m
        self.max_climb = max_climb_rate_mps
        self.max_descent = max_descent_rate_mps
        self.flare_gain = flare_decay_gain

        self.filtered_agl = target_cruise_agl_m
        self.last_agl = target_cruise_agl_m
        self.last_timestamp: Optional[float] = None
        self.mode = AltitudeMode.HOLD_AGL

    def update(self,
               timestamp: float,
               raw_laser_range_m: float,
               roll_deg: float,
               pitch_deg: float,
               is_landing_commanded: bool = False,
               vertical_accel_mps2: float = 0.0) -> TerrainState:
        """
        Updates laser altimeter state and computes vertical rate command (m/s, positive = climb).
        """
        is_first_sample = (self.last_timestamp is None)
        if is_first_sample:
            dt = 0.05
        else:
            dt = max(0.005, min(0.2, timestamp - self.last_timestamp))
        self.last_timestamp = timestamp

        # 1. Body tilt geometric projection: h_agl = R_laser * cos(roll) * cos(pitch)
        cos_roll = math.cos(math.radians(roll_deg))
        cos_pitch = math.cos(math.radians(pitch_deg))
        tilt_factor = max(0.2, cos_roll * cos_pitch)
        projected_agl = raw_laser_range_m * tilt_factor

        # 2. Outlier rejection and exponential moving average (EMA)
        # Reject obvious glitches (< 0.05m or > 120m)
        if 0.05 <= projected_agl <= 125.0:
            if is_first_sample:
                self.filtered_agl = projected_agl
            else:
                alpha = 0.35
                self.filtered_agl = alpha * projected_agl + (1.0 - alpha) * self.filtered_agl
        h_agl = self.filtered_agl

        h_dot = (h_agl - self.last_agl) / dt
        self.last_agl = h_agl

        # 3. State Machine & Mode Determination
        is_touchdown = False
        if is_landing_commanded:
            if h_agl <= self.touchdown_threshold or vertical_accel_mps2 > 5.0:
                self.mode = AltitudeMode.TOUCHDOWN
                is_touchdown = True
            elif h_agl <= self.flare_altitude:
                self.mode = AltitudeMode.FLARE
            else:
                self.mode = AltitudeMode.APPROACH_DESCENT
        else:
            self.mode = AltitudeMode.HOLD_AGL

        # 4. Vertical Velocity Command Generation
        kp = 0.8
        kd = 0.15
        climb_cmd = 0.0

        if self.mode == AltitudeMode.TOUCHDOWN:
            climb_cmd = 0.0
            target_h = 0.0
        elif self.mode == AltitudeMode.FLARE:
            # Asymptotic flare descent rate: v_down = gain * h, so climb_cmd = -v_down
            flare_v_down = max(0.2, min(self.max_descent, self.flare_gain * h_agl))
            climb_cmd = -flare_v_down
            target_h = 0.0
        elif self.mode == AltitudeMode.APPROACH_DESCENT:
            target_h = self.flare_altitude
            err_h = target_h - h_agl
            climb_cmd = max(-self.max_descent, min(self.max_climb, kp * err_h - kd * h_dot))
        else:  # HOLD_AGL / TERRAIN_FOLLOW
            target_h = self.target_cruise_agl
            err_h = target_h - h_agl
            climb_cmd = max(-self.max_descent, min(self.max_climb, kp * err_h - kd * h_dot))

        proximity_alert = (h_agl < 5.0 and not is_landing_commanded)

        return TerrainState(
            mode=self.mode,
            filtered_agl_m=round(h_agl, 2),
            raw_range_m=round(raw_laser_range_m, 2),
            target_agl_m=round(target_h, 2),
            climb_rate_cmd_mps=round(climb_cmd, 2),
            is_ground_proximity_alert=proximity_alert,
            is_touchdown_confirmed=is_touchdown
        )

    def reset(self, initial_agl: float = 30.0):
        """Resets controller state."""
        self.filtered_agl = initial_agl
        self.last_agl = initial_agl
        self.last_timestamp = None
        self.mode = AltitudeMode.HOLD_AGL
