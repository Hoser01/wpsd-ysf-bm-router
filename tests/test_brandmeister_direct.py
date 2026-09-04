from __future__ import annotations

from ysf_bm_router.brandmeister.direct import _pad


def test_pad_truncates_and_space_pads() -> None:
    assert _pad(b"W0WC", 10) == b"W0WC      "
    assert _pad(b"ABCDEFGHIJK", 10) == b"ABCDEFGHIJ"
