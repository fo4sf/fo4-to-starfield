"""Stage and verify the Vault 111 surface entrance lift cog asset component (Round 15 Wave A Item 4b).

Converts `vltelevatorexterior.nif` via `pipeline.Converter.convert_anim_object` using the
per-game contract in `src/fo4sf/core/lift_pairs.json` (zero hardcoded Fallout 4 constants in
shared logic), validates the toggle clips (`StateA_Idle` top-open rest, `StateA_Play` `stage8`
descent `-59.1425 m` / `18.6667 s`, `StateB_Play` `stage4` ascent/open), verifies that every
generated texture already lives in `FO4Port*.ba2` (ships only `meshes/`, `geometries/`,
`materials/`), and writes `surface_cog_manifest.json`, `plan.json`, and `README.txt`.

Never edits Starfield `Data\\`, never launches `Starfield.exe`, and refuses output directories
inside a Git worktree or game installation folder.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from typing import Callable, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (
    os.path.join(REPO, "src"),
    os.path.join(REPO, "scripts", "planet"),
    HERE,
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_anim_console as mac  # noqa: E402
from make_newgame import new_partial  # noqa: E402
from make_workshop_probe import sha256  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402

DEFAULT_PAIR_ID = "fo4.vault111_exit"
LIFT_PAIRS_JSON = os.path.join(REPO, "src", "fo4sf", "core", "lift_pairs.json")
SURFACE_COG_KIND = "surface-lift-cog"
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"


def ensure_game_closed(system=None) -> None:
    """Refuse to stage if Starfield.exe is running or process inspection fails."""
    sys_obj = system if system is not None else System()
    try:
        pids = sys_obj.pids(GAME_EXE)
    except ValueError as err:
        sys.exit(f"refused: cannot confirm {GAME_EXE} is closed ({err})")
    if pids:
        joined = ", ".join(str(p) for p in pids)
        sys.exit(f"refused: {GAME_EXE} is running (pid {joined}); close the game first")


def load_lift_pair(pair_id: str = DEFAULT_PAIR_ID, json_path: str = LIFT_PAIRS_JSON) -> dict:
    """Load and validate an available lift pair entry from `lift_pairs.json`."""
    if not os.path.isfile(json_path):
        sys.exit(f"missing lift_pairs.json: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema_version") != 1:
        sys.exit(f"unsupported lift_pairs.json schema_version: {data.get('schema_version')!r}")
    pairs = data.get("pairs") or {}
    if pair_id not in pairs:
        sys.exit(f"lift pair {pair_id!r} not found in {json_path} (have {sorted(pairs)})")
    pair = pairs[pair_id]
    if not pair.get("available"):
        reason = pair.get("unavailable_reason") or "not marked available"
        sys.exit(f"lift pair {pair_id!r} is unavailable: {reason}")
    for key in ("interior", "surface", "merge_offset_m", "platform_radius_m"):
        if not pair.get(key):
            sys.exit(f"lift pair {pair_id!r} missing required section {key!r}")
    return pair


def validate_surface_cog_animation(anim: dict, pair: dict) -> None:
    """Enforce the surface cog animation, collision, and clip-motion contract from `lift_pairs.json`."""
    surf = pair["surface"]
    expected_idles = surf.get("idles", "toggle")
    expected_bodies = int(surf["expected_moving_bodies"])
    expected_counts = dict(surf["expected_carried_by_bone"])

    if anim.get("idles") != expected_idles or anim.get("moving_bodies") != expected_bodies:
        sys.exit(
            f"surface cog lacks expected idle mode or moving collision "
            f"(idles={anim.get('idles')!r}, moving_bodies={anim.get('moving_bodies')!r}, "
            f"expected idles={expected_idles!r}, moving_bodies={expected_bodies})"
        )

    fc = anim.get("fo4_collision")
    if fc is not None:
        counts: Dict[str, int] = {}
        for item in fc.get("carried_bodies") or ():
            bone = item.get("bone")
            counts[bone] = counts.get(bone, 0) + 1
        if not fc.get("carried") or fc.get("box_fallback_bones") or counts != expected_counts:
            sys.exit(
                f"surface cog carried collision differs from {surf['source_nif']}: "
                f"counts={counts}, fallbacks={fc.get('box_fallback_bones')}"
            )

    clips = {c["name"]: c for c in anim.get("clips") or ()}
    want_clips = {"StateA_Play", "StateB_Play", "StateA_Idle", "StateB_Idle"}
    if len(clips) != len(anim.get("clips") or ()) or set(clips) != want_clips:
        sys.exit(f"surface cog needs exactly the four toggle clips {sorted(want_clips)}, got {sorted(clips)}")

    a_idle = clips["StateA_Idle"]
    if a_idle.get("hold_of") != "StateA_Play" or a_idle.get("hold_frame") != "first":
        sys.exit(
            "surface cog StateA_Idle must hold StateA_Play's first frame (surface top open pose)"
        )
    b_idle = clips["StateB_Idle"]
    if b_idle.get("hold_of") != "StateA_Play" or b_idle.get("hold_frame") != "last":
        sys.exit(
            "surface cog StateB_Idle must hold StateA_Play's last frame (shaft bottom closed pose)"
        )

    desc_slot = surf["descend_clip"]
    desc_sec = float(surf["descend_duration_s"])
    desc_dz = -abs(float(surf["descend_drop_m"]))
    asc_slot = surf["ascend_reset_clip"]
    asc_sec = float(surf["ascend_reset_duration_s"])
    asc_dz = abs(float(surf["ascend_rise_m"]))

    for slot, seconds, dz in ((desc_slot, desc_sec, desc_dz), (asc_slot, asc_sec, asc_dz)):
        c = clips.get(slot, {})
        motion = [m for m in c.get("motion", []) if m.get("bone") == "b_Platform"]
        if len(motion) != 1 or not math.isfinite(c.get("seconds", 0.0)) or abs(c.get("seconds", 0.0) - seconds) > 0.05:
            sys.exit(
                f"surface cog clip {slot} duration {c.get('seconds')!r} differs from {seconds} s"
            )
        m = motion[0]
        travel = m.get("travel_m") or ()
        if (
            len(travel) != 3
            or any(not math.isfinite(v) for v in travel)
            or any(abs(a - b) > 0.1 for a, b in zip(travel, (0.0, 0.0, dz)))
            or not math.isfinite(m.get("rotation_deg", 0.0))
            or abs(m.get("rotation_deg", 0.0)) > 0.1
        ):
            sys.exit(f"surface cog clip {slot} b_Platform travel {travel!r} differs from (0, 0, {dz})")


def inspect_source(a) -> int:
    """Read-only inspection of the source NIF sequences for the selected lift pair."""
    from fo4sf import pipeline

    pair = load_lift_pair(a.pair, a.lift_pairs)
    surf = pair["surface"]
    src = pipeline.Fo4Archives(a.fo4_data)
    raw = src.mesh(surf["source_nif"])
    if raw is None:
        sys.exit(f"source mesh {surf['source_nif']} not found in {a.fo4_data}")
    rows = mac.sequences_table(raw)
    motion = mac.sequence_motion(raw, [r["name"] for r in rows])
    print(f"pair: {pair['id']} ({pair['game']}), source: {surf['source_nif']} ({len(raw)} bytes)")
    print(f"  states={surf['states']} xy_offset_m={surf['xy_offset_m']} z_offset_m={surf['z_offset_m']} rot_z_deg={surf['rot_z_deg']}")
    for r in rows:
        print(f"  {r['name']}: {r['seconds']} s, tracks {', '.join(r['bones']) or 'none'}; text keys: {'; '.join(r['text_keys']) or 'none'}")
        for m in motion.get(r["name"], []):
            if m["bone"] in ("b_Platform", "b_Hatch Left", "b_Hatch Right"):
                print(f"      {m['bone']}: travel {m['travel_m']} m, turns {m['rotation_deg']} deg")
    return 0


def stage(
    a,
    converter: Optional[Callable] = None,
    port_names_fn: Optional[Callable[[str], set]] = None,
) -> int:
    """Stage the surface cog assets, manifest, and plan.json into a fresh directory."""
    if converter is None:
        ensure_game_closed()
    pair = load_lift_pair(a.pair, a.lift_pairs)
    surf = pair["surface"]
    final = os.path.abspath(a.out)
    mac.refuse_forbidden_out_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")

    port_data = a.port_data or a.starfield_data
    sf_esm = os.path.join(a.starfield_data, "Starfield.esm")
    port_esm = os.path.join(port_data, "FO4Port.esm")
    for p in (sf_esm, port_esm):
        if not os.path.isfile(p):
            sys.exit(f"missing required plugin: {p}")

    before = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    staging = os.path.join(work, "conversion")
    os.makedirs(staging)

    _src, conv = (converter or mac.build_converter)(a, staging)
    res = conv.convert_anim_object(
        surf["source_nif"],
        dict(surf["states"]),
        getattr(a, "foley", "") or None,
        idles=surf.get("idles", "toggle"),
    )
    if not res.get("ok"):
        sys.exit(f"surface cog did not convert: {res.get('reason')} (attempt kept in {out})")

    anim = res["anim"]
    validate_surface_cog_animation(anim, pair)

    out_data = os.path.join(out, "Data")
    copied, textures = mac.collect_kit_files(staging, out_data)
    port_names = (port_names_fn or mac.port_archive_names)(port_data)
    lacking = mac.missing_textures(textures, port_names)
    if lacking:
        sys.exit(
            f"surface cog conversion emitted {len(lacking)} texture(s) absent from FO4Port archives "
            f"(the kit ships none): {lacking[:8]} (attempt kept in {out})"
        )

    model_rel = res["out_name"].replace("/", "\\") + ".nif"
    manifest = {
        "pair_id": pair["id"],
        "game": pair["game"],
        "source_nif": surf["source_nif"],
        "cog_plugin": surf["cog_plugin"],
        "cog_base_id": surf["cog_base_id"],
        "cog_edid": surf["cog_edid"],
        "cog_name": surf["cog_name"],
        "graph_anam": surf["graph_anam"],
        "model": model_rel,
        "rig": anim["skeleton"],
        "anims": anim["animations"],
        "states": dict(surf["states"]),
        "idles": surf.get("idles", "toggle"),
        "xy_offset_m": list(surf["xy_offset_m"]),
        "z_offset_m": surf["z_offset_m"],
        "rot_z_deg": surf["rot_z_deg"],
        "descend_duration_s": surf["descend_duration_s"],
        "descend_drop_m": surf["descend_drop_m"],
        "descend_fade_at_s": surf["descend_fade_at_s"],
        "ascend_reset_duration_s": surf["ascend_reset_duration_s"],
        "platform_radius_m": pair["platform_radius_m"],
        "world_overrides": 0,
        "anim": anim,
        "kit_files": copied,
        "textures_not_shipped": textures,
    }
    with open(os.path.join(out, "surface_cog_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)

    shutil.rmtree(work)
    if {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)} != before:
        sys.exit(f"Starfield.esm or FO4Port.esm changed during conversion (attempt kept in {out})")

    plan = {
        "kind": SURFACE_COG_KIND,
        "version": 1,
        "pair_id": pair["id"],
        "cog_plugin": surf["cog_plugin"],
        "cog_base_id": surf["cog_base_id"],
        "cog_edid": surf["cog_edid"],
        "cog_name": surf["cog_name"],
        "model": model_rel,
        "rig": anim["skeleton"],
        "anims": anim["animations"],
        "graph_anam": surf["graph_anam"],
        "world_overrides": 0,
        "states": dict(surf["states"]),
        "outputs": mac.probe_a.stage_files(out),
        "inputs": {k: {"sha256": v} for k, v in before.items()},
    }
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            f"Vault 111 surface entrance lift cog asset component ({pair['id']}).\n"
            f"ACTI {surf['cog_base_id']} {surf['cog_edid']} '{surf['cog_name']}' -> {model_rel}\n"
            f"States: {surf['states']} (toggle); descend {surf['descend_duration_s']} s (-{surf['descend_drop_m']} m), "
            f"fade at {surf['descend_fade_at_s']} s.\n"
            f"Shipped assets: {len(copied)} file(s) under Data/ (zero textures, zero WRLD overrides).\n"
        )

    os.replace(out, final)
    print(f"staged {final}: {pair['id']}, {len(copied)} assets, 0 WRLD overrides")
    return 0


def verify_stage(
    stage_dir: str,
    plan: dict,
    port_data: Optional[str] = None,
    starfield_data: Optional[str] = None,
) -> list[str]:
    """Return a list of drift/contract problems for a staged surface cog directory ([] = pass)."""
    problems: list[str] = []
    if plan.get("kind") != SURFACE_COG_KIND or plan.get("world_overrides") != 0:
        return [f"invalid surface cog plan.json (kind={plan.get('kind')!r}, world_overrides={plan.get('world_overrides')!r})"]
    now = mac.probe_a.stage_files(stage_dir)
    for rel, h in plan.get("outputs", {}).items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != h:
            problems.append(f"{rel} changed after stage (sha256 {now[rel]}, plan {h})")
    extra = sorted(set(now) - set(plan.get("outputs", {})))
    if extra:
        problems.append(f"unexpected files not in plan.json: {extra}")
    if port_data is not None or starfield_data is not None:
        sf_dir = starfield_data or port_data
        p_dir = port_data or starfield_data
        for name, folder in (("Starfield.esm", sf_dir), ("FO4Port.esm", p_dir)):
            p = os.path.join(folder, name)
            if not os.path.isfile(p):
                problems.append(f"missing {name} in {folder}")
            elif sha256(p) != plan["inputs"][name]["sha256"]:
                problems.append(f"{name} changed since stage")
    return problems


def verify(a) -> int:
    plan_path = os.path.join(a.stage, "plan.json")
    if not os.path.isfile(plan_path):
        sys.exit(f"missing {plan_path}")
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    problems = verify_stage(a.stage, plan, a.port_data or None, getattr(a, "starfield_data", "") or None)
    for p in problems:
        print("FAIL ", p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s)")
    return 0 if not problems else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")

    ins = sub.add_parser("inspect-source")
    ins.add_argument("--fo4-data", required=True)
    ins.add_argument("--pair", default=DEFAULT_PAIR_ID)
    ins.add_argument("--lift-pairs", default=LIFT_PAIRS_JSON)

    st = sub.add_parser("stage")
    st.add_argument("--out", required=True)
    st.add_argument("--pair", default=DEFAULT_PAIR_ID)
    st.add_argument("--lift-pairs", default=LIFT_PAIRS_JSON)
    st.add_argument("--starfield-data", default=os.path.join(STARFIELD, "Data"))
    st.add_argument("--port-data", default="")
    st.add_argument("--fo4-data", required=True)
    st.add_argument("--door-anim-dll", required=True)
    st.add_argument("--collision-template", required=True)
    st.add_argument("--texconv", required=True)
    st.add_argument("--content-resources", default=cr)
    st.add_argument("--foley", default="")

    vf = sub.add_parser("verify")
    vf.add_argument("--stage", required=True)
    vf.add_argument("--port-data", default="")
    vf.add_argument("--starfield-data", default="")

    a = p.parse_args(argv)
    return {"inspect-source": inspect_source, "stage": stage, "verify": verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
