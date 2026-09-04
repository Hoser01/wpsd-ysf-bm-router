from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from ysf_bm_router.ysf.fich import YsfDecodeError, parse_ysfd_frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize ysf-bm-router NDJSON captures.")
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()

    records = [json.loads(line) for line in args.capture.open(encoding="utf-8")]
    print(f"records={len(records)}")
    print(f"kinds={dict(collections.Counter(r['packet_kind'] for r in records))}")
    print(f"lengths={dict(collections.Counter(r['length'] for r in records))}")

    decoded = []
    for record in records:
        if record["packet_kind"] != "ysfd":
            continue
        try:
            frame = parse_ysfd_frame(bytes.fromhex(record["hex"]))
        except YsfDecodeError as exc:
            print(f"seq={record['seq']} decode_error={exc}")
            continue
        decoded.append(frame.fich.dgid)
        print(
            f"seq={record['seq']} dgid={frame.fich.dgid} "
            f"fn={frame.fich.frame_number} dt={frame.fich.data_type} "
            f"ft={frame.fich.frame_type} sql={frame.fich.sql_open} "
            f"src={frame.source} dst={frame.destination} stream_frame={frame.frame_number}"
        )

    print(f"decoded_dgids={dict(collections.Counter(decoded))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
