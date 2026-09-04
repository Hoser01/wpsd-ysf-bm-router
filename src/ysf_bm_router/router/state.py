from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ysf_bm_router.models import AppConfig, Route


class FrameDecision(str, Enum):
    FORWARD = "forward"
    SUPPRESS_SELECTOR = "suppress_selector"
    SELECT_AND_FORWARD = "select_and_forward"
    IGNORE_UNKNOWN_DGID = "ignore_unknown_dgid"
    BLOCKED_BY_SILENCE_PERIOD = "blocked_by_silence_period"


@dataclass(frozen=True)
class RouteEvent:
    decision: FrameDecision
    active_route: Route
    selected_route: Route | None = None
    reason: str = ""


@dataclass
class RouterState:
    config: AppConfig
    active_route: Route
    last_voice_activity: float | None = None
    last_route_change: float | None = None

    @classmethod
    def from_config(cls, config: AppConfig) -> "RouterState":
        config.validate()
        return cls(config=config, active_route=config.default_route())

    def handle_transmission_start(self, dgid: int, now: float) -> RouteEvent:
        route = self.config.enabled_route_for_dgid(dgid)
        if route is None:
            self.last_voice_activity = now
            return RouteEvent(
                decision=FrameDecision.IGNORE_UNKNOWN_DGID,
                active_route=self.active_route,
                reason=f"No enabled route for DG-ID {dgid}",
            )

        if route.dgid == self.active_route.dgid:
            self.last_voice_activity = now
            return RouteEvent(
                decision=FrameDecision.FORWARD,
                active_route=self.active_route,
                selected_route=route,
            )

        if not self._silence_period_has_passed(now):
            self.last_voice_activity = now
            return RouteEvent(
                decision=FrameDecision.BLOCKED_BY_SILENCE_PERIOD,
                active_route=self.active_route,
                selected_route=route,
                reason="Transmission occurred before the configured silence period elapsed",
            )

        self.active_route = route
        self.last_route_change = now
        self.last_voice_activity = now
        if not self.config.behavior.suppress_route_change_transmission:
            return RouteEvent(
                decision=FrameDecision.SELECT_AND_FORWARD,
                active_route=self.active_route,
                selected_route=route,
                reason=f"DG-ID {dgid} selected TG {route.talkgroup}",
            )

        return RouteEvent(
            decision=FrameDecision.SUPPRESS_SELECTOR,
            active_route=self.active_route,
            selected_route=route,
            reason=f"DG-ID {dgid} selected TG {route.talkgroup}",
        )

    def maybe_return_to_default(self, now: float) -> RouteEvent | None:
        minutes = self.config.behavior.return_to_default_minutes
        if minutes == 0 or self.active_route.dgid == self.config.behavior.default_dgid:
            return None
        if self.last_voice_activity is None:
            return None

        if now - self.last_voice_activity < minutes * 60:
            return None

        self.active_route = self.config.default_route()
        self.last_route_change = now
        return RouteEvent(
            decision=FrameDecision.SUPPRESS_SELECTOR,
            active_route=self.active_route,
            selected_route=self.active_route,
            reason=f"Returned to default DG-ID {self.active_route.dgid}",
        )

    def _silence_period_has_passed(self, now: float) -> bool:
        last_activity = self.last_voice_activity
        if last_activity is None:
            return True
        return now - last_activity >= self.config.behavior.tg_change_silence_seconds
