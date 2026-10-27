"""
TEKNOFEST 2026 Uluslararası İHA - MAVLink Haberleşme ve Telemetri Köprüsü
-------------------------------------------------------------------------
NVIDIA Jetson / Görev Bilgisayarı ile Pixhawk (ArduPilot/PX4) uçuş kontrol
kartı arasında çift yönlü yüksek hızlı MAVLink haberleşmesi sağlar.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import time
import math


@dataclass
class DroneTelemetry:
    altitude_agl: float = 0.0
    latitude: float = 41.0082
    longitude: float = 28.9784
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    ground_speed: float = 0.0
    heading_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    voltage_v: float = 16.2  # 4S dolu voltaj
    battery_remaining_pct: float = 95.0
    satellites_visible: int = 14
    armed: bool = False
    flight_mode: str = "GUIDED"
    last_packet_time: float = 0.0


class MavlinkBridge:
    def __init__(self, connection_str: str = "udp:127.0.0.1:14550", baud: int = 115200, mock_mode: bool = False):
        self.connection_str = connection_str
        self.baud = baud
        self.mock_mode = mock_mode
        self.mav = None
        self.telemetry = DroneTelemetry()
        self.connected = False

        self._init_connection()

    def _init_connection(self):
        if self.mock_mode:
            print("[COMMS] Mock MAVLink simülasyon modu devrede.")
            self.connected = True
            self.telemetry.last_packet_time = time.monotonic()
            return

        try:
            from pymavlink import mavutil
            print(f"[COMMS] AutoPilot'a bağlanılıyor: {self.connection_str} (Baud: {self.baud})...")
            self.mav = mavutil.mavlink_connection(self.connection_str, baud=self.baud)
            # Bağlantı doğrulaması için kısa bekleme
            msg = self.mav.wait_heartbeat(timeout=1.5)
            if msg:
                self.connected = True
                print(f"[COMMS] Pixhawk Kalp Atışı Alındı! (Sistem: {self.mav.target_system}, Bileşen: {self.mav.target_component})")
            else:
                print("[COMMS] UYARI: Donanımdan kalp atışı gelmedi. Simülasyon moduna geçiliyor.")
                self.mock_mode = True
                self.connected = True
        except Exception as e:
            print(f"[COMMS] MAVLink bağlantı hatası ({e}). Simülasyon moduna geçiliyor.")
            self.mock_mode = True
            self.connected = True

    def send_heartbeat(self):
        """Otopilota görev bilgisayarı kalp atışı iletir (1 Hz)."""
        if self.mock_mode or self.mav is None:
            self.telemetry.last_packet_time = time.monotonic()
            return

        try:
            from pymavlink import mavutil
            self.mav.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0, 0
            )
        except Exception as e:
            print(f"[COMMS] Kalp atışı iletim hatası: {e}")

    def send_velocity_ned(self, vx: float, vy: float, vz: float, yaw_rate_deg_s: float = 0.0):
        """
        Yerel NED (Kuzey-Doğu-Aşağı) koordinatlarında İHA'ya hız vektörü gönderir.
        Görsel Denetimli Kontrol (Visual Servoing) için esastır.
        """
        if self.mock_mode or self.mav is None:
            # Simülasyon içi konum güncelleme
            dt = 0.05
            self.telemetry.vx = vx
            self.telemetry.vy = vy
            self.telemetry.vz = vz
            self.telemetry.ground_speed = math.hypot(vx, vy)
            self.telemetry.altitude_agl = max(0.0, self.telemetry.altitude_agl - vz * dt)
            self.telemetry.last_packet_time = time.monotonic()
            return

        try:
            from pymavlink import mavutil
            yaw_rate_rad = math.radians(yaw_rate_deg_s)
            type_mask = 0b0000101111000111  # Yalnızca vx, vy, vz ve yaw_rate aktif

            self.mav.mav.set_position_target_local_ned_send(
                0,  # time_boot_ms
                self.mav.target_system,
                self.mav.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_NED,
                type_mask,
                0, 0, 0,  # x, y, z (kullanılmıyor)
                vx, vy, vz,  # vx, vy, vz (m/s)
                0, 0, 0,  # ivmeler (kullanılmıyor)
                0, yaw_rate_rad  # yaw, yaw_rate (rad/s)
            )
        except Exception as e:
            print(f"[COMMS] Hız komutu gönderim hatası: {e}")

    def set_servo(self, channel: int, pwm_us: int):
        """
        Yük bırakma servosunu tetiklemek için MAV_CMD_DO_SET_SERVO komutu gönderir.
        """
        print(f"[COMMS] MAVLink: MAV_CMD_DO_SET_SERVO CH{channel} -> {pwm_us} us")
        if self.mock_mode or self.mav is None:
            return

        try:
            from pymavlink import mavutil
            self.mav.mav.command_long_send(
                self.mav.target_system,
                self.mav.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,  # Onay
                channel,
                pwm_us,
                0, 0, 0, 0, 0
            )
        except Exception as e:
            print(f"[COMMS] Servo komut iletim hatası: {e}")

    def trigger_rtl(self):
        """İHA'ya Return-To-Launch (Eve Dönüş) komutu gönderir."""
        print("[COMMS] MAVLink: MAV_CMD_NAV_RETURN_TO_LAUNCH gönderildi!")
        self.telemetry.flight_mode = "RTL"
        if self.mock_mode or self.mav is None:
            return

        try:
            from pymavlink import mavutil
            self.mav.mav.command_long_send(
                self.mav.target_system,
                self.mav.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0, 0, 0, 0, 0, 0, 0, 0
            )
        except Exception as e:
            print(f"[COMMS] RTL komut iletim hatası: {e}")

    def fetch_flight_data(self) -> DroneTelemetry:
        """En güncel uçuş telemetri paketini döndürür."""
        if self.mock_mode or self.mav is None:
            return self.telemetry

        try:
            # Gelen paketleri tüket ve telemetriyi güncelle
            while True:
                msg = self.mav.recv_msg()
                if msg is None:
                    break

                msg_type = msg.get_type()
                self.telemetry.last_packet_time = time.monotonic()

                if msg_type == "GLOBAL_POSITION_INT":
                    self.telemetry.altitude_agl = msg.relative_alt / 1000.0  # mm -> m
                    self.telemetry.latitude = msg.lat / 1e7
                    self.telemetry.longitude = msg.lon / 1e7
                    self.telemetry.vx = msg.vx / 100.0
                    self.telemetry.vy = msg.vy / 100.0
                    self.telemetry.vz = msg.vz / 100.0
                    self.telemetry.heading_deg = msg.hdg / 100.0
                    self.telemetry.ground_speed = math.hypot(self.telemetry.vx, self.telemetry.vy)

                elif msg_type == "ATTITUDE":
                    self.telemetry.roll_deg = math.degrees(msg.roll)
                    self.telemetry.pitch_deg = math.degrees(msg.pitch)

                elif msg_type == "SYS_STATUS":
                    self.telemetry.voltage_v = msg.voltage_battery / 1000.0
                    self.telemetry.battery_remaining_pct = float(msg.battery_remaining)

                elif msg_type == "GPS_RAW_INT":
                    self.telemetry.satellites_visible = msg.satellites_visible

                elif msg_type == "HEARTBEAT":
                    self.telemetry.armed = bool(msg.base_mode & 128)
        except Exception as e:
            print(f"[COMMS] Telemetri okuma hatası: {e}")

        return self.telemetry
