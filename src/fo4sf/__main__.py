"""fo4sf CLI entry point.

python -m fo4sf status   # report config and basic coverage
"""
import argparse
import sys

from .config import load_config, status_summary


def cmd_status(args):
    cfg = load_config(args.config)
    print("fo4sf status")
    print(status_summary(cfg))
    # Placeholder coverage until a real manifest exists
    print("manifest: none (run a conversion to create one)")
    print("coverage: T0 placeholders only (no assets converted in this environment)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 to Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: config.toml or $FO4SF_CONFIG)")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("status", help="print config summary and coverage")
    st.set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
