#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path


YSF_SYNC = b"YSFD"


@dataclass(frozen=True)
class Candidate:
    offset: int
    value: int
    masked_7bit: int
    confidence: str
    reason: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture local YSFGateway UDP packets for DG-ID parser development."
    )
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=42002)
    parser.add_argument(
        "--output",
        default="/tmp/ysf-bm-router-capture.ndjson",
        help="NDJSON capture output path.",
    )
    parser.add_argument(
        "--max-packets",
        type=int,
        default=0,
        help="Stop after this many packets. 0 means run until Ctrl-C.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    print(f"listening udp://{args.bind}:{args.port}")
    print(f"writing {output}")
    print("press Ctrl-C to stop")

    count = 0
    with output.open("a", encoding="utf-8") as handle:
        try:
            while args.max_packets == 0 or count < args.max_packets:
                data, addr = sock.recvfrom(2048)
                count += 1
                record = build_record(count, data, addr)
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
                handle.flush()
                print_summary(record)
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def build_record(count: int, data: bytes, addr: tuple[str, int]) -> dict:
    now = time.time()
    candidates = [asdict(candidate) for candidate in candidate_dgids(data)]
    ascii_preview = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data[:96])
    return {
        "seq": count,
        "time": now,
        "time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "source": {"host": addr[0], "port": addr[1]},
        "length": len(data),
        "packet_kind": packet_kind(data),
        "ascii_preview": ascii_preview,
        "hex": data.hex(),
        "base64": base64.b64encode(data).decode("ascii"),
        "dgid_candidates": candidates,
    }


def packet_kind(data: bytes) -> str:
    if data.startswith(YSF_SYNC):
        return "ysfd"
    if data.startswith(b"YSFP"):
        return "ysfp"
    if data.startswith(b"YSFI"):
        return "ysfi"
    if data.startswith(b"YSFU"):
        return "ysfu"
    if data.startswith(b"YSFL"):
        return "ysfl"
    if data.startswith(b"YSFO"):
        return "ysfo"
    return "unknown"


def candidate_dgids(data: bytes) -> list[Candidate]:
    candidates: list[Candidate] = []

    # The common YSF UDP voice frame starts with "YSFD", then metadata, then
    # the encoded FICH/payload area. These offsets are intentionally broad
    # probes. We will narrow them after correlating real captures.
    interesting_offsets = [
        4,
        14,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
    ]

    for offset in interesting_offsets:
        if offset >= len(data):
            continue
        value = data[offset]
        masked = value & 0x7F
        if 0 <= masked <= 99 or masked == 127:
            reason = "known YSF/FICH probe offset"
            confidence = "probe"
            if data.startswith(YSF_SYNC) and 34 <= offset <= 50:
                confidence = "fich-area-probe"
            candidates.append(Candidate(offset, value, masked, confidence, reason))

    return candidates


def print_summary(record: dict) -> None:
    candidates = record["dgid_candidates"]
    compact = ", ".join(
        f"@{item['offset']}={item['masked_7bit']}" for item in candidates[:12]
    )
    if len(candidates) > 12:
        compact += ", ..."
    print(
        f"#{record['seq']:04d} {record['packet_kind']} "
        f"len={record['length']} from={record['source']['host']}:{record['source']['port']} "
        f"dgid? [{compact}] ascii={record['ascii_preview']!r}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
