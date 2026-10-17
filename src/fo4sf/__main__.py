"""fo4sf CLI entry point.

python -m fo4sf status   # report config paths, versions, and basic existence checks
"""
import argparse
import sys

from .config import load_config, status_summary, ConfigError


def cmd_status(args):
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("fo4sf status")
    print(status_summary(cfg))
    # Placeholder coverage until a real manifest exists
    print("manifest: none (run a conversion to create one)")
    print("coverage: T0 placeholders only (no assets converted in this environment)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 to Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: config.toml or $FO4SF_CONFIG)")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("status", help="print config summary and coverage")
    st.set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
