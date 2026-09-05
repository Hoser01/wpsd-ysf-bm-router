from __future__ import annotations

import os
from pathlib import Path

import pytest

from ysf_bm_router.config import atomic_write_config, config_to_toml, load_config
from ysf_bm_router.models import AppConfig, BehaviorConfig, BrandMeisterConfig, Route, YsfConfig
from ysf_bm_router.wpsd_detect import apply_detected_settings, detect_wpsd_settings, prefill_config


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


def test_detect_wpsd_settings_copies_common_hotspot_values(tmp_path: Path) -> None:
    mmdvmhost = tmp_path / "mmdvmhost"
    ysf2dmr = tmp_path / "ysf2dmr"
    dmrgateway = tmp_path / "dmrgateway"
    mmdvmhost.write_text(
        """
[General]
Callsign=W0WC
Id=3129301

[Info]
RXFrequency=431150000
TXFrequency=431150000
Power=1
Latitude=37.0842
Longitude=-94.5133
Height=300
Location=Joplin, Missouri
Description=W0WC Hotspot
URL=https://wpsd.radio/

[DMR]
ColorCode=1
""".strip(),
        encoding="utf-8",
    )
    ysf2dmr.write_text(
        """
[DMR Network]
Address=3103.master.brandmeister.network
Port=62031
Password=secret-pass
Options=TS2_1=3205642;
""".strip(),
        encoding="utf-8",
    )
    dmrgateway.write_text("", encoding="utf-8")

    detected = detect_wpsd_settings((mmdvmhost, ysf2dmr, dmrgateway))

    assert detected["callsign"] == "W0WC"
    assert detected["dmr_id"] == "312930110"
    assert detected["password"] == "secret-pass"
    assert detected["master_password"] == "secret-pass"
    assert detected["master_server"] == "3103.master.brandmeister.network"
    assert detected["master_options"] == "TS2_1=3205642;"
    assert detected["rx_frequency"] == 431150000
    assert detected["tx_frequency"] == 431150000
    assert detected["location"] == "Joplin, Missouri"


def test_apply_detected_settings_only_fills_missing_values() -> None:
    config = AppConfig(
        ysf=YsfConfig(reflector_name="CUSTOM"),
        brandmeister=BrandMeisterConfig(callsign="N0CALL", password=""),
        behavior=BehaviorConfig(default_dgid=10),
        routes=(Route(10, 3205642, "LZ", "N0NMS / LZ", "LZ", 10),),
    )

    updated = apply_detected_settings(
        config,
        {"reflector_name": "YSF-BM-TEST", "callsign": "W0WC", "password": "secret-pass"},
        only_missing=True,
    )

    assert updated.ysf.reflector_name == "CUSTOM"
    assert updated.brandmeister.callsign == "N0CALL"
    assert updated.brandmeister.password == "secret-pass"


def test_prefill_config_writes_detected_values(tmp_path: Path) -> None:
    seed = tmp_path / "seed.toml"
    output = tmp_path / "router.toml"
    mmdvmhost = tmp_path / "mmdvmhost"
    ysf2dmr = tmp_path / "ysf2dmr"
    dmrgateway = tmp_path / "dmrgateway"
    seed.write_text(config_to_toml(load_config(Path("config/ysf-bm-router.toml"))), encoding="utf-8")
    mmdvmhost.write_text(
        """
[General]
Callsign=W0WC
Id=3129301
""".strip(),
        encoding="utf-8",
    )
    ysf2dmr.write_text(
        """
[DMR Network]
Password=secret-pass
""".strip(),
        encoding="utf-8",
    )
    dmrgateway.write_text("", encoding="utf-8")

    prefill_config(seed, output, wpsd_paths=(mmdvmhost, ysf2dmr, dmrgateway))

    config = load_config(output)
    assert config.ysf.reflector_name == "YSF-BM-TEST"
    assert config.brandmeister.callsign == "W0WC"
    assert config.brandmeister.dmr_id == "312930110"
    assert config.brandmeister.password == "secret-pass"
    assert config.brandmeister.master_password == "secret-pass"
