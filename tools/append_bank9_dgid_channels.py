from __future__ import annotations

import csv
import sys
import tomllib
from pathlib import Path


SOURCE = Path(r"D:\z_backup\onedrive\Desktop\FT5D 2026-09-01.csv")
ROUTES = Path("config/ysf-bm-router.toml")
OUTPUT = Path(r"D:\z_backup\onedrive\Desktop\FT5D 2026-09-01 Bank9 DGID.csv")

BANK_START_INDEX = 28
BANK8_INDEX = BANK_START_INDEX + 7
BANK9_INDEX = BANK_START_INDEX + 8
RX_DGID_INDEX = 16
TX_DGID_INDEX = 17
NAME_INDEX = 10
COMMENT_INDEX = 52


def main() -> int:
    rows = list(csv.reader(SOURCE.open(newline="", encoding="utf-8-sig")))
    if len(rows) != 900:
        raise SystemExit(f"Expected 900 ADMS rows, found {len(rows)}")
    if sorted(set(len(row) for row in rows)) != [54]:
        raise SystemExit("Expected every ADMS row to have 54 columns")

    routes = tomllib.loads(ROUTES.read_text(encoding="utf-8"))["routes"]
    routes = sorted((route for route in routes if route.get("enabled", True)), key=lambda r: r["sort_order"])

    existing_bank8 = [row for row in rows if row[BANK8_INDEX] == "ON"]
    wpsd_hotspot_rows = [
        row
        for row in rows
        if row[NAME_INDEX].strip().upper().startswith("WPSD BM")
        and row[2].strip()
        and row[3].strip()
    ]
    if not wpsd_hotspot_rows:
        raise SystemExit("Could not find an existing WPSD BM hotspot row to use as template")

    template = wpsd_hotspot_rows[0]
    active_indexes = [i for i, row in enumerate(rows) if row[NAME_INDEX].strip()]
    next_index = max(active_indexes) + 1

    if next_index + len(routes) > len(rows):
        raise SystemExit("Not enough blank memory slots to append Bank 8 DG-ID channels")

    existing_names = {row[NAME_INDEX].strip().upper() for row in rows if row[NAME_INDEX].strip()}
    added = []

    for offset, route in enumerate(routes):
        dgid = int(route["dgid"])
        base_name = f"DG{dgid:02d} {route['short_name']}"
        name = unique_name(base_name[:16], existing_names)

        row = template[:]
        row[0] = str(next_index + offset + 1)
        row[NAME_INDEX] = name
        row[RX_DGID_INDEX] = "RX 00"
        row[TX_DGID_INDEX] = f"TX {dgid:02d}"
        row[COMMENT_INDEX] = f"TG {route['talkgroup']} {route['long_name']}"

        for bank in range(24):
            row[BANK_START_INDEX + bank] = "OFF"
        row[BANK9_INDEX] = "ON"

        rows[next_index + offset] = row
        existing_names.add(name.upper())
        added.append((row[0], name, row[2], row[TX_DGID_INDEX], row[COMMENT_INDEX]))

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(rows)

    validate_output(OUTPUT, expected_added=len(routes))
    print(f"wrote={OUTPUT}")
    print(f"added={len(added)}")
    print(f"first_added={added[0]}")
    print(f"last_added={added[-1]}")
    return 0


def unique_name(name: str, existing_names: set[str]) -> str:
    if name.upper() not in existing_names:
        return name

    for number in range(2, 100):
        suffix = f" {number}"
        candidate = f"{name[:16 - len(suffix)]}{suffix}"
        if candidate.upper() not in existing_names:
            return candidate

    raise ValueError(f"Could not create unique ADMS name for {name}")


def validate_output(path: Path, expected_added: int) -> None:
    data = path.read_bytes()
    rows = list(csv.reader(path.open(newline="", encoding="utf-8")))
    active = [row for row in rows if row[NAME_INDEX].strip()]
    issues = []

    if len(rows) != 900:
        issues.append(f"row count {len(rows)}")
    if sorted(set(len(row) for row in rows)) != [54]:
        issues.append("column count is not 54 for every row")
    if data.count(b"\n") != 900 or data.count(b"\r") != 0:
        issues.append("line endings changed")
    if data.count(b'"') != 0:
        issues.append("quote characters present")
    for i, row in enumerate(rows, start=1):
        if row[0] != str(i):
            issues.append(f"bad memory number at row {i}: {row[0]}")
            break

    bank8_count = sum(1 for row in rows if row[BANK8_INDEX] == "ON")
    bank9_count = sum(1 for row in rows if row[BANK9_INDEX] == "ON")
    if bank8_count != 1:
        issues.append(f"Bank 8 count {bank8_count}, expected existing count 1")
    if bank9_count != expected_added:
        issues.append(f"Bank 9 count {bank9_count}, expected {expected_added}")

    if len(active) != 534 + expected_added:
        issues.append(f"active count {len(active)}, expected {534 + expected_added}")

    if issues:
        raise SystemExit("Validation failed: " + "; ".join(issues))

    print(f"active_rows={len(active)}")
    print(f"bank8_count={bank8_count}")
    print(f"bank9_count={bank9_count}")
    print("validation=ok")


if __name__ == "__main__":
    raise SystemExit(main())
