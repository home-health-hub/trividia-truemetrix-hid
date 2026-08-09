#!/usr/bin/env python3
"""Standalone command-line client for Trividia Health TRUE METRIX meters."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import logging
import sys

from ._version import __version__
from .client import TrueMetrixClient, TrueMetrixError, discover

_LOGGER = logging.getLogger("trividia_truemetrix_hid")


def _print_json(obj) -> None:
    data = dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj
    print(json.dumps(data, indent=2, default=str))


def _run_discover() -> None:
    devices = discover()
    if not devices:
        print("No TRUE METRIX meters found.", file=sys.stderr)
        return
    for entry in devices:
        product = entry.get("product_string") or "(unknown)"
        path = entry["path"]
        path_str = path.decode(errors="replace") if isinstance(path, bytes) else str(path)
        vid, pid = entry["vendor_id"], entry["product_id"]
        print(f"{path_str}  {product}  vid=0x{vid:04x} pid=0x{pid:04x}")


def _write_csv(readings, out_path: str) -> None:
    with open(out_path, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["Time", "Glucose(mg/dL)", "Out of Range", "Control Solution"])
        for reading in readings:
            writer.writerow(
                [
                    reading.device_time.isoformat(),
                    reading.value_mg_dl,
                    reading.out_of_range or "",
                    reading.is_control_solution,
                ]
            )


def _run(args: argparse.Namespace) -> None:
    path = args.path.encode() if args.path else None
    with TrueMetrixClient(path=path) as client:
        info = client.get_device_info()
        if args.info:
            _print_json(info)
            return

        readings = client.get_readings(include_control_solution=args.include_control_solution)
        if args.csv:
            _write_csv(readings, args.csv)
            print(f"Wrote {len(readings)} readings to {args.csv}", file=sys.stderr)
        else:
            _print_json({"device": dataclasses.asdict(info), "readings": [
                dataclasses.asdict(r) for r in readings
            ]})


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-d", "--discover", action="store_true", help="list connected meters and exit"
    )
    parser.add_argument(
        "-p", "--path", help="HID device path to use (from --discover); default: first found"
    )
    parser.add_argument(
        "-i", "--info", action="store_true",
        help="print device info (model/serial/firmware) and exit",
    )
    parser.add_argument("-c", "--csv", metavar="PATH", help="write readings to a CSV file")
    parser.add_argument(
        "-C", "--include-control-solution", action="store_true",
        help="include control-solution test records, excluded by default",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the trividia-truemetrix console script."""
    args = _parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.discover:
        _run_discover()
        return

    try:
        _run(args)
    except TrueMetrixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
