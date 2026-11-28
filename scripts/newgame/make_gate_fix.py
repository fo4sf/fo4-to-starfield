"""Stage the Vault 111 yellow gate collision fix, and install it (S2 yellow gates, FAL-976).

The yellow gate of the gear room (FO4 V111GearRoomGate01) is a frozen STAT in the owner's installed port (reference 001317 of
FO4Port.esm, model `..._xrgd_<hash>.nif`). The owner walks through it: its two leaves are static bodies on FO4 layer 55
(L_CLUTTER_NOCUT), and Starfield's character controller passes through a static body on that layer (a supported hypothesis, research
log 2026-10-17; the New Atlantis turnstile leaves are the only vanilla layer-55 bodies). The converter already writes such a leaf as
1 L_STATIC (meshcollision.static_filter, main) but the installed model predates it, and the cog door kit overrides only the door.

This stage takes the installed model out of the port's own archives, rewrites the collisionFilterInfo of its layer-55 bodies to L_STATIC
(src/fo4sf/relayer.py: four bytes per body, nothing else), writes it on a NEW model path beside the old one (nothing archived is
replaced) and builds FO4SFGateFix.esm: an OVERRIDE of the STAT base of the reference, its model the new path. Every other placement of
that base follows (the gate leaves of both Vault 111 gear-room doors, Vault 114).

usage:
  python make_gate_fix.py read --starfield-data <Starfield Data> [--port-data <dir>] [--ref <hex id>]
      READ ONLY: the reference's record flags, the installed model's collision objects, bodies, shape kinds and layers (names and counts).
  python make_gate_fix.py stage --out <new dir> --starfield-data <Starfield Data> [--port-data <dir with FO4Port.esm and its archives>]
         [--ref <hex local id, default 001317>]
      1. the plugin tool's `info`: the reference's STAT base and model (refused when the reference is missing or the base is not a STAT);
      2. the model's bytes from FO4Port*.ba2 (refused when no archive holds it, or when it has no layer-55 body: nothing to fix);
      3. the relayered model on <model>_gf.nif; the plugin built and read back (offline_check.txt); plan.json (SHA-256 of every file) and
         README.txt. Built in <out>.partial-<time>-<pid> and renamed to <out> only when every step passed.
  python make_gate_fix.py install --dir <stage> --starfield <game dir> | uninstall|status|order|active --starfield <game dir>
      exp_install.py's installer on a record of its own (Data\\FO4SFGateFix.install.json), next to the other probes, game closed.
Nothing of the game enters the repo: the model is read on the PC and written only into the stage folder. Needs the game's archives
(the PC's part); the unit tests run on synthetic files.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))

PROJECT = os.path.join(REPO, "dotnet", "GateFix")
PLUGIN = "FO4SFGateFix.esm"
KIND = "gate-fix"
SUFFIX = "_gf"
DEFAULT_REF = "001317"
RECORD = "FO4SFGateFix.install.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    from make_newgame import run as _run
    return _run(cmd)


def new_partial(final):
    from make_newgame import new_partial as _np
    return _np(final)


def parse_info(text):
    """{"base_id": "00DEF8", "model": "Meshes/..."} from the plugin tool's info output; exits when either is missing."""
    import re
    base = re.search(r"^BASE_ID 0x([0-9A-Fa-f]+)", text, re.M)
    model = re.search(r"^MODEL (.+)$", text, re.M)
    if not base or not model or not model.group(1).strip():
        sys.exit("the plugin tool's info did not give BASE_ID and MODEL (is the base's model empty?)")
    return {"base_id": base.group(1), "model": model.group(1).strip().replace("\\", "/")}


def new_model_path(port_model):
    """(archive name with Meshes/, plugin path below Meshes with backslashes) for the relayered copy of the port's model."""
    name = port_model.replace("\\", "/")
    if not name.lower().endswith(".nif"):
        sys.exit(f"the base's model {port_model} is not a .nif")
    full = name[:-4] + SUFFIX + ".nif"
    below = full.split("/", 1)[1] if full.lower().startswith("meshes/") else full
    return full, below.replace("/", "\\")


def find_in_archives(port_data, name):
    """(bytes, archive file name) of `name` from the one FO4Port*.ba2 beside the plugin that holds it, or None.
    Exits when two archives hold it: the game would read one of them and a stage made from the other is not the model under test."""
    from fo4sf import ba2
    held = []
    for fn in sorted(os.listdir(port_data)):
        if fn.lower().startswith("fo4port") and fn.lower().endswith(".ba2"):
            try:
                a = ba2.Ba2(os.path.join(port_data, fn))
                if a.find(name) is not None:
                    held.append((fn, a))
            except (ba2.Ba2Error, OSError):
                continue
    if len(held) > 1:
        sys.exit(f"{name} is in {len(held)} archives ({', '.join(fn for fn, _ in held)}): name the one the game reads, "
                 "remove the other from the folder, and stage again; nothing staged")
    return (held[0][1].read(name), held[0][0]) if held else None


def relayer_model(raw):
    from fo4sf import relayer
    new, notes = relayer.relayer_nif(raw)
    if not notes:
        sys.exit("the installed model has no layer-55 body: there is nothing for this fix to change (the gate's cause is elsewhere); nothing staged")
    return new, notes


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the gate fix's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
    problems = []
    now = stage_files(stage_dir)
    for rel, h in plan["outputs"].items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != h:
            problems.append(f"{rel} changed after the stage (sha256 {now[rel]}, plan {h})")
    extra = sorted(set(now) - set(plan["outputs"]))
    if extra:
        problems.append(f"files not in plan.json: {extra}")
    if data is not None:
        p = os.path.join(data, "Starfield.esm")
        if not os.path.isfile(p):
            problems.append(f"no Starfield.esm in {data}: name the game's Data folder (the install: the game folder)")
        elif sha256(p) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since the stage: re-stage")
        q = os.path.join(data, "FO4Port.esm")
        if not os.path.isfile(q):
            problems.append(f"no FO4Port.esm in {data}: the override is built on that plugin's record")
        elif sha256(q) != plan["inputs"]["FO4Port.esm"]["sha256"]:
            problems.append("FO4Port.esm changed since the stage (the override was built on another one): re-stage")
    return problems


def stage_files(out):
    """{path relative to the stage, "/" separated: SHA-256} of the plugin and every file under Data/."""
    files = {}
    for name in sorted(os.listdir(out)):
        if name.lower().endswith(".esm"):
            files[name] = sha256(os.path.join(out, name))
    for root, dirs, names in os.walk(os.path.join(out, "Data")):
        dirs.sort()
        for n in sorted(names):
            p = os.path.join(root, n)
            files[os.path.relpath(p, out).replace(os.sep, "/")] = sha256(p)
    return files


def node_name(f, i):
    """The node block's name string, or '' (block 0 of a NiNode starts with its name index)."""
    import struct
    try:
        idx, = struct.unpack_from("<i", f.blocks[i], 0)
        return f.strings[idx].decode("latin-1") if 0 <= idx < len(f.strings) else ""
    except struct.error:
        return ""


def describe_body(f, world, body):
    """Lines for one body: the owning node's name and world transform, and the body's bounds in model (root) space, metres.
    Names, numbers and counts only; the triangles themselves are not printed."""
    t, rot, sc = world(body["node"])
    pts = [v for tri in body["triangles"] for v in tri]
    lines = [f"node name {node_name(f, body['node'])!r}, world translation ({t[0]:.4f}, {t[1]:.4f}, {t[2]:.4f}), scale {sc:.4f}, "
             f"rotation rows {[round(x, 4) for x in rot]}"]
    if pts:
        lo = [min(p[a] for p in pts) for a in range(3)]
        hi = [max(p[a] for p in pts) for a in range(3)]
        lines.append("bounds lo (%.4f, %.4f, %.4f) hi (%.4f, %.4f, %.4f) size (%.4f, %.4f, %.4f) centre (%.4f, %.4f, %.4f)" % (
            *lo, *hi, *(h - l for h, l in zip(hi, lo)), *((h + l) / 2 for h, l in zip(hi, lo))))
    return lines


def read_model(a):
    """READ ONLY: names, ids, layers and counts of the installed gate model's collision; writes nothing, installs nothing."""
    from fo4sf import nif as nifmod, sfbodies
    ref = a.ref or DEFAULT_REF
    port_data = a.port_data or a.starfield_data
    sf_esm, port_esm = os.path.join(a.starfield_data, "Starfield.esm"), os.path.join(port_data, "FO4Port.esm")
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    text = run(tool + ["info", port_esm, sf_esm, "--ref", ref]).stdout
    info = parse_info(text)
    got = find_in_archives(port_data, info["model"])
    if got is None:
        print(f"MODEL NOT IN ANY FO4Port*.ba2: {info['model']} (loose file, or another archive?)")
        return 1
    raw, archive = got
    f = nifmod.parse(raw)
    print(f"MODEL {info['model']} in {archive}, {len(raw)} bytes, {len(f.blocks)} blocks")
    objs = [i for i in range(len(f.blocks)) if f.type_of(i) == "bhkNPCollisionObject"]
    other = sorted({f.type_of(i) for i in range(len(f.blocks)) if "bhk" in f.type_of(i) or "Collision" in f.type_of(i)})
    print(f"COLLISION_OBJECTS {len(objs)}; block types with bhk/Collision in the name: {other}")
    try:
        bodies = sfbodies.nif_bodies(raw)
    except Exception as e:  # noqa: BLE001 (a read tool says what it could not read, whatever it was)
        print(f"BODIES UNREADABLE: {type(e).__name__}: {e}")
        return 1
    print(f"BODIES {len(bodies)}")
    world = nifmod.world_transforms(f)
    for k, b in enumerate(bodies):
        print(f"  body {k}: node {b['node']} shape {b['shape']} layer {b['layer']} triangles {len(b['triangles'])}")
        for line in describe_body(f, world, b):
            print("    " + line)
    print(f"LAYERS {sorted({b['layer'] for b in bodies})}")
    return 0


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    ref = a.ref or DEFAULT_REF
    port_data = a.port_data or a.starfield_data
    sf_esm, port_esm = os.path.join(a.starfield_data, "Starfield.esm"), os.path.join(port_data, "FO4Port.esm")
    before = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    out = new_partial(final)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    info = parse_info(run(tool + ["info", port_esm, sf_esm, "--ref", ref]).stdout)
    got = find_in_archives(port_data, info["model"])
    if got is None:
        sys.exit(f"no FO4Port*.ba2 beside {port_esm} holds {info['model']}: is the model loose or in another archive? (attempt kept in {out})")
    raw, archive = got
    new_raw, notes = relayer_model(raw)
    full, below = new_model_path(info["model"])
    dst = os.path.join(out, "Data", *full.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(new_raw)
    wrote = run(tool + ["build", port_esm, sf_esm, out, "--ref", ref, "--model", below]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), port_esm, sf_esm, "--ref", ref, "--model", below]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check + "\n".join(notes) + "\n")
    manifest = {"ref": ref, "base_id": info["base_id"], "port_model": info["model"], "archive": archive, "model": full,
                "source_sha256": hashlib.sha256(raw).hexdigest(), "bytes_before": len(raw), "bytes_after": len(new_raw),
                "bodies_relayered": len(notes), "notes": notes}
    with open(os.path.join(out, "gate_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    after = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    if after != before:
        sys.exit(f"Starfield.esm or FO4Port.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out),
            "inputs": {k: {"sha256": v} for k, v in before.items()}, "ref": ref}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Yellow gate collision fix ({datetime.date.today().isoformat()}). S2 yellow gates, FAL-976.
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): an override of the STAT base 0x{info['base_id']} (the base of reference {ref}) with the model of
the port's own gate, {len(notes)} layer-55 body(ies) rewritten to L_STATIC (4 bytes each), on the new path {full}. Masters Starfield.esm +
FO4Port.esm. Checked against Starfield.esm {before['Starfield.esm']}, FO4Port.esm {before['FO4Port.esm']}.
Install (the owner's word, game closed; loose files are not read, the installer packs them into a ba2):
  python scripts\\\\newgame\\\\make_gate_fix.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\\\newgame\\\\make_gate_fix.py uninstall --starfield <game dir>
Test in game (a throwaway state, no save): start a new game or `coc` into the Vault 111 cryo cell, go to the gear-room gate and walk
into it; `getpos` before and after each try. Pass = the player is stopped by the gate on 3 tries. Fail = walks through: then layer 55
was not the cause and the next read is the body's layer and motion type in the installed model. THROWAWAY STATE ONLY, NO SAVE.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {full}, {len(notes)} body(ies) relayered, gate_manifest.json, plan.json, README.txt")
    return 0


def install(a):
    d = os.path.abspath(a.dir)
    path = os.path.join(d, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_gate_fix.py first")
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    problems = verify_stage(d, plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("gate fix not installed: the stage does not match its plan.json or Data (re-stage): " + "; ".join(problems))
    return run_installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack", "--plugins", ",".join(plan["plugins"])])


def run_installer(argv):
    """exp_install.py's main on this tool's own record."""
    import exp_install
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("--starfield-data", required=True)
    r.add_argument("--port-data", default="")
    r.add_argument("--ref", default="")
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield-data", required=True)
    s.add_argument("--port-data", default="")
    s.add_argument("--ref", default="")
    for name in ("install", "uninstall", "status", "order", "active"):
        p = sub.add_parser(name)
        p.add_argument("--starfield", required=True)
        if name == "install":
            p.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "read":
        return read_model(a)
    if a.cmd == "stage":
        return stage(a)
    if a.cmd == "install":
        return install(a)
    return run_installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
