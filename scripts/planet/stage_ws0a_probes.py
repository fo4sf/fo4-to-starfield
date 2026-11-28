"""Stage offline WS0a Tier 1/2/3 probes (FO4SFWorkshopProbe.esm, FO4SFWorkshopProbe_P6.esm, FO4SFBuildPieces.esm + .pex).

Probe records live strictly in test-kit plugins; zero probe records are written to player-bundle plugins.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))

from make_newgame import extract_sources, new_partial, run  # noqa: E402
import make_build_pieces as mbp  # noqa: E402
import make_workshop_probe as wp  # noqa: E402

WS0A_SCRIPT = "FO4SF_WS0aProbeQuest"
WS0A_PSC = os.path.join(HERE, WS0A_SCRIPT + ".psc")
PROBE_PROJECT = os.path.join(REPO, "dotnet", "WorkshopProbe")
BP_PROJECT = os.path.join(REPO, "dotnet", "BuildPieces")

TIERS = {
    "tier1": ["b1", "b2", "P15", "P18", "P12", "P13", "P14a", "P14b"],
    "tier2": ["P3", "P4", "P9", "P16", "P17", "P6", "P8a", "P8b"],
    "tier3": ["P11", "P5", "P10", "P19", "P1"],
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage(a: argparse.Namespace) -> int:
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder")
    for req in (a.starfield, a.core, a.compiler, a.content_resources):
        if not req or not os.path.isfile(req):
            sys.exit(f"missing required input: {req!r}")

    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    scripts_out = os.path.join(out, "Data", "Scripts")
    os.makedirs(scripts_out, exist_ok=True)

    probe_cmd = ["dotnet", "run", "-c", "Release", "--project", PROBE_PROJECT, "--"]
    opts = ["--sfbgs00d", a.sfbgs00d] if (a.sfbgs00d and os.path.isfile(a.sfbgs00d)) else []
    wrote_probe = run(probe_cmd + ["ws0a-build", a.starfield, out] + opts).stdout
    chk_probe = run(probe_cmd + ["ws0a-check", os.path.join(out, "FO4SFWorkshopProbe.esm")]).stdout

    bp_cmd = ["dotnet", "run", "-c", "Release", "--project", BP_PROJECT, "--"]
    bp_opts = ["--set", "fo4", "--shell", "clone", "--category", "vanilla"]
    wrote_bp = run(bp_cmd + ["build", a.starfield, a.core, out] + bp_opts).stdout
    chk_bp = run(bp_cmd + ["check", os.path.join(out, "FO4SFBuildPieces.esm"), a.starfield, a.core] + bp_opts).stdout
    pieces_raw = run(bp_cmd + ["pieces", a.core, "--set", "fo4"]).stdout
    pieces_json = json.loads(([ln for ln in pieces_raw.splitlines() if ln.startswith("[")] or [pieces_raw])[-1])

    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote_probe + chk_probe + wrote_bp + chk_bp)

    src_dir = extract_sources(a.content_resources, work)
    for sc_name, sc_path in (
        (WS0A_SCRIPT, WS0A_PSC),
        (wp.SCRIPT, wp.PSC),
        (wp.HAND_SCRIPT, wp.HAND_PSC),
    ):
        with open(sc_path, encoding="utf-8") as f:
            ok, err = wp.compile_text(a.compiler, f.read(), src_dir, scripts_out, sc_name)
        if not ok:
            sys.exit(f"Papyrus compile of {sc_name}.psc failed: {err}")

    with open(mbp.PSC, encoding="utf-8") as f:
        bp_text = mbp.set_core_ids(f.read(), pieces_json)
    ok, err = wp.compile_text(a.compiler, bp_text, src_dir, scripts_out, mbp.SCRIPT)
    if not ok:
        sys.exit(f"Papyrus compile of {mbp.SCRIPT}.psc failed: {err}")

    shutil.rmtree(work)

    outputs = {}
    for root, _, names in os.walk(out):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, out).replace(os.sep, "/")
            if rel in ("plan.json", "README.txt"):
                continue
            outputs[rel] = sha256(p)

    plan = {
        "kind": "ws0a-probes",
        "version": 1,
        "date": datetime.date.today().isoformat(),
        "tiers": TIERS,
        "plugins": sorted(n for n in outputs if n.lower().endswith(".esm")),
        "outputs": outputs,
    }
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            "WS0a Tier 1-3 offline probe kit (test-kit only; never installed in player saves).\n"
            "Plugins: FO4SFWorkshopProbe.esm (+ optional FO4SFWorkshopProbe_P6.esm), FO4SFBuildPieces.esm.\n"
            f"Probes staged: Tier1={','.join(TIERS['tier1'])} Tier2={','.join(TIERS['tier2'])} Tier3={','.join(TIERS['tier3'])}.\n"
        )
    os.replace(out, final)
    print(f"staged {final}: {len(outputs)} files across {len(plan['plugins'])} test-kit plugins")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield", default=os.path.join(wp.STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--sfbgs00d", default=os.path.join(wp.STARFIELD, "Data", "SFBGS00D.esm"))
    s.add_argument("--core", required=True)
    s.add_argument("--compiler", default=os.path.join(wp.STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(wp.STARFIELD, "Tools", "ContentResources.zip"))
    a = p.parse_args(argv)
    return stage(a)


if __name__ == "__main__":
    raise SystemExit(main())
