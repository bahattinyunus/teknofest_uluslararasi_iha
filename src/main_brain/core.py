"""
TEKNOFEST 2026 Uluslararası İHA - Elit Komuta ve Karar Merkezi (ArchitectCore)
=============================================================================
Tüm alt sistemleri (Görüntü İşleme, Hedef Takip, Görsel Denetimli Kontrol,
Balistik Hesaplayıcı, Aviyonik Güvenlik, Yük Bırakma ve MAVLink Telemetri)
tek bir orkestrasyon altında senkronize eden ana zeka modülü.
"""

from typing import Dict, Any, Optional
import os
import sys
import time
import argparse
import yaml
import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.vision.detector import VisionDetector, TargetType, TargetDetection
from src.vision.tracker import TargetTracker
from src.vision.camera import CameraInterface
from src.navigation.ballistics import BallisticsCalculator, DropPrediction
from src.navigation.visual_servoing import VisualServoController
from src.navigation.mission_planner import MissionPlanner, MissionState, MissionTask
from src.avionics.failsafe import FailsafeManager, FailsafeLevel, AvionicsHealth
from src.avionics.actuator import PayloadReleaseController, PayloadStatus
from src.telemetry.comms import MavlinkBridge, DroneTelemetry
from src.telemetry.logger import MissionLogger


class ArchitectCore:
    def __init__(self, config_path: str = "config/mission_config.yaml", mode: str = "simulation", task: int = 2):
        self.mode = mode.lower()
        self.config_path = config_path
        self.config = self._load_config(config_path)

        print("=" * 70)
        print("🛸 UAV-ARCHITECT-GLOBAL: TEKNOFEST 2026 ELİT KOMUTA MERKEZİ BAŞLATILIYOR")
        print(f"[*] Çalışma Modu : {self.mode.upper()}")
        print(f"[*] Görev No     : {task}")
        print("=" * 70)

        # 1. Telemetri ve MAVLink Köprüsü
        is_mock_comms = (self.mode == "simulation")
        telemetry_cfg = self.config.get("telemetry", {})
        self.comms = MavlinkBridge(
            connection_str=telemetry_cfg.get("connection_string", "udp:127.0.0.1:14550"),
            baud=telemetry_cfg.get("baudrate", 115200),
            mock_mode=is_mock_comms
        )

        # 2. Aviyonik ve Acil Durum (Failsafe)
        self.failsafe = FailsafeManager(self.config)

        # 3. Aktüatör ve Çift Yük Mekanizması
        self.actuator = PayloadReleaseController(self.config)
        self.actuator.set_comms_bridge(self.comms)
        self.actuator.arm_mechanism()

        # 4. Görüntü İşleme, Kamera ve Takip
        vision_cfg = self.config.get("vision", {})
        camera_src = "synthetic" if self.mode == "simulation" else vision_cfg.get("camera_source", 0)
        self.camera = CameraInterface(
            source=camera_src,
            width=vision_cfg.get("frame_width", 1280),
            height=vision_cfg.get("frame_height", 720),
            fps=vision_cfg.get("fps", 30)
        )
        self.detector = VisionDetector(self.config)
        self.tracker = TargetTracker(alpha=0.7)

        # 5. Navigasyon ve Balistik Yönlendirme
        self.ballistics = BallisticsCalculator(self.config)
        self.servo_controller = VisualServoController(self.config)

        # 6. Görev Durum Makinesi
        self.planner = MissionPlanner(self.config)
        if task == 1:
            self.planner.set_task(MissionTask.TASK_1_COORDINATION)
        elif task == 2:
            self.planner.set_task(MissionTask.TASK_2_DUAL_PAYLOAD)
        else:
            self.planner.set_task(MissionTask.COMBINED_FULL)

        # 7. Telemetri Günlük Kaydedici
        self.logger = MissionLogger()

        self.running = False
        self.status = "HAZIR"
        self.active_locked_target: Optional[TargetDetection] = None
        self.latest_drop_prediction: Optional[DropPrediction] = None

    def _load_config(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[CORE] Yapılandırma dosyası okunamadı ({path}): {e}")
        return {}

    def step(self) -> Dict[str, Any]:
        """
        Komuta merkezinin tek bir döngü adımı (20-50 Hz periyotla çalışır).
        """
        # 1. Telemetri Verilerini Al
        telem = self.comms.fetch_flight_data()
        self.comms.send_heartbeat()

        # 2. Aviyonik ve Failsafe Değerlendirmesi
        health = AvionicsHealth(
            voltage_v=telem.voltage_v,
            current_a=15.0,
            altitude_agl_m=telem.altitude_agl,
            distance_from_home_m=20.0,
            last_heartbeat_time=telem.last_packet_time,
            satellites_visible=telem.satellites_visible,
            ekf_healthy=True
        )
        fs_level, fs_reason = self.failsafe.evaluate(health)
        if self.failsafe.failsafe_triggered:
            self.comms.trigger_rtl()

        # 3. Kamera Görüntüsünü Al ve Hedef Tespiti Yap
        ret, frame = self.camera.read_frame()
        detections = []
        if ret and frame is not None:
            detections = self.detector.detect(frame)

        # Hangi hedefin arandığını belirle
        target_a_detected = any(d.target_type == TargetType.TARGET_A for d in detections)
        target_b_detected = any(d.target_type == TargetType.TARGET_B for d in detections)

        desired_target = None
        if self.planner.state in (MissionState.SEARCHING_TARGET_A, MissionState.LOCKING_TARGET_A):
            desired_target = TargetType.TARGET_A
        elif self.planner.state in (MissionState.SEARCHING_TARGET_B, MissionState.LOCKING_TARGET_B):
            desired_target = TargetType.TARGET_B

        # Takipçiyi güncelle
        self.active_locked_target = self.tracker.update(detections, desired_target_type=desired_target)
        target_a_locked = bool(self.active_locked_target and self.active_locked_target.target_type == TargetType.TARGET_A)
        target_b_locked = bool(self.active_locked_target and self.active_locked_target.target_type == TargetType.TARGET_B)

        # 4. Balistik ve Görsel Denetim Hesaplamaları
        ballistics_ready = False
        lead_dist = 0.0
        miss_dist = 999.0

        if self.active_locked_target is not None:
            cmd = self.servo_controller.compute_control(
                target_offset_norm=self.active_locked_target.normalized_offset,
                target_center_px=self.active_locked_target.center_px,
                screen_dims=(frame.shape[1], frame.shape[0]) if frame is not None else (1280, 720)
            )

            # Hedefe doğru hız komutu gönder
            if self.planner.state in (MissionState.LOCKING_TARGET_A, MissionState.LOCKING_TARGET_B):
                self.comms.send_velocity_ned(cmd.vx_mps, cmd.vy_mps, cmd.vz_mps, cmd.yaw_rate_deg_s)

            # Balistik tahmin yap
            uav_xy = (0.0, 0.0)
            # Normalleştirilmiş sapmadan tahmini yer mesafesi (irtifa * tan(fov/2 * norm))
            fov_rad = np.radians(85.0)
            t_ground_x = telem.altitude_agl * np.tan(fov_rad / 2.0) * self.active_locked_target.normalized_offset[1]
            t_ground_y = telem.altitude_agl * np.tan(fov_rad / 2.0) * self.active_locked_target.normalized_offset[0]

            prediction = self.ballistics.predict_impact(
                uav_pos_xy=uav_xy,
                target_pos_xy=(t_ground_x, t_ground_y),
                velocity_xy=(telem.vx if abs(telem.vx) > 0.1 else 2.5, telem.vy),
                altitude_m=max(5.0, telem.altitude_agl),
                wind_xy=(0.0, 0.0)
            )
            self.latest_drop_prediction = prediction
            lead_dist = prediction.lead_distance_m
            miss_dist = prediction.predicted_miss_distance_m
            ballistics_ready = prediction.is_within_tolerance or (cmd.is_centered and miss_dist < 3.5)

        # 5. Görev Durum Makinesini Güncelle
        prev_state = self.planner.state
        new_state = self.planner.update(
            altitude_agl=telem.altitude_agl,
            target_a_detected=target_a_detected,
            target_a_locked=target_a_locked,
            target_b_detected=target_b_detected,
            target_b_locked=target_b_locked,
            ballistics_ready=ballistics_ready,
            failsafe_triggered=self.failsafe.failsafe_triggered
        )

        # 6. Duruma Özel Eylemler
        if new_state == MissionState.DROPPING_PAYLOAD_1 and prev_state != MissionState.DROPPING_PAYLOAD_1:
            print("[CORE] >>> HEDEF A'YA 1. YÜK (KIRMIZI) BIRAKILIYOR! <<<")
            self.actuator.release_payload_for_target("TARGET_A")
            self.logger.log_event("PAYLOAD_RELEASE", {"slot": 1, "target": "TARGET_A", "color": "red", "altitude": telem.altitude_agl})
            self.tracker.reset()

        elif new_state == MissionState.DROPPING_PAYLOAD_2 and prev_state != MissionState.DROPPING_PAYLOAD_2:
            print("[CORE] >>> HEDEF B'YE 2. YÜK (MAVİ) BIRAKILIYOR! <<<")
            self.actuator.release_payload_for_target("TARGET_B")
            self.logger.log_event("PAYLOAD_RELEASE", {"slot": 2, "target": "TARGET_B", "color": "blue", "altitude": telem.altitude_agl})
            self.tracker.reset()

        elif new_state == MissionState.RETURN_TO_LAUNCH and prev_state != MissionState.RETURN_TO_LAUNCH:
            self.comms.trigger_rtl()
            self.logger.log_event("RTL_INITIATED", {"altitude": telem.altitude_agl})

        # Simülasyon modunda irtifa ve dinamik ilerletme
        if self.mode == "simulation":
            if new_state == MissionState.TAKEOFF:
                telem.altitude_agl += 1.5
            elif new_state in (MissionState.SEARCHING_TARGET_A, MissionState.SEARCHING_TARGET_B):
                telem.altitude_agl = 35.0
                telem.vx = 4.0
            elif new_state in (MissionState.LOCKING_TARGET_A, MissionState.LOCKING_TARGET_B):
                telem.altitude_agl = 20.0
            elif new_state == MissionState.LANDING:
                telem.altitude_agl = max(0.0, telem.altitude_agl - 1.2)

        # 7. Telemetri Günlüğüne Kaydet
        self.logger.log_telemetry_row(
            state=new_state.value,
            altitude_agl=telem.altitude_agl,
            ground_speed=telem.ground_speed,
            vx=telem.vx,
            vy=telem.vy,
            vz=telem.vz,
            battery_v=telem.voltage_v,
            target_locked=self.active_locked_target is not None,
            target_type=self.active_locked_target.target_type.value if self.active_locked_target else "NONE",
            lead_dist=lead_dist,
            miss_dist=miss_dist,
            payloads_left=self.actuator.get_remaining_payload_count()
        )

        return {
            "state": new_state.value,
            "altitude_agl": telem.altitude_agl,
            "ground_speed": telem.ground_speed,
            "detections_count": len(detections),
            "locked_target": self.active_locked_target.target_type.value if self.active_locked_target else None,
            "payloads_remaining": self.actuator.get_remaining_payload_count(),
            "failsafe_status": fs_level.value
        }

    def start_mission(self):
        """Görev dizisini resmi olarak başlatır."""
        self.running = True
        self.status = "OPERASYONEL"
        self.planner.transition_to(MissionState.PREFLIGHT_CHECK, "Kullanıcı/GCS görev başlat komutu verdi")
        print("[CORE] Görev dizisi başlatıldı...")

    def stop_mission(self):
        self.running = False
        self.status = "DURDURULDU"
        self.logger.close()
        self.camera.release()
        print("[CORE] Görev tamamlandı veya durduruldu.")

    def run_simulation(self, max_seconds: float = 40.0):
        """Tam uçuş simülasyonunu baştan sona icra eder."""
        self.start_mission()
        start_time = time.monotonic()
        print(f"[SIMULATOR] Simülasyon başlatıldı (Max: {max_seconds}s)...")

        while self.running and (time.monotonic() - start_time) < max_seconds:
            info = self.step()
            state_str = info["state"]
            alt = info["altitude_agl"]
            pl = info["payloads_remaining"]
            lock = info["locked_target"] or "YOK"

            print(f"\r[T+{time.monotonic()-start_time:.1f}s] DURUM: {state_str:<20} | İrtifa: {alt:5.1f}m | Kilit: {lock:<10} | Kalan Yük: {pl}", end="")

            if state_str == MissionState.LANDED.value:
                print("\n[SIMULATOR] İHA başarıyla iniş yaptı. Görev eksiksiz icra edildi!")
                break

            time.sleep(0.1)

        self.stop_mission()
        print("\n[SIMULATOR] Simülasyon sona erdi.")


def main():
    parser = argparse.ArgumentParser(description="TEKNOFEST 2026 Uluslararası İHA Elit Komuta Merkezi")
    parser.add_argument("--mode", choices=["simulation", "sitl", "live"], default="simulation", help="Çalışma modu")
    parser.add_argument("--task", type=int, choices=[1, 2, 3], default=2, help="Görev Numarası (1: ∞ Uçuş, 2: Çift Yük Bırakma, 3: Tümü)")
    parser.add_argument("--config", default="config/mission_config.yaml", help="Yapılandırma dosyası yolu")
    parser.add_argument("--duration", type=float, default=30.0, help="Simülasyon maksimum süresi (saniye)")

    args = parser.parse_args()
    core = ArchitectCore(config_path=args.config, mode=args.mode, task=args.task)

    if args.mode == "simulation":
        core.run_simulation(max_seconds=args.duration)
    else:
        core.start_mission()
        try:
            while core.running:
                core.step()
                time.sleep(0.05)
        except KeyboardInterrupt:
            core.stop_mission()


if __name__ == "__main__":
    main()
