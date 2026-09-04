from __future__ import annotations

import logging
import select
import socket
import time
from collections import deque
from dataclasses import dataclass

from .brandmeister.transport import BrandMeisterTransport
from .models import AppConfig
from .router.state import FrameDecision, RouterState
from .ysf.fich import (
    YsfDecodeError,
    make_ysfd_header_frame,
    parse_ysfd_frame,
    rewrite_ysfd_dgid,
    rewrite_ysfd_for_mmdvm,
    rewrite_ysfd_source_field,
    rewrite_ysfd_vd2_source,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PacketResult:
    kind: str
    forwarded: bool
    reason: str
    dgid: int | None = None
    talkgroup: int | None = None


class RouterRuntime:
    def __init__(
        self,
        config: AppConfig,
        transport: BrandMeisterTransport,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self.logger = logger or LOGGER
        self.state = RouterState.from_config(config)
        self._suppress_dgid: int | None = None
        self._last_suppressed_at: float | None = None
        self._selector_gap_seconds = 0.75
        self._ysf_gateway_addr: tuple[str, int] = ("127.0.0.1", 42000)
        self._return_queue: deque[bytes] = deque()
        self._next_return_send_at = 0.0
        self._return_stream_active = False
        self._return_playout_active = False
        self._last_return_frame_at: float | None = None
        self._return_stream_gap_seconds = 2.0

    def serve_forever(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.config.ysf.listen_address, self.config.ysf.listen_port))
        self.transport.connect()
        self.transport.select_talkgroup(self.state.active_route.talkgroup)
        self.logger.info(
            "listening on udp://%s:%s as %s",
            self.config.ysf.listen_address,
            self.config.ysf.listen_port,
            self.config.ysf.reflector_name,
        )
        try:
            while True:
                now = time.monotonic()
                self._clock_transport()
                self._flush_return_queue(sock, now)
                readable = self._select_readable(sock, now)
                if sock in readable:
                    data, addr = sock.recvfrom(2048)
                    self._ysf_gateway_addr = addr
                    if data.startswith(b"YSFP"):
                        sock.sendto(data, addr)
                    result = self.handle_packet(data, now=time.monotonic())
                    self.logger.debug(
                        "packet from=%s:%s kind=%s forwarded=%s dgid=%s tg=%s reason=%s",
                        addr[0],
                        addr[1],
                        result.kind,
                        result.forwarded,
                        result.dgid,
                        result.talkgroup,
                        result.reason,
                    )
                if self._transport_is_readable(readable):
                    self._enqueue_brandmeister_packets(sock)
                self._flush_return_queue(sock, time.monotonic())
        finally:
            self.transport.disconnect()
            sock.close()

    def handle_packet(self, data: bytes, now: float | None = None) -> PacketResult:
        now = time.monotonic() if now is None else now
        default_event = self.state.maybe_return_to_default(now)
        if default_event is not None:
            self.transport.select_talkgroup(default_event.active_route.talkgroup)
            self.logger.info(default_event.reason)

        if data.startswith(b"YSFP"):
            self.transport.forward_ysf_payload(data, self.state.active_route.talkgroup)
            return PacketResult(
                kind="ysfp",
                forwarded=True,
                reason="poll forwarded",
                talkgroup=self.state.active_route.talkgroup,
            )
        if data.startswith(b"YSFU"):
            return PacketResult(kind="ysfu", forwarded=False, reason="disconnect")
        if not data.startswith(b"YSFD"):
            return PacketResult(kind="unknown", forwarded=False, reason="ignored")

        try:
            frame = parse_ysfd_frame(data)
        except YsfDecodeError as exc:
            self.logger.warning("failed to decode YSFD frame: %s", exc)
            return PacketResult(kind="ysfd", forwarded=False, reason=str(exc))

        if self._is_currently_suppressing(frame.fich.dgid, now):
            return PacketResult(
                kind="ysfd",
                forwarded=False,
                reason="selector burst suppressed",
                dgid=frame.fich.dgid,
                talkgroup=self.state.active_route.talkgroup,
            )

        event = self.state.handle_transmission_start(frame.fich.dgid, now)
        route = event.active_route

        if event.decision == FrameDecision.SUPPRESS_SELECTOR:
            self.transport.select_talkgroup(route.talkgroup)
            self._suppress_selector_burst(frame.fich.dgid, now)
            self.logger.info(
                "route change dgid=%s tg=%s name=%s",
                route.dgid,
                route.talkgroup,
                route.long_name,
            )
            return PacketResult(
                kind="ysfd",
                forwarded=False,
                reason=event.reason,
                dgid=frame.fich.dgid,
                talkgroup=route.talkgroup,
            )

        if event.decision == FrameDecision.SELECT_AND_FORWARD:
            self.transport.select_talkgroup(route.talkgroup)
            self.logger.info(
                "route change dgid=%s tg=%s name=%s",
                route.dgid,
                route.talkgroup,
                route.long_name,
            )
            self.transport.forward_ysf_payload(data, route.talkgroup)
            return PacketResult(
                kind="ysfd",
                forwarded=True,
                reason=event.reason,
                dgid=frame.fich.dgid,
                talkgroup=route.talkgroup,
            )

        if event.decision == FrameDecision.BLOCKED_BY_SILENCE_PERIOD:
            self.transport.forward_ysf_payload(data, route.talkgroup)
            return PacketResult(
                kind="ysfd",
                forwarded=True,
                reason=event.reason,
                dgid=frame.fich.dgid,
                talkgroup=route.talkgroup,
            )

        if event.decision == FrameDecision.IGNORE_UNKNOWN_DGID:
            self.transport.forward_ysf_payload(data, route.talkgroup)
            return PacketResult(
                kind="ysfd",
                forwarded=True,
                reason=event.reason,
                dgid=frame.fich.dgid,
                talkgroup=route.talkgroup,
            )

        self.transport.forward_ysf_payload(data, route.talkgroup)
        return PacketResult(
            kind="ysfd",
            forwarded=True,
            reason="forwarded",
            dgid=frame.fich.dgid,
            talkgroup=route.talkgroup,
        )

    def _suppress_selector_burst(self, dgid: int, now: float) -> None:
        self._suppress_dgid = dgid
        self._last_suppressed_at = now

    def _is_currently_suppressing(self, dgid: int, now: float) -> bool:
        if self._suppress_dgid is None or self._last_suppressed_at is None:
            return False
        if now - self._last_suppressed_at > self._selector_gap_seconds:
            self._suppress_dgid = None
            self._last_suppressed_at = None
            return False
        if self._suppress_dgid != dgid:
            return False

        self._last_suppressed_at = now
        return True

    def _select_readable(self, ysf_sock: socket.socket, now: float | None = None) -> list[object]:
        inputs: list[object] = [ysf_sock]
        filenos = getattr(self.transport, "filenos", None)
        if callable(filenos):
            inputs.extend(item for item in filenos() if item.fileno() >= 0)
        else:
            fileno = getattr(self.transport, "fileno", None)
            if callable(fileno) and fileno() >= 0:
                inputs.append(self.transport)
        readable, _, _ = select.select(inputs, [], [], self._select_timeout(now))
        return readable

    def _select_timeout(self, now: float | None = None) -> float:
        transport_timeout_fn = getattr(self.transport, "select_timeout", None)
        transport_timeout = transport_timeout_fn(now) if callable(transport_timeout_fn) else None
        if not self._return_queue:
            return min(1.0, transport_timeout) if transport_timeout is not None else 1.0
        now = time.monotonic() if now is None else now
        return_timeout = max(0.0, self._next_return_send_at - now)
        if transport_timeout is not None:
            return min(1.0, return_timeout, transport_timeout)
        return min(1.0, return_timeout)

    def _transport_is_readable(self, readable: list[object]) -> bool:
        if any(item is self.transport for item in readable):
            return True
        filenos = getattr(self.transport, "filenos", None)
        if callable(filenos):
            transports = set(filenos())
            return any(item in transports for item in readable)
        return False

    def _clock_transport(self) -> None:
        clock = getattr(self.transport, "clock", None)
        if callable(clock):
            clock()

    def _enqueue_brandmeister_packets(self, ysf_sock: socket.socket | None = None) -> None:
        recv_packet = getattr(self.transport, "recv_packet", None)
        if not callable(recv_packet):
            return

        while True:
            packet = recv_packet()
            if packet is None:
                return

            for data in self._prepare_brandmeister_packets_for_ysf(packet.data, time.monotonic()):
                if self.config.behavior.return_frame_interval_seconds == 0 and ysf_sock is not None:
                    ysf_sock.sendto(data, self._ysf_gateway_addr)
                    self.logger.debug("forwarded BrandMeister packet to YSFGateway immediately len=%s", len(data))
                    continue
                self._return_queue.append(data)
                self.logger.debug("queued BrandMeister packet for YSFGateway len=%s depth=%s", len(data), len(self._return_queue))

    def _flush_return_queue(self, ysf_sock: socket.socket, now: float | None = None) -> None:
        if not self._return_queue:
            return
        now = time.monotonic() if now is None else now
        if now < self._next_return_send_at:
            return

        data = self._return_queue.popleft()
        ysf_sock.sendto(data, self._ysf_gateway_addr)
        self._return_playout_active = True
        self._next_return_send_at = now + self.config.behavior.return_frame_interval_seconds
        self.logger.debug("forwarded BrandMeister packet to YSFGateway len=%s depth=%s", len(data), len(self._return_queue))

    def _prepare_brandmeister_packets_for_ysf(self, data: bytes, now: float | None = None) -> list[bytes]:
        if not data.startswith(b"YSFD"):
            return [data]
        now = time.monotonic() if now is None else now
        try:
            frame = parse_ysfd_frame(data)
            self.logger.debug(
                "return YSFD source=%s gateway=%s dest=%s seq=%s dgid=%s fi=%s cm=%s fn=%s/%s dt=%s voip=%s sql=%s",
                frame.source,
                frame.gateway,
                frame.destination,
                frame.frame_number,
                frame.fich.dgid,
                frame.fich.information_type,
                frame.fich.communication_mode,
                frame.fich.frame_number,
                frame.fich.frame_total,
                frame.fich.data_type,
                frame.fich.voip,
                frame.fich.sql_open,
            )
            insert_header = self._should_insert_return_header(frame, now)
            return_dgid = self.state.active_route.dgid if self.config.behavior.rewrite_return_dgid else frame.fich.dgid
            if self.config.behavior.rewrite_return_dgid:
                data = rewrite_ysfd_for_mmdvm(data, return_dgid)
            if self.config.behavior.rewrite_return_source:
                data = rewrite_ysfd_source_field(data, self.config.brandmeister.callsign)
            if self.config.behavior.show_dgid_callsign:
                source = f"{self.state.active_route.dgid}/{frame.gateway.strip()}"
                data = rewrite_ysfd_vd2_source(data, source)
            packets = [data]
            if insert_header:
                packets.insert(
                    0,
                    make_ysfd_header_frame(
                        data,
                        return_dgid,
                        self.config.brandmeister.callsign,
                        frame.gateway or frame.source or self.config.brandmeister.callsign,
                    ),
                )
            if frame.fich.information_type == 2:
                self._return_stream_active = False
                self._last_return_frame_at = None
            else:
                self._return_stream_active = True
                self._last_return_frame_at = now
            return packets
        except YsfDecodeError as exc:
            self.logger.warning("failed to rewrite returned YSFD metadata: %s", exc)
            return [data]

    def _should_insert_return_header(self, frame, now: float) -> bool:
        if not self.config.behavior.insert_return_header:
            return False
        if frame.fich.information_type == 0:
            if (
                not self._return_stream_active
                or self._last_return_frame_at is None
                or now - self._last_return_frame_at > self._return_stream_gap_seconds
            ):
                self._start_return_playout_delay(now)
            self._return_stream_active = True
            self._last_return_frame_at = now
            return False
        if frame.fich.information_type == 2:
            self._return_playout_active = False
            return False
        if not self._return_stream_active:
            self._start_return_playout_delay(now)
            return True
        if self._last_return_frame_at is None:
            self._start_return_playout_delay(now)
            return True
        is_new_stream = now - self._last_return_frame_at > self._return_stream_gap_seconds
        if is_new_stream:
            self._start_return_playout_delay(now)
        return is_new_stream

    def _start_return_playout_delay(self, now: float) -> None:
        self._return_playout_active = False
        self._next_return_send_at = max(
            self._next_return_send_at,
            now + self.config.behavior.return_start_delay_seconds,
        )
