"""Stage the Concord four-option talk probe (FAL-865): empty plugin + four-slot movie + DialogueMenu twin.

usage: python scripts/dialogue/make_concord_talk.py stage <dir>
       python scripts/dialogue/make_concord_talk.py check <FO4SFConcordTalk.esm>
       python scripts/dialogue/make_concord_talk.py info-set

The plugin has no records. It exists so the session archive (FO4SFConcordTalk - Main.ba2) loads. The movie is
scripts/ui/make_dialogue_wheel_swf.py. stage always twins it at Interface/DialogueMenu.swf (REPLACE the host movie,
KEEP the DialogueMenu class). Starfield's own Interface archive is not touched. Nothing is written into the repo.
No Fallout 4 lines, no converted INFO records this slice.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
UI = os.path.join(REPO, "scripts", "ui")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, UI)
sys.path.insert(0, HERE)
from fo4sf.planet.esm import ESM, EsmError, Plugin, PluginWriter  # noqa: E402
import concord_info_set as info  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402
import make_probe_swf as swf  # noqa: E402

PLUGIN = "FO4SFConcordTalk.esm"
ARCHIVE = "FO4SFConcordTalk - Main.ba2"
MASTERS = ["Starfield.esm"]
MOVIE = "Interface/FO4SF_DialogueWheel.swf"
TWIN = info.REPLACE_MOVIE
AUTHOR = "FO4SF"
DESCRIPTION = "FAL-865 Concord four-option talk: empty; loads the DialogueMenu twin"


def plugin_bytes():
    return PluginWriter(MASTERS, flags=ESM, author=AUTHOR, description=DESCRIPTION).to_bytes()


def stage(out):
    """Writes the plugin, the wheel movie, and the DialogueMenu twin. Returns plugin, movie, twin paths."""
    os.makedirs(out, exist_ok=True)
    esm = os.path.join(out, PLUGIN)
    with open(esm, "wb") as f:
        f.write(plugin_bytes())
    movie = os.path.join(out, "Data", *MOVIE.split("/"))
    data = wheel.write_movie(movie)
    twin = os.path.join(out, "Data", *TWIN.split("/"))
    os.makedirs(os.path.dirname(twin), exist_ok=True)
    with open(twin, "wb") as f:
        f.write(data)
    return esm, movie, twin


def check(path):
    with Plugin(path) as p:
        if not p.flags & ESM:
            raise EsmError(f"{path}: the ESM flag is not set")
        if p.masters != MASTERS:
            raise EsmError(f"{path}: masters {p.masters}, expected {MASTERS}")
        if p.groups:
            raise EsmError(f"{path}: has groups {sorted(p.groups)}, the talk plugin is empty")
        return {"plugin": os.path.basename(path), "flags": p.flags, "masters": p.masters, "groups": 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("out")
    c = sub.add_parser("check")
    c.add_argument("plugin")
    sub.add_parser("info-set")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            esm, movie, twin = stage(a.out)
            check(esm)
            print(f"staged {esm}, {movie} and twin {twin}; pack into {ARCHIVE}")
        elif a.cmd == "check":
            print(f"ok: {check(a.plugin)}")
        else:
            print(json.dumps(info.check(info.info_set()), indent=2, sort_keys=True))
    except (EsmError, swf.SwfError, info.InfoSetError, OSError) as e:
        print(f"make_concord_talk: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
