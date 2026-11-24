"""Extract bounded SanctuaryHillsWorld pre-war strip inputs, BTD terrain, objects.json, FO4SFHome host world, and pure sky checks."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fo4sf.planet import home_planet_spec as hspec  # noqa: E402
from fo4sf.prewar import s1_spec, sanctuary_strip  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fo4-esm", required=True, help="Path to Fallout4.esm")
    ap.add_argument("--out-dir", required=True, help="Staging root directory for Data/, objects.json, overlays_params.json")
    ap.add_argument("--world-edid", default="FO4SF_PrewarSanctuaryWorld")
    ap.add_argument("--rect", nargs=4, type=int, default=list(s1_spec.DEFAULT_STRIP_RECT), metavar=("GX0", "GX1", "GY0", "GY1"))
    ap.add_argument("--starfield-esm", help="Optional Starfield.esm to materialize FO4SFPrewar_Sanctuary.esm via TerrainOverlays")
    ap.add_argument("--host-esm-dir", help="Directory containing FO4SFHome.esm (default: same dir as --out-dir)")
    ap.add_argument("--run-overlays", action="store_true", help="Invoke dotnet/TerrainOverlays to build FO4SFPrewar_Sanctuary.esm")
    ap.add_argument("--emit-sky-esm", action="store_true", help="Also emit standalone 0-master FO4SFPrewarSky.esm")
    ap.add_argument("--report-json", help="Optional output path for summary JSON report")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    gx0, gx1, gy0, gy1 = args.rect
    report = sanctuary_strip.write_strip_stage_inputs(
        args.fo4_esm,
        args.out_dir,
        gx0=gx0,
        gx1=gx1,
        gy0=gy0,
        gy1=gy1,
        world_edid=args.world_edid,
        emit_standalone_sky=args.emit_sky_esm,
    )

    if args.run_overlays:
        if not args.starfield_esm:
            raise SystemExit("--run-overlays requires --starfield-esm")
        if args.host_esm_dir:
            src_home = os.path.join(args.host_esm_dir, hspec.HOME_MASTER)
            dst_home = os.path.join(args.out_dir, hspec.HOME_MASTER)
            if os.path.abspath(src_home) != os.path.abspath(dst_home):
                shutil.copyfile(src_home, dst_home)
        overlays_proj = os.path.join(ROOT, "dotnet", "TerrainOverlays", "TerrainOverlays.csproj")
        subprocess.run(
            ["dotnet", "run", "--project", overlays_proj, "-c", "Release", "--", args.starfield_esm, args.out_dir],
            cwd=ROOT,
            check=True,
        )
        world_esm = os.path.join(args.out_dir, s1_spec.PLUGIN_PREWAR_WORLD)
        home_bind = sanctuary_strip.bind_prewar_world_to_home(world_esm, world_edid=args.world_edid)
        report["world_esm"] = world_esm
        report["reg_esm"] = os.path.join(args.out_dir, "FO4SFPrewar_Sanctuary_Home.esm")
        report["home_sky_bind"] = home_bind

    if args.report_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.report_json)), exist_ok=True)
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    print(
        f"prewar strip staged in {args.out_dir}: cells={report['fo4_cells']} "
        f"tile={report['sf_tile_n']}x{report['sf_tile_n']} placed={report['placed_objects']} "
        f"btd={report['btd_bytes']}B sky={report.get('sky_plugin') or 'FO4SFHome'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
