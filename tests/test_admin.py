from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from ysf_bm_router.admin import build_config_from_payload
from ysf_bm_router.admin import read_wpsd_theme
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


def test_read_wpsd_theme_maps_ini_colors(tmp_path: Path) -> None:
    theme_path = tmp_path / "wpsd-css.ini"
    theme_path.write_text(
        """[Background]
PageColor=#010203
ContentColor=#05090C
BannersColor=#020405
NavPanelColor=#030707
ModeCellActiveColor=#18A558
ModeCellInactiveColor=#A93232
DropdownColor=#070D10
TableRowBgEvenColor=#080E12
TableRowBgOddColor=#04080A

[Text]
TextColor=#EEF7F4
TextSectionColor=#8FE7D2
TextLinkColor=#B58CFF
BannersColor=#E28A1A

[ExtraSettings]
TableBorderColor=#132328
""",
        encoding="utf-8",
    )

    theme = read_wpsd_theme(theme_path)

    assert theme["source"] == "wpsd"
    assert theme["path"] == str(theme_path)
    assert theme["variables"]["--bg"] == "#010203"
    assert theme["variables"]["--panel"] == "#05090c"
    assert theme["variables"]["--accent"] == "#18a558"
    assert theme["variables"]["--accent-2"] == "#e28a1a"
    assert theme["variables"]["--link"] == "#b58cff"


def test_read_wpsd_theme_uses_fallback_for_missing_file(tmp_path: Path) -> None:
    theme = read_wpsd_theme(tmp_path / "missing.ini")

    assert theme["source"] == "fallback"
    assert theme["variables"]["--bg"] == "#050708"
