"""
Unit tests for Hardware-In-The-Loop (HIL) MAVLink v2 Telemetry Engine
"""
import pytest
import math
from src.telemetry.mavlink_hil import (
    MAVLinkHILEngine,
    MAVType,
    MAVAutopilot,
    MAVState,
    MAVCmd,
    calculate_mavlink_crc
)


def test_mavlink_heartbeat_encode_decode():
    engine = MAVLinkHILEngine(sys_id=1, comp_id=1)
    packet_bytes = engine.pack_heartbeat(
        mav_type=MAVType.QUADROTOR,
        autopilot=MAVAutopilot.ARDUPILOT,
        system_status=MAVState.ACTIVE
    )
    assert len(packet_bytes) > 10
    assert packet_bytes[0] == 0xFD  # MAVLink v2 Magic byte

    # Decode
    decoded = engine.decode_packet(packet_bytes)
    assert decoded is not None
    assert decoded.msg_id == MAVLinkHILEngine.MSG_HEARTBEAT
    assert decoded.sys_id == 1
    assert decoded.comp_id == 1
    assert engine.metrics.packets_sent == 1
    assert engine.metrics.packets_received == 1


def test_mavlink_global_position_int_pack():
    engine = MAVLinkHILEngine(sys_id=1, comp_id=1)
    packet_bytes = engine.pack_global_position_int(
        time_boot_ms=12500,
        lat_deg=41.0082,
        lon_deg=28.9784,
        alt_m=35.5,
        relative_alt_m=30.0,
        vx_mps=12.5,
        vy_mps=-1.2,
        vz_mps=0.0,
        hdg_deg=180.0
    )
    decoded = engine.decode_packet(packet_bytes)
    assert decoded is not None
    assert decoded.msg_id == MAVLinkHILEngine.MSG_GLOBAL_POSITION_INT


def test_mavlink_command_long_roundtrip():
    engine = MAVLinkHILEngine(sys_id=1, comp_id=1)
    cmd_bytes = engine.pack_command_long(
        target_system=1,
        target_component=1,
        command=MAVCmd.DO_SET_SERVO,
        param1=9.0,   # servo channel 9
        param2=1900.0 # 1900 us PWM
    )
    decoded = engine.decode_packet(cmd_bytes)
    assert decoded is not None
    assert decoded.msg_id == MAVLinkHILEngine.MSG_COMMAND_LONG

    unpacked = engine.unpack_command_long(decoded.payload)
    assert unpacked["command"] == MAVCmd.DO_SET_SERVO
    assert math.isclose(unpacked["param1"], 9.0, abs_tol=1e-3)
    assert math.isclose(unpacked["param2"], 1900.0, abs_tol=1e-3)


def test_mavlink_corrupted_crc_rejected():
    engine = MAVLinkHILEngine(sys_id=1, comp_id=1)
    packet_bytes = engine.pack_heartbeat()
    # Corrupt a byte in the payload
    corrupted = bytearray(packet_bytes)
    corrupted[11] ^= 0xFF

    decoded = engine.decode_packet(bytes(corrupted))
    assert decoded is None
    assert engine.metrics.crc_errors == 1
