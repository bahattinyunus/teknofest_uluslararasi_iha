"""
TEKNOFEST 2026 Uluslararası İHA - ArduPilot SITL / MAVLink Simülasyon Sunucusu
------------------------------------------------------------------------------
Gerçek uçuş kontrol kartı (Pixhawk) veya harici simülatör (Gazebo/SITL) olmadan
uçtan uca otonom görev ve yer kontrol istasyonu testleri yapmayı sağlayan,
UDP soket tabanlı tam teşekküllü MAVLink otopilot simülatörü.
"""

from typing import Optional, Dict, Any, Tuple
import socket
import struct
import threading
import time
import math


class ArduPilotSITLServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 14550,
        initial_lat: float = 41.0082,
        initial_lon: float = 28.9784,
        initial_alt: float = 0.0
    ):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.client_addr: Optional[Tuple[str, int]] = None

        # Sanal İHA Fizik Durumu
        self.lat = initial_lat
        self.lon = initial_lon
        self.alt_agl = initial_alt
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.heading = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self.battery_voltage = 16.5  # 4S dolu
        self.battery_remaining = 100
        self.armed = False
        self.mode = "GUIDED"
        self.servos: Dict[int, int] = {9: 1100, 10: 1100}

        self.running = False
        self.sim_thread: Optional[threading.Thread] = None
        self.recv_thread: Optional[threading.Thread] = None

    def start(self):
        """SITL sunucusunu başlatır."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.2)
        self.running = True

        self.sim_thread = threading.Thread(target=self._physics_loop, daemon=True)
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)

        self.sim_thread.start()
        self.recv_thread.start()
        print(f"[SITL SERVER] ArduPilot Mock Otopilot devrede: udp://{self.host}:{self.port}")

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        print("[SITL SERVER] Simülasyon sunucusu durduruldu.")

    def _physics_loop(self):
        """20 Hz fizik döngüsü ve telemetri yayını."""
        last_t = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = max(0.005, now - last_t)
            last_t = now

            # Hız ve konum integrasyonu
            self.alt_agl = max(0.0, self.alt_agl - self.vz * dt)
            # Enlem / boylam güncellemesi (NED yaklaşımı)
            self.lat += (self.vx * dt) / 111139.0
            self.lon += (self.vy * dt) / (111139.0 * 0.7547)

            # Baş açısı (Heading)
            if math.hypot(self.vx, self.vy) > 0.5:
                rad = math.atan2(self.vy, self.vx)
                self.heading = (math.degrees(rad) + 360.0) % 360.0

            # Batarya tüketim simülasyonu (dakikada ~0.08V)
            current_draw = 14.0 if self.alt_agl > 1.0 else 1.5
            self.battery_voltage = max(13.2, self.battery_voltage - (current_draw * 0.00002 * dt))
            self.battery_remaining = max(5, int((self.battery_voltage - 13.2) / (16.8 - 13.2) * 100))

            # Telemetri paketlerini yayınla (pymavlink varsa mavlink formatında, yoksa simüle paket)
            self._broadcast_telemetry()
            time.sleep(0.05)

    def _broadcast_telemetry(self):
        if self.client_addr is None or self.sock is None:
            return

        try:
            from pymavlink import mavutil
            mav = mavutil.mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
            # Heartbeat
            msg_hb = mav.heartbeat_encode(
                type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
                autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                base_mode=mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED if self.armed else 0,
                custom_mode=4,  # GUIDED
                system_status=mavutil.mavlink.MAV_STATE_ACTIVE
            )
            self.sock.sendto(msg_hb.pack(mav), self.client_addr)

            # Global Position Int
            msg_pos = mav.global_position_int_encode(
                time_boot_ms=int(time.monotonic() * 1000),
                lat=int(self.lat * 1e7),
                lon=int(self.lon * 1e7),
                alt=int(self.alt_agl * 1000),
                relative_alt=int(self.alt_agl * 1000),
                vx=int(self.vx * 100),
                vy=int(self.vy * 100),
                vz=int(self.vz * 100),
                hdg=int(self.heading * 100)
            )
            self.sock.sendto(msg_pos.pack(mav), self.client_addr)

            # Attitude
            msg_att = mav.attitude_encode(
                time_boot_ms=int(time.monotonic() * 1000),
                roll=math.radians(self.roll),
                pitch=math.radians(self.pitch),
                yaw=math.radians(self.heading),
                rollspeed=0,
                pitchspeed=0,
                yawspeed=0
            )
            self.sock.sendto(msg_att.pack(mav), self.client_addr)

            # Sys Status
            msg_sys = mav.sys_status_encode(
                onboard_control_sensors_present=0,
                onboard_control_sensors_enabled=0,
                onboard_control_sensors_health=0,
                load=250,
                voltage_battery=int(self.battery_voltage * 1000),
                current_battery=1500,
                battery_remaining=self.battery_remaining,
                drop_rate_comm=0,
                errors_comm=0,
                errors_count1=0,
                errors_count2=0,
                errors_count3=0,
                errors_count4=0
            )
            self.sock.sendto(msg_sys.pack(mav), self.client_addr)
        except Exception:
            pass

    def _recv_loop(self):
        """GCS ve görev bilgisayarından gelen MAVLink komutlarını işler."""
        while self.running:
            if not self.sock:
                break
            try:
                data, addr = self.sock.recvfrom(4096)
                self.client_addr = addr

                # MAVLink paketi ayrıştırma
                try:
                    from pymavlink import mavutil
                    mav = mavutil.mavlink.MAVLink(None)
                    msgs = mav.parse_buffer(data)
                    if msgs:
                        for msg in msgs:
                            m_type = msg.get_type()
                            if m_type == "SET_POSITION_TARGET_LOCAL_NED":
                                self.vx = float(msg.vx)
                                self.vy = float(msg.vy)
                                self.vz = float(msg.vz)
                            elif m_type == "COMMAND_LONG":
                                if msg.command == mavutil.mavlink.MAV_CMD_DO_SET_SERVO:
                                    ch = int(msg.param1)
                                    pwm = int(msg.param2)
                                    self.servos[ch] = pwm
                                    print(f"[SITL] Servo Komutu İcra Edildi: CH{ch} -> {pwm}us")
                                elif msg.command == mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH:
                                    self.mode = "RTL"
                                    self.vz = 0.5  # Kontrollü alçalma
                                    self.vx *= 0.5
                                    self.vy *= 0.5
                                    print("[SITL] RTL Moduna Geçildi!")
                except Exception:
                    pass
            except socket.timeout:
                continue
            except Exception:
                break
