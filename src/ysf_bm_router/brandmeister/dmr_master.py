from __future__ import annotations

import hashlib
import logging
import select
import socket
import time
from collections import deque
from random import SystemRandom

from ysf_bm_router.bridge.modeconv import (
    DMR_SILENCE_DATA,
    YSF_SILENCE,
    dmr_voice_frame_to_ysf_vch,
    make_dmr_lc_control_payload,
    make_dmr_voice_payload,
    ysf_vd2_frame_to_dmr_voice_frames,
)
from ysf_bm_router.dmr.homebrew import (
    DMRD_PACKET_LENGTH,
    DT_TERMINATOR_WITH_LC,
    DT_VOICE,
    DT_VOICE_SYNC,
    DT_VOICE_LC_HEADER,
    DmrFrame,
    build_dmrd_packet,
    parse_dmrd_packet,
)
from ysf_bm_router.models import BrandMeisterConfig
from ysf_bm_router.ysf.fich import (
    make_ysfd_header_frame,
    make_ysfd_terminator_frame,
    make_ysfd_vd2_data_frame,
    parse_ysfd_frame,
)

from .direct import BrandMeisterError, BrandMeisterPacket, DirectBrandMeisterTransport


LOGGER = logging.getLogger(__name__)
YSF_RADIO_ID = "*****"
YSF_DT1 = bytes([0x31, 0x22, 0x62, 0x5F, 0x29, 0x00, 0x00, 0x00, 0x00, 0x00])
YSF_DT2 = bytes([0x00, 0x00, 0x00, 0x00, 0x6C, 0x20, 0x1C, 0x20, 0x03, 0x08])


class DmrMasterBrandMeisterTransport:
    """BrandMeister Homebrew receiver that emits freshly assembled YSF frames."""

    def __init__(
        self,
        config: BrandMeisterConfig,
        logger: logging.Logger | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.config = config
        self.logger = logger or LOGGER
        self.timeout = timeout
        self.socket: socket.socket | None = None
        self.connected = False
        self.selected_talkgroup: int | None = None
        self._ysf_queue: deque[bytes] = deque()
        self._vch_chunks: deque[bytes] = deque()
        self._stream_id: int | None = None
        self._source = config.callsign
        self._destination = "ALL"
        self._ysf_sequence = 0
        self._ysf_data_count = 0
        self._last_ping_at = 0.0
        self._dmr_sequence = 0
        self._dmr_stream_id = 0
        self._dmr_tx_active = False
        self._dmr_voice_count = 0
        self._dmr_tx_queue: deque[tuple[int, int | None, bytes | None]] = deque()
        self._next_dmr_send_at = 0.0
        self._dmr_frame_interval_seconds = 0.055
        self._self_subscriber_id = _subscriber_id_from_repeater_id(config.dmr_id) if config.dmr_id else 0

    def connect(self) -> None:
        self._validate_config()
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                self._connect_once()
                return
            except (OSError, BrandMeisterError) as exc:
                last_error = exc
                self.logger.warning("DMR master login attempt %s failed: %s", attempt, exc)
                self._close_socket()
                time.sleep(min(attempt * 2.0, 5.0))
        raise BrandMeisterError(f"BrandMeister DMR master login failed: {last_error}")

    def _connect_once(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.config.master_local_port:
            sock.bind(("", self.config.master_local_port))
        sock.settimeout(self.timeout)
        sock.connect((self._master_server, self.config.master_port or self.config.port))
        self.socket = sock

        self._send_login()
        salt = self._wait_for_challenge()
        self._send_challenge(salt)
        self._wait_for_ack()
        self._send_config()
        self._wait_for_ack()
        self._send_options()
        sock.setblocking(False)
        self.connected = True
        self._last_ping_at = time.monotonic()
        self.logger.info(
            "BrandMeister DMR master connected server=%s port=%s callsign=%s id=%s",
            self._master_server,
            self.config.master_port or self.config.port,
            self.config.callsign,
            self.config.dmr_id,
        )

    def disconnect(self) -> None:
        if self.socket is not None:
            try:
                self.socket.send(b"RPTCL" + self._dmr_id_bytes)
            except OSError:
                pass
        self._close_socket()
        self.logger.info("BrandMeister DMR master disconnected")

    def _close_socket(self) -> None:
        if self.socket is None:
            return
        self.socket.close()
        self.socket = None
        self.connected = False

    def select_talkgroup(self, talkgroup: int) -> None:
        self.selected_talkgroup = talkgroup
        self._destination = "ALL"
        self.logger.info("BrandMeister DMR return TG context: %s", talkgroup)

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        if not self.connected:
            return
        try:
            frame = parse_ysfd_frame(payload)
        except ValueError:
            return
        if frame.fich.information_type == 0:
            self._dmr_stream_id = SystemRandom().randrange(1, 0xFFFFFFFF)
            self._dmr_sequence = 0
            self._dmr_voice_count = 0
            self._dmr_tx_active = True
            for _ in range(3):
                self._queue_dmrd_control(talkgroup, DT_VOICE_LC_HEADER)
            self.logger.info("BrandMeister DMR activity opened tg=%s stream=%08x", talkgroup, self._dmr_stream_id)
        elif frame.fich.information_type == 1 and self._dmr_tx_active:
            for dmr_payload in ysf_vd2_frame_to_dmr_voice_frames(payload):
                self._queue_dmrd_voice(talkgroup, dmr_payload)
        elif frame.fich.information_type == 2 and self._dmr_tx_active:
            while self._dmr_voice_count % 6:
                self._queue_dmrd_voice(talkgroup, DMR_SILENCE_DATA)
            self._queue_dmrd_control(talkgroup, DT_TERMINATOR_WITH_LC)
            self._dmr_tx_active = False
            self.logger.info("BrandMeister DMR activity closed tg=%s stream=%08x", talkgroup, self._dmr_stream_id)

    def clock(self) -> None:
        if not self.connected:
            return
        now = time.monotonic()
        if now - self._last_ping_at >= 5.0:
            self._last_ping_at = now
            self._send_ping()
        self._flush_dmr_tx_queue(now)

    def select_timeout(self, now: float | None = None) -> float | None:
        if not self._dmr_tx_queue:
            return None
        now = time.monotonic() if now is None else now
        return max(0.0, self._next_dmr_send_at - now)

    def fileno(self) -> int:
        if self.socket is None:
            return -1
        return self.socket.fileno()

    def recv_packet(self) -> BrandMeisterPacket | None:
        if self._ysf_queue:
            return BrandMeisterPacket(self._ysf_queue.popleft())

        sock = self._socket()
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return None

        data = sock.recv(2048)
        if data.startswith(b"MSTPONG") or data.startswith(b"RPTACK") or data.startswith(b"RPTSBKN"):
            return None
        if not data.startswith(b"DMRD"):
            self.logger.debug("ignored DMR master packet prefix=%r len=%s", data[:8], len(data))
            return None
        if len(data) != DMRD_PACKET_LENGTH:
            self.logger.warning("ignored DMRD packet with unexpected len=%s", len(data))
            return None

        frame = parse_dmrd_packet(data)
        self.logger.debug(
            "received DMRD src=%s dst=%s stream=%08x type=%s n=%s",
            frame.source_id,
            frame.destination_id,
            frame.stream_id,
            frame.data_type,
            frame.voice_index,
        )
        self._process_dmr_frame(frame)
        if self._ysf_queue:
            return BrandMeisterPacket(self._ysf_queue.popleft())
        return None

    @property
    def _master_server(self) -> str:
        return self.config.master_server or self.config.server

    @property
    def _dmr_id_bytes(self) -> bytes:
        return int(self.config.dmr_id).to_bytes(4, "big")

    def _validate_config(self) -> None:
        missing = []
        for field in ("callsign", "dmr_id"):
            if not getattr(self.config, field):
                missing.append(field)
        if not self._password:
            missing.append("master_password")
        if not self._master_server:
            missing.append("master_server")
        if missing:
            raise BrandMeisterError(f"Missing BrandMeister DMR master config: {', '.join(missing)}")

    def _send_login(self) -> None:
        self._send(b"RPTL" + self._dmr_id_bytes)

    def _wait_for_challenge(self) -> bytes:
        while True:
            data = self._socket().recv(2048)
            if data.startswith(b"RPTACK") and len(data) >= 10:
                return data[6:10]
            if data.startswith(b"MSTNAK"):
                raise BrandMeisterError("BrandMeister DMR master rejected login")

    def _send_challenge(self, salt: bytes) -> None:
        secret_hash = hashlib.sha256(salt + self._password.encode()).digest()
        self._send(b"RPTK" + self._dmr_id_bytes + secret_hash)

    def _wait_for_ack(self) -> None:
        while True:
            data = self._socket().recv(2048)
            if data.startswith(b"RPTACK"):
                return
            if data.startswith(b"MSTNAK"):
                raise BrandMeisterError("BrandMeister DMR master returned MSTNAK")

    def _send_config(self) -> None:
        self._send(_build_config_packet(self.config))

    def _send_options(self) -> None:
        options = self.config.master_options.strip()
        if not options:
            return
        self._send(_build_options_packet(self.config, options))
        self.logger.info("BrandMeister DMR master options sent")

    def _send_ping(self) -> None:
        self._send(b"RPTPING" + self._dmr_id_bytes)

    def _process_dmr_frame(self, frame: DmrFrame) -> None:
        if frame.is_header:
            if self._stream_id == frame.stream_id:
                return
            self._start_stream(frame)
            return
        if frame.is_voice:
            if self._stream_id != frame.stream_id:
                self._start_stream(frame)
            for chunk in dmr_voice_frame_to_ysf_vch(frame.payload):
                self._vch_chunks.append(chunk)
            self._flush_vch_chunks()
            return
        if frame.is_terminator:
            if self._stream_id is not None:
                while self._vch_chunks and len(self._vch_chunks) < 5:
                    self._vch_chunks.append(YSF_SILENCE)
                self._flush_vch_chunks(force=True)
                self._ysf_queue.append(
                    make_ysfd_terminator_frame(
                        0,
                        self.config.callsign,
                        self._source,
                        self._destination,
                        sequence=self._ysf_sequence,
                        communication_mode=0,
                    )
                )
            self._end_stream()

    def _start_stream(self, frame: DmrFrame) -> None:
        self._stream_id = frame.stream_id
        self._source = self._display_source_for_dmr_id(frame.source_id)
        self._destination = "ALL"
        self._ysf_sequence = 0
        self._ysf_data_count = 0
        self._vch_chunks.clear()
        self._ysf_queue.append(
            make_ysfd_header_frame(
                None,
                0,
                self.config.callsign,
                self._source,
                self._destination,
                communication_mode=0,
                ysf_radio_id=YSF_RADIO_ID,
            )
        )

    def _end_stream(self) -> None:
        self._stream_id = None
        self._vch_chunks.clear()

    def _flush_vch_chunks(self, force: bool = False) -> None:
        while len(self._vch_chunks) >= 5:
            chunks = [self._vch_chunks.popleft() for _ in range(5)]
            self._ysf_queue.append(
                make_ysfd_vd2_data_frame(
                    chunks,
                    0,
                    self.config.callsign,
                    self._source,
                    self._destination,
                    sequence=self._ysf_sequence + 1,
                    frame_number=self._ysf_data_count % 8,
                    data_channel=self._data_channel_for_frame(self._ysf_data_count % 8),
                    communication_mode=0,
                )
            )
            self._ysf_sequence = (self._ysf_sequence + 1) % 128
            self._ysf_data_count += 1
        if force and self._vch_chunks:
            while len(self._vch_chunks) < 5:
                self._vch_chunks.append(YSF_SILENCE)
            self._flush_vch_chunks()

    def _data_channel_for_frame(self, frame_number: int) -> bytes:
        if frame_number == 0:
            return b"*****" + YSF_RADIO_ID.encode("ascii")
        if frame_number == 1:
            return self._source[:10].ljust(10).encode("ascii", errors="replace")
        if frame_number == 2:
            return self._destination[:10].ljust(10).encode("ascii", errors="replace")
        if frame_number == 5:
            return b"     " + YSF_RADIO_ID.encode("ascii")
        if frame_number == 6:
            return YSF_DT1
        if frame_number == 7:
            return YSF_DT2
        return b"          "

    def _display_source_for_dmr_id(self, source_id: int) -> str:
        if source_id == self._self_subscriber_id:
            return self.config.callsign
        return str(source_id) if source_id else self.config.callsign

    def _send(self, data: bytes) -> None:
        self._socket().send(data)

    def _queue_dmrd_control(self, talkgroup: int, data_type: int) -> None:
        self._dmr_tx_queue.append((talkgroup, data_type, None))

    def _queue_dmrd_voice(self, talkgroup: int, payload: bytes) -> None:
        self._dmr_tx_queue.append((talkgroup, None, payload))
        self._dmr_voice_count += 1

    def _flush_dmr_tx_queue(self, now: float | None = None) -> None:
        if not self.connected or not self._dmr_tx_queue:
            return
        now = time.monotonic() if now is None else now
        if now < self._next_dmr_send_at:
            return
        talkgroup, data_type, payload = self._dmr_tx_queue.popleft()
        if data_type is None:
            if payload is None:
                return
            self._send_dmrd_voice(talkgroup, payload)
        else:
            self._send_dmrd_control(talkgroup, data_type)
        self._next_dmr_send_at = now + self._dmr_frame_interval_seconds

    def _send_dmrd_control(self, talkgroup: int, data_type: int) -> None:
        stream_id = self._dmr_stream_id or SystemRandom().randrange(1, 0xFFFFFFFF)
        source_id = _subscriber_id_from_repeater_id(self.config.dmr_id)
        packet = build_dmrd_packet(
            DmrFrame(
                sequence=self._dmr_sequence,
                slot=2,
                source_id=source_id,
                destination_id=talkgroup,
                repeater_id=int(self.config.dmr_id),
                stream_id=stream_id,
                data_type=data_type,
                voice_index=0,
                flco_group=True,
                payload=make_dmr_lc_control_payload(self.config.color_code, data_type, source_id, talkgroup),
                ber=0,
                rssi=0,
            )
        )
        self._send(packet)
        self._dmr_sequence = (self._dmr_sequence + 1) % 256

    def _send_dmrd_voice(self, talkgroup: int, payload: bytes) -> None:
        voice_index = (self._dmr_sequence - 3) % 6
        data_type = DT_VOICE_SYNC if voice_index == 0 else DT_VOICE
        source_id = _subscriber_id_from_repeater_id(self.config.dmr_id)
        packet = build_dmrd_packet(
            DmrFrame(
                sequence=self._dmr_sequence,
                slot=2,
                source_id=source_id,
                destination_id=talkgroup,
                repeater_id=int(self.config.dmr_id),
                stream_id=self._dmr_stream_id,
                data_type=data_type,
                voice_index=voice_index,
                flco_group=True,
                payload=make_dmr_voice_payload(payload, self.config.color_code, voice_index, source_id, talkgroup),
                ber=0,
                rssi=0,
            )
        )
        self._send(packet)
        self._dmr_sequence = (self._dmr_sequence + 1) % 256

    def _socket(self) -> socket.socket:
        if self.socket is None:
            raise BrandMeisterError("BrandMeister DMR master socket is not connected")
        return self.socket

    @property
    def _password(self) -> str:
        return self.config.master_password or self.config.password


class HybridDmrReturnBrandMeisterTransport:
    """Use YSF Direct audio while keeping the DMR master login available."""

    def __init__(
        self,
        config: BrandMeisterConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or LOGGER
        self.direct = DirectBrandMeisterTransport(config, logger=self.logger)
        self.return_receiver = DmrMasterBrandMeisterTransport(config, logger=self.logger)

    def connect(self) -> None:
        self.direct.connect()
        self.return_receiver.connect()

    def disconnect(self) -> None:
        self.return_receiver.disconnect()
        self.direct.disconnect()

    def select_talkgroup(self, talkgroup: int) -> None:
        self.direct.select_talkgroup(talkgroup)
        self.return_receiver.select_talkgroup(talkgroup)

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        self.direct.forward_ysf_payload(payload, talkgroup)

    def clock(self) -> None:
        self.return_receiver.clock()

    def select_timeout(self, now: float | None = None) -> float | None:
        return self.return_receiver.select_timeout(now)

    def fileno(self) -> int:
        return self.direct.fileno()

    def filenos(self) -> list[object]:
        return [self.direct]

    def recv_packet(self) -> BrandMeisterPacket | None:
        return self.direct.recv_packet()


def _build_config_packet(config: BrandMeisterConfig) -> bytes:
    callsign = config.callsign[:8]
    location = config.location or "WPSD"
    description = config.description or "ysf-bm-router"
    url = config.url or "https://wpsd.radio"
    slots = "4" if config.hotspot_type == "MMDVM_DMO" else "1"
    power = min(max(config.power, 0), 99)
    height = min(max(config.height, 0), 999)
    latitude = f"{config.latitude:08.6f}"[:8]
    longitude = f"{config.longitude:09.6f}"[:9]
    body = (
        f"{callsign:<8.8}"
        f"{config.rx_frequency:09d}"
        f"{config.tx_frequency:09d}"
        f"{power:02d}"
        f"{config.color_code:02d}"
        f"{latitude}"
        f"{longitude}"
        f"{height:03d}"
        f"{location:<20.20}"
        f"{description:<19.19}"
        f"{slots}"
        f"{url:<124.124}"
        f"{config.version:<40.40}"
        f"{config.hotspot_type:<40.40}"
    ).encode("ascii", errors="replace")
    if len(body) != 294:
        body = body[:294].ljust(294, b" ")
    return b"RPTC" + int(config.dmr_id).to_bytes(4, "big") + body


def _build_options_packet(config: BrandMeisterConfig, options: str | None = None) -> bytes:
    value = config.master_options if options is None else options
    return b"RPTO" + int(config.dmr_id).to_bytes(4, "big") + value.encode("ascii", errors="replace")


def _subscriber_id_from_repeater_id(dmr_id: str) -> int:
    value = int(dmr_id)
    if value <= 0xFFFFFF:
        return value
    return int(str(value)[:-2])
