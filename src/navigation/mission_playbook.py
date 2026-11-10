"""
TEKNOFEST 2026 - Declarative Mission Playbook & Dynamic Replanner
Orchestrates multi-phase flight scripts (Takeoff -> Figure 8 -> Recon -> Drop 1 -> Drop 2 -> RTL),
evaluating dynamic target opportunities and re-sequencing phases on the fly.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import math


class PlaybookPhase(Enum):
    STANDBY = "STANDBY"
    TAKEOFF = "TAKEOFF"
    TASK_1_FIGURE_EIGHT = "TASK_1_FIGURE_EIGHT"
    TASK_2_SEARCH = "TASK_2_SEARCH"
    ATTACK_TARGET_A = "ATTACK_TARGET_A"
    ATTACK_TARGET_B = "ATTACK_TARGET_B"
    POST_DROP_CLIMB = "POST_DROP_CLIMB"
    RETURN_TO_BASE = "RETURN_TO_BASE"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"


@dataclass
class PlaybookWaypoint:
    x_m: float
    y_m: float
    z_m: float
    speed_mps: float
    acceptance_radius_m: float = 2.5
    action_description: str = ""


@dataclass
class PlaybookStatus:
    current_phase: PlaybookPhase
    phase_index: int
    total_phases: int
    waypoints_completed: int
    total_waypoints: int
    assigned_target: Optional[str]
    payload_slot_assigned: int
    opportunity_replan_triggered: bool
    estimated_phase_remaining_s: float


class MissionPlaybook:
    """
    Executes competition mission scripts and dynamically re-plans targets
    based on opportunity cost (energy, wind direction, and line-of-sight).
    """
    def __init__(self,
                 target_cruise_alt_m: float = 30.0,
                 takeoff_alt_m: float = 25.0,
                 figure_eight_radius_m: float = 30.0):
        self.cruise_alt = target_cruise_alt_m
        self.takeoff_alt = takeoff_alt_m
        self.figure_eight_radius = figure_eight_radius_m

        self.phases: List[PlaybookPhase] = [
            PlaybookPhase.STANDBY,
            PlaybookPhase.TAKEOFF,
            PlaybookPhase.TASK_1_FIGURE_EIGHT,
            PlaybookPhase.TASK_2_SEARCH,
            PlaybookPhase.ATTACK_TARGET_A,
            PlaybookPhase.ATTACK_TARGET_B,
            PlaybookPhase.RETURN_TO_BASE,
            PlaybookPhase.LANDING
        ]
        self.current_phase_idx = 0
        self.current_wp_idx = 0
        self.active_waypoints: List[PlaybookWaypoint] = []
        self.replan_history: List[str] = []

        self._build_phase_waypoints()

    def _build_phase_waypoints(self):
        phase = self.phases[self.current_phase_idx]
        self.active_waypoints.clear()
        self.current_wp_idx = 0

        if phase == PlaybookPhase.TAKEOFF:
            self.active_waypoints.append(
                PlaybookWaypoint(0.0, 0.0, self.takeoff_alt, 3.0, 1.5, "Vertical Climb")
            )
        elif phase == PlaybookPhase.TASK_1_FIGURE_EIGHT:
            # 8-point figure-8 polygon
            R = self.figure_eight_radius
            for i in range(8):
                theta = (2.0 * math.pi * i) / 8.0
                wx = R * math.sin(theta)
                wy = R * math.sin(theta) * math.cos(theta)
                self.active_waypoints.append(
                    PlaybookWaypoint(wx, wy, self.cruise_alt, 10.0, 3.0, f"Figure-8 WP {i+1}")
                )
        elif phase == PlaybookPhase.TASK_2_SEARCH:
            # Lawn-mower search grid
            for row in range(3):
                x_pos = -40.0 if row % 2 == 0 else 40.0
                y_pos = (row - 1) * 25.0
                self.active_waypoints.append(
                    PlaybookWaypoint(x_pos, y_pos, self.cruise_alt, 8.0, 3.0, f"Search Row {row+1}")
                )
        elif phase in (PlaybookPhase.ATTACK_TARGET_A, PlaybookPhase.ATTACK_TARGET_B):
            self.active_waypoints.append(
                PlaybookWaypoint(0.0, 0.0, self.cruise_alt, 5.0, 1.0, f"Target Approach Run")
            )
        elif phase == PlaybookPhase.RETURN_TO_BASE:
            self.active_waypoints.append(
                PlaybookWaypoint(0.0, 0.0, self.cruise_alt, 12.0, 2.0, "RTL Inbound")
            )
        elif phase == PlaybookPhase.LANDING:
            self.active_waypoints.append(
                PlaybookWaypoint(0.0, 0.0, 0.0, 1.5, 0.5, "Final Touchdown")
            )

    def evaluate_opportunity_replan(self,
                                     current_uav_pos: Tuple[float, float],
                                     detected_target_type: str,
                                     target_pos: Tuple[float, float],
                                     headwind_mps: float) -> bool:
        """
        Determines whether to swap the order of Target A and Target B based on opportunity cost.
        Returns True if a replan was executed.
        """
        current_phase = self.phases[self.current_phase_idx]
        if current_phase not in (PlaybookPhase.TASK_2_SEARCH, PlaybookPhase.ATTACK_TARGET_A):
            return False

        # If currently assigned to A, but Target B is spotted directly ahead with favorable headwind
        if detected_target_type == "TARGET_B" and current_phase == PlaybookPhase.ATTACK_TARGET_A:
            dist_to_b = math.dist(current_uav_pos, target_pos)
            # Opportunity benefit: target B is closer than 35m and headwind is favorable (< 3 m/s tailwind)
            if dist_to_b < 35.0 and headwind_mps > -2.0:
                # Re-sequence: Attack Target B first!
                idx_a = self.phases.index(PlaybookPhase.ATTACK_TARGET_A)
                idx_b = self.phases.index(PlaybookPhase.ATTACK_TARGET_B)
                self.phases[idx_a], self.phases[idx_b] = self.phases[idx_b], self.phases[idx_a]
                self._build_phase_waypoints()
                msg = f"Re-sequenced: Target B prioritized at dist={dist_to_b:.1f}m"
                self.replan_history.append(msg)
                return True

        return False

    def update(self, current_uav_xyz: Tuple[float, float, float]) -> PlaybookStatus:
        """
        Updates waypoint tracking and advances mission phases automatically.
        """
        cx, cy, cz = current_uav_xyz
        replan_triggered = False

        if self.current_wp_idx < len(self.active_waypoints):
            wp = self.active_waypoints[self.current_wp_idx]
            dist_to_wp = math.dist((cx, cy, cz), (wp.x_m, wp.y_m, wp.z_m))
            if dist_to_wp <= wp.acceptance_radius_m:
                self.current_wp_idx += 1
                if self.current_wp_idx >= len(self.active_waypoints):
                    self.advance_phase()

        curr_phase = self.phases[self.current_phase_idx]
        assigned_target = None
        payload_slot = 0
        if curr_phase == PlaybookPhase.ATTACK_TARGET_A:
            assigned_target = "TARGET_A_HEXAGON"
            payload_slot = 1  # Slot 1: Red Payload for Target A
        elif curr_phase == PlaybookPhase.ATTACK_TARGET_B:
            assigned_target = "TARGET_B_TRIANGLE"
            payload_slot = 2  # Slot 2: Blue Payload for Target B

        return PlaybookStatus(
            current_phase=curr_phase,
            phase_index=self.current_phase_idx,
            total_phases=len(self.phases),
            waypoints_completed=self.current_wp_idx,
            total_waypoints=len(self.active_waypoints),
            assigned_target=assigned_target,
            payload_slot_assigned=payload_slot,
            opportunity_replan_triggered=bool(self.replan_history),
            estimated_phase_remaining_s=max(0.0, (len(self.active_waypoints) - self.current_wp_idx) * 4.0)
        )

    def advance_phase(self):
        """Advances to the next mission phase."""
        if self.current_phase_idx < len(self.phases) - 1:
            self.current_phase_idx += 1
            self._build_phase_waypoints()

    def reset(self):
        """Resets playbook to starting standby condition."""
        self.current_phase_idx = 0
        self.current_wp_idx = 0
        self.replan_history.clear()
        self._build_phase_waypoints()
