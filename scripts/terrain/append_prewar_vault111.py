"""Losslessly append PrewarVault111 S1 cell (>= 0x00EFAB) onto a Slot 1 FO4Port.esm without touching Museum/<=0x00EFAA IDs."""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fo4sf.prewar import s1_spec, vault111_append


def parse_hex_or_int(val: str) -> int:
    return int(val, 0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-esm", required=True, help="Slot 1 base FO4Port.esm (read-only)")
    ap.add_argument("--out-esm", required=True, help="Destination extended FO4Port.esm")
    ap.add_argument("--fo4-esm", help="Optional Fallout4.esm to extract PrewarVault111 NAVMs & persistent markers")
    ap.add_argument(
        "--start-id",
        type=parse_hex_or_int,
        default=s1_spec.MIN_PREWAR_PORT_START_ID,
        help=f"Slot 2 starting local FormID (default 0x{s1_spec.MIN_PREWAR_PORT_START_ID:06X})",
    )
    ap.add_argument("--source-shell", default="FO4Port_PrewarVault111")
    ap.add_argument("--new-cell", default="FO4Port_PrewarVault111S1")
    ap.add_argument("--report-json", help="Optional path for append verification JSON")
    args = ap.parse_args(argv)

    with open(args.base_esm, "rb") as f:
        base_bytes = f.read()

    navms = []
    pers_specs = []
    if args.fo4_esm:
        src = vault111_append.extract_prewar_v111_source(args.fo4_esm)
        navms = src["navms"]
        pers_specs = src["pers_refs"]

    out_bytes, report = vault111_append.append_prewar_vault111_lossless(
        base_bytes,
        start_id=args.start_id,
        fo4_navms=navms,
        extra_persistent_specs=pers_specs,
        source_shell_edid=args.source_shell,
        new_cell_edid=args.new_cell,
    )
    ver = vault111_append.verify_lossless_append(
        base_bytes,
        out_bytes,
        int(report["start_id"], 16),
        allow_navi_update=bool(navms),
    )
    report.update(ver)

    os.makedirs(os.path.dirname(os.path.abspath(args.out_esm)), exist_ok=True)
    with open(args.out_esm, "wb") as f:
        f.write(out_bytes)

    if args.report_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.report_json)), exist_ok=True)
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    print(
        f"wrote {args.out_esm}: preserved={report['preserved_records']} "
        f"appended={report['appended_records']} cell={report['new_cell_edid']} "
        f"({report['new_cell_fid']}) next={report['next_object_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
