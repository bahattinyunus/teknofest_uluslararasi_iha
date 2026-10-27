"""
TEKNOFEST 2026 Uluslararası İHA - Çift Yük Bırakma Mekanizması (Actuators)
------------------------------------------------------------------------
Kırmızı ve Mavi yüklerin servolar vasıtasıyla hassas, güvenli ve bağımsız
olarak bırakılmasını yöneten donanım aktüatör kontrolcüsü.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
import time


class PayloadStatus(str, Enum):
    LOADED = "LOADED"
    ARMED = "ARMED"
    RELEASED = "RELEASED"
    FAILED = "FAILED"


@dataclass
class PayloadSlot:
    slot_id: int
    color: str            # "red" | "blue"
    target_type: str      # "TARGET_A" | "TARGET_B"
    servo_channel: int    # PWM Kanalı (ör. 9, 10)
    open_pwm: int         # Bırakma PWM (ör. 1900us)
    closed_pwm: int       # Kilitli PWM (ör. 1100us)
    status: PayloadStatus
    release_timestamp: Optional[float] = None


class PayloadReleaseController:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        p_cfg = cfg.get("payload", {})
        slots_cfg = p_cfg.get("payload_slots", {})

        # Slot 1: Kırmızı Yük (Hedef A - Mavi için)
        s1 = slots_cfg.get("slot_1", {})
        self.slot_1 = PayloadSlot(
            slot_id=1,
            color=s1.get("color", "red"),
            target_type=s1.get("target_type", "TARGET_A"),
            servo_channel=s1.get("servo_channel", 9),
            open_pwm=s1.get("open_pwm", 1900),
            closed_pwm=s1.get("closed_pwm", 1100),
            status=PayloadStatus.LOADED
        )

        # Slot 2: Mavi Yük (Hedef B - Kırmızı için)
        s2 = slots_cfg.get("slot_2", {})
        self.slot_2 = PayloadSlot(
            slot_id=2,
            color=s2.get("color", "blue"),
            target_type=s2.get("target_type", "TARGET_B"),
            servo_channel=s2.get("servo_channel", 10),
            open_pwm=s2.get("open_pwm", 1900),
            closed_pwm=s2.get("closed_pwm", 1100),
            status=PayloadStatus.LOADED
        )

        self.armed_for_release = False
        self.comms_bridge = None  # MAVLink köprüsü bağlanabilir

    def set_comms_bridge(self, bridge):
        self.comms_bridge = bridge

    def arm_mechanism(self):
        """Yük bırakma güvenlik kilidini açar."""
        self.armed_for_release = True
        if self.slot_1.status == PayloadStatus.LOADED:
            self.slot_1.status = PayloadStatus.ARMED
        if self.slot_2.status == PayloadStatus.LOADED:
            self.slot_2.status = PayloadStatus.ARMED
        print("[ACTUATOR] Yük bırakma mekanizması KURULDU (ARMED).")

    def disarm_mechanism(self):
        """Güvenlik kilidini kapatır."""
        self.armed_for_release = False
        if self.slot_1.status == PayloadStatus.ARMED:
            self.slot_1.status = PayloadStatus.LOADED
        if self.slot_2.status == PayloadStatus.ARMED:
            self.slot_2.status = PayloadStatus.LOADED
        print("[ACTUATOR] Yük bırakma mekanizması KİLİTLENDİ (DISARMED).")

    def release_payload_for_target(self, target_type: str) -> bool:
        """
        Hedef tipine karşılık gelen yükü otonom olarak bırakır.
        TARGET_A -> Slot 1 (Kırmızı Yük)
        TARGET_B -> Slot 2 (Mavi Yük)
        """
        if not self.armed_for_release:
            print("[ACTUATOR UYARI] Bırakma reddedildi: Mekanizma ARM edilmemiş!")
            return False

        if target_type == "TARGET_A":
            return self._trigger_slot(self.slot_1)
        elif target_type == "TARGET_B":
            return self._trigger_slot(self.slot_2)
        else:
            print(f"[ACTUATOR HATA] Tanımsız hedef tipi: {target_type}")
            return False

    def _trigger_slot(self, slot: PayloadSlot) -> bool:
        if slot.status == PayloadStatus.RELEASED:
            print(f"[ACTUATOR] Slot {slot.slot_id} ({slot.color}) daha önce bırakılmış.")
            return False

        print(f"[ACTUATOR] >>> BIRAKMA EMRİ <<< : Slot {slot.slot_id} ({slot.color} Yük) -> Servo CH{slot.servo_channel} PWM={slot.open_pwm}")
        
        # MAVLink üzerinden Pixhawk servo kanalını tetikle
        if self.comms_bridge is not None:
            self.comms_bridge.set_servo(slot.servo_channel, slot.open_pwm)

        slot.status = PayloadStatus.RELEASED
        slot.release_timestamp = time.monotonic()
        return True

    def get_remaining_payload_count(self) -> int:
        count = 0
        if self.slot_1.status in (PayloadStatus.LOADED, PayloadStatus.ARMED):
            count += 1
        if self.slot_2.status in (PayloadStatus.LOADED, PayloadStatus.ARMED):
            count += 1
        return count
