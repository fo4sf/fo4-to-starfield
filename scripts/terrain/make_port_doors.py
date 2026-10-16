"""The interior side of the scripted load doors (docs/terrain/scripted-doors.md): a post-pass over a pinned FO4Port.esm
staging that gives each interior door REFR the FO4SF_LoadDoor VMAD pointing back at the exterior arrival marker the core
build wrote (DestinationPlugin = the core plugin, DestinationId = the marker's plugin-local id), into a NEW folder.

    python scripts/terrain/make_port_doors.py stage --port <integ staging> --core <core64 staging with doors> --out <new folder>
    python scripts/terrain/make_port_doors.py check --port <integ staging> --out <that folder>

stage  hard-links every file of --port into --out (the archives, the loose trees, the json files; the plugin is COPIED),
       then patches the plugin in place with scripts/terrain/vmad_patch.py: for every door of the core's objects.json
       ("doors") the REFR of destination.id (the interior door, its plugin-local id) gets one Local script with the two
       properties; writes port_doors.json (what was patched, the VMAD bytes) and README.txt. Refuses an existing --out,
       a destination plugin other than the port's, a door whose core formids.json entry lacks the arrival id.
check  vmad_patch.check between the pinned plugin and the patched one (every other record byte-identical, the GRUP tree
       the same, only the enclosing groups' sizes changed) and each patched REFR's VMAD decoded back to the core's
       entry; offline_check.json. Nothing is deployed; the pinned staging is never written.
"""
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_core64c as mk  # noqa: E402
import vmad_patch  # noqa: E402

PORT_PLUGIN = mk.PORT_PLUGIN
REPORT = "port_doors.json"


def link_all(src, dst, skip=()):
    """Hard-link every file of src into dst (directories mirrored), except the names in skip; (linked, copied)."""
    linked = copied = 0
    for root, _dirs, names in os.walk(src):
        rel = os.path.relpath(root, src)
        out = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(out, exist_ok=True)
        for n in names:
            if rel == "." and n in skip:
                continue
            s, d = os.path.join(root, n), os.path.join(out, n)
            try:
                os.link(s, d)
                linked += 1
            except OSError:
                shutil.copy2(s, d)
                copied += 1
    return linked, copied


def door_links(core, core_plugin):
    """[{src, port_id, plugin, local_id, vmad}] for every door of the core staging: the interior REFR to patch and the
    VMAD it gets (DestinationPlugin = the core plugin, DestinationId = the arrival marker's local id)."""
    objects = mk.load(os.path.join(core, "objects.json"))
    ids = mk.load(os.path.join(core, "formids.json"))
    out = []
    for e in objects.get("doors") or []:
        d = e["destination"]
        if d["plugin"].casefold() != PORT_PLUGIN.casefold():
            raise ValueError(f"{e['src']}: destination plugin {d['plugin']} is not {PORT_PLUGIN}")
        got = (ids.get("doors") or {}).get(e["src"]) or {}
        if "arrival" not in got:
            raise ValueError(f"{e['src']}: core formids.json has no arrival marker id")
        marker = int(got["arrival"], 16)
        vmad = vmad_patch.load_door_vmad(e["script"]["name"], mk.DOOR_PLUGIN_PROPERTY, core_plugin, mk.DOOR_ID_PROPERTY, marker)
        out.append({"src": e["src"], "port_id": int(d["id"]), "door": d.get("door"), "cell": d.get("cell"),
                    "script": e["script"]["name"], "plugin": core_plugin, "local_id": marker, "arrival": e["arrival"],
                    "exterior_ref": got.get("ref"), "exterior_base": got.get("base"), "vmad": vmad.hex()})
    if len({l["port_id"] for l in out}) != len(out):
        raise ValueError("two doors name one interior REFR")
    return out


def cmd_stage(a):
    t0 = time.time()
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists; this writes a NEW folder")
    prm, _ov = mk.core_params(a.core)
    try:
        links = door_links(a.core, prm["plugin"])
    except (ValueError, KeyError, OSError) as e:
        sys.exit(f"doors: {e}")
    if not links:
        sys.exit("the core staging has no doors (objects.json \"doors\")")
    src_plugin = os.path.join(a.port, PORT_PLUGIN)
    buf = vmad_patch.read(src_plugin)
    patched = []
    for l in links:
        buf, info = vmad_patch.patch(buf, l["port_id"], bytes.fromhex(l["vmad"]))
        patched.append({**l, **{k: info[k] for k in ("offset", "old_size", "new_size", "delta")}})
    os.makedirs(a.out)
    linked, copied = link_all(a.port, a.out, skip=(PORT_PLUGIN,))
    with open(os.path.join(a.out, PORT_PLUGIN), "wb") as f:
        f.write(buf)
    rep = {"port": os.path.abspath(a.port), "core": os.path.abspath(a.core), "plugin": PORT_PLUGIN,
           "source_bytes": os.path.getsize(src_plugin), "bytes": len(buf), "doors": patched,
           "linked": linked, "copied": copied, "seconds": round(time.time() - t0, 1)}
    mk.save(os.path.join(a.out, REPORT), rep, indent=1)
    lines = [f"FO4Port doors (scripted load doors, docs/terrain/scripted-doors.md). NOT deployed. Built from {rep['port']}",
             f"(every file hard-linked; {PORT_PLUGIN} copied and patched in place) and {rep['core']} (the exterior side).",
             f"Each interior door REFR below carries the {links[0]['script']} script pointing at its exterior arrival marker:",
             f"  {mk.DOOR_PLUGIN_PROPERTY} = \"{prm['plugin']}\", {mk.DOOR_ID_PROPERTY} = the marker's plugin-local id.", ""]
    for l in patched:
        lines.append(f"  {PORT_PLUGIN} REFR {l['port_id']:06X} ({l['cell']} {l['door']}) <- {l['src']}: {mk.DOOR_ID_PROPERTY} "
                     f"{l['local_id']} (0x{l['local_id']:06X}) at {l['arrival']['pos']}; VMAD {len(l['vmad']) // 2} bytes")
    lines += ["", f"Check: python scripts/terrain/make_port_doors.py check --port {a.port} --out {a.out}",
              "Install: as the pinned interiors staging (the archives are the same files); the plugin needs",
              f"{prm['plugin']} loaded in the same session (the script resolves it by file name at run time, no master link).",
              "The .pex of the script must be in an archive of an active plugin (loose scripts are not read on this install)."]
    with open(os.path.join(a.out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    for l in patched:
        print(f"  {PORT_PLUGIN} {l['port_id']:06X} <- {l['src']}: {mk.DOOR_PLUGIN_PROPERTY}={l['plugin']} {mk.DOOR_ID_PROPERTY}={l['local_id']} "
              f"(record {l['old_size']} -> {l['new_size']} bytes at {l['offset']})")
    print(f"wrote {a.out}: {len(patched)} door REFR(s) patched, {rep['source_bytes']:,} -> {len(buf):,} bytes, "
          f"{linked} files linked, {copied} copied; {rep['seconds']} s")
    return 0


def cmd_check(a):
    t0 = time.time()
    rep = mk.load(os.path.join(a.out, REPORT))
    old = vmad_patch.read(os.path.join(a.port, PORT_PLUGIN))
    new = vmad_patch.read(os.path.join(a.out, PORT_PLUGIN))
    checks = []

    def need(cond, what):
        checks.append([what, bool(cond)])
    ids = [l["port_id"] for l in rep["doors"]]
    probs = vmad_patch.check(old, new, ids)
    need(not probs, f"nothing but the {len(ids)} door REFR VMADs changed ({len(probs)} problems: {probs[:3]})")
    need(len(new) - len(old) == sum(l["delta"] for l in rep["doors"]),
         f"size grew by the inserted VMADs only ({len(old):,} -> {len(new):,} bytes)")
    for l in rep["doors"]:
        vm = vmad_patch.refr_vmad(new, l["port_id"])
        props, why = vmad_patch.door_properties(vm or b"", l["script"], mk.DOOR_PLUGIN_PROPERTY, mk.DOOR_ID_PROPERTY)
        need(props == (l["plugin"], l["local_id"]),
             f"REFR {l['port_id']:06X}: {l['script']} {mk.DOOR_PLUGIN_PROPERTY}={l['plugin']} {mk.DOOR_ID_PROPERTY}={l['local_id']} "
             f"({props if props else why})")
        need(vm == bytes.fromhex(l["vmad"]), f"REFR {l['port_id']:06X}: VMAD bytes as staged")
        need(vmad_patch.refr_vmad(old, l["port_id"]) is None, f"REFR {l['port_id']:06X}: had no VMAD in the pinned plugin")
    if a.core:
        try:
            links = {l["port_id"]: l for l in door_links(a.core, mk.core_params(a.core)[0]["plugin"])}
        except (ValueError, KeyError, OSError) as e:
            need(False, f"core doors: {e}")
            links = {}
        need(set(links) == set(ids) and all(links[i]["vmad"] == l["vmad"] for i in ids for l in rep["doors"] if l["port_id"] == i),
             f"the core's {len(links)} door(s) are the patched REFRs with the same VMADs")
    ok = all(c[1] for c in checks)
    out = {"checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "pass": ok, "checks": checks, "seconds": round(time.time() - t0, 1)}
    mk.save(os.path.join(a.out, "offline_check.json"), out, indent=1)
    for what, good in checks:
        print(("  ok   " if good else "  FAIL ") + what)
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--port", required=True, help="the pinned interiors staging (FO4Port.esm, formids.json, archives)")
    s.add_argument("--core", required=True, help="the core staging with doors (objects.json, formids.json, overlays_params.json)")
    s.add_argument("--out", required=True, help="NEW folder")
    s = sub.add_parser("check")
    s.add_argument("--port", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--core", default="", help="also compare with the core staging's doors")
    a = ap.parse_args(argv)
    return {"stage": cmd_stage, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
