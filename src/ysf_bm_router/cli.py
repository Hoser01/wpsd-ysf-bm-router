from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .brandmeister.factory import build_brandmeister_transport
from .brandmeister.transport import DryRunBrandMeisterTransport
from .config import load_config
from .runtime import RouterRuntime


def main() -> int:
    parser = argparse.ArgumentParser(prog="ysf-bm-router")
    parser.add_argument(
        "--config",
        default="/opt/ysf-bm-router/config/ysf-bm-router.toml",
        help="Path to ysf-bm-router TOML configuration.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run with a logging-only BrandMeister transport.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = load_config(Path(args.config))
    if args.check_config:
        print(
            f"config ok: {len(config.routes)} routes, "
            f"default DG-ID {config.behavior.default_dgid}"
        )
        return 0

    transport = (
        DryRunBrandMeisterTransport()
        if args.dry_run
        else build_brandmeister_transport(config.brandmeister)
    )
    RouterRuntime(config, transport).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
