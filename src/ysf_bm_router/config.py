from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from .models import AppConfig, BehaviorConfig, BrandMeisterConfig, Route, YsfConfig

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib


def load_config(path: str | Path) -> AppConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    config = config_from_mapping(data)
    config.validate()
    return config


def config_from_mapping(data: dict[str, Any]) -> AppConfig:
    routes = tuple(Route(**item) for item in data.get("routes", []))
    return AppConfig(
        ysf=YsfConfig(**data.get("ysf", {})),
        brandmeister=BrandMeisterConfig(**data.get("brandmeister", {})),
        behavior=BehaviorConfig(**data.get("behavior", {})),
        routes=routes,
    )


def config_to_toml(config: AppConfig) -> str:
    lines: list[str] = []
    _append_section(lines, "ysf", config.ysf)
    _append_section(lines, "brandmeister", config.brandmeister)
    _append_section(lines, "behavior", config.behavior)
    for route in sorted(config.routes, key=lambda item: item.sort_order):
        lines.append("[[routes]]")
        for field in fields(route):
            value = getattr(route, field.name)
            lines.append(f"{field.name} = {_format_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_config(path: str | Path, text: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    existing_stat = destination.stat() if destination.exists() else None
    if destination.exists():
        backup = destination.with_suffix(destination.suffix + ".bak")
        shutil.copy2(destination, backup)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
        if existing_stat is not None:
            os.chmod(destination, existing_stat.st_mode)
            try:
                os.chown(destination, existing_stat.st_uid, existing_stat.st_gid)
            except AttributeError:  # pragma: no cover - Windows
                pass
    except Exception:
        try:
            os.unlink(temp_name)
        finally:
            raise


def _append_section(lines: list[str], name: str, value: object) -> None:
    if not is_dataclass(value):
        raise TypeError(f"{name} is not a dataclass")
    lines.append(f"[{name}]")
    for field in fields(value):
        lines.append(f"{field.name} = {_format_toml_value(getattr(value, field.name))}")
    lines.append("")


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = "" if value is None else str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
