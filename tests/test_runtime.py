from __future__ import annotations

from dataclasses import replace

from ysf_bm_router.config import load_config
from ysf_bm_router.runtime import RouterRuntime
from ysf_bm_router.ysf.fich import make_ysfd_vd2_data_frame, parse_ysfd_frame


class RecordingTransport:
    def __init__(self) -> None:
        self.selected: list[int] = []
        self.forwarded: list[int] = []

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def select_talkgroup(self, talkgroup: int) -> None:
        self.selected.append(talkgroup)

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        self.forwarded.append(talkgroup)


class ReturnTransport(RecordingTransport):
    def __init__(self, packets: list[bytes]) -> None:
        super().__init__()
        self.packets = packets

    def recv_packet(self):
        from ysf_bm_router.brandmeister.direct import BrandMeisterPacket

        if not self.packets:
            return None
        return BrandMeisterPacket(self.packets.pop(0))


class FakeHybridTransport:
    def __init__(self, direct_packets: list[bytes], return_packets: list[bytes]) -> None:
        self.direct = ReturnTransport(direct_packets)
        self.return_receiver = ReturnTransport(return_packets)

    def recv_packet(self):
        from ysf_bm_router.brandmeister.dmr_master import HybridDmrReturnBrandMeisterTransport

        return HybridDmrReturnBrandMeisterTransport.recv_packet(self)


class RecordingSocket:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))


def test_runtime_forwards_default_dgid() -> None:
    transport = RecordingTransport()
    runtime = RouterRuntime(load_config("config/ysf-bm-router.toml"), transport)

    result = runtime.handle_packet(read_fixture("dgid10_seq20.bin"), now=100.0)

    assert result.forwarded is True
    assert result.dgid == 10
    assert result.talkgroup == 3205642
    assert transport.forwarded == [3205642]


def test_runtime_forwards_ysf_poll_to_brandmeister() -> None:
    transport = RecordingTransport()
    runtime = RouterRuntime(load_config("config/ysf-bm-router.toml"), transport)

    result = runtime.handle_packet(b"YSFPW0WC      ", now=100.0)

    assert result.forwarded is True
    assert result.talkgroup == 3205642
    assert transport.forwarded == [3205642]


def test_runtime_selects_new_route_and_suppresses_selector_burst() -> None:
    transport = RecordingTransport()
    config = with_route_change_suppression()
    runtime = RouterRuntime(config, transport)

    first = runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=100.0)
    second = runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=100.5)

    assert first.forwarded is False
    assert first.talkgroup == 31291
    assert second.forwarded is False
    assert second.reason == "selector burst suppressed"
    assert transport.selected == [31291]
    assert transport.forwarded == []


def test_runtime_forwards_after_selector_suppression_window() -> None:
    transport = RecordingTransport()
    config = with_route_change_suppression()
    runtime = RouterRuntime(config, transport)

    runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=100.0)
    result = runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=102.0)

    assert result.forwarded is True
    assert result.talkgroup == 31291
    assert transport.forwarded == [31291]


def test_runtime_suppresses_entire_contiguous_selector_burst() -> None:
    transport = RecordingTransport()
    config = with_route_change_suppression()
    runtime = RouterRuntime(config, transport)

    for step in range(25):
        result = runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=100.0 + step * 0.1)
        assert result.forwarded is False

    assert transport.forwarded == []


def test_runtime_selects_new_route_and_forwards_when_suppression_disabled() -> None:
    transport = RecordingTransport()
    runtime = RouterRuntime(load_config("config/ysf-bm-router.toml"), transport)

    result = runtime.handle_packet(read_fixture("dgid22_seq32.bin"), now=100.0)

    assert result.forwarded is True
    assert result.talkgroup == 31291
    assert transport.selected == [31291]
    assert transport.forwarded == [31291]


def test_runtime_paces_brandmeister_return_queue() -> None:
    transport = ReturnTransport([b"one", b"two"])
    runtime = RouterRuntime(load_config("config/ysf-bm-router.toml"), transport)
    sock = RecordingSocket()

    runtime._enqueue_brandmeister_packets()
    runtime._flush_return_queue(sock, now=100.0)
    runtime._flush_return_queue(sock, now=100.05)
    runtime._flush_return_queue(sock, now=100.11)

    assert sock.sent == [
        (b"one", ("127.0.0.1", 42000)),
        (b"two", ("127.0.0.1", 42000)),
    ]


def test_runtime_can_forward_brandmeister_return_without_dgid_rewrite() -> None:
    config = load_config("config/ysf-bm-router.toml")
    config = replace(
        config,
        behavior=replace(
            config.behavior,
            return_frame_interval_seconds=0,
            rewrite_return_dgid=False,
            rewrite_return_source=False,
        ),
    )
    runtime = RouterRuntime(config, ReturnTransport([read_fixture("dgid10_seq20.bin")]))
    sock = RecordingSocket()

    runtime._enqueue_brandmeister_packets(sock)

    assert sock.sent[0][0] == read_fixture("dgid10_seq20.bin")


def test_runtime_inserts_header_before_first_brandmeister_return_frame() -> None:
    config = load_config("config/ysf-bm-router.toml")
    config = replace(
        config,
        behavior=replace(
            config.behavior,
            insert_return_header=True,
            return_frame_interval_seconds=0,
            rewrite_return_source=True,
        ),
    )
    runtime = RouterRuntime(config, ReturnTransport([make_communications_frame(read_fixture("dgid10_seq20.bin"))]))
    sock = RecordingSocket()

    runtime._enqueue_brandmeister_packets(sock)

    assert len(sock.sent) == 2
    header = parse_ysfd_frame(sock.sent[0][0])
    voice = parse_ysfd_frame(sock.sent[1][0])
    assert header.fich.information_type == 0
    assert header.fich.dgid == 10
    assert header.source == config.brandmeister.callsign
    assert voice.fich.information_type != 0


def test_runtime_inserted_header_keeps_return_dgid_when_rewrite_disabled() -> None:
    config = load_config("config/ysf-bm-router.toml")
    config = replace(
        config,
        behavior=replace(
            config.behavior,
            insert_return_header=True,
            return_frame_interval_seconds=0,
            rewrite_return_dgid=False,
            rewrite_return_source=False,
        ),
    )
    data = make_ysfd_vd2_data_frame([bytes([index]) * 13 for index in range(5)], 0, "W0WC", "W0WC")
    runtime = RouterRuntime(config, ReturnTransport([data]))
    sock = RecordingSocket()

    runtime._enqueue_brandmeister_packets(sock)

    assert parse_ysfd_frame(sock.sent[0][0]).fich.dgid == 0
    assert parse_ysfd_frame(sock.sent[1][0]).fich.dgid == 0


def test_hybrid_return_uses_direct_packets() -> None:
    transport = FakeHybridTransport([b"direct"], [b"converted"])

    packet = transport.recv_packet()

    assert packet is not None
    assert packet.data == b"direct"

    assert transport.recv_packet() is None


def with_route_change_suppression():
    config = load_config("config/ysf-bm-router.toml")
    return replace(
        config,
        behavior=replace(config.behavior, suppress_route_change_transmission=True),
    )


def read_fixture(name: str) -> bytes:
    from pathlib import Path

    return Path("tests/fixtures/ysf", name).read_bytes()


def make_communications_frame(packet: bytes) -> bytes:
    from ysf_bm_router.vendor.pysfreflector import ysffich

    result = bytearray(packet)
    assert ysffich.decode(result[40:])
    ysffich.setFI(1)
    ysffich.encode(result)
    return bytes(result)
