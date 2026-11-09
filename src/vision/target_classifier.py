"""
TEKNOFEST 2026 - Advanced Multi-Target Classifier & Persistent Tracker
Provides robust geometric shape classification (Blue Hexagon vs Red Triangle),
temporal track association, flicker rejection, and occlusion handling.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict
import math


class TargetType(Enum):
    TARGET_A_HEXAGON = "TARGET_A_HEXAGON"  # Blue Hexagon
    TARGET_B_TRIANGLE = "TARGET_B_TRIANGLE" # Red Triangle
    UNKNOWN = "UNKNOWN"


@dataclass
class TargetDetection:
    target_type: TargetType
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    center_norm: Tuple[float, float] # (-1.0 to 1.0, -1.0 to 1.0)
    num_vertices: int
    circularity: float
    color_purity: float
    area_px: float


@dataclass
class TrackedTarget:
    track_id: int
    target_type: TargetType
    confidence: float
    bbox: Tuple[int, int, int, int]
    center_norm: Tuple[float, float]
    velocity_norm: Tuple[float, float]
    age_frames: int
    hits: int
    lost_frames: int
    is_confirmed: bool


class TargetClassifier:
    """
    Combines geometric polygon analysis, color metrics, and Kalman-like temporal tracking
    to reliably distinguish TEKNOFEST 2026 targets under vibration and lighting variations.
    """
    def __init__(self,
                 min_confirmation_hits: int = 4,
                 max_lost_frames: int = 5,
                 max_association_dist_norm: float = 0.25):
        self.min_confirmation_hits = min_confirmation_hits
        self.max_lost_frames = max_lost_frames
        self.max_association_dist_norm = max_association_dist_norm

        self._next_track_id = 1
        self.tracks: Dict[int, TrackedTarget] = {}

    def classify_contour(self,
                          vertices: int,
                          area: float,
                          perimeter: float,
                          color_name: str,
                          bbox: Tuple[int, int, int, int],
                          frame_dims: Tuple[int, int] = (640, 480)) -> TargetDetection:
        """
        Classifies an observed contour into Target A (Hexagon) or Target B (Triangle)
        using combined geometric symmetry, circularity, and color purity.
        """
        if perimeter <= 0.0 or area <= 0.0:
            return TargetDetection(TargetType.UNKNOWN, 0.0, bbox, (0.0, 0.0), vertices, 0.0, 0.0, area)

        # Circularity = 4 * pi * Area / (Perimeter^2)
        # Regular Hexagon theoretical circularity: pi * sqrt(3) / 6 ~= 0.9069
        # Equilateral Triangle theoretical circularity: pi * sqrt(3) / 9 ~= 0.6046
        circularity = (4.0 * math.pi * area) / (perimeter * perimeter)

        x, y, w, h = bbox
        cx = x + w / 2.0
        cy = y + h / 2.0
        fw, fh = frame_dims
        norm_x = (cx - (fw / 2.0)) / (fw / 2.0)
        norm_y = (cy - (fh / 2.0)) / (fh / 2.0)

        aspect_ratio = min(w, h) / max(w, h) if max(w, h) > 0 else 1.0

        # Target A Evaluation: Blue Hexagon (5 to 8 vertices, high circularity ~0.90, blue color)
        is_blue = "blue" in color_name.lower()
        is_red = "red" in color_name.lower()

        hex_geom_score = max(0.0, 1.0 - abs(circularity - 0.907) / 0.35)
        hex_vertex_score = 1.0 if 5 <= vertices <= 7 else 0.5 if vertices == 8 else 0.2
        hex_conf = (0.4 * (1.0 if is_blue else 0.0) +
                    0.3 * hex_geom_score +
                    0.2 * hex_vertex_score +
                    0.1 * aspect_ratio)

        # Target B Evaluation: Red Triangle (3 to 4 vertices, circularity ~0.60, red color)
        tri_geom_score = max(0.0, 1.0 - abs(circularity - 0.605) / 0.30)
        tri_vertex_score = 1.0 if vertices == 3 else 0.6 if vertices == 4 else 0.2
        tri_conf = (0.4 * (1.0 if is_red else 0.0) +
                    0.3 * tri_geom_score +
                    0.2 * tri_vertex_score +
                    0.1 * aspect_ratio)

        if hex_conf > tri_conf and hex_conf >= 0.55:
            target_type = TargetType.TARGET_A_HEXAGON
            confidence = min(0.99, hex_conf)
            color_purity = 1.0 if is_blue else 0.3
        elif tri_conf >= 0.50:
            target_type = TargetType.TARGET_B_TRIANGLE
            confidence = min(0.99, tri_conf)
            color_purity = 1.0 if is_red else 0.3
        else:
            target_type = TargetType.UNKNOWN
            confidence = max(hex_conf, tri_conf)
            color_purity = 0.0

        return TargetDetection(
            target_type=target_type,
            confidence=round(confidence, 3),
            bbox=bbox,
            center_norm=(round(norm_x, 3), round(norm_y, 3)),
            num_vertices=vertices,
            circularity=round(circularity, 3),
            color_purity=round(color_purity, 2),
            area_px=round(area, 1)
        )

    def update_tracks(self, detections: List[TargetDetection]) -> List[TrackedTarget]:
        """
        Associates current frame detections with existing tracks using nearest centroid matching.
        Manages track lifecycle, confirmation, and eviction.
        """
        valid_dets = [d for d in detections if d.target_type != TargetType.UNKNOWN]

        # Age existing tracks and predict position with simple velocity model
        for track in self.tracks.values():
            track.age_frames += 1
            track.lost_frames += 1
            # Predict
            pred_x = track.center_norm[0] + track.velocity_norm[0]
            pred_y = track.center_norm[1] + track.velocity_norm[1]
            track.center_norm = (pred_x, pred_y)

        # Greedy association
        matched_det_indices = set()
        matched_track_ids = set()

        for det_idx, det in enumerate(valid_dets):
            best_track_id = None
            min_dist = float("inf")

            for track_id, track in self.tracks.items():
                if track_id in matched_track_ids:
                    continue
                # Same target type match only
                if track.target_type != det.target_type:
                    continue

                dx = det.center_norm[0] - track.center_norm[0]
                dy = det.center_norm[1] - track.center_norm[1]
                dist = math.hypot(dx, dy)

                if dist < min_dist and dist <= self.max_association_dist_norm:
                    min_dist = dist
                    best_track_id = track_id

            if best_track_id is not None:
                # Update matched track
                track = self.tracks[best_track_id]
                old_x, old_y = track.center_norm
                new_x, new_y = det.center_norm

                # Alpha-beta filter update
                alpha = 0.7
                smoothed_x = alpha * new_x + (1.0 - alpha) * old_x
                smoothed_y = alpha * new_y + (1.0 - alpha) * old_y
                vx = smoothed_x - old_x
                vy = smoothed_y - old_y

                track.center_norm = (round(smoothed_x, 3), round(smoothed_y, 3))
                track.velocity_norm = (round(vx, 3), round(vy, 3))
                track.bbox = det.bbox
                track.confidence = round(0.6 * det.confidence + 0.4 * track.confidence, 3)
                track.hits += 1
                track.lost_frames = 0
                if track.hits >= self.min_confirmation_hits:
                    track.is_confirmed = True

                matched_det_indices.add(det_idx)
                matched_track_ids.add(best_track_id)

        # Initialize new tracks for unmatched detections
        for det_idx, det in enumerate(valid_dets):
            if det_idx not in matched_det_indices:
                new_track = TrackedTarget(
                    track_id=self._next_track_id,
                    target_type=det.target_type,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    center_norm=det.center_norm,
                    velocity_norm=(0.0, 0.0),
                    age_frames=1,
                    hits=1,
                    lost_frames=0,
                    is_confirmed=(self.min_confirmation_hits <= 1)
                )
                self.tracks[self._next_track_id] = new_track
                self._next_track_id += 1

        # Prune tracks that have been lost for too long
        dead_tracks = [t_id for t_id, t in self.tracks.items() if t.lost_frames > self.max_lost_frames]
        for t_id in dead_tracks:
            del self.tracks[t_id]

        return list(self.tracks.values())

    def get_confirmed_target(self, target_type: TargetType) -> Optional[TrackedTarget]:
        """Returns the highest-confidence confirmed track matching the requested target type."""
        candidates = [
            t for t in self.tracks.values()
            if t.target_type == target_type and t.is_confirmed and t.lost_frames == 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.confidence)

    def reset(self):
        """Resets all tracks."""
        self.tracks.clear()
        self._next_track_id = 1
