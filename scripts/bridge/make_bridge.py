"""Stage the observation bridge experiment (docs/ai/test-queue.md "Bridge"; the owner's decision D1 of 2026-10-14).

The bridge replaces the runner's screenshot-and-OCR position reads with a file the game writes itself: the Papyrus
quest script FO4SF_Bridge (FO4SF_Bridge.psc here) logs the player's position, heading, cell and worldspace twice a
second to <My Games>/Starfield/Logs/Script/User/fo4sf.0.log and echoes the global FO4SF_Cmd when the console sets it.
scripts/game/bridge_log.py reads that file.

usage:
  python make_bridge.py stage --out <experiment dir> [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
                              [--plugin FO4SFBridge.esm] [--interval 0.5]
      1. dotnet/Bridge build: the plugin (a global and a start-game-enabled quest carrying the script);
      2. the Papyrus compile: the base scripts the script imports come out of the Creation Kit's ContentResources.zip
         (Scripts/Source/*.psc and Starfield_Papyrus_Flags.flg) into <out>/work, the .pex goes to <out>/Data/Scripts
         (loose scripts are not read on this install: exp_install.py --pack puts Data into "<plugin> - Main.ba2");
      3. dotnet/Bridge check: the plugin read back (offline_check.txt); README.txt and plan.json.
  python make_bridge.py ini [--my-games <dir>] [--dry-run]
      StarfieldCustom.ini gets the [Papyrus] logging keys the user log needs (bEnableLogging, bEnableTrace,
      bLoadDebugInformation = 1); other sections and keys stay; the previous file is kept as a .bak copy. Run before
      the launch of the go/no-go (it is the owner's game configuration: only in a window the owner declared).
Install (the runner, game closed):
  python scripts/game/exp_install.py install --exp-dir <out> --starfield <game> --plugins FO4SFBridge.esm --pack
Go/no-go in game: launch, load any save, wait 5 s: `python scripts/game/bridge_log.py latest` prints a line with
pos=...; type `set FO4SF_Cmd to 7` in the console: `bridge_log.py wait-cmd 7` returns within a second.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
PAPYRUS_KEYS = (("bEnableLogging", "1"), ("bEnableTrace", "1"), ("bLoadDebugInformation", "1"))
IMPORTS = ("Actor", "Cell", "Debug", "Form", "Game", "GlobalVariable", "Location", "ObjectReference", "Quest",
           "ScriptObject", "Utility", "WorldSpace")


def run(cmd, cwd=None):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        sys.exit(f"{cmd[0]} exit {r.returncode}")
    return r.stdout


def extract_sources(zip_path, work):
    """The base .psc files the bridge script imports, and the flags file, from ContentResources.zip into work/Source."""
    want = {f"Scripts/Source/{n}.psc" for n in IMPORTS} | {"Scripts/Source/Starfield_Papyrus_Flags.flg"}
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    got = set()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name in want:
                with z.open(name) as f, open(os.path.join(src, os.path.basename(name)), "wb") as o:
                    shutil.copyfileobj(f, o)
                got.add(name)
    missing = sorted(want - got)
    if missing:
        sys.exit(f"ContentResources.zip lacks {missing}")
    return src


def compile_script(compiler, src_dir, out_dir):
    """PapyrusCompiler.exe on every .psc of this folder (FO4SF_Bridge, the quest script; FO4SF_Probe, the console's
    cgf functions), each invoked by its bare name from this folder (the compiler compares the file name with the
    Scriptname and rejects a path); the .pex files land in out_dir. Returns the quest script's .pex."""
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(f for f in os.listdir(HERE) if f.lower().endswith(".psc")):
        cmd = [compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"]
        out = run(cmd, cwd=HERE)
        if "Compilation succeeded" not in out or not os.path.exists(os.path.join(out_dir, name[:-4] + ".pex")):
            sys.exit(f"the Papyrus compile did not produce {name[:-4]}.pex")
    return os.path.join(out_dir, "FO4SF_Bridge.pex")


def stage(a):
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = os.path.join(out, "work")
    bridge = os.path.join(REPO, "dotnet", "Bridge")
    run(["dotnet", "run", "-c", "Release", "--project", bridge, "--", "build", "--out", out, "--plugin", a.plugin,
         "--interval", str(a.interval)])
    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    check = run(["dotnet", "run", "-c", "Release", "--project", bridge, "--", "check", os.path.join(out, a.plugin)])
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    shutil.copy(os.path.join(HERE, "FO4SF_Bridge.psc"), os.path.join(out, "FO4SF_Bridge.psc"))
    plan = {"kind": "bridge", "plugin": a.plugin, "interval_s": a.interval, "script": "FO4SF_Bridge",
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf.0.log",
            "ini": {"section": "Papyrus", "keys": dict(PAPYRUS_KEYS)},
            "go_no_go": ["launch and load any save", "bridge_log.py latest: ok with pos", "console: set FO4SF_Cmd to 7",
                         "bridge_log.py wait-cmd 7: within 1 s", "walk 2 s with W: wait-move 0.5"]}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Observation bridge experiment (Claude, {datetime.date.today().isoformat()}). docs/ai/test-queue.md "Bridge".
{a.plugin}: GLOB FO4SF_Cmd (0x800) + QUST FO4SF_BridgeQuest (0x801, start game enabled) carrying FO4SF_Bridge.
Data\\Scripts\\FO4SF_Bridge.pex: compiled from FO4SF_Bridge.psc (this folder) with the game's PapyrusCompiler.
Install (game closed): python scripts\\game\\exp_install.py install --exp-dir "{out}" --starfield <game> --plugins {a.plugin} --pack
Before launch, once: python scripts\\bridge\\make_bridge.py ini   (StarfieldCustom.ini [Papyrus] logging keys)
In game: the user log {plan['log']} gets one line every {a.interval} s:
  FO4SF rt=<s> pos=<x> <y> <z> ang=<deg> cell=<decimal form id> world=<decimal form id> loaded=True|False [cmd=<n>] n=<count>
Read it: python scripts\\game\\bridge_log.py latest | wait-cmd 7 | wait-move
Uninstall: exp_install.py uninstall.
""")
    print(f"staged {out}: {a.plugin}, {os.path.relpath(pex, out)}, offline_check.txt, plan.json, README.txt")


def ensure_ini(text):
    """StarfieldCustom.ini text with the [Papyrus] logging keys set (added or updated in place); other content kept.
    Returns (new_text, changed)."""
    lines = text.splitlines()
    out, changed, in_section, seen, found = [], False, False, set(), False
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_section:                                   # leaving [Papyrus]: add the keys it lacked
                for k, v in PAPYRUS_KEYS:
                    if k.lower() not in seen:
                        out.append(f"{k}={v}")
                        changed = True
            in_section = s.lower() == "[papyrus]"
            found = found or in_section
            out.append(line)
            continue
        if in_section:
            m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m:
                k = m.group(1)
                for want, v in PAPYRUS_KEYS:
                    if k.lower() == want.lower():
                        seen.add(want.lower())
                        if m.group(2) != v:
                            out.append(f"{want}={v}")
                            changed = True
                        else:
                            out.append(line)
                        break
                else:
                    out.append(line)
                continue
        out.append(line)
    if in_section:
        for k, v in PAPYRUS_KEYS:
            if k.lower() not in seen:
                out.append(f"{k}={v}")
                changed = True
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append("[Papyrus]")
        out.extend(f"{k}={v}" for k, v in PAPYRUS_KEYS)
        changed = True
    return "\n".join(out) + "\n", changed


def my_games():
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "OneDrive", "Documents"), os.path.join(home, "Documents")):
        p = os.path.join(base, "My Games", "Starfield")
        if os.path.isdir(p):
            return p
    sys.exit("no My Games\\Starfield folder found")


def write_ini(path, dry_run):
    """The [Papyrus] keys into the ini at path (created when missing; the previous file kept as .bak-<time>).
    Returns True when the file was (or would be) changed; raises OSError when the folder refuses the write."""
    old = open(path, encoding="utf-8-sig").read() if os.path.exists(path) else ""
    new, changed = ensure_ini(old)
    if not changed:
        print(f"{path}: [Papyrus] logging keys already set")
        return False
    if dry_run:
        print(f"{path} would become:\n{new}")
        return True
    if os.path.exists(path):
        bak = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, bak)
        print(f"kept {bak}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"wrote {path}: [Papyrus] " + " ".join(f"{k}={v}" for k, v in PAPYRUS_KEYS))
    return True


def ini(a):
    """StarfieldCustom.ini in My Games first; when that folder refuses the write (2026-10-14: Windows Controlled Folder
    Access blocks python.exe in Documents and reports it as "file not found", Defender event 1123), the game folder's
    own Starfield.ini takes the keys instead (--game-dir; the game reads it before the My Games overrides)."""
    folder = a.my_games or my_games()
    custom = os.path.join(folder, "StarfieldCustom.ini")
    try:
        write_ini(custom, a.dry_run)
        return
    except OSError as e:
        print(f"{custom}: cannot write ({e.strerror or e}); Windows Controlled Folder Access blocks our scripts in "
              f"Documents (allow python.exe there, or create the file by hand). Falling back to the game folder's Starfield.ini")
    game_ini = os.path.join(a.game_dir, "Starfield.ini")
    if not os.path.exists(game_ini):
        sys.exit(f"no {game_ini} either")
    write_ini(game_ini, a.dry_run)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--plugin", default="FO4SFBridge.esm")
    s.add_argument("--interval", type=float, default=0.5)
    i = sub.add_parser("ini")
    i.add_argument("--my-games", default="")
    i.add_argument("--game-dir", default=STARFIELD, help="the fallback ini's folder when My Games refuses the write")
    i.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "stage":
        stage(a)
    else:
        ini(a)


if __name__ == "__main__":
    main()
