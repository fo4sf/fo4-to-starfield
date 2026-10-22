"""Stage FO4SFMapMarkers.esm: the quest that puts the core's map markers into the merged world the player walks in
(docs/terrain/map-markers.md "Markers in the merged world").

usage:
  python scripts/mapmarkers/make_map_markers.py stage --core <FO4TerrainCore.esm> --out <NEW folder>
                                                     [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
      1. dotnet/MapMarkers build: the plugin (one start-game-enabled quest carrying FO4SF_MapMarkers, its Markers the
         core's MapMarker REFRs, LocalX / LocalY / LocalZ their positions as overridden below), plus an override of
         each of those REFRs: the marker's own name on the map (no UseLocationName flag) and the arrival lifted
         --z-lift metres (a multiple of 0.1; default the tool's 2.5) above the core's sampled terrain height;
      2. the Papyrus compile of FO4SF_MapMarkers.psc (base sources from the Creation Kit's ContentResources.zip, as
         scripts/bridge/make_bridge.py), the .pex into <out>/Data/Scripts;
      3. dotnet/MapMarkers check: the plugin read back against the core (offline_check.txt); core.json (the core's
         sha256, which the installer requires in Data); README.txt.
Install (game closed), with the core it was built from active (its own record, beside exp_install's experiment):
  python scripts/game/map_markers_install.py install --dir <out> --starfield <game>
The plugin names the core's references by FormID, so it is rebuilt with every core build.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "bridge"))
import make_bridge  # noqa: E402  (run, extract_sources, the default tool paths)

SCRIPT = "FO4SF_MapMarkers"
LOG = "<My Games>/Starfield/Logs/Script/User/fo4sf_map.0.log"


def compile_script(compiler, src_dir, out_dir):
    """PapyrusCompiler.exe on FO4SF_MapMarkers.psc by its bare name from this folder; returns the .pex path."""
    os.makedirs(out_dir, exist_ok=True)
    name = SCRIPT + ".psc"
    out = make_bridge.run([compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
                          cwd=HERE)
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    return pex


PLUGIN = "FO4SFMapMarkers.esm"   # the one name scripts/game/map_markers_install.py installs
PIN = "core.json"                # {"masters": {core file name: sha256}}: the core this plugin's FormIDs belong to


def stage(a):
    a.plugin = PLUGIN
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} is not empty: stage into a new folder")
    with open(a.core, "rb") as f:                        # the installer refuses any other core build
        core_sha256 = hashlib.sha256(f.read()).hexdigest()
    os.makedirs(out, exist_ok=True)
    tool = os.path.join(REPO, "dotnet", "MapMarkers")
    lift = [] if a.z_lift is None else ["--z-lift", repr(float(a.z_lift))]
    built = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "build", "--core", a.core,
                             "--out", out, "--plugin", a.plugin] + lift)
    src = make_bridge.extract_sources(a.content_resources, os.path.join(out, "work"))
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    check = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "check",
                             os.path.join(out, a.plugin), a.core] + lift)
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(built + check)
    with open(os.path.join(out, PIN), "w", encoding="utf-8") as f:
        json.dump({"masters": {os.path.basename(a.core): core_sha256}}, f, indent=1)
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Map markers into the merged world (Claude-cloud, {datetime.date.today().isoformat()}). docs/terrain/map-markers.md.
{a.plugin}: QUST FO4SF_MapMarkersQuest (0x800, start game enabled) carrying {SCRIPT}, built against
  {os.path.abspath(a.core)} (its MapMarker REFRs by FormID: rebuild with every core build), and an override of
  each of those REFRs: the marker's own name on the map, the arrival lifted {'the tool\'s default 2.5' if a.z_lift is None else a.z_lift} m.
  {PIN} pins that core's sha256: the installer refuses a Data folder holding any other build of it.
Data\\Scripts\\{SCRIPT}.pex: compiled from {SCRIPT}.psc here.
Install (game closed), with the core active (its own record, beside exp_install's experiment; packs the .pex):
  python scripts\\game\\map_markers_install.py install --dir "{out}" --starfield <game>
In game: outdoors in the Commonwealth the log {LOG} gets one line per marker moved:
  FO4SF_MAP rt=<s> moved <i> to <x> <y> <z> target <x> <y> <z> before=<distance> d=<distance> moves=<n>
Then open the map. Uninstall: map_markers_install.py uninstall --starfield <game>. Uninstall it before a core swap
  and install it again after (its only master, the core, leaves Plugins.txt during the swap).
""")
    print(f"staged {out}: {a.plugin}, {os.path.relpath(pex, out)}, {PIN}, offline_check.txt, README.txt")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the FO4TerrainCore.esm the plugin is installed with")
    s.add_argument("--out", required=True)
    s.add_argument("--compiler", default=os.path.join(make_bridge.STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(make_bridge.STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--z-lift", type=float, default=None,
                   help="metres the override lifts each marker above the core's height, a multiple of 0.1 (default: the tool's 2.5)")
    a = ap.parse_args(argv)
    stage(a)


if __name__ == "__main__":
    main()
