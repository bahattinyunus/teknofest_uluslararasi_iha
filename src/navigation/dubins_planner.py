"""
TEKNOFEST 2026 Uluslararası İHA - 3B Dubins Kinodinamik Rota Planlayıcı
=======================================================================
Sabit kanatlı İHA'lar için minimum dönüş yarıçapı kısıtı:
    R_min = V^2 / (g * tan(phi_max))
altında iki yönelimli nokta (x0, y0, z0, psi0) -> (x1, y1, z1, psi1) arasında
en kısa eğrilik-kısıtlı CSC (LSL, RSR, LSR, RSL) Dubins yörüngesini analitik
olarak çözer, 3B tırmanma/alçalma açısını (glide slope) doğrular ve otopilot
için örneklenmiş ara noktalar (waypoints) üretir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DubinsPose:
    """3B konum ve yönelim (radyan veya derece dönüşümlü)."""
    x_m: float
    y_m: float
    z_m: float
    heading_rad: float


@dataclass
class DubinsPath:
    """En kısa CSC Dubins eğrisi ve örneklenmiş 3B noktalar."""
    path_type: str                    # "LSL" | "RSR" | "LSR" | "RSL"
    turn_radius_m: float
    seg_lengths_m: Tuple[float, float, float]
    total_length_2d_m: float
    total_length_3d_m: float
    climb_angle_deg: float
    glide_slope_feasible: bool
    samples: List[DubinsPose]


class DubinsPathPlanner:
    """
    Analitik CSC (LSL, RSR, LSR, RSL) 3B Dubins Kinodinamik Rota Planlayıcısı.
    """

    GRAVITY = 9.80665

    def __init__(self, max_climb_angle_deg: float = 18.0):
        self.max_climb_angle_deg = float(max_climb_angle_deg)

    @classmethod
    def compute_min_turn_radius(cls, airspeed_mps: float, max_bank_deg: float = 35.0) -> float:
        """Sabit kanat koordineli dönüş minimum yarıçapını hesaplar: R = V^2 / (g * tan(phi))."""
        bank_rad = math.radians(max(5.0, min(65.0, max_bank_deg)))
        v = max(1.0, float(airspeed_mps))
        return (v * v) / (cls.GRAVITY * math.tan(bank_rad))

    @staticmethod
    def _mod2pi(angle: float) -> float:
        return angle % (2.0 * math.pi)

    def _solve_lsl(self, d: float, alpha: float, beta: float) -> Optional[Tuple[float, float, float]]:
        tmp0 = d + math.sin(alpha) - math.sin(beta)
        p_sq = 2.0 + d * d - 2.0 * math.cos(alpha - beta) + 2.0 * d * (math.sin(alpha) - math.sin(beta))
        if p_sq < 0.0:
            return None
        tmp1 = math.atan2(math.cos(beta) - math.cos(alpha), tmp0)
        t = self._mod2pi(-alpha + tmp1)
        p = math.sqrt(p_sq)
        q = self._mod2pi(beta - tmp1)
        return (t, p, q)

    def _solve_rsr(self, d: float, alpha: float, beta: float) -> Optional[Tuple[float, float, float]]:
        tmp0 = d - math.sin(alpha) + math.sin(beta)
        p_sq = 2.0 + d * d - 2.0 * math.cos(alpha - beta) + 2.0 * d * (math.sin(beta) - math.sin(alpha))
        if p_sq < 0.0:
            return None
        tmp1 = math.atan2(math.cos(alpha) - math.cos(beta), tmp0)
        t = self._mod2pi(alpha - tmp1)
        p = math.sqrt(p_sq)
        q = self._mod2pi(-beta + tmp1)
        return (t, p, q)

    def _solve_lsr(self, d: float, alpha: float, beta: float) -> Optional[Tuple[float, float, float]]:
        p_sq = -2.0 + d * d + 2.0 * math.cos(alpha - beta) + 2.0 * d * (math.sin(alpha) + math.sin(beta))
        if p_sq < 0.0:
            return None
        p = math.sqrt(p_sq)
        tmp2 = math.atan2(-math.cos(alpha) - math.cos(beta), d + math.sin(alpha) + math.sin(beta)) - math.atan2(-2.0, p)
        t = self._mod2pi(-alpha + tmp2)
        q = self._mod2pi(-self._mod2pi(beta) + tmp2)
        return (t, p, q)

    def _solve_rsl(self, d: float, alpha: float, beta: float) -> Optional[Tuple[float, float, float]]:
        p_sq = d * d - 2.0 + 2.0 * math.cos(alpha - beta) - 2.0 * d * (math.sin(alpha) + math.sin(beta))
        if p_sq < 0.0:
            return None
        p = math.sqrt(p_sq)
        tmp2 = math.atan2(math.cos(alpha) + math.cos(beta), d - math.sin(alpha) - math.sin(beta)) - math.atan2(2.0, p)
        t = self._mod2pi(alpha - tmp2)
        q = self._mod2pi(beta - tmp2)
        return (t, p, q)

    @staticmethod
    def _propagate_segment(x: float, y: float, psi: float, seg_len: float, seg_type: str, r: float) -> Tuple[float, float, float]:
        if seg_type == "S":
            return x + seg_len * math.cos(psi), y + seg_len * math.sin(psi), psi
        if seg_type == "L":
            dpsi = seg_len / r
            nx = x + r * (math.sin(psi + dpsi) - math.sin(psi))
            ny = y - r * (math.cos(psi + dpsi) - math.cos(psi))
            return nx, ny, psi + dpsi
        # "R"
        dpsi = seg_len / r
        nx = x - r * (math.sin(psi - dpsi) - math.sin(psi))
        ny = y + r * (math.cos(psi - dpsi) - math.cos(psi))
        return nx, ny, psi - dpsi

    def plan(
        self,
        start: DubinsPose,
        goal: DubinsPose,
        turn_radius_m: float,
        step_size_m: float = 5.0,
    ) -> DubinsPath:
        """Start ve Goal arasında en kısa 3B Dubins yolunu hesaplar ve örnekler."""
        r = max(1.0, float(turn_radius_m))
        dx = goal.x_m - start.x_m
        dy = goal.y_m - start.y_m
        dist = math.hypot(dx, dy)
        d = dist / r
        theta = self._mod2pi(math.atan2(dy, dx)) if dist > 1e-6 else 0.0
        alpha = self._mod2pi(start.heading_rad - theta)
        beta = self._mod2pi(goal.heading_rad - theta)

        solvers = {
            "LSL": self._solve_lsl,
            "RSR": self._solve_rsr,
            "LSR": self._solve_lsr,
            "RSL": self._solve_rsl,
        }

        best_type = "LSL"
        best_norm_segs: Optional[Tuple[float, float, float]] = None
        best_cost = float("inf")

        for ptype, fn in solvers.items():
            segs = fn(d, alpha, beta)
            if segs is None:
                continue
            cost = segs[0] + segs[1] + segs[2]
            if cost < best_cost:
                best_cost = cost
                best_type = ptype
                best_norm_segs = segs

        if best_norm_segs is None:
            best_norm_segs = (0.0, d, 0.0)
            best_type = "LSL"

        s1, s2, s3 = best_norm_segs[0] * r, best_norm_segs[1] * r, best_norm_segs[2] * r
        total_2d = s1 + s2 + s3
        dz = goal.z_m - start.z_m
        total_3d = math.hypot(total_2d, dz)
        climb_deg = math.degrees(math.atan2(abs(dz), max(1e-3, total_2d)))
        feasible = climb_deg <= self.max_climb_angle_deg

        # Yol boyunca nokta örnekleme
        n_steps = max(2, int(math.ceil(total_2d / max(0.5, step_size_m))))
        samples: List[DubinsPose] = []
        seg_types = (best_type[0], best_type[1], best_type[2])
        seg_lens = (s1, s2, s3)

        for i in range(n_steps + 1):
            s = (total_2d * i) / n_steps
            frac = i / n_steps
            z_interp = start.z_m + dz * frac

            cx, cy, cpsi = start.x_m, start.y_m, start.heading_rad
            rem = s
            for stype, slen in zip(seg_types, seg_lens):
                if rem <= slen:
                    cx, cy, cpsi = self._propagate_segment(cx, cy, cpsi, rem, stype, r)
                    break
                cx, cy, cpsi = self._propagate_segment(cx, cy, cpsi, slen, stype, r)
                rem -= slen

            samples.append(DubinsPose(round(cx, 3), round(cy, 3), round(z_interp, 3), self._mod2pi(cpsi)))

        return DubinsPath(
            path_type=best_type,
            turn_radius_m=round(r, 3),
            seg_lengths_m=(round(s1, 3), round(s2, 3), round(s3, 3)),
            total_length_2d_m=round(total_2d, 3),
            total_length_3d_m=round(total_3d, 3),
            climb_angle_deg=round(climb_deg, 2),
            glide_slope_feasible=feasible,
            samples=samples,
        )
