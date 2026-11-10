"""
TEKNOFEST 2026 - L1 Adaptive Controller & Disturbance Observer (DOB) Subsystem
Provides real-time aerodynamic disturbance estimation, wind gust compensation,
and mass/CG shift compensation (e.g. after releasing Payload 1).
"""
from dataclasses import dataclass
from typing import Tuple, Optional
import math


@dataclass
class DisturbanceState:
    """Estimated lumped disturbance and compensation metrics."""
    time_s: float
    dist_x_mps2: float       # disturbance acceleration in North / X
    dist_y_mps2: float       # disturbance acceleration in East / Y
    dist_z_mps2: float       # disturbance acceleration in Down / Z
    gust_magnitude_mps2: float
    is_severe_turbulence: bool
    compensated_ax: float
    compensated_ay: float
    compensated_az: float
    desired_pitch_deg: float
    desired_roll_deg: float


class L1AdaptiveController:
    """
    Disturbance Observer (DOB) based adaptive compensator for multirotor UAVs.
    Estimates unmodeled external forces (aerodynamic drag, wind gusts, motor degradation)
    and produces feedforward anti-disturbance control signals.
    """
    GRAVITY = 9.80665

    def __init__(self,
                 obs_gain_l: float = 8.0,            # velocity observer gain
                 obs_gain_kd: float = 12.0,          # disturbance adaptation gain
                 max_compensation_mps2: float = 4.0, # saturation limit for safety
                 severe_turbulence_thresh: float = 3.5):
        self.gain_l = obs_gain_l
        self.gain_kd = obs_gain_kd
        self.max_comp = max_compensation_mps2
        self.turbulence_thresh = severe_turbulence_thresh

        # Internal state estimates
        self.hat_vx = 0.0
        self.hat_vy = 0.0
        self.hat_vz = 0.0

        self.hat_dx = 0.0
        self.hat_dy = 0.0
        self.hat_dz = 0.0

        self.last_timestamp: Optional[float] = None

    def update(self,
               timestamp: float,
               measured_vel_xyz: Tuple[float, float, float],
               applied_accel_xyz: Tuple[float, float, float],
               desired_accel_xyz: Tuple[float, float, float]) -> DisturbanceState:
        """
        Updates observer with latest sensor measurements and computes anti-disturbance commands.
        """
        meas_vx, meas_vy, meas_vz = measured_vel_xyz
        cmd_ax, cmd_ay, cmd_az = applied_accel_xyz
        des_ax, des_ay, des_az = desired_accel_xyz

        if self.last_timestamp is None:
            dt = 0.05
            self.hat_vx, self.hat_vy, self.hat_vz = meas_vx, meas_vy, meas_vz
        else:
            dt = max(0.001, min(0.2, timestamp - self.last_timestamp))
        self.last_timestamp = timestamp

        # Velocity prediction error
        err_vx = self.hat_vx - meas_vx
        err_vy = self.hat_vy - meas_vy
        err_vz = self.hat_vz - meas_vz

        # Observer derivative updates
        # d(hat_v)/dt = a_cmd + hat_d - L * (hat_v - v_meas)
        dot_vx = cmd_ax + self.hat_dx - self.gain_l * err_vx
        dot_vy = cmd_ay + self.hat_dy - self.gain_l * err_vy
        dot_vz = cmd_az + self.hat_dz - self.gain_l * err_vz

        # d(hat_d)/dt = -Kd * (hat_v - v_meas)
        dot_dx = -self.gain_kd * err_vx
        dot_dy = -self.gain_kd * err_vy
        dot_dz = -self.gain_kd * err_vz

        # Euler integration
        self.hat_vx += dot_vx * dt
        self.hat_vy += dot_vy * dt
        self.hat_vz += dot_vz * dt

        self.hat_dx += dot_dx * dt
        self.hat_dy += dot_dy * dt
        self.hat_dz += dot_dz * dt

        # Saturation of disturbance estimate
        self.hat_dx = max(-self.max_comp, min(self.max_comp, self.hat_dx))
        self.hat_dy = max(-self.max_comp, min(self.max_comp, self.hat_dy))
        self.hat_dz = max(-self.max_comp, min(self.max_comp, self.hat_dz))

        gust_mag = math.sqrt(self.hat_dx ** 2 + self.hat_dy ** 2 + self.hat_dz ** 2)
        is_severe = gust_mag >= self.turbulence_thresh

        # Compensated acceleration: a_comp = a_des - hat_d
        comp_ax = des_ax - self.hat_dx
        comp_ay = des_ay - self.hat_dy
        comp_az = des_az - self.hat_dz

        # Attitude conversion: roll/pitch tilt angles in body frame
        # theta ~= -ax / g, phi ~= ay / g
        pitch_rad = -math.atan2(comp_ax, self.GRAVITY)
        roll_rad = math.atan2(comp_ay, self.GRAVITY)

        return DisturbanceState(
            time_s=round(timestamp, 3),
            dist_x_mps2=round(self.hat_dx, 3),
            dist_y_mps2=round(self.hat_dy, 3),
            dist_z_mps2=round(self.hat_dz, 3),
            gust_magnitude_mps2=round(gust_mag, 3),
            is_severe_turbulence=is_severe,
            compensated_ax=round(comp_ax, 3),
            compensated_ay=round(comp_ay, 3),
            compensated_az=round(comp_az, 3),
            desired_pitch_deg=round(math.degrees(pitch_rad), 2),
            desired_roll_deg=round(math.degrees(roll_rad), 2)
        )

    def reset(self):
        """Resets observer states."""
        self.hat_vx = 0.0
        self.hat_vy = 0.0
        self.hat_vz = 0.0
        self.hat_dx = 0.0
        self.hat_dy = 0.0
        self.hat_dz = 0.0
        self.last_timestamp = None
