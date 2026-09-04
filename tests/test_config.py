from __future__ import annotations

import os
from pathlib import Path

import pytest

from ysf_bm_router.config import atomic_write_config, config_to_toml, load_config
from ysf_bm_router.models import AppConfig, BehaviorConfig, BrandMeisterConfig, Route, YsfConfig


def test_seed_config_loads() -> None:
    config = load_config(Path("config/ysf-bm-router.toml"))

    assert len(config.routes) == 35
    assert config.default_route().dgid == 10
    assert config.enabled_route_for_dgid(22).talkgroup == 31291


def test_duplicate_dgid_is_invalid() -> None:
    config = AppConfig(
        ysf=YsfConfig(),
        brandmeister=BrandMeisterConfig(),
        behavior=BehaviorConfig(default_dgid=10),
        routes=(
            Route(10, 3205642, "LZ", "N0NMS / LZ", "LZ", 10),
            Route(10, 31291, "SWMO", "SWMO", "Missouri", 22),
        ),
    )

    with pytest.raises(ValueError, match="Duplicate DG-ID"):
        config.validate()


def test_duplicate_talkgroup_is_allowed() -> None:
    config = AppConfig(
        ysf=YsfConfig(),
        brandmeister=BrandMeisterConfig(),
        behavior=BehaviorConfig(default_dgid=29),
        routes=(
            Route(29, 31298, "KCN ARES", "KCN ARES", "Missouri", 29),
            Route(57, 31298, "KCN ARES", "KCN ARES", "Kansas", 57),
        ),
    )

    config.validate()


def test_dmr_master_backend_requires_homebrew_port() -> None:
    config = AppConfig(
        ysf=YsfConfig(),
        brandmeister=BrandMeisterConfig(backend="dmr_master", port=42001),
        behavior=BehaviorConfig(default_dgid=10),
        routes=(Route(10, 3205642, "LZ", "N0NMS / LZ", "LZ", 10),),
    )

    with pytest.raises(ValueError, match="Homebrew/DMR master port"):
        config.validate()


def test_hybrid_backend_requires_master_server() -> None:
    config = AppConfig(
        ysf=YsfConfig(),
        brandmeister=BrandMeisterConfig(backend="hybrid_dmr_return", master_server=""),
        behavior=BehaviorConfig(default_dgid=10),
        routes=(Route(10, 3205642, "LZ", "N0NMS / LZ", "LZ", 10),),
    )

    with pytest.raises(ValueError, match="master_server"):
        config.validate()


def test_rejects_unknown_brandmeister_backend() -> None:
    config = AppConfig(
        ysf=YsfConfig(),
        brandmeister=BrandMeisterConfig(backend="wat"),
        behavior=BehaviorConfig(default_dgid=10),
        routes=(Route(10, 3205642, "LZ", "N0NMS / LZ", "LZ", 10),),
    )

    with pytest.raises(ValueError, match="backend"):
        config.validate()


def test_atomic_write_creates_backup(tmp_path: Path) -> None:
    config_path = tmp_path / "router.toml"
    config_path.write_text("old", encoding="utf-8")

    atomic_write_config(config_path, "new")

    assert config_path.read_text(encoding="utf-8") == "new"
    assert config_path.with_suffix(".toml.bak").read_text(encoding="utf-8") == "old"


def test_atomic_write_preserves_existing_file_mode(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("Windows does not preserve POSIX group mode bits")

    config_path = tmp_path / "router.toml"
    config_path.write_text("old", encoding="utf-8")
    config_path.chmod(0o640)

    atomic_write_config(config_path, "new")

    assert config_path.stat().st_mode & 0o777 == 0o640


def test_config_to_toml_round_trips_seed_config(tmp_path: Path) -> None:
    original = load_config(Path("config/ysf-bm-router.toml"))
    config_path = tmp_path / "router.toml"

    config_path.write_text(config_to_toml(original), encoding="utf-8")
    reloaded = load_config(config_path)

    assert reloaded == original
