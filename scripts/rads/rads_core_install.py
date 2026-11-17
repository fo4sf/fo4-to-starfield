"""Install / uninstall / status / order / active for a staged FO4SFRads.esm package (docs/rads/rads-core.md).

usage:
  python scripts/rads/rads_core_install.py install --dir <stage dir> --starfield <game dir> [--prepacked <ba2>]
  python scripts/rads/rads_core_install.py uninstall|status|order|active --starfield <game dir>

Uses its own install record (Data/FO4SFRads.install.json) so any installed core experiment (FO4SFExp.install.json)
or probe kit is untouched. Game closed for install and uninstall.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_rads_core  # noqa: E402

RECORD = "FO4SFRads.install.json"


def installer(argv):
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def prepacked_supported():
    with open(exp_install.__file__, encoding="utf-8") as f:
        return "--prepacked" in f.read()


def install(a):
    if getattr(a, "prepacked", "") and not prepacked_supported():
        sys.exit("--prepacked is not supported by this exp_install.py; nothing installed.")
    d = os.path.abspath(a.dir)
    plan = make_rads_core.load_plan(d)
    problems = make_rads_core.verify_stage(d, plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("rads core not installed: stage does not match plan.json or Data (re-stage): " + "; ".join(problems))
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != names:
        sys.exit(f"rads core not installed: stage holds {names}, plan.json lists {plan['plugins']}")
    return installer(
        ["install", "--exp-dir", d, "--starfield", a.starfield, "--pack", "--plugins", ",".join(plan["plugins"])]
        + (["--prepacked", a.prepacked] if getattr(a, "prepacked", "") else [])
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="staged rads-core folder (install)")
    ap.add_argument("--prepacked", default="", help="verify and install an existing archive without rebuilding")
    ap.add_argument("--starfield", required=True, help="Starfield game root directory")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
