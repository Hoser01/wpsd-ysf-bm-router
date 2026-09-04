from __future__ import annotations

import hashlib
import logging
import select
import socket
from dataclasses import dataclass

from ysf_bm_router.models import BrandMeisterConfig


LOGGER = logging.getLogger(__name__)


class BrandMeisterError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrandMeisterPacket:
    data: bytes


class DirectBrandMeisterTransport:
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

    def connect(self) -> None:
        self._validate_config()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        sock.connect((self.config.server, self.config.port))
        self.socket = sock

        self._send_login()
        salt = self._wait_for_challenge()
        self._send_challenge(salt)
        sock.setblocking(False)
        self.connected = True
        self.logger.info(
            "BrandMeister YSF Direct connected server=%s port=%s callsign=%s",
            self.config.server,
            self.config.port,
            self.config.callsign,
        )

    def disconnect(self) -> None:
        if self.socket is None:
            return
        try:
            logout = b"YSFU" + _pad(self.config.callsign.encode("ascii"), 10)
            self.socket.send(logout)
            self.socket.send(logout)
        except OSError:
            pass
        self.socket.close()
        self.socket = None
        self.connected = False
        self.logger.info("BrandMeister YSF Direct disconnected")

    def select_talkgroup(self, talkgroup: int) -> None:
        self._send(
            b"YSFO"
            + _pad(self.config.callsign.encode("ascii"), 10)
            + f"group={talkgroup}".encode("ascii")
        )
        self.selected_talkgroup = talkgroup
        self.logger.info("BrandMeister TG select: %s", talkgroup)

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        self._send(payload)
        self.logger.debug("forwarded YSF frame to BrandMeister tg=%s len=%s", talkgroup, len(payload))

    def fileno(self) -> int:
        if self.socket is None:
            return -1
        return self.socket.fileno()

    def recv_packet(self) -> BrandMeisterPacket | None:
        sock = self._socket()
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return None
        data = sock.recv(2048)
        if data.startswith(b"YSFACK"):
            self.logger.debug("BrandMeister ACK")
            return None
        if data.startswith(b"YSFNAK"):
            self.logger.warning("BrandMeister returned YSFNAK")
            return None
        if data.startswith(b"YSFP"):
            self.logger.debug("BrandMeister poll")
            return None
        return BrandMeisterPacket(data=data)

    def _validate_config(self) -> None:
        missing = []
        for field in ("server", "callsign", "password"):
            if not getattr(self.config, field):
                missing.append(field)
        if not self.config.port:
            missing.append("port")
        if missing:
            raise BrandMeisterError(f"Missing BrandMeister config: {', '.join(missing)}")

    def _send_login(self) -> None:
        self._send(b"YSFL" + _pad(self.config.callsign.encode("ascii"), 10))

    def _wait_for_challenge(self) -> bytes:
        sock = self._socket()
        while True:
            data = sock.recv(2048)
            if data.startswith(b"YSFACK") and len(data) >= 20:
                self.logger.debug("BrandMeister login challenge received")
                return data[16:20]
            if data.startswith(b"YSFNAK"):
                raise BrandMeisterError("BrandMeister rejected login")

    def _send_challenge(self, salt: bytes) -> None:
        secret_hash = hashlib.sha256(salt + self.config.password.encode()).digest()
        self._send(b"YSFK" + _pad(self.config.callsign.encode("ascii"), 10) + secret_hash)

    def _send(self, data: bytes) -> None:
        self._socket().send(data)

    def _socket(self) -> socket.socket:
        if self.socket is None:
            raise BrandMeisterError("BrandMeister socket is not connected")
        return self.socket


def _pad(data: bytes, length: int) -> bytes:
    return data[:length].ljust(length, b" ")
