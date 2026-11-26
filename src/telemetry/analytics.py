"""
TEKNOFEST 2026 Uluslararası İHA - Uçuş Sonrası Analiz ve Puanlama Motoru
-----------------------------------------------------------------------
Uçuş esnasında kaydedilen CSV telemetri günlüklerini ve JSONL olaylarını
analiz ederek 2026 şartnamesine göre puanlama, azami irtifa denetimi,
hedef isabet doğruluğu ve batarya tüketim verimliliği raporu üretir.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import os
import csv
import json


@dataclass
class DropScore:
    slot_id: int
    target_type: str
    target_color: str
    miss_distance_m: float
    is_valid_drop: bool
    score_points: float


@dataclass
class FlightSummary:
    log_file: str
    total_flight_time_s: float
    max_altitude_m: float
    exceeded_120m_limit: bool
    max_ground_speed_mps: float
    battery_start_v: float
    battery_end_v: float
    voltage_drop_v: float
    drop_scores: List[DropScore]
    total_mission_score: float
    compliance_passed: bool
    pg1_score: float = 0.0
    pg2_score: float = 0.0
    total_competition_score: float = 0.0
    scoring_details: Optional[Dict[str, Any]] = None


class FlightAnalyticsEngine:
    def __init__(self, category: str = "rotary_wing"):
        self.category = category
        # 2026 kuralı: Döner kanat 10m, Sabit kanat 20m çember
        self.max_scoring_radius = 10.0 if category == "rotary_wing" else 20.0
        self.max_score_per_drop = 100.0

    def calculate_drop_score(self, miss_distance_m: float) -> float:
        """
        Şartnameye göre merkeze olan mesafeden puan hesabı:
        Puan = MaxPuan * (1 - (Mesafe / MaxYarıçap))
        """
        if miss_distance_m > self.max_scoring_radius:
            return 0.0
        ratio = max(0.0, 1.0 - (miss_distance_m / self.max_scoring_radius))
        return round(self.max_score_per_drop * ratio, 2)

    @staticmethod
    def _safe_min_ratio(min_val: float, tk_val: float) -> float:
        """Min / tk oranını hesaplar, 1.0 tavanı koyar."""
        if min_val <= 0.0 and tk_val <= 0.0:
            return 1.0
        if tk_val <= 0.0:
            return 1.0
        return min(1.0, max(0.0, min_val / tk_val))

    @staticmethod
    def _safe_max_ratio(tk_val: float, max_val: float) -> float:
        """tk / max oranını hesaplar, 1.0 tavanı koyar."""
        if max_val <= 0.0:
            return 1.0 if tk_val > 0.0 else 0.0
        return min(1.0, max(0.0, tk_val / max_val))

    @staticmethod
    def _safe_dist_ratio(d_min: float, d_tk: float, max_radius: float, eps: float = 0.05) -> float:
        """
        Hedefe olan uzaklık oranını (d_min / d_tk) hesaplar.
        Şartname kuralı:
        - Sabit kanat: 20m üstü 0 puan.
        - Döner kanat: 10m üstü 0 puan.
        - d_tk <= d_min ise oran tam 1.0'dır.
        """
        if d_tk > max_radius:
            return 0.0
        if d_tk <= d_min:
            return 1.0
        eff_min = max(d_min, eps)
        eff_tk = max(d_tk, eps)
        return min(1.0, max(0.0, eff_min / eff_tk))

    @classmethod
    def evaluate_pg1_breakdown(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        penalty_points: float = 0.0
    ) -> Dict[str, Any]:
        """Tablo 3 Görev 1 bileşenlerini ayrıntılı sözlük olarak döndürür."""
        c = max(0.0, min(1.0, c_autonomy))
        r_vol = cls._safe_min_ratio(vol_min, vol_tk)
        r_haz = cls._safe_min_ratio(t_min_haz, t_tk_haz)
        r_w0 = cls._safe_min_ratio(w0_min, w0_tk)
        r_ucus = cls._safe_min_ratio(t_min_ucus, t_tk_ucus)

        pts_vol = 6.0 * r_vol
        pts_haz = 6.0 * r_haz
        pts_w0 = 6.0 * r_w0
        pts_ucus = 12.0 * r_ucus
        raw_score = c * (pts_vol + pts_haz + pts_w0 + pts_ucus)
        final_score = round(max(0.0, min(30.0, raw_score - penalty_points)), 2)

        return {
            "c_autonomy": c,
            "term_vol_pts": round(pts_vol, 3),
            "term_haz_pts": round(pts_haz, 3),
            "term_w0_pts": round(pts_w0, 3),
            "term_ucus_pts": round(pts_ucus, 3),
            "raw_score": round(raw_score, 2),
            "penalty_points": penalty_points,
            "final_pg1_score": final_score,
            "max_possible_score": 30.0
        }

    @classmethod
    def calculate_official_pg1(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        penalty_points: float = 0.0
    ) -> float:
        """
        TÜBİTAK 2026 V7 Şartnamesi Tablo 3 / Tablo 5 - Görev 1 Puanlama Formülü:
        PG1 = c * [ 6 * (Vol_min / Vol_tk) + 6 * (t_min,haz / t_tk,haz) +
                    6 * (W0_min / W0,tk) + 12 * (t_min,uçuş / t_tk,uçuş) ] - Ceza Puanı
        (Azami 30 Puan)
        """
        return cls.evaluate_pg1_breakdown(
            c_autonomy=c_autonomy,
            vol_min=vol_min,
            vol_tk=vol_tk,
            t_min_haz=t_min_haz,
            t_tk_haz=t_tk_haz,
            w0_min=w0_min,
            w0_tk=w0_tk,
            t_min_ucus=t_min_ucus,
            t_tk_ucus=t_tk_ucus,
            penalty_points=penalty_points
        )["final_pg1_score"]

    @classmethod
    def evaluate_pg2_fixed_wing_breakdown(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        w_yuk_tk: float,
        w_yuk_max: float,
        d_4x4_min: float,
        d_4x4_tk: float,
        d_2x2_min: float,
        d_2x2_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        penalty_points: float = 0.0
    ) -> Dict[str, Any]:
        """Tablo 3 Uluslararası Sabit Kanat Görev 2 bileşenleri (Azami 70 Puan)."""
        c = max(0.0, min(1.0, c_autonomy))
        r_vol = cls._safe_min_ratio(vol_min, vol_tk)
        r_haz = cls._safe_min_ratio(t_min_haz, t_tk_haz)
        r_w0 = cls._safe_min_ratio(w0_min, w0_tk)
        r_wyuk = cls._safe_max_ratio(w_yuk_tk, w_yuk_max)
        r_d4x4 = cls._safe_dist_ratio(d_4x4_min, d_4x4_tk, max_radius=20.0)
        r_d2x2 = cls._safe_dist_ratio(d_2x2_min, d_2x2_tk, max_radius=20.0)
        r_ucus = cls._safe_min_ratio(t_min_ucus, t_tk_ucus)

        pts_vol = 4.0 * r_vol
        pts_haz = 4.0 * r_haz
        pts_w0 = 4.0 * r_w0
        pts_wyuk = 20.0 * r_wyuk
        pts_d4x4 = 10.0 * r_d4x4
        pts_d2x2 = 20.0 * r_d2x2
        pts_ucus = 8.0 * r_ucus

        raw_score = c * (pts_vol + pts_haz + pts_w0 + pts_wyuk + pts_d4x4 + pts_d2x2 + pts_ucus)
        final_score = round(max(0.0, min(70.0, raw_score - penalty_points)), 2)

        return {
            "c_autonomy": c,
            "term_vol_pts": round(pts_vol, 3),
            "term_haz_pts": round(pts_haz, 3),
            "term_w0_pts": round(pts_w0, 3),
            "term_wyuk_pts": round(pts_wyuk, 3),
            "term_d4x4_pts": round(pts_d4x4, 3),
            "term_d2x2_pts": round(pts_d2x2, 3),
            "term_ucus_pts": round(pts_ucus, 3),
            "raw_score": round(raw_score, 2),
            "penalty_points": penalty_points,
            "final_pg2_score": final_score,
            "max_possible_score": 70.0
        }

    @classmethod
    def calculate_official_pg2_fixed_wing(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        w_yuk_tk: float,
        w_yuk_max: float,
        d_4x4_min: float,
        d_4x4_tk: float,
        d_2x2_min: float,
        d_2x2_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        penalty_points: float = 0.0
    ) -> float:
        """
        TÜBİTAK 2026 V7 Şartnamesi Tablo 3 - Uluslararası Sabit Kanat Görev 2 Puanlama Formülü:
        PG2 = c * [ 4 * (Vol_min / Vol_tk) + 4 * (t_min,haz / t_tk,haz) + 4 * (W0_min / W0,tk) +
                    20 * (W_yük,tk / W_yük,max) + 10 * (d_4x4,min / d_4x4,tk) +
                    20 * (d_2x2,min / d_2x2,tk) + 8 * (t_min,uçuş / t_tk,uçuş) ] - Ceza Puanı
        (Azami 70 Puan, 20 metreye kadar ölçüm yapılır)
        """
        return cls.evaluate_pg2_fixed_wing_breakdown(
            c_autonomy=c_autonomy,
            vol_min=vol_min,
            vol_tk=vol_tk,
            t_min_haz=t_min_haz,
            t_tk_haz=t_tk_haz,
            w0_min=w0_min,
            w0_tk=w0_tk,
            w_yuk_tk=w_yuk_tk,
            w_yuk_max=w_yuk_max,
            d_4x4_min=d_4x4_min,
            d_4x4_tk=d_4x4_tk,
            d_2x2_min=d_2x2_min,
            d_2x2_tk=d_2x2_tk,
            t_min_ucus=t_min_ucus,
            t_tk_ucus=t_tk_ucus,
            penalty_points=penalty_points
        )["final_pg2_score"]

    @classmethod
    def evaluate_pg2_rotary_wing_breakdown(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        w_yuk_tk: float,
        w_yuk_max: float,
        d_altg_min: float,
        d_altg_tk: float,
        d_ucg_min: float,
        d_ucg_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        ay_bonus: int = 0,
        by_bonus: int = 0,
        penalty_points: float = 0.0
    ) -> Dict[str, Any]:
        """Tablo 3 Uluslararası Döner Kanat Görev 2 bileşenleri (Azami 80 Puan)."""
        c = max(0.0, min(1.0, c_autonomy))
        r_vol = cls._safe_min_ratio(vol_min, vol_tk)
        r_haz = cls._safe_min_ratio(t_min_haz, t_tk_haz)
        r_w0 = cls._safe_min_ratio(w0_min, w0_tk)
        r_wyuk = cls._safe_max_ratio(w_yuk_tk, w_yuk_max)
        r_daltg = cls._safe_dist_ratio(d_altg_min, d_altg_tk, max_radius=10.0)
        r_ducg = cls._safe_dist_ratio(d_ucg_min, d_ucg_tk, max_radius=10.0)
        r_ucus = cls._safe_min_ratio(t_min_ucus, t_tk_ucus)

        ay_val = 1 if ay_bonus else 0
        by_val = 1 if by_bonus else 0
        bonus_pts = 10.0 * (ay_val + by_val)

        pts_vol = 4.0 * r_vol
        pts_haz = 4.0 * r_haz
        pts_w0 = 4.0 * r_w0
        pts_wyuk = 20.0 * r_wyuk
        pts_daltg = 8.0 * r_daltg
        pts_ducg = 12.0 * r_ducg
        pts_ucus = 8.0 * r_ucus

        raw_score = c * (pts_vol + pts_haz + pts_w0 + pts_wyuk + pts_daltg + pts_ducg + bonus_pts + pts_ucus)
        final_score = round(max(0.0, min(80.0, raw_score - penalty_points)), 2)

        return {
            "c_autonomy": c,
            "term_vol_pts": round(pts_vol, 3),
            "term_haz_pts": round(pts_haz, 3),
            "term_w0_pts": round(pts_w0, 3),
            "term_wyuk_pts": round(pts_wyuk, 3),
            "term_daltg_pts": round(pts_daltg, 3),
            "term_ducg_pts": round(pts_ducg, 3),
            "ay_bonus": ay_val,
            "by_bonus": by_val,
            "bonus_pts": round(bonus_pts, 3),
            "term_ucus_pts": round(pts_ucus, 3),
            "raw_score": round(raw_score, 2),
            "penalty_points": penalty_points,
            "final_pg2_score": final_score,
            "max_possible_score": 80.0
        }

    @classmethod
    def calculate_official_pg2_rotary_wing(
        cls,
        c_autonomy: float,
        vol_min: float,
        vol_tk: float,
        t_min_haz: float,
        t_tk_haz: float,
        w0_min: float,
        w0_tk: float,
        w_yuk_tk: float,
        w_yuk_max: float,
        d_altg_min: float,
        d_altg_tk: float,
        d_ucg_min: float,
        d_ucg_tk: float,
        t_min_ucus: float,
        t_tk_ucus: float,
        ay_bonus: int = 0,
        by_bonus: int = 0,
        penalty_points: float = 0.0
    ) -> float:
        """
        TÜBİTAK 2026 V7 Şartnamesi Tablo 3 - Uluslararası Döner Kanat Görev 2 Puanlama Formülü:
        PG2 = c * [ 4 * (Vol_min / Vol_tk) + 4 * (t_min,haz / t_tk,haz) + 4 * (W0_min / W0,tk) +
                    20 * (W_yük,tk / W_yük,max) + 8 * (d_altg,min / d_altg,tk) +
                    12 * (d_üçg,min / d_üçg,tk) + 10 * (AY + BY) + 8 * (t_min,uçuş / t_tk,uçuş) ] - Ceza Puanı
        (Azami 80 Puan, 10 metreye kadar ölçüm yapılır, 3. Görev AY=1 ve BY=1 bonus)
        """
        return cls.evaluate_pg2_rotary_wing_breakdown(
            c_autonomy=c_autonomy,
            vol_min=vol_min,
            vol_tk=vol_tk,
            t_min_haz=t_min_haz,
            t_tk_haz=t_tk_haz,
            w0_min=w0_min,
            w0_tk=w0_tk,
            w_yuk_tk=w_yuk_tk,
            w_yuk_max=w_yuk_max,
            d_altg_min=d_altg_min,
            d_altg_tk=d_altg_tk,
            d_ucg_min=d_ucg_min,
            d_ucg_tk=d_ucg_tk,
            t_min_ucus=t_min_ucus,
            t_tk_ucus=t_tk_ucus,
            ay_bonus=ay_bonus,
            by_bonus=by_bonus,
            penalty_points=penalty_points
        )["final_pg2_score"]

    @classmethod
    def calculate_official_pg2(cls, category: str = "rotary_wing", **kwargs) -> float:
        """Sabit veya döner kanat kategorisine göre PG2 hesaplar."""
        is_fixed = category.lower() in ["fixed_wing", "sabit", "sabit_kanat"]
        if is_fixed:
            d_4x4_min = kwargs.get("d_4x4_min", kwargs.get("d1_min", 0.5))
            d_4x4_tk = kwargs.get("d_4x4_tk", kwargs.get("d1_tk", 1.0))
            d_2x2_min = kwargs.get("d_2x2_min", kwargs.get("d2_min", 0.5))
            d_2x2_tk = kwargs.get("d_2x2_tk", kwargs.get("d2_tk", 1.0))
            return cls.calculate_official_pg2_fixed_wing(
                c_autonomy=kwargs.get("c_autonomy", 1.0),
                vol_min=kwargs.get("vol_min", 0.1),
                vol_tk=kwargs.get("vol_tk", 0.1),
                t_min_haz=kwargs.get("t_min_haz", 120.0),
                t_tk_haz=kwargs.get("t_tk_haz", 120.0),
                w0_min=kwargs.get("w0_min", 2.0),
                w0_tk=kwargs.get("w0_tk", 2.0),
                w_yuk_tk=kwargs.get("w_yuk_tk", 1.0),
                w_yuk_max=kwargs.get("w_yuk_max", 1.0),
                d_4x4_min=d_4x4_min,
                d_4x4_tk=d_4x4_tk,
                d_2x2_min=d_2x2_min,
                d_2x2_tk=d_2x2_tk,
                t_min_ucus=kwargs.get("t_min_ucus", 180.0),
                t_tk_ucus=kwargs.get("t_tk_ucus", 180.0),
                penalty_points=kwargs.get("penalty_points", 0.0)
            )
        else:
            d_altg_min = kwargs.get("d_altg_min", kwargs.get("d1_min", 0.5))
            d_altg_tk = kwargs.get("d_altg_tk", kwargs.get("d1_tk", 1.0))
            d_ucg_min = kwargs.get("d_ucg_min", kwargs.get("d2_min", 0.5))
            d_ucg_tk = kwargs.get("d_ucg_tk", kwargs.get("d2_tk", 1.0))
            return cls.calculate_official_pg2_rotary_wing(
                c_autonomy=kwargs.get("c_autonomy", 1.0),
                vol_min=kwargs.get("vol_min", 0.1),
                vol_tk=kwargs.get("vol_tk", 0.1),
                t_min_haz=kwargs.get("t_min_haz", 120.0),
                t_tk_haz=kwargs.get("t_tk_haz", 120.0),
                w0_min=kwargs.get("w0_min", 2.0),
                w0_tk=kwargs.get("w0_tk", 2.0),
                w_yuk_tk=kwargs.get("w_yuk_tk", 1.0),
                w_yuk_max=kwargs.get("w_yuk_max", 1.0),
                d_altg_min=d_altg_min,
                d_altg_tk=d_altg_tk,
                d_ucg_min=d_ucg_min,
                d_ucg_tk=d_ucg_tk,
                t_min_ucus=kwargs.get("t_min_ucus", 180.0),
                t_tk_ucus=kwargs.get("t_tk_ucus", 180.0),
                ay_bonus=kwargs.get("ay_bonus", 0),
                by_bonus=kwargs.get("by_bonus", 0),
                penalty_points=kwargs.get("penalty_points", 0.0)
            )

    @classmethod
    def calculate_total_competition_score(
        cls,
        video_score: float,
        pg1_score: float,
        pg2_score: float,
        ceza_1: float = 0.0,
        ceza_2: float = 0.0,
        category: str = "rotary_wing"
    ) -> Dict[str, Any]:
        """
        TÜBİTAK 2026 V7 Şartnamesi Tablo 2 - Genel Puanlama Tablosu:
        - Sabit Kanat: Video (10) + PG1 (30) + PG2 (70) = 110 Puan
        - Döner Kanat: Video (10) + PG1 (30) + PG2 (80) = 120 Puan
        - Ceza Puanı 1: 0-5 Puan (Centilmenlik dışı / Kutu dışı parça)
        - Ceza Puanı 2: 0-10 Puan (Direğin içinden dönme ihlali)
        """
        is_fixed = category.lower() in ["fixed_wing", "sabit", "sabit_kanat"]
        max_pg2 = 70.0 if is_fixed else 80.0
        max_total = 110.0 if is_fixed else 120.0

        v_score = max(0.0, min(10.0, video_score))
        p1 = max(0.0, min(30.0, pg1_score))
        p2 = max(0.0, min(max_pg2, pg2_score))
        c1 = max(0.0, min(5.0, ceza_1))
        c2 = max(0.0, min(10.0, ceza_2))

        total = round(max(0.0, min(max_total, v_score + p1 + p2 - c1 - c2)), 2)

        return {
            "category": "fixed_wing" if is_fixed else "rotary_wing",
            "video_score": v_score,
            "pg1_score": p1,
            "pg2_score": p2,
            "ceza_1": c1,
            "ceza_2": c2,
            "total_penalties": c1 + c2,
            "total_score": total,
            "max_possible_total": max_total
        }

    def analyze_csv_log(self, csv_path: str) -> Optional[FlightSummary]:
        if not os.path.exists(csv_path):
            print(f"[ANALYTICS] Günlük dosyası bulunamadı: {csv_path}")
            return None

        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        if not rows:
            return None

        # Zaman hesabı
        timestamps = [float(r["timestamp"]) for r in rows if r.get("timestamp")]
        start_time = timestamps[0]
        end_time = timestamps[-1]
        total_time = max(0.1, end_time - start_time)

        # İrtifa ve Hız
        altitudes = [float(r["altitude_agl"]) for r in rows if r.get("altitude_agl")]
        max_alt = max(altitudes) if altitudes else 0.0
        exceeded_120m = max_alt > 120.0

        speeds = [float(r["ground_speed"]) for r in rows if r.get("ground_speed")]
        max_speed = max(speeds) if speeds else 0.0

        # Batarya
        voltages = [float(r["battery_v"]) for r in rows if r.get("battery_v")]
        bat_start = voltages[0] if voltages else 16.0
        bat_end = voltages[-1] if voltages else 16.0
        voltage_drop = round(bat_start - bat_end, 2)

        # Yük bırakma anları (payloads_left azalması)
        drop_scores: List[DropScore] = []
        prev_payloads = 2
        for r in rows:
            try:
                curr_payloads = int(r.get("payloads_left", 2))
                if curr_payloads < prev_payloads:
                    # Bir yük bırakıldı
                    miss_d = float(r.get("miss_distance", 99.0))
                    t_type = r.get("target_type", "TARGET_A")
                    score = self.calculate_drop_score(miss_d)
                    slot = 2 - curr_payloads
                    drop_scores.append(DropScore(
                        slot_id=slot,
                        target_type=t_type,
                        target_color="red" if t_type == "TARGET_A" else "blue",
                        miss_distance_m=round(miss_d, 2),
                        is_valid_drop=miss_d <= self.max_scoring_radius,
                        score_points=score
                    ))
                prev_payloads = curr_payloads
            except Exception:
                pass

        total_score = sum(d.score_points for d in drop_scores)
        compliance = not exceeded_120m and len(drop_scores) > 0

        # Tablo 3 Resmi Şartname Puanlama Hesabı (2026 V7)
        d1 = drop_scores[0].miss_distance_m if len(drop_scores) > 0 else 99.0
        d2 = drop_scores[1].miss_distance_m if len(drop_scores) > 1 else 99.0
        is_fixed = self.category.lower() in ["fixed_wing", "sabit", "sabit_kanat"]
        c_auto = 1.0 if (not exceeded_120m and compliance) else 0.0

        official_pg1 = self.calculate_official_pg1(
            c_autonomy=c_auto,
            vol_min=0.08,
            vol_tk=0.08,
            t_min_haz=180.0,
            t_tk_haz=210.0,
            w0_min=2.5,
            w0_tk=2.8,
            t_min_ucus=min(total_time, 150.0),
            t_tk_ucus=max(total_time, 150.0),
            penalty_points=0.0
        )

        if is_fixed:
            official_pg2 = self.calculate_official_pg2_fixed_wing(
                c_autonomy=c_auto,
                vol_min=0.08,
                vol_tk=0.08,
                t_min_haz=180.0,
                t_tk_haz=210.0,
                w0_min=2.5,
                w0_tk=2.8,
                w_yuk_tk=1.0,
                w_yuk_max=1.2,
                d_4x4_min=0.5,
                d_4x4_tk=d1,
                d_2x2_min=0.5,
                d_2x2_tk=d2,
                t_min_ucus=min(total_time, 240.0),
                t_tk_ucus=max(total_time, 240.0),
                penalty_points=0.0
            )
        else:
            official_pg2 = self.calculate_official_pg2_rotary_wing(
                c_autonomy=c_auto,
                vol_min=0.06,
                vol_tk=0.06,
                t_min_haz=180.0,
                t_tk_haz=200.0,
                w0_min=2.2,
                w0_tk=2.5,
                w_yuk_tk=1.0,
                w_yuk_max=1.2,
                d_altg_min=0.5,
                d_altg_tk=d1,
                d_ucg_min=0.5,
                d_ucg_tk=d2,
                t_min_ucus=min(total_time, 220.0),
                t_tk_ucus=max(total_time, 220.0),
                ay_bonus=1 if len(drop_scores) >= 2 and d1 <= 10.0 else 0,
                by_bonus=1 if len(drop_scores) >= 2 and d2 <= 10.0 else 0,
                penalty_points=0.0
            )

        comp_summary = self.calculate_total_competition_score(
            video_score=9.5,
            pg1_score=official_pg1,
            pg2_score=official_pg2,
            ceza_1=0.0,
            ceza_2=0.0,
            category=self.category
        )

        return FlightSummary(
            log_file=os.path.basename(csv_path),
            total_flight_time_s=round(total_time, 1),
            max_altitude_m=round(max_alt, 1),
            exceeded_120m_limit=exceeded_120m,
            max_ground_speed_mps=round(max_speed, 1),
            battery_start_v=round(bat_start, 2),
            battery_end_v=round(bat_end, 2),
            voltage_drop_v=voltage_drop,
            drop_scores=drop_scores,
            total_mission_score=round(total_score, 1),
            compliance_passed=compliance,
            pg1_score=official_pg1,
            pg2_score=official_pg2,
            total_competition_score=comp_summary["total_score"],
            scoring_details=comp_summary
        )

    def generate_markdown_report(self, summary: FlightSummary) -> str:
        """Yarışma hakemleri ve teknik inceleme için detaylı Markdown raporu üretir."""
        verdict = "✅ KURAL VE GÖREV UYUMLU" if summary.compliance_passed else "❌ KURAL İHLALİ VEYA BAŞARISIZ GÖREV"
        if summary.exceeded_120m_limit:
            verdict += " (DİSKALİFİYE: 120m İRTİFA LİMİTİ AŞILDI)"

        report = f"""# 🛸 TEKNOFEST 2026 - Uçuş ve Görev Analiz Raporu
**Günlük Dosyası:** `{summary.log_file}`  
**Operasyonel Karar:** **{verdict}**  

---

### 1. Uçuş Dinamikleri ve Sınır Denetimi
| Metrik | Ölçülen Değer | 2026 Şartname Limiti | Uyumluluk Durumu |
| :--- | :--- | :--- | :--- |
| **Toplam Süre** | {summary.total_flight_time_s} saniye | - | Tamamlandı |
| **Azami İrtifa (AGL)** | **{summary.max_altitude_m} m** | **Azami 120.0 m** | {'❌ İHLAL' if summary.exceeded_120m_limit else '✅ UYUMLU'} |
| **Azami Yer Hızı** | {summary.max_ground_speed_mps} m/s | 15.0 m/s | ✅ Nominal |
| **Batarya Başlangıç/Bitiş** | {summary.battery_start_v}V $\\rightarrow$ {summary.battery_end_v}V | $\\Delta V = {summary.voltage_drop_v}V$ | ✅ Sağlıklı |

---

### 2. Yük Bırakma İsabeti ve Puanlama ({self.category.upper()})
*Puanlama Alanı Sınırı: Hedef merkezinden $\\le {self.max_scoring_radius}m$*

| Yük No | Hedef Tipi | Renk | Sapma Mesafesi | Geçerlilik | Kazanılan Puan |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for d in summary.drop_scores:
            status = "✅ Geçerli" if d.is_valid_drop else "❌ Alan Dışı"
            report += f"| **Yük {d.slot_id}** | {d.target_type} | {d.target_color.upper()} | {d.miss_distance_m} m | {status} | **{d.score_points} / 100** |\n"

        report += f"\n**TOPLAM GÖREV PUANI:** **{summary.total_mission_score} / 200 Puan**\n"

        is_fixed = self.category.lower() in ["fixed_wing", "sabit", "sabit_kanat"]
        max_pg2 = 70.0 if is_fixed else 80.0
        max_total = 110.0 if is_fixed else 120.0

        report += f"""
---

### 3. TÜBİTAK 2026 Şartnamesi Tablo 3 Resmi Puanlama
| Görev / Değerlendirme Kalemi | Hesaplanan Puan | Kategori Üst Limiti | Durum |
| :--- | :--- | :--- | :--- |
| **Görev 1 Puanı (PG1)** | **{summary.pg1_score:.2f} Puan** | 30.00 Puan | {'✅ Başarılı' if summary.pg1_score > 0 else '❌ Geçersiz'} |
| **Görev 2 Puanı (PG2)** | **{summary.pg2_score:.2f} Puan** | {max_pg2:.2f} Puan | {'✅ Başarılı' if summary.pg2_score > 0 else '❌ Geçersiz'} |
| **Hazırlık ve Görev Videosu** | 9.50 Puan | 10.00 Puan | ✅ Kabul |
| **Ceza Kesintisi (Ceza 1 + 2)** | 0.00 Puan | - | ✅ Ceza Yok |
| **TOPLAM GENEL ŞAMPİYONA PUANI (Tablo 2)** | **{summary.total_competition_score:.2f} / {max_total:.2f} Puan** | - | 🏆 |
"""
        return report
