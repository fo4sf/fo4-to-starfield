"""Install / uninstall the map markers plugin next to the converted build (docs/terrain/map-markers.md).

The same deployment as the observation bridge (bridge_install.py, whose functions this module reuses with its own
names): FO4SFMapMarkers.esm and "FO4SFMapMarkers - Main.ba2" (the compiled FO4SF_MapMarkers.pex, packed: loose
scripts are not read on this install) go into the game's Data folder, "*FO4SFMapMarkers.esm" goes to the end of
Plugins.txt, and Data\\FO4SFMapMarkers.install.json records what was added. It is independent of exp_install.py's one
experiment record, so it rides along with the installed core set. install refuses unless every master of the staged
plugin (the core, FO4TerrainCore.esm) is an active Plugins.txt line and a readable plugin in Data with the sha256 the
stage pinned (core.json; the receipt keeps a copy); order refuses the same way before it moves or reactivates the line. order moves its line to the end; cycle.ps1 runs it
before the bridge's order (and active after the save loads, as exp_install's), so the planned reads' load indexes (the experiment's, FO4Port's) stay as they were.
Uninstall it before a core swap (exp_install uninstall + install): its only master leaves Plugins.txt meanwhile, and
exp_install refuses missing masters. Install it again after the swap.

usage: python map_markers_install.py install|uninstall|status|order|active --dir <staged dir> --starfield <game dir>
       (the staged dir: scripts/mapmarkers/make_map_markers.py stage, e.g. D:\\Modding\\staging\\mapmarkers_v6e_wfc10)
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_install  # noqa: E402

# A private copy of bridge_install: its functions read these module globals, and the bridge's own module keeps its own.
_spec = importlib.util.spec_from_file_location("_fo4sf_map_markers_kit", os.path.join(HERE, "bridge_install.py"))
kit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kit)
kit.RECORD = RECORD = "FO4SFMapMarkers.install.json"
kit.PLUGIN = PLUGIN = "FO4SFMapMarkers.esm"
kit.ARCHIVE = ARCHIVE = "FO4SFMapMarkers - Main.ba2"
kit.PEX = PEX = os.path.join("Data", "Scripts", "FO4SF_MapMarkers.pex")
kit.KIT = "map markers plugin"
kit.STAGE_HINT = "scripts/mapmarkers/make_map_markers.py stage"
PIN = "core.json"     # make_map_markers.py stage: {"masters": {core file name: sha256}}
PIN_KEY = "masters_sha256"   # the same pins, copied into this install's receipt


def read_pin(directory):
    """{master name casefolded: sha256} from a staged folder's core.json; exits when it is missing or malformed (a
    stage made before the pin: stage it again)."""
    p = os.path.join(directory, PIN)
    try:
        with open(p, encoding="utf-8") as f:
            masters = json.load(f)["masters"]
        return {str(k).casefold(): str(v).lower() for k, v in masters.items()}
    except (OSError, ValueError, KeyError, AttributeError) as error:
        sys.exit(f"map markers plugin: no core pin in {p} ({error}); stage it again with make_map_markers.py")


def require_masters(plugin, data, action, pins):
    """Every master of `plugin` is an active Plugins.txt line (or one the game loads by itself) AND a readable plugin
    in this Data folder whose sha256 is the pinned build (the plugin names that core's records by FormID: another build
    under the same name would bind its quests to other records), and no main-build recovery is pending. Exits before
    anything is written."""
    try:
        exp_install.require_complete_master(data)
        masters = exp_install.plugin_masters(plugin)
    except (OSError, ValueError) as error:
        sys.exit(f"map markers plugin not {action}: {error}")
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    for m in masters:
        if exp_install.implicit(m):
            continue
        if kit.plugin_line_present(lines, m) is None:
            sys.exit(f"map markers plugin not {action}: its master {m} is not active in Plugins.txt "
                     "(install the core set first)")
        try:
            path = exp_install.data_path(data, m)
            exp_install.plugin_masters(path)
            got = exp_install.digest(path)
        except (OSError, ValueError) as error:
            sys.exit(f"map markers plugin not {action}: its master {m} is not a readable plugin in Data ({error})")
        want = pins.get(m.casefold())
        if want != got:
            sys.exit(f"map markers plugin not {action}: Data\\{m} is not the core it was staged against "
                     f"(sha256 {got[:12]}..., pinned {(want or 'none')[:12]}...): stage it again against this core")


def pin_receipt(rec_p, pins):
    """Copy the stage's pins into the receipt, so order checks the core even after the staged folder is gone."""
    rec = kit.read_record(rec_p)
    if rec.get(PIN_KEY) != pins:
        rec[PIN_KEY] = pins
        kit.deployment.write_manifest(rec_p, rec)


def receipt_pins(rec_p):
    """The receipt's pins, else the recorded staged folder's (an install interrupted before pin_receipt)."""
    rec = kit.read_record(rec_p)
    if isinstance(rec.get(PIN_KEY), dict):
        return rec[PIN_KEY]
    return read_pin(rec.get("dir") or "")


def active(a):
    """Read-only, after the save has loaded (cycle.ps1): exit 1 unless the installed plugin's line is still active.
    Loading a save can make Starfield restore the save's own load order, after order ran."""
    data, rec_p = kit.record_path(a)
    if not os.path.exists(rec_p):
        print(f"{PLUGIN} not installed")
        return
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    if kit.plugin_line_present(lines, PLUGIN) is None:
        sys.exit(f"{PLUGIN} is installed but not active in Plugins.txt (the save's load order replaced it?)")
    print(f"{PLUGIN} active")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged map markers folder (install)")
    ap.add_argument("--starfield", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir")
        d, plugin, _pex = kit.staged(a)
        pins = read_pin(d)
        data, rec_p = kit.record_path(a)
        require_masters(plugin, data, "installed", pins)
        kit.install(a)
        pin_receipt(rec_p, pins)
    elif a.cmd == "uninstall":
        kit.uninstall(a)
    elif a.cmd == "order":
        data, rec_p = kit.record_path(a)
        if os.path.exists(rec_p):                         # never reactivate or move the line while a master is held
            require_masters(os.path.join(data, PLUGIN), data, "ordered", receipt_pins(rec_p))
        kit.order(a)
    elif a.cmd == "active":
        active(a)
    else:
        kit.status(a)


if __name__ == "__main__":
    main()
