from __future__ import annotations

import pytest

from ysf_bm_router.ysf.fich import (
    YsfDecodeError,
    decode_dgid_from_fich_bytes,
    make_ysfd_header_frame,
    make_ysfd_terminator_frame,
    make_ysfd_vd2_data_frame,
    parse_ysfd_frame,
    rewrite_ysfd_dgid,
    rewrite_ysfd_for_mmdvm,
    rewrite_ysfd_source_field,
    rewrite_ysfd_vd2_source,
)


def test_decodes_dgid_10_from_live_ysfd_fixture() -> None:
    frame = parse_ysfd_frame(read_fixture("dgid10_seq20.bin"))

    assert frame.source == "W0WC"
    assert frame.gateway == "W0WC"
    assert frame.destination == "ALL"
    assert frame.fich.dgid == 10


def test_decodes_dgid_22_from_live_ysfd_fixture() -> None:
    frame = parse_ysfd_frame(read_fixture("dgid22_seq32.bin"))

    assert frame.fich.dgid == 22


def test_decodes_dgid_40_from_live_ysfd_fixture() -> None:
    frame = parse_ysfd_frame(read_fixture("dgid40_seq07.bin"))

    assert frame.fich.dgid == 40


def test_rewrite_ysfd_dgid_updates_fich_sq() -> None:
    packet = read_fixture("dgid10_seq20.bin")

    rewritten = rewrite_ysfd_dgid(packet, 22)

    assert parse_ysfd_frame(packet).fich.dgid == 10
    assert parse_ysfd_frame(rewritten).fich.dgid == 22


def test_rewrite_ysfd_for_mmdvm_updates_dgid() -> None:
    rewritten = rewrite_ysfd_for_mmdvm(read_fixture("dgid10_seq20.bin"), 22)

    assert parse_ysfd_frame(rewritten).fich.dgid == 22


def test_rewrite_ysfd_source_field_updates_network_source() -> None:
    rewritten = rewrite_ysfd_source_field(read_fixture("dgid10_seq20.bin"), "W0WC")

    assert parse_ysfd_frame(rewritten).source == "W0WC"


def test_rewrite_ysfd_vd2_source_keeps_non_vd2_frame_unchanged() -> None:
    packet = read_fixture("dgid10_seq20.bin")

    assert rewrite_ysfd_vd2_source(packet, "22/W0WC") == packet


def test_make_ysfd_header_frame_sets_header_fich_and_callsigns() -> None:
    header = make_ysfd_header_frame(read_fixture("dgid10_seq20.bin"), 22, "W0WC", "KF0LZ")
    frame = parse_ysfd_frame(header)

    assert frame.source == "W0WC"
    assert frame.gateway == "KF0LZ"
    assert frame.destination == "ALL"
    assert frame.frame_number == 0
    assert frame.fich.information_type == 0
    assert frame.fich.dgid == 22
    assert frame.fich.communication_mode == 0
    assert frame.fich.frame_number == 0
    assert frame.fich.frame_total == 7
    assert frame.fich.data_type == 2
    assert frame.fich.voip is False


def test_make_ysfd_header_frame_without_template() -> None:
    header = make_ysfd_header_frame(None, 22, "W0WC", "3129301", "TG31291")
    frame = parse_ysfd_frame(header)

    assert len(header) == 155
    assert frame.source == "W0WC"
    assert frame.gateway == "3129301"
    assert frame.destination == "TG31291"
    assert frame.fich.information_type == 0
    assert frame.fich.dgid == 22


def test_make_ysfd_vd2_data_frame_sets_communications_fich() -> None:
    packet = make_ysfd_vd2_data_frame(
        [bytes([index]) * 13 for index in range(5)],
        22,
        "W0WC",
        "KF0LZ",
        sequence=3,
        frame_number=2,
        data_channel=b"TG31291   ",
    )
    frame = parse_ysfd_frame(packet)

    assert len(packet) == 155
    assert frame.source == "W0WC"
    assert frame.gateway == "KF0LZ"
    assert frame.frame_number == 6
    assert frame.fich.information_type == 1
    assert frame.fich.frame_number == 2
    assert frame.fich.frame_total == 7
    assert frame.fich.dgid == 22


def test_make_ysfd_vd2_data_frame_can_set_communication_mode() -> None:
    packet = make_ysfd_vd2_data_frame(
        [bytes([index]) * 13 for index in range(5)],
        0,
        "W0WC",
        "W0WC",
        communication_mode=1,
    )

    assert parse_ysfd_frame(packet).fich.communication_mode == 1


def test_make_ysfd_vd2_data_frame_places_vch_chunks_at_native_offsets() -> None:
    chunks = [bytes([index + 1]) * 13 for index in range(5)]

    packet = make_ysfd_vd2_data_frame(chunks, 0, "W0WC", "W0WC")
    payload = packet[35:]

    for index, chunk in enumerate(chunks):
        start = 35 + (index * 18)
        assert payload[start : start + 13] == chunk


def test_make_ysfd_terminator_frame_sets_terminator_fich() -> None:
    packet = make_ysfd_terminator_frame(22, "W0WC", "3129301", "TG31291", sequence=7)
    frame = parse_ysfd_frame(packet)

    assert len(packet) == 155
    assert frame.frame_number == 14
    assert frame.fich.information_type == 2
    assert frame.fich.dgid == 22


def test_empty_fich_is_invalid() -> None:
    with pytest.raises(YsfDecodeError):
        decode_dgid_from_fich_bytes(b"")


def test_non_ysfd_packet_is_invalid() -> None:
    with pytest.raises(YsfDecodeError, match="not a YSFD"):
        parse_ysfd_frame(b"YSFPW0WC      ")


def read_fixture(name: str) -> bytes:
    from pathlib import Path

    return Path("tests/fixtures/ysf", name).read_bytes()
