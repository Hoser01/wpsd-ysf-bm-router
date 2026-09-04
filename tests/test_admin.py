from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from ysf_bm_router.admin import build_config_from_payload
from ysf_bm_router.config import load_config


def test_admin_payload_builds_valid_config() -> None:
    config = load_config(Path("config/ysf-bm-router.toml"))
    payload = asdict(config)

    updated = build_config_from_payload(payload)

    assert updated == config


def test_admin_payload_rejects_duplicate_dgid() -> None:
    config = load_config(Path("config/ysf-bm-router.toml"))
    payload = asdict(config)
    payload["routes"][1]["dgid"] = payload["routes"][0]["dgid"]

    with pytest.raises(ValueError, match="Duplicate DG-ID"):
        build_config_from_payload(payload)
