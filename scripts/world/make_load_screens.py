"""Build and verify `FO4SFLoadScreens.esm` (Option B default; zero Starfield.esm mutation)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fo4sf.world.load_screens import verify_load_screens_plugin, write_load_screens_plugin  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and check FO4SFLoadScreens.esm")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Generate FO4SFLoadScreens.esm against Starfield.esm")
    p_build.add_argument("--starfield", required=True, help="Path to Starfield.esm (read-only)")
    p_build.add_argument("--out", required=True, help="Output FO4SFLoadScreens.esm path")
    p_build.add_argument("--data-dir", default=None, help="Optional staging Data dir to write blank placeholder DDS")

    p_check = sub.add_parser("check", help="Verify FO4SFLoadScreens.esm overrides and conditions")
    p_check.add_argument("--starfield", required=True, help="Path to Starfield.esm (read-only)")
    p_check.add_argument("--plugin", required=True, help="Path to FO4SFLoadScreens.esm")

    args = parser.parse_args(argv)
    if args.cmd == "build":
        rep = write_load_screens_plugin(
            args.starfield,
            args.out,
            write_blank_icon_under_data=args.data_dir,
        )
        print(json.dumps(rep, indent=2))
        return 0
    rep = verify_load_screens_plugin(args.plugin, args.starfield)
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
