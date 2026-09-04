from __future__ import annotations

import pytest

from pathlib import Path

from ysf_bm_router.bridge.modeconv import (
    dmr_voice_frame_to_ysf_vch,
    make_dmr_control_payload,
    make_dmr_lc_control_payload,
    make_dmr_voice_payload,
    ysf_vd2_frame_to_dmr_voice_frames,
)
from ysf_bm_router.brandmeister.dmr_master import (
    DmrMasterBrandMeisterTransport,
    _build_options_packet,
    _subscriber_id_from_repeater_id,
)
from ysf_bm_router.dmr.homebrew import (
    DT_TERMINATOR_WITH_LC,
    DT_VOICE,
    DT_VOICE_LC_HEADER,
    DT_VOICE_SYNC,
    DmrFrame,
    build_dmrd_packet,
    parse_dmrd_packet,
)
from ysf_bm_router.models import BrandMeisterConfig


def test_parse_dmrd_voice_sync_packet() -> None:
    frame = parse_dmrd_packet(make_dmrd(flags=0x90))

    assert frame.slot == 2
    assert frame.source_id == 3161899
    assert frame.destination_id == 3205642
    assert frame.repeater_id == 312930110
    assert frame.stream_id == 0x12345678
    assert frame.data_type == DT_VOICE_SYNC
    assert frame.voice_index == 0
    assert frame.is_voice is True


def test_parse_dmrd_header_and_terminator_packets() -> None:
    header = parse_dmrd_packet(make_dmrd(flags=0xA1))
    terminator = parse_dmrd_packet(make_dmrd(flags=0xA2))

    assert header.data_type == DT_VOICE_LC_HEADER
    assert header.is_header is True
    assert terminator.data_type == DT_TERMINATOR_WITH_LC
    assert terminator.is_terminator is True


def test_parse_dmrd_private_call_flag_is_not_data_sync() -> None:
    frame = parse_dmrd_packet(make_dmrd(flags=0xE1))

    assert frame.data_type == DT_VOICE_LC_HEADER
    assert frame.flco_group is False


def test_parse_dmrd_plain_voice_packet() -> None:
    frame = parse_dmrd_packet(make_dmrd(flags=0x83))

    assert frame.data_type == DT_VOICE
    assert frame.voice_index == 3


def test_build_dmrd_round_trip() -> None:
    frame = DmrFrame(
        sequence=42,
        slot=2,
        source_id=3161899,
        destination_id=3205642,
        repeater_id=312930110,
        stream_id=0x12345678,
        data_type=DT_TERMINATOR_WITH_LC,
        voice_index=DT_TERMINATOR_WITH_LC,
        flco_group=True,
        payload=bytes(range(33)),
        ber=0,
        rssi=0,
    )

    packet = build_dmrd_packet(frame)
    parsed = parse_dmrd_packet(packet)

    assert len(packet) == 55
    assert parsed == frame


def test_parse_dmrd_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="55 bytes"):
        parse_dmrd_packet(b"DMRD")
    with pytest.raises(ValueError, match="not a DMRD"):
        parse_dmrd_packet(b"BAD!" + bytes(51))


def test_dmr_voice_frame_to_ysf_vch_returns_three_chunks() -> None:
    chunks = dmr_voice_frame_to_ysf_vch(bytes(range(33)))

    assert len(chunks) == 3
    assert all(len(chunk) == 13 for chunk in chunks)
    assert len(set(chunks)) > 1


def test_ysf_vd2_frame_to_dmr_voice_frames_returns_two_frames() -> None:
    frames = ysf_vd2_frame_to_dmr_voice_frames(Path("tests/fixtures/ysf/dgid10_seq20.bin").read_bytes())

    assert len(frames) == 2
    assert all(len(frame) == 33 for frame in frames)


def test_dmr_voice_payload_adds_sync_or_embedded_lc() -> None:
    base = ysf_vd2_frame_to_dmr_voice_frames(Path("tests/fixtures/ysf/dgid10_seq20.bin").read_bytes())[0]

    sync = make_dmr_voice_payload(base, 1, 0, 3129301, 3205642)
    embedded = make_dmr_voice_payload(base, 1, 1, 3129301, 3205642)

    assert sync[13:20] != base[13:20]
    assert embedded[13:20] != base[13:20]
    assert embedded[15:18] != bytes(3)


def test_dmr_control_payload_contains_sync_and_slot_type() -> None:
    payload = make_dmr_control_payload(1, DT_VOICE_LC_HEADER)

    assert len(payload) == 33
    assert payload[13:20] != bytes(7)
    assert payload[12] != 0
    assert payload[20] != 0


def test_dmr_lc_control_payload_contains_full_lc() -> None:
    bare = make_dmr_control_payload(1, DT_VOICE_LC_HEADER)
    payload = make_dmr_lc_control_payload(1, DT_VOICE_LC_HEADER, 3129301, 3205642)

    assert len(payload) == 33
    assert payload[13:20] == bare[13:20]
    assert payload[0:12] != bytes(12)
    assert payload[21:33] != bytes(12)


def test_build_homebrew_options_packet() -> None:
    config = BrandMeisterConfig(dmr_id="312930110", master_options="TS2_1=3205642;")

    packet = _build_options_packet(config)

    assert packet.startswith(b"RPTO")
    assert packet[4:8] == int(config.dmr_id).to_bytes(4, "big")
    assert packet[8:] == b"TS2_1=3205642;"


def test_subscriber_id_is_derived_from_extended_hotspot_id() -> None:
    assert _subscriber_id_from_repeater_id("312930110") == 3129301
    assert _subscriber_id_from_repeater_id("3129301") == 3129301


def test_self_dmr_return_uses_plain_callsign() -> None:
    config = BrandMeisterConfig(callsign="W0WC", dmr_id="312930110")
    transport = DmrMasterBrandMeisterTransport(config)

    assert transport._display_source_for_dmr_id(3129301) == "W0WC"


def test_duplicate_dmr_lc_header_does_not_restart_return_stream() -> None:
    config = BrandMeisterConfig(callsign="W0WC", dmr_id="312930110")
    transport = DmrMasterBrandMeisterTransport(config)
    header = parse_dmrd_packet(make_dmrd(flags=0xA1))

    transport._process_dmr_frame(header)
    transport._process_dmr_frame(header)

    assert len(transport._ysf_queue) == 1


def test_dmr_return_data_channel_matches_native_dmr2ysf_cadence() -> None:
    transport = DmrMasterBrandMeisterTransport(BrandMeisterConfig(callsign="W0WC"))
    transport._source = "W0WC"
    transport._destination = "ALL"

    assert transport._data_channel_for_frame(0) == b"**********"
    assert transport._data_channel_for_frame(1) == b"W0WC      "
    assert transport._data_channel_for_frame(2) == b"ALL       "
    assert transport._data_channel_for_frame(5) == b"     *****"
    assert transport._data_channel_for_frame(6) == bytes([0x31, 0x22, 0x62, 0x5F, 0x29, 0, 0, 0, 0, 0])
    assert transport._data_channel_for_frame(7) == bytes([0, 0, 0, 0, 0x6C, 0x20, 0x1C, 0x20, 0x03, 0x08])


def make_dmrd(flags: int) -> bytes:
    packet = bytearray(55)
    packet[0:4] = b"DMRD"
    packet[4] = 7
    packet[5:8] = (3161899).to_bytes(3, "big")
    packet[8:11] = (3205642).to_bytes(3, "big")
    packet[11:15] = (312930110).to_bytes(4, "big")
    packet[15] = flags
    packet[16:20] = (0x12345678).to_bytes(4, "big")
    packet[20:53] = bytes(range(33))
    packet[53] = 2
    packet[54] = 99
    return bytes(packet)
