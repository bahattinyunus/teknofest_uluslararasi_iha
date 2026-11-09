"""
TEKNOFEST 2026 - Hardware-In-The-Loop (HIL) MAVLink v2 Telemetry Engine
Pure-Python, zero-dependency implementation of MAVLink v2 framing, CRC-16 checksum,
and binary serialization for standard GCS interoperability (QGroundControl, Mission Planner, Web GCS).
"""
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple, Dict, Any, List


class MAVType(IntEnum):
    GENERIC = 0
    QUADROTOR = 2
    HEXAROTOR = 13
    FIXED_WING = 1


class MAVAutopilot(IntEnum):
    GENERIC = 0
    ARDUPILOT = 3
    PX4 = 12


class MAVState(IntEnum):
    UNINIT = 0
    BOOT = 1
    CALIBRATING = 2
    STANDBY = 3
    ACTIVE = 4
    CRITICAL = 5
    EMERGENCY = 6


class MAVCmd(IntEnum):
    NAV_WAYPOINT = 16
    NAV_RETURN_TO_LAUNCH = 20
    NAV_LAND = 21
    NAV_TAKEOFF = 22
    DO_SET_SERVO = 183
    COMPONENT_ARM_DISARM = 400


@dataclass
class MAVLinkPacket:
    seq: int
    sys_id: int
    comp_id: int
    msg_id: int
    payload: bytes
    crc: int


@dataclass
class HILMetrics:
    packets_sent: int = 0
    packets_received: int = 0
    crc_errors: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_rtt_ms: float = 0.0


def calculate_mavlink_crc(buffer: bytes, crc_extra: int = 0) -> int:
    """
    Computes MAVLink X.25 / MCRF4XX CRC-16.
    """
    crc = 0xFFFF
    for b in buffer:
        tmp = b ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF

    # Accumulate CRC extra byte
    if crc_extra != 0:
        tmp = crc_extra ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF

    return crc


class MAVLinkHILEngine:
    """
    MAVLink v2 binary protocol engine for Hardware-In-The-Loop simulation
    and real-time flight computer telemetry interfacing.
    """
    MAGIC_V2 = 0xFD

    # Message IDs and their standard CRC Extra constants
    MSG_HEARTBEAT = 0
    CRC_EXTRA_HEARTBEAT = 50

    MSG_SYS_STATUS = 1
    CRC_EXTRA_SYS_STATUS = 124

    MSG_ATTITUDE = 30
    CRC_EXTRA_ATTITUDE = 39

    MSG_GLOBAL_POSITION_INT = 33
    CRC_EXTRA_GLOBAL_POSITION_INT = 104

    MSG_VFR_HUD = 74
    CRC_EXTRA_VFR_HUD = 20

    MSG_COMMAND_LONG = 76
    CRC_EXTRA_COMMAND_LONG = 152

    def __init__(self, sys_id: int = 1, comp_id: int = 1):
        self.sys_id = sys_id
        self.comp_id = comp_id
        self.seq = 0
        self.metrics = HILMetrics()

    def _next_seq(self) -> int:
        s = self.seq
        self.seq = (self.seq + 1) % 256
        return s

    def encode_packet(self, msg_id: int, payload: bytes, crc_extra: int = 0) -> bytes:
        """
        Encodes payload into standard MAVLink v2 frame:
        [STX=0xFD, LEN, INC_FLAGS, COMPAT_FLAGS, SEQ, SYS_ID, COMP_ID, MSG_ID(3B), PAYLOAD, CRC(2B)]
        """
        stx = self.MAGIC_V2
        length = len(payload)
        incompat_flags = 0
        compat_flags = 0
        seq = self._next_seq()

        msg_id_bytes = struct.pack("<I", msg_id)[:3]

        header = struct.pack(
            "<BBBBBB",
            stx,
            length,
            incompat_flags,
            compat_flags,
            seq,
            self.sys_id
        ) + bytes([self.comp_id]) + msg_id_bytes

        # Checksum is calculated over header (excluding STX) + payload + crc_extra
        crc_buffer = header[1:] + payload
        crc = calculate_mavlink_crc(crc_buffer, crc_extra)
        crc_bytes = struct.pack("<H", crc)

        packet = header + payload + crc_bytes
        self.metrics.packets_sent += 1
        self.metrics.bytes_sent += len(packet)
        return packet

    def decode_packet(self, data: bytes, crc_extra_map: Optional[Dict[int, int]] = None) -> Optional[MAVLinkPacket]:
        """
        Parses and validates a MAVLink v2 binary packet.
        """
        if len(data) < 12:
            return None

        self.metrics.bytes_received += len(data)

        stx, length, incompat, compat, seq, sys_id, comp_id = struct.unpack("<BBBBBBB", data[:7])
        if stx != self.MAGIC_V2:
            return None

        msg_id = data[7] | (data[8] << 8) | (data[9] << 16)
        expected_len = 10 + length + 2
        if len(data) < expected_len:
            return None

        payload = data[10:10 + length]
        received_crc = struct.unpack("<H", data[10 + length:10 + length + 2])[0]

        crc_extra = 0
        if crc_extra_map and msg_id in crc_extra_map:
            crc_extra = crc_extra_map[msg_id]
        elif msg_id == self.MSG_HEARTBEAT:
            crc_extra = self.CRC_EXTRA_HEARTBEAT
        elif msg_id == self.MSG_SYS_STATUS:
            crc_extra = self.CRC_EXTRA_SYS_STATUS
        elif msg_id == self.MSG_ATTITUDE:
            crc_extra = self.CRC_EXTRA_ATTITUDE
        elif msg_id == self.MSG_GLOBAL_POSITION_INT:
            crc_extra = self.CRC_EXTRA_GLOBAL_POSITION_INT
        elif msg_id == self.MSG_VFR_HUD:
            crc_extra = self.CRC_EXTRA_VFR_HUD
        elif msg_id == self.MSG_COMMAND_LONG:
            crc_extra = self.CRC_EXTRA_COMMAND_LONG

        calc_crc = calculate_mavlink_crc(data[1:10 + length], crc_extra)
        if calc_crc != received_crc:
            self.metrics.crc_errors += 1
            return None

        self.metrics.packets_received += 1
        return MAVLinkPacket(
            seq=seq,
            sys_id=sys_id,
            comp_id=comp_id,
            msg_id=msg_id,
            payload=payload,
            crc=received_crc
        )

    # ---------------- Pack Helpers ----------------

    def pack_heartbeat(self,
                       mav_type: MAVType = MAVType.QUADROTOR,
                       autopilot: MAVAutopilot = MAVAutopilot.ARDUPILOT,
                       base_mode: int = 129,  # Armed + Auto
                       custom_mode: int = 3,  # AUTO
                       system_status: MAVState = MAVState.ACTIVE) -> bytes:
        """Packs HEARTBEAT message (ID 0, len 9)."""
        payload = struct.pack("<IBBBBB", custom_mode, mav_type, autopilot, base_mode, system_status, 3)
        return self.encode_packet(self.MSG_HEARTBEAT, payload, self.CRC_EXTRA_HEARTBEAT)

    def pack_global_position_int(self,
                                 time_boot_ms: int,
                                 lat_deg: float,
                                 lon_deg: float,
                                 alt_m: float,
                                 relative_alt_m: float,
                                 vx_mps: float,
                                 vy_mps: float,
                                 vz_mps: float,
                                 hdg_deg: float) -> bytes:
        """Packs GLOBAL_POSITION_INT (ID 33, len 28)."""
        lat_int = int(lat_deg * 1e7)
        lon_int = int(lon_deg * 1e7)
        alt_mm = int(alt_m * 1000.0)
        rel_alt_mm = int(relative_alt_m * 1000.0)
        vx_cm = int(vx_mps * 100.0)
        vy_cm = int(vy_mps * 100.0)
        vz_cm = int(vz_mps * 100.0)
        hdg_cdeg = int(hdg_deg * 100.0)

        payload = struct.pack(
            "<IiiiihhhH",
            time_boot_ms,
            lat_int,
            lon_int,
            alt_mm,
            rel_alt_mm,
            vx_cm,
            vy_cm,
            vz_cm,
            hdg_cdeg
        )
        return self.encode_packet(self.MSG_GLOBAL_POSITION_INT, payload, self.CRC_EXTRA_GLOBAL_POSITION_INT)

    def pack_attitude(self,
                      time_boot_ms: int,
                      roll_rad: float,
                      pitch_rad: float,
                      yaw_rad: float,
                      rollspeed_rads: float = 0.0,
                      pitchspeed_rads: float = 0.0,
                      yawspeed_rads: float = 0.0) -> bytes:
        """Packs ATTITUDE (ID 30, len 28)."""
        payload = struct.pack(
            "<Iffffff",
            time_boot_ms,
            roll_rad,
            pitch_rad,
            yaw_rad,
            rollspeed_rads,
            pitchspeed_rads,
            yawspeed_rads
        )
        return self.encode_packet(self.MSG_ATTITUDE, payload, self.CRC_EXTRA_ATTITUDE)

    def pack_command_long(self,
                          target_system: int,
                          target_component: int,
                          command: MAVCmd,
                          confirmation: int = 0,
                          param1: float = 0.0,
                          param2: float = 0.0,
                          param3: float = 0.0,
                          param4: float = 0.0,
                          param5: float = 0.0,
                          param6: float = 0.0,
                          param7: float = 0.0) -> bytes:
        """Packs COMMAND_LONG (ID 76, len 33)."""
        payload = struct.pack(
            "<fffffffHBB",
            param1, param2, param3, param4, param5, param6, param7,
            command,
            target_system,
            target_component
        )
        return self.encode_packet(self.MSG_COMMAND_LONG, payload, self.CRC_EXTRA_COMMAND_LONG)

    def unpack_command_long(self, payload: bytes) -> Dict[str, Any]:
        """Unpacks COMMAND_LONG payload."""
        p1, p2, p3, p4, p5, p6, p7, cmd, target_sys, target_comp = struct.unpack("<fffffffHBB", payload)
        return {
            "param1": p1, "param2": p2, "param3": p3, "param4": p4,
            "param5": p5, "param6": p6, "param7": p7,
            "command": cmd,
            "target_system": target_sys,
            "target_component": target_comp
        }
