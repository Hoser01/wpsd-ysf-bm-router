#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import struct
import time
from pathlib import Path


ETH_P_ALL = 0x0003


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture raw YSF UDP payloads without tcpdump.")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--out", default="/tmp/ysfd-capture.jsonl")
    parser.add_argument("--iface", default="")
    args = parser.parse_args()

    out = Path(args.out)
    raw_out = out.with_suffix(out.suffix + ".bin")
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    if args.iface:
        sock.bind((args.iface, 0))
    sock.settimeout(0.5)

    deadline = time.monotonic() + args.seconds
    count = 0
    with out.open("w", encoding="utf-8") as jsonl, raw_out.open("wb") as raw:
        while time.monotonic() < deadline:
            try:
                packet = sock.recv(4096)
            except socket.timeout:
                continue

            parsed = parse_udp_payload(packet)
            if parsed is None:
                continue
            src_ip, dst_ip, src_port, dst_port, payload = parsed
            if not payload.startswith((b"YSFD", b"YSFP", b"YSFL", b"YSFU", b"YSFO", b"YSFACK", b"YSFNAK")):
                continue

            count += 1
            raw.write(len(payload).to_bytes(2, "big"))
            raw.write(payload)
            jsonl.write(json.dumps(summarize(count, src_ip, dst_ip, src_port, dst_port, payload)) + "\n")
            jsonl.flush()

    print(f"captured={count} jsonl={out} raw={raw_out}")


def parse_udp_payload(packet: bytes) -> tuple[str, str, int, int, bytes] | None:
    for ip_offset in (14, 16):
        if len(packet) < ip_offset + 28:
            continue
        version = packet[ip_offset] >> 4
        ihl = (packet[ip_offset] & 0x0F) * 4
        if version != 4 or ihl < 20:
            continue
        if packet[ip_offset + 9] != 17:
            continue
        total_len = int.from_bytes(packet[ip_offset + 2 : ip_offset + 4], "big")
        udp_offset = ip_offset + ihl
        if len(packet) < udp_offset + 8:
            continue
        udp_len = int.from_bytes(packet[udp_offset + 4 : udp_offset + 6], "big")
        if udp_len < 8:
            continue
        payload_offset = udp_offset + 8
        payload_end = payload_offset + udp_len - 8
        if total_len and payload_end > ip_offset + total_len:
            continue
        src_ip = socket.inet_ntoa(packet[ip_offset + 12 : ip_offset + 16])
        dst_ip = socket.inet_ntoa(packet[ip_offset + 16 : ip_offset + 20])
        src_port, dst_port = struct.unpack("!HH", packet[udp_offset : udp_offset + 4])
        return src_ip, dst_ip, src_port, dst_port, packet[payload_offset:payload_end]
    return None


def summarize(count: int, src_ip: str, dst_ip: str, src_port: int, dst_port: int, payload: bytes) -> dict[str, object]:
    item: dict[str, object] = {
        "n": count,
        "ts": time.time(),
        "src": f"{src_ip}:{src_port}",
        "dst": f"{dst_ip}:{dst_port}",
        "len": len(payload),
        "magic": payload[:6].decode("ascii", errors="replace"),
        "hex": payload.hex(),
    }
    if payload.startswith(b"YSFD") and len(payload) >= 35:
        item.update(
            {
                "net": payload[4:14].decode("ascii", errors="replace").rstrip(),
                "gw": payload[14:24].decode("ascii", errors="replace").rstrip(),
                "dst_call": payload[24:34].decode("ascii", errors="replace").rstrip(),
                "seq": payload[34],
            }
        )
    return item


if __name__ == "__main__":
    main()
