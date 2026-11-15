"""Install / uninstall of the staged Concord four-option talk (scripts/dialogue/make_concord_talk.py).

usage: python scripts/dialogue/concord_talk_install.py install --dir <stage> --starfield <game dir>
       python scripts/dialogue/concord_talk_install.py uninstall|status|order|active --starfield <game dir>

Own record Data/FO4SFConcordTalk.install.json. install checks: one empty plugin FO4SFConcordTalk.esm.
A staged Interface/DialogueMenu.swf is a refuse. At install the player's host movie is copied from their
archives and four slots are overlaid on Menu_mc (PC). --host-swf is tests only. Game closed. Nothing of
the game enters the repo.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "ui"))
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
import exp_install  # noqa: E402
import dialogue_menu_overlay as overlay  # noqa: E402
import make_concord_talk as mct  # noqa: E402

RECORD = "FO4SFConcordTalk.install.json"


def installer(argv):
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def stage_problems(d):
    problems = []
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if names != [mct.PLUGIN]:
        problems.append(f"the stage holds plugins {names}, expected [{mct.PLUGIN!r}]")
    else:
        try:
            mct.check(os.path.join(d, mct.PLUGIN))
        except mct.EsmError as e:
            problems.append(str(e))
    data = os.path.join(d, "Data")
    found = sorted(os.path.relpath(os.path.join(r, f), data).replace(os.sep, "/")
                   for r, _, fs in os.walk(data) for f in fs) if os.path.isdir(data) else []
    if mct.HOST_MOVIE in found:
        problems.append(f"replace host movie is killed: Data holds {mct.HOST_MOVIE}")
    allowed = {mct.MOVIE, }
    extra = [p for p in found if p not in allowed]
    if extra:
        problems.append(f"Data holds extra {extra}")
    return problems


def install(a):
    d = os.path.abspath(a.dir)
    problems = stage_problems(d)
    if problems:
        print("concord talk not installed (re-stage with make_concord_talk.py stage): " + "; ".join(problems),
              file=sys.stderr)
        sys.exit(1)
    host_swf = getattr(a, "host_swf", "") or ""
    try:
        if host_swf:
            with open(host_swf, "rb") as f:
                host_bytes = f.read()
        else:
            host_bytes = overlay.extract_host_movie(a.starfield)
        killed = overlay.refuse_own_replacement(host_bytes)
        if killed:
            print(f"concord talk not installed: {killed}", file=sys.stderr)
            sys.exit(1)
        patched = overlay.overlay_inject(host_bytes)
    except overlay.OverlayError as e:
        print(f"concord talk not installed: {e}", file=sys.stderr)
        sys.exit(1)
    dest = os.path.join(d, "Data", *mct.HOST_MOVIE.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(patched)
    wheel = os.path.join(d, "Data", *mct.MOVIE.split("/"))
    if os.path.isfile(wheel):
        os.remove(wheel)
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack",
                      "--plugins", mct.PLUGIN] +
                     (["--prepacked", a.prepacked] if getattr(a, "prepacked", "") else []))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged folder (install)")
    ap.add_argument("--prepacked", default="", help="verify and install this existing archive; never build")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    ap.add_argument("--host-swf", default="", help="tests only: a host-shaped movie instead of the player's archive")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
