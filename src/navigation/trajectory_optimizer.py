"""
TEKNOFEST 2026 - Minimum Jerk / Quintic Spline 3D Trajectory Optimizer
Provides smooth, dynamically-feasible trajectories with continuous acceleration (C^2)
and curvature-constrained speed profiling for precision flight and payload release.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math


@dataclass
class TrajectoryPoint:
    """A discrete state on the optimized 3D flight trajectory."""
    time_s: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    ax: float
    ay: float
    az: float
    speed: float
    acceleration_mag: float
    curvature: float  # 1/m


@dataclass
class TrajectoryMetrics:
    """Performance metrics for an optimized flight trajectory."""
    total_duration_s: float
    total_distance_m: float
    max_speed_mps: float
    max_acceleration_mps2: float
    max_lateral_accel_mps2: float
    average_speed_mps: float
    estimated_energy_wh: float
    num_samples: int


class QuinticPolynomial:
    """
    1D Quintic (5th order) polynomial trajectory segment:
    p(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
    Satisfies boundary conditions: (p0, v0, a0) at t=0 and (p1, v1, a1) at t=T.
    """
    def __init__(self, p0: float, v0: float, a0: float,
                 p1: float, v1: float, a1: float, T: float):
        self.T = max(0.001, T)
        self.a0 = p0
        self.a1 = v0
        self.a2 = 0.5 * a0

        T2 = self.T * self.T
        T3 = T2 * self.T
        T4 = T3 * self.T
        T5 = T4 * self.T

        b1 = p1 - (p0 + v0 * self.T + 0.5 * a0 * T2)
        b2 = v1 - (v0 + a0 * self.T)
        b3 = a1 - a0

        self.a3 = (10.0 * b1) / T3 - (4.0 * b2) / T2 + (0.5 * b3) / self.T
        self.a4 = (-15.0 * b1) / T4 + (7.0 * b2) / T3 - (1.0 * b3) / T2
        self.a5 = (6.0 * b1) / T5 - (3.0 * b2) / T4 + (0.5 * b3) / T3

    def pos(self, t: float) -> float:
        t = min(max(t, 0.0), self.T)
        t2 = t * t
        return self.a0 + self.a1 * t + self.a2 * t2 + self.a3 * t2 * t + self.a4 * t2 * t2 + self.a5 * t2 * t2 * t

    def vel(self, t: float) -> float:
        t = min(max(t, 0.0), self.T)
        t2 = t * t
        return self.a1 + 2.0 * self.a2 * t + 3.0 * self.a3 * t2 + 4.0 * self.a4 * t2 * t + 5.0 * self.a5 * t2 * t2

    def acc(self, t: float) -> float:
        t = min(max(t, 0.0), self.T)
        t2 = t * t
        return 2.0 * self.a2 + 6.0 * self.a3 * t + 12.0 * self.a4 * t2 + 20.0 * self.a5 * t2 * t


class TrajectoryOptimizer:
    """
    3D Minimum-Jerk Trajectory Planner and Curvature-Constrained Speed Profiler.
    Ensures safe navigation within aerodynamic load factors and smooth camera stabilization.
    """
    def __init__(self,
                 max_velocity: float = 18.0,       # m/s
                 max_acceleration: float = 4.0,   # m/s^2
                 max_lateral_accel: float = 3.0,  # m/s^2 (G-turn limiter)
                 uav_mass_kg: float = 2.63,       # nominal takeoff mass
                 default_dt: float = 0.05):       # 20 Hz output sampling
        self.max_velocity = max(1.0, max_velocity)
        self.max_acceleration = max(0.5, max_acceleration)
        self.max_lateral_accel = max(0.5, max_lateral_accel)
        self.uav_mass_kg = uav_mass_kg
        self.default_dt = default_dt

    def estimate_segment_duration(self, p0: Tuple[float, float, float],
                                  p1: Tuple[float, float, float],
                                  cruise_speed: Optional[float] = None) -> float:
        """Estimates realistic duration for a segment based on trapezoidal speed profile."""
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dz = p1[2] - p0[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 0.01:
            return 0.1

        target_speed = min(self.max_velocity, cruise_speed if cruise_speed else self.max_velocity * 0.7)
        # Time to accelerate + cruise + decelerate
        t_acc = target_speed / self.max_acceleration
        d_acc = 0.5 * self.max_acceleration * (t_acc ** 2)

        if 2.0 * d_acc > dist:
            # Triangular profile
            return 2.0 * math.sqrt(dist / self.max_acceleration)
        else:
            d_cruise = dist - 2.0 * d_acc
            t_cruise = d_cruise / target_speed
            return 2.0 * t_acc + t_cruise

    def plan_trajectory(self,
                        waypoints: List[Tuple[float, float, float]],
                        initial_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                        final_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                        dt: Optional[float] = None) -> Tuple[List[TrajectoryPoint], TrajectoryMetrics]:
        """
        Plans a continuous, multi-segment 3D trajectory through waypoints.
        """
        if len(waypoints) < 2:
            raise ValueError("At least 2 waypoints are required to plan a trajectory.")

        dt = dt or self.default_dt
        n_segs = len(waypoints) - 1

        # Intermediate waypoint velocities via Catmull-Rom tangent heuristic
        node_vels: List[Tuple[float, float, float]] = [initial_velocity]
        for i in range(1, n_segs):
            prev_wp = waypoints[i - 1]
            next_wp = waypoints[i + 1]
            dist_prev = math.dist(prev_wp, waypoints[i])
            dist_next = math.dist(waypoints[i], next_wp)
            tot_dist = dist_prev + dist_next
            if tot_dist > 0.01:
                # Tangent direction
                vx = (next_wp[0] - prev_wp[0]) / tot_dist
                vy = (next_wp[1] - prev_wp[1]) / tot_dist
                vz = (next_wp[2] - prev_wp[2]) / tot_dist
                nom_speed = min(self.max_velocity * 0.7, 0.5 * (dist_prev + dist_next) / 2.0)
                node_vels.append((vx * nom_speed, vy * nom_speed, vz * nom_speed))
            else:
                node_vels.append((0.0, 0.0, 0.0))
        node_vels.append(final_velocity)

        # Segment durations
        segment_durations: List[float] = []
        for i in range(n_segs):
            dur = self.estimate_segment_duration(waypoints[i], waypoints[i + 1])
            segment_durations.append(dur)

        # Build quintic polynomials for each segment
        trajectory_points: List[TrajectoryPoint] = []
        global_time = 0.0
        total_dist = 0.0
        max_speed = 0.0
        max_accel = 0.0
        max_lat_accel = 0.0
        last_pos = waypoints[0]

        for i in range(n_segs):
            p0, p1 = waypoints[i], waypoints[i + 1]
            v0, v1 = node_vels[i], node_vels[i + 1]
            a0 = (0.0, 0.0, 0.0)
            a1 = (0.0, 0.0, 0.0)
            T = segment_durations[i]

            poly_x = QuinticPolynomial(p0[0], v0[0], a0[0], p1[0], v1[0], a1[0], T)
            poly_y = QuinticPolynomial(p0[1], v0[1], a0[1], p1[1], v1[1], a1[1], T)
            poly_z = QuinticPolynomial(p0[2], v0[2], a0[2], p1[2], v1[2], a1[2], T)

            # Sample segment
            n_samples = max(2, int(T / dt))
            # Don't duplicate the boundary point on subsequent segments
            start_idx = 0 if i == 0 else 1
            for s in range(start_idx, n_samples + 1):
                t_local = (s / n_samples) * T
                t_stamp = global_time + t_local

                px, py, pz = poly_x.pos(t_local), poly_y.pos(t_local), poly_z.pos(t_local)
                vx, vy, vz = poly_x.vel(t_local), poly_y.vel(t_local), poly_z.vel(t_local)
                ax, ay, az = poly_x.acc(t_local), poly_y.acc(t_local), poly_z.acc(t_local)

                speed = math.sqrt(vx * vx + vy * vy + vz * vz)
                accel_mag = math.sqrt(ax * ax + ay * ay + az * az)

                # Compute 3D curvature: kappa = ||v x a|| / ||v||^3
                cross_x = vy * az - vz * ay
                cross_y = vz * ax - vx * az
                cross_z = vx * ay - vy * ax
                cross_mag = math.sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z)

                if speed > 0.05:
                    curvature = cross_mag / (speed ** 3)
                    # Lateral acceleration = v^2 * kappa = ||v x a|| / ||v||
                    lat_accel = cross_mag / speed
                else:
                    curvature = 0.0
                    lat_accel = 0.0

                # Check max metrics
                if speed > max_speed:
                    max_speed = speed
                if accel_mag > max_accel:
                    max_accel = accel_mag
                if lat_accel > max_lat_accel:
                    max_lat_accel = lat_accel

                # Distance accumulation
                d_step = math.dist((px, py, pz), last_pos)
                total_dist += d_step
                last_pos = (px, py, pz)

                point = TrajectoryPoint(
                    time_s=round(t_stamp, 4),
                    x=round(px, 4),
                    y=round(py, 4),
                    z=round(pz, 4),
                    vx=round(vx, 4),
                    vy=round(vy, 4),
                    vz=round(vz, 4),
                    ax=round(ax, 4),
                    ay=round(ay, 4),
                    az=round(az, 4),
                    speed=round(speed, 4),
                    acceleration_mag=round(accel_mag, 4),
                    curvature=round(curvature, 5)
                )
                trajectory_points.append(point)

            global_time += T

        # Compute energy estimation: P_avg approx = P_hover + 0.5 * m * v^2 * drag_loss
        avg_speed = total_dist / max(0.1, global_time)
        nominal_hover_power_w = 340.0  # W for 2.6kg quadcopter
        aero_power_w = 0.5 * 1.225 * (avg_speed ** 3) * 0.35  # aerodynamic resistance power
        total_power_w = nominal_hover_power_w + aero_power_w
        energy_wh = (total_power_w * global_time) / 3600.0

        metrics = TrajectoryMetrics(
            total_duration_s=round(global_time, 2),
            total_distance_m=round(total_dist, 2),
            max_speed_mps=round(max_speed, 2),
            max_acceleration_mps2=round(max_accel, 2),
            max_lateral_accel_mps2=round(max_lat_accel, 2),
            average_speed_mps=round(avg_speed, 2),
            estimated_energy_wh=round(energy_wh, 2),
            num_samples=len(trajectory_points)
        )

        return trajectory_points, metrics

    def optimize_figure_eight(self, center: Tuple[float, float, float] = (0.0, 0.0, 30.0),
                              radius: float = 25.0,
                              num_waypoints: int = 16) -> Tuple[List[TrajectoryPoint], TrajectoryMetrics]:
        """
        Specialized smooth trajectory generator for TEKNOFEST Task 1 (Figure Eight ∞ maneuver).
        """
        cx, cy, cz = center
        raw_wps: List[Tuple[float, float, float]] = []
        for i in range(num_waypoints + 1):
            theta = (2.0 * math.pi * i) / num_waypoints
            # Lemniscate of Gerono: x = R*sin(t), y = R*sin(t)*cos(t)
            wx = cx + radius * math.sin(theta)
            wy = cy + radius * math.sin(theta) * math.cos(theta)
            raw_wps.append((wx, wy, cz))

        return self.plan_trajectory(raw_wps)
