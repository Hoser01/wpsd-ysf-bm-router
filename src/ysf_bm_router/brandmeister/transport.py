from __future__ import annotations

import logging
from typing import Protocol


class BrandMeisterTransport(Protocol):
    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def select_talkgroup(self, talkgroup: int) -> None:
        ...

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        ...


class DryRunBrandMeisterTransport:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.connected = False
        self.selected_talkgroup: int | None = None
        self.forwarded_frames = 0

    def connect(self) -> None:
        self.connected = True
        self.logger.info("dry-run BrandMeister transport connected")

    def disconnect(self) -> None:
        self.connected = False
        self.logger.info("dry-run BrandMeister transport disconnected")

    def select_talkgroup(self, talkgroup: int) -> None:
        self.selected_talkgroup = talkgroup
        self.logger.info("dry-run BrandMeister TG select: %s", talkgroup)

    def forward_ysf_payload(self, payload: bytes, talkgroup: int) -> None:
        self.forwarded_frames += 1
        self.logger.debug(
            "dry-run forward YSF frame len=%s tg=%s count=%s",
            len(payload),
            talkgroup,
            self.forwarded_frames,
        )
