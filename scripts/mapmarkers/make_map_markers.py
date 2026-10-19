"""Stage FO4SFMapMarkers.esm: the quest that puts the core's map markers into the merged world the player walks in
(docs/terrain/map-markers.md "Markers in the merged world").

usage:
  python scripts/mapmarkers/make_map_markers.py stage --core <FO4TerrainCore.esm> --out <NEW folder>
                                                     [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
      1. dotnet/MapMarkers build: the plugin (one start-game-enabled quest carrying FO4SF_MapMarkers, its Markers the
         core's MapMarker REFRs, LocalX / LocalY / LocalZ their written positions);
      2. the Papyrus compile of FO4SF_MapMarkers.psc (base sources from the Creation Kit's ContentResources.zip, as
         scripts/bridge/make_bridge.py), the .pex into <out>/Data/Scripts;
      3. dotnet/MapMarkers check: the plugin read back against the core (offline_check.txt); README.txt.
Install (game closed), with the core it was built from active (its own record, beside exp_install's experiment):
  python scripts/game/map_markers_install.py install --dir <out> --starfield <game>
The plugin names the core's references by FormID, so it is rebuilt with every core build.
"""
import argparse
import datetime
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


def stage(a):
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} is not empty: stage into a new folder")
    os.makedirs(out, exist_ok=True)
    tool = os.path.join(REPO, "dotnet", "MapMarkers")
    built = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "build", "--core", a.core,
                             "--out", out, "--plugin", a.plugin])
    src = make_bridge.extract_sources(a.content_resources, os.path.join(out, "work"))
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    check = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "check",
                             os.path.join(out, a.plugin), a.core])
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(built + check)
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Map markers into the merged world (Claude-cloud, {datetime.date.today().isoformat()}). docs/terrain/map-markers.md.
{a.plugin}: QUST FO4SF_MapMarkersQuest (0x800, start game enabled) carrying {SCRIPT}, built against
  {os.path.abspath(a.core)} (its MapMarker REFRs by FormID: rebuild with every core build).
Data\\Scripts\\{SCRIPT}.pex: compiled from {SCRIPT}.psc here.
Install (game closed), with the core active (its own record, beside exp_install's experiment; packs the .pex):
  python scripts\\game\\map_markers_install.py install --dir "{out}" --starfield <game>
In game: outdoors in the Commonwealth the log {LOG} gets one line per marker moved:
  FO4SF_MAP rt=<s> moved <i> to <x> <y> <z> target <x> <y> <z> before=<distance> d=<distance> moves=<n>
Then open the map. Uninstall: map_markers_install.py uninstall --starfield <game>. After a core swap, run
  map_markers_install.py order --starfield <game> so the plugin loads after the core again.
""")
    print(f"staged {out}: {a.plugin}, {os.path.relpath(pex, out)}, offline_check.txt, README.txt")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the FO4TerrainCore.esm the plugin is installed with")
    s.add_argument("--out", required=True)
    s.add_argument("--compiler", default=os.path.join(make_bridge.STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(make_bridge.STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--plugin", default="FO4SFMapMarkers.esm")
    a = ap.parse_args(argv)
    stage(a)


if __name__ == "__main__":
    main()
