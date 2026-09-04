from __future__ import annotations

import logging

from ysf_bm_router.models import BrandMeisterConfig

from .direct import DirectBrandMeisterTransport
from .dmr_master import DmrMasterBrandMeisterTransport, HybridDmrReturnBrandMeisterTransport
from .transport import BrandMeisterTransport


def build_brandmeister_transport(
    config: BrandMeisterConfig,
    logger: logging.Logger | None = None,
) -> BrandMeisterTransport:
    if config.backend == "ysf_direct":
        return DirectBrandMeisterTransport(config, logger=logger)
    if config.backend == "dmr_master":
        return DmrMasterBrandMeisterTransport(config, logger=logger)
    if config.backend == "hybrid_dmr_return":
        return HybridDmrReturnBrandMeisterTransport(config, logger=logger)
    raise ValueError(f"Unsupported BrandMeister backend: {config.backend}")
