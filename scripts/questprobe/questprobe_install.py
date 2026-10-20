"""Install / uninstall the quest-engine probe (docs/questprobe/engine-questions.md) next to the converted build.

Starfield on the test PC reads no loose files (sResourceDataDirsFinal=STRINGS\\ only, install thread 19 Oct), so the
probe's three scripts ship in "FO4SFQuestProbe - Main.ba2", packed from the staged Data tree at install time, and
exp_install.py keeps one experiment record, so the probe is its own small deployment. Both are what bridge_install.py
already does for the bridge: this reuses its record, packing, archive check, Plugins.txt journal and exact uninstall
under the probe's names (its messages still say "bridge"). The probe's record is Data\\FO4SFQuestProbe.install.json.

usage: python questprobe_install.py install|uninstall|status|order --dir <staged probe dir> --starfield <game dir>
       python questprobe_install.py pack-check --dir <staged probe dir> --starfield <game dir>
           builds the archive into a temporary folder with the game's Archive2 and checks its contents against the
           staged Data tree; touches nothing in the game. Run it before the owner's line, offline.
install refuses a staged folder whose plugin or scripts differ from its plan.json (make_questprobe.py stage).
Nothing runs on its own: install is the owner's line ("Install the quest probe plugin."), with the game closed.
"""
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "game"))
sys.path.insert(0, os.path.join(HERE, "..", "newgame"))
import bridge_install  # noqa: E402
import exp_install  # noqa: E402
from make_newgame import sha256  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from fo4sf.ba2 import Ba2  # noqa: E402

NAMES = {
    "RECORD": "FO4SFQuestProbe.install.json",
    "PLUGIN": "FO4SFQuestProbe.esm",
    "ARCHIVE": "FO4SFQuestProbe - Main.ba2",
    "PEX": os.path.join("Data", "Scripts", "FO4SF_QProbeQuest.pex"),
}


def configure():
    """Point bridge_install's module names at the probe (its functions read them at call time)."""
    for k, v in NAMES.items():
        setattr(bridge_install, k, v)


def check_plan(directory):
    """The staged folder is the one make_questprobe.py published: plan.json's kind, plugin and every script hash."""
    path = os.path.join(directory, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_questprobe.py first")
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != "questprobe" or plan.get("plugin") != NAMES["PLUGIN"]:
        sys.exit(f"{path} is not a quest-probe plan")
    wanted = {plan["plugin"]: plan["plugin_sha256"]}
    wanted.update({os.path.join("Data", "Scripts", s + ".pex"): h for s, h in plan["scripts"].items()})
    for rel, h in wanted.items():
        p = os.path.join(directory, rel)
        if not os.path.isfile(p) or sha256(p) != h:
            sys.exit(f"{p} is not the staged file (plan.json {h}); re-stage, do not install")
    extra = sorted(os.path.relpath(os.path.join(r, n), directory) for r, _, ns in os.walk(os.path.join(directory, "Data"))
                   for n in ns if os.path.relpath(os.path.join(r, n), directory) not in wanted)
    if extra:
        sys.exit(f"files in the staged Data tree that plan.json does not name (they would be packed): {extra}")
    return plan


def pack_check(a):
    d = os.path.abspath(a.dir)
    plan = check_plan(d)
    source = bridge_install.source_inventory(d)
    with tempfile.TemporaryDirectory(prefix="fo4sf-qprobe-pack-") as tmp:
        ba2 = exp_install.build_ba2(SimpleNamespace(starfield=a.starfield), os.path.join(d, "Data"),
                                    os.path.join(tmp, NAMES["ARCHIVE"]))
        exp_install.verify_archive(ba2, bridge_install.archive_inputs(source))
        size, digest = os.path.getsize(ba2), exp_install.digest(ba2)
        # the names as stored in the archive, relative to the game's Data folder (verify_archive already required them
        # to be exactly the staged Data tree minus its "Data/" prefix; job 12 printed the staged paths, which misled)
        entries = sorted(e.name.replace("\\", "/") for e in Ba2(ba2).entries)
    print(f"pack-check ok: \"{NAMES['ARCHIVE']}\" {size:,} bytes sha256 {digest}, {len(entries)} archive entries "
          f"(relative to Data): " + ", ".join(entries) + f"; {len(plan['scripts'])} script(s) in plan.json")
    return 0


def main(argv=None):
    configure()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["pack-check"]:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd")
        ap.add_argument("--dir", required=True)
        ap.add_argument("--starfield", required=True)
        return pack_check(ap.parse_args(argv))
    if argv[:1] == ["install"]:
        # parse --dir the way argparse does (--dir X, --dir=X, an unambiguous prefix), so no spelling skips the plan
        # check (20 Oct review on #393: "--dir=X" did)
        import argparse
        ap = argparse.ArgumentParser(add_help=False)
        ap.add_argument("--dir")
        known, _ = ap.parse_known_args(argv[1:])
        if not known.dir:
            sys.exit("install needs --dir <staged probe dir> (its plan.json is checked first)")
        check_plan(os.path.abspath(known.dir))
    bridge_install.main(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
