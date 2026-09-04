from __future__ import annotations

from dataclasses import replace

from ysf_bm_router.config import load_config
from ysf_bm_router.router.state import FrameDecision, RouterState


def test_default_route_is_active_on_start() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))

    assert state.active_route.dgid == 10
    assert state.active_route.talkgroup == 3205642


def test_same_dgid_forwards_voice() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))

    event = state.handle_transmission_start(dgid=10, now=100.0)

    assert event.decision == FrameDecision.FORWARD
    assert event.active_route.talkgroup == 3205642


def test_new_dgid_selects_talkgroup_and_forwards() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))

    event = state.handle_transmission_start(dgid=22, now=100.0)

    assert event.decision == FrameDecision.SELECT_AND_FORWARD
    assert event.active_route.dgid == 22
    assert event.active_route.talkgroup == 31291


def test_new_dgid_can_suppress_selector_transmission() -> None:
    config = load_config("config/ysf-bm-router.toml")
    config = replace(
        config,
        behavior=replace(config.behavior, suppress_route_change_transmission=True),
    )
    state = RouterState.from_config(config)

    event = state.handle_transmission_start(dgid=22, now=100.0)

    assert event.decision == FrameDecision.SUPPRESS_SELECTOR
    assert event.active_route.dgid == 22
    assert event.active_route.talkgroup == 31291


def test_unknown_dgid_does_not_change_active_route() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))

    event = state.handle_transmission_start(dgid=99, now=100.0)

    assert event.decision == FrameDecision.IGNORE_UNKNOWN_DGID
    assert event.active_route.dgid == 10


def test_silence_period_blocks_route_change() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))
    state.handle_transmission_start(dgid=10, now=100.0)

    event = state.handle_transmission_start(dgid=22, now=101.0)

    assert event.decision == FrameDecision.BLOCKED_BY_SILENCE_PERIOD
    assert state.active_route.dgid == 10


def test_return_to_default_after_inactivity() -> None:
    state = RouterState.from_config(load_config("config/ysf-bm-router.toml"))
    state.handle_transmission_start(dgid=22, now=100.0)

    event = state.maybe_return_to_default(now=100.0 + 31 * 60)

    assert event is not None
    assert event.active_route.dgid == 10
