#!/usr/bin/env python3
"""Build per-node binary shards from the NYC 311 CSV."""

import argparse
import csv
import os
import re
import struct
from datetime import datetime


RECORD_FMT = "<iffIHBB"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
assert RECORD_SIZE == 20

NODES = "ABCDEFGHI"
STATUS = {
    "open": 1,
    "closed": 2,
    "pending": 3,
    "assigned": 4,
    "in progress": 5,
}
BOROUGH = {
    "manhattan": 1,
    "bronx": 2,
    "brooklyn": 3,
    "queens": 4,
    "staten island": 5,
}


def parse_year(value: str) -> int:
    if not value:
        return 0
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).year
        except ValueError:
            pass
    match = re.search(r"(20\d{2}|19\d{2})", value)
    return int(match.group(1)) if match else 0


def parse_zip(value: str) -> int:
    match = re.search(r"\d{5}", value or "")
    return int(match.group(0)) if match else 0


def parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def code(mapping: dict[str, int], value: str) -> int:
    return mapping.get((value or "").strip().lower(), 0)


def row_to_record(row: dict[str, str]) -> bytes:
    return struct.pack(
        RECORD_FMT,
        int(row.get("Unique Key") or 0),
        parse_float(row.get("Latitude")),
        parse_float(row.get("Longitude")),
        parse_zip(row.get("Incident Zip")),
        parse_year(row.get("Created Date")),
        code(STATUS, row.get("Status")),
        code(BOROUGH, row.get("Borough")),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--out-dir", default="shards")
    parser.add_argument("--limit", type=int, default=0,
                        help="maximum rows to shard; 0 means all rows")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    paths = {n: os.path.join(args.out_dir, f"shard_{n}.bin") for n in NODES}
    counts = {n: 0 for n in NODES}

    with open(args.csv_path, newline="", encoding="utf-8", errors="replace") as src:
        reader = csv.DictReader(src)
        files = {n: open(paths[n], "wb") for n in NODES}
        try:
            for idx, row in enumerate(reader):
                if args.limit and idx >= args.limit:
                    break
                node = NODES[idx % len(NODES)]
                files[node].write(row_to_record(row))
                counts[node] += 1
        finally:
            for f in files.values():
                f.close()

    total = sum(counts.values())
    print(f"Wrote {total} records ({total * RECORD_SIZE} bytes)")
    for node in NODES:
        print(f"  {node}: {counts[node]} records -> {paths[node]}")


if __name__ == "__main__":
    main()
