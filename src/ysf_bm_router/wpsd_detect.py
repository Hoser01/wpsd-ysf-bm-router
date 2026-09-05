from __future__ import annotations

import argparse
import configparser
from dataclasses import replace
from pathlib import Path

from .config import atomic_write_config, config_to_toml, load_config
from .models import AppConfig, BrandMeisterConfig, YsfConfig


DEFAULT_PATHS = (
    Path("/etc/mmdvmhost"),
    Path("/etc/ysf2dmr"),
    Path("/etc/dmrgateway"),
)


def detect_wpsd_settings(paths: tuple[Path, ...] = DEFAULT_PATHS, hotspot_suffix: str = "10") -> dict[str, object]:
    configs = {path.name.lower(): _read_ini(path) for path in paths}
    mmdvm = configs.get("mmdvmhost", configparser.ConfigParser())
    ysf2dmr = configs.get("ysf2dmr", configparser.ConfigParser())
    dmrgateway = configs.get("dmrgateway", configparser.ConfigParser())

    dmr_id = _first_value(
        (ysf2dmr, "DMR Network", "Id"),
        (ysf2dmr, "DMR Network", "RadioID"),
        (dmrgateway, "DMR Network 1", "Id"),
        (dmrgateway, "DMR Network 1", "RadioID"),
        (mmdvm, "DMR", "Id"),
        (mmdvm, "General", "Id"),
    )
    dmr_id = _with_hotspot_suffix(dmr_id, hotspot_suffix)

    password = _first_value(
        (ysf2dmr, "DMR Network", "Password"),
        (ysf2dmr, "DMR Network", "Pass"),
        (dmrgateway, "DMR Network 1", "Password"),
        (dmrgateway, "DMR Network 1", "Pass"),
        (dmrgateway, "DMR Network 2", "Password"),
        (dmrgateway, "DMR Network 2", "Pass"),
    )

    detected: dict[str, object] = {
        "reflector_name": "YSF-BM-TEST",
        "callsign": _first_value(
            (mmdvm, "General", "Callsign"),
            (ysf2dmr, "Info", "Callsign"),
            (dmrgateway, "General", "Callsign"),
        ),
        "dmr_id": dmr_id,
        "password": password,
        "master_password": password,
        "master_server": _first_value(
            (ysf2dmr, "DMR Network", "Address"),
            (ysf2dmr, "DMR Network", "Addr"),
            (dmrgateway, "DMR Network 1", "Address"),
        ),
        "master_port": _first_int(
            (ysf2dmr, "DMR Network", "Port"),
            (dmrgateway, "DMR Network 1", "Port"),
        ),
        "master_options": _first_value(
            (ysf2dmr, "DMR Network", "Options"),
            (dmrgateway, "DMR Network 1", "Options"),
        ),
        "rx_frequency": _first_int(
            (mmdvm, "Info", "RXFrequency"),
            (mmdvm, "General", "RXFrequency"),
        ),
        "tx_frequency": _first_int(
            (mmdvm, "Info", "TXFrequency"),
            (mmdvm, "General", "TXFrequency"),
        ),
        "color_code": _first_int((mmdvm, "DMR", "ColorCode")),
        "power": _first_int((mmdvm, "Info", "Power")),
        "latitude": _first_float((mmdvm, "Info", "Latitude")),
        "longitude": _first_float((mmdvm, "Info", "Longitude")),
        "height": _first_int((mmdvm, "Info", "Height")),
        "location": _first_value((mmdvm, "Info", "Location")),
        "description": _first_value((mmdvm, "Info", "Description")),
        "url": _first_value((mmdvm, "Info", "URL")),
    }
    return {key: value for key, value in detected.items() if value not in ("", None)}


def apply_detected_settings(
    config: AppConfig,
    detected: dict[str, object],
    *,
    only_missing: bool = False,
) -> AppConfig:
    ysf_updates: dict[str, object] = {}
    bm_updates: dict[str, object] = {}

    if "reflector_name" in detected and _should_update(config.ysf.reflector_name, only_missing):
        ysf_updates["reflector_name"] = str(detected["reflector_name"])

    for key in BrandMeisterConfig.__dataclass_fields__:
        if key in detected and _should_update(getattr(config.brandmeister, key), only_missing):
            bm_updates[key] = detected[key]

    return replace(
        config,
        ysf=replace(config.ysf, **ysf_updates) if ysf_updates else config.ysf,
        brandmeister=replace(config.brandmeister, **bm_updates) if bm_updates else config.brandmeister,
    )


def prefill_config(
    seed_path: Path,
    output_path: Path,
    *,
    only_missing: bool = False,
    hotspot_suffix: str = "10",
    wpsd_paths: tuple[Path, ...] = DEFAULT_PATHS,
) -> dict[str, object]:
    config = load_config(output_path if output_path.exists() else seed_path)
    detected = detect_wpsd_settings(wpsd_paths, hotspot_suffix=hotspot_suffix)
    updated = apply_detected_settings(config, detected, only_missing=only_missing)
    atomic_write_config(output_path, config_to_toml(updated))
    return detected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prefill ysf-bm-router config from WPSD files.")
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hotspot-suffix", default="10")
    parser.add_argument("--only-missing", action="store_true")
    args = parser.parse_args(argv)

    detected = prefill_config(
        args.seed,
        args.output,
        only_missing=args.only_missing,
        hotspot_suffix=args.hotspot_suffix,
    )
    visible = ", ".join(sorted(key for key in detected if "password" not in key))
    if visible:
        print(f"Detected WPSD settings: {visible}")
    if "password" in detected or "master_password" in detected:
        print("Copied BrandMeister hotspot password from WPSD config.")
    return 0


def _read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str.lower
    if path.exists():
        parser.read(path, encoding="utf-8")
    return parser


def _first_value(*candidates: tuple[configparser.ConfigParser, str, str]) -> str:
    for parser, section, key in candidates:
        value = _get_value(parser, section, key)
        if value:
            return value
    return ""


def _first_int(*candidates: tuple[configparser.ConfigParser, str, str]) -> int | None:
    value = _first_value(*candidates)
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _first_float(*candidates: tuple[configparser.ConfigParser, str, str]) -> float | None:
    value = _first_value(*candidates)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _get_value(parser: configparser.ConfigParser, section: str, key: str) -> str:
    actual_section = _find_section(parser, section)
    if not actual_section:
        return ""
    if not parser.has_option(actual_section, key.lower()):
        return ""
    return parser.get(actual_section, key.lower()).strip().strip('"').strip("'")


def _find_section(parser: configparser.ConfigParser, section: str) -> str:
    for candidate in parser.sections():
        if candidate.lower() == section.lower():
            return candidate
    return ""


def _with_hotspot_suffix(dmr_id: str, hotspot_suffix: str) -> str:
    digits = "".join(char for char in dmr_id if char.isdigit())
    suffix = "".join(char for char in hotspot_suffix if char.isdigit())
    if not digits:
        return ""
    if len(digits) <= 7 and suffix:
        return f"{digits}{int(suffix):02d}"
    return digits


def _should_update(current: object, only_missing: bool) -> bool:
    if not only_missing:
        return True
    return current in ("", None, 0, 0.0)


if __name__ == "__main__":
    raise SystemExit(main())
