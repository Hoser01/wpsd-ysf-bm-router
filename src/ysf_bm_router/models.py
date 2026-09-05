from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    dgid: int
    talkgroup: int
    short_name: str
    long_name: str
    region: str
    sort_order: int
    enabled: bool = True

    def validate(self) -> None:
        if not 0 <= self.dgid <= 99:
            raise ValueError(f"DG-ID must be between 0 and 99: {self.dgid}")
        if self.talkgroup <= 0:
            raise ValueError(f"Talkgroup must be positive: {self.talkgroup}")
        if not self.short_name.strip():
            raise ValueError("Route short_name is required")
        if not self.long_name.strip():
            raise ValueError("Route long_name is required")


@dataclass(frozen=True)
class YsfConfig:
    listen_address: str = "127.0.0.1"
    listen_port: int = 42002
    reflector_name: str = "YSF-BM-TEST"


@dataclass(frozen=True)
class BrandMeisterConfig:
    server: str = ""
    port: int = 42001
    callsign: str = ""
    dmr_id: str = ""
    password: str = ""
    backend: str = "ysf_direct"
    master_server: str = ""
    master_port: int = 62031
    master_password: str = ""
    master_local_port: int = 62032
    master_jitter_ms: int = 360
    master_options: str = ""
    hotspot_type: str = "MMDVM_DMO"
    rx_frequency: int = 431150000
    tx_frequency: int = 426150000
    color_code: int = 1
    power: int = 1
    latitude: float = 0.0
    longitude: float = 0.0
    height: int = 0
    location: str = ""
    description: str = "ysf-bm-router"
    url: str = ""
    version: str = "20260726_WPSD"


@dataclass(frozen=True)
class BehaviorConfig:
    default_dgid: int = 10
    return_to_default_minutes: int = 30
    tg_change_silence_seconds: float = 2.0
    return_frame_interval_seconds: float = 0.1
    return_start_delay_seconds: float = 0.0
    rewrite_return_dgid: bool = True
    rewrite_return_source: bool = True
    insert_return_header: bool = False
    suppress_route_change_transmission: bool = False
    show_dgid_callsign: bool = True
    acknowledge_tg_change: bool = True


@dataclass(frozen=True)
class AppConfig:
    ysf: YsfConfig
    brandmeister: BrandMeisterConfig
    behavior: BehaviorConfig
    routes: tuple[Route, ...]

    def validate(self) -> None:
        if not self.routes:
            raise ValueError("At least one route is required")

        seen_dgids: set[int] = set()
        for route in self.routes:
            route.validate()
            if route.dgid in seen_dgids:
                raise ValueError(f"Duplicate DG-ID: {route.dgid}")
            seen_dgids.add(route.dgid)

        if self.behavior.default_dgid not in seen_dgids:
            raise ValueError(
                f"Default DG-ID {self.behavior.default_dgid} does not exist in routes"
            )

        if self.behavior.tg_change_silence_seconds < 0:
            raise ValueError("TG change silence seconds cannot be negative")

        if self.behavior.return_to_default_minutes < 0:
            raise ValueError("Return-to-default minutes cannot be negative")

        if self.behavior.return_frame_interval_seconds < 0:
            raise ValueError("Return frame interval seconds cannot be negative")

        if self.behavior.return_start_delay_seconds < 0:
            raise ValueError("Return start delay seconds cannot be negative")

        if self.brandmeister.backend not in {"ysf_direct", "dmr_master", "hybrid_dmr_return"}:
            raise ValueError(
                "BrandMeister backend must be 'ysf_direct', 'dmr_master', or 'hybrid_dmr_return'"
            )

        if self.brandmeister.backend == "dmr_master" and self.brandmeister.port == 42001:
            raise ValueError(
                "DMR master backend requires the Homebrew/DMR master port, usually 62031"
            )

        if self.brandmeister.backend == "hybrid_dmr_return" and not self.brandmeister.master_server:
            raise ValueError("Hybrid DMR return backend requires master_server")

    def enabled_route_for_dgid(self, dgid: int) -> Route | None:
        for route in self.routes:
            if route.dgid == dgid and route.enabled:
                return route
        return None

    def default_route(self) -> Route:
        route = self.enabled_route_for_dgid(self.behavior.default_dgid)
        if route is None:
            raise ValueError("Default route is disabled or missing")
        return route
