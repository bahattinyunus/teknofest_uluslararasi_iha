import struct
import pytest
from src.telemetry.mission_uploader import (
    MAVLinkMissionUploader,
    MissionItem,
    MAV_CMD_NAV_WAYPOINT,
    MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
    MAV_MISSION_ACCEPTED
)


def test_mission_item_int_payload_structure():
    item = MissionItem(
        seq=5,
        lat=40.1234567,
        lon=29.7654321,
        alt_m=35.5,
        command=MAV_CMD_NAV_WAYPOINT,
        param1_hold_time_s=3.0,
        param2_accept_radius_m=2.5
    )

    payload = item.to_item_int_payload(target_sys=1, target_comp=1)
    assert len(payload) == 38  # Standard MAVLink v2 MISSION_ITEM_INT payload length

    # Parse and verify
    p1, p2, p3, p4, lat_i, lon_i, alt, seq, cmd, t_sys, t_comp, frame, curr, autocont, m_type = struct.unpack(
        "<ffffiifHHBBBBBB", payload
    )
    assert abs(p1 - 3.0) < 1e-3
    assert abs(p2 - 2.5) < 1e-3
    assert lat_i == int(round(40.1234567 * 1e7))
    assert lon_i == int(round(29.7654321 * 1e7))
    assert abs(alt - 35.5) < 1e-3
    assert seq == 5
    assert cmd == MAV_CMD_NAV_WAYPOINT
    assert frame == MAV_FRAME_GLOBAL_RELATIVE_ALT_INT


def test_mission_uploader_count_packet():
    uploader = MAVLinkMissionUploader(sys_id=255, comp_id=1, target_sys=1, target_comp=1)
    items = [
        MissionItem(seq=0, lat=40.0, lon=29.0, alt_m=20.0),
        MissionItem(seq=1, lat=40.1, lon=29.1, alt_m=25.0)
    ]
    raw_packet = uploader.start_upload(items)
    assert len(raw_packet) > 10
    assert uploader.state == "COUNT_SENT"
    assert len(uploader.mission_items) == 2


def test_mission_uploader_handshake_simulation():
    uploader = MAVLinkMissionUploader()
    items = [
        MissionItem(seq=0, lat=40.0, lon=29.0, alt_m=20.0),
        MissionItem(seq=1, lat=40.001, lon=29.001, alt_m=30.0),
        MissionItem(seq=2, lat=40.002, lon=29.002, alt_m=25.0)
    ]

    res = uploader.simulate_mock_handshake(items)
    assert res["success"] is True
    assert res["state"] == "COMPLETE"
    assert res["items_uploaded"] == 3
    assert res["ack_result"] == MAV_MISSION_ACCEPTED
