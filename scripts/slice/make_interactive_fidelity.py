"""Converter interactive fidelity driver (CF-5 part 1).

Subcommands:
  precheck     Verify FO4SF_ActivateChain.psc required natives/events in ContentResources.zip.
  diff-counts  Deterministic before/after subrecord count diff (XESP, XLOC, XLKR, XAPR, XTEL) on target cells
               (alias: measure). Outputs counts, record signatures, exterior grids and hex FormIDs only.
  reconvert    Re-export and re-convert interior cell(s) via Fo4Export + PluginSpike --interactive-fidelity,
               run InteractiveFidelity check, and diff before/after counts against a baseline port.
  stage        Build FO4SFInteractiveFidelity.esm, run Mutagen check, compile FO4SF_ActivateChain.pex,
               measure before/after counts, and write plan.json + README.txt atomically.
  fold         Hardlink/copy fold a staged interactive-fidelity build into a core set (never mutating a
               hardlinked README.txt in place) and verify SHA-256 pins before publishing.
  verify       Verify plugin, compiled script and master SHA-256 pins against plan.json.
"""
import argparse
import datetime
import errno
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

PLUGIN = "FO4SFInteractiveFidelity.esm"
CHAIN_SCRIPT = "FO4SF_ActivateChain"
LEGACY_CHAIN_SCRIPT = "DefaultActivateLinkedRefOnActivate"
LOAD_DOOR_SCRIPTS = ("fo4sf_loaddoor", "fo4sf_animatedloaddoor")
LEGACY_LINK_CUSTOM02 = ("starfield.esm", 0x05D5E7)
MULTIREF_LOD_FO4 = ("fallout4.esm", 0x195411)

NATIVES = {
    CHAIN_SCRIPT: {
        "ScriptObject": ["OnInit"],
        "ObjectReference": ["OnCellAttach", "OnLoad", "OnActivate", "BlockActivation", "Activate"],
        "Utility": ["Wait"],
    }
}

# Target cell preset for CF-5 part 1 measurements (hex FormIDs and Starfield 100 m exterior grids only).
CF5_PRESET_GROUPS = (
    {
        "group": "vault_111",
        "fo4_interiors": (0x000016D8,),
        "default_port_interiors": (0x0011F3,),
        "exterior_grids": ((-13, 12), (-13, 13)),
    },
    {
        "group": "red_rocket",
        "fo4_interiors": (0x0005E62F,),
        "default_port_interiors": (0x002338,),
        "exterior_grids": ((-10, 11), (-11, 11)),
    },
    {
        "group": "concord",
        "fo4_interiors": (),
        "default_port_interiors": (),
        "exterior_grids": ((-9, 10), (-9, 9), (-8, 10), (-10, 10), (-9, 11)),
    },
    {
        "group": "fort_hagen",
        "fo4_interiors": (0x000BB078, 0x000CD2AE),
        "default_port_interiors": (0x00BA4B, 0x00CFC6),
        "exterior_grids": ((-13, -2), (-13, -1), (-12, -2)),
    },
)

FAMILIES = ("xesp", "xloc", "xlkr", "xapr", "xtel")
INSTALL_LINE_RE = re.compile(r"exp_install\.py install\b.*--plugins (?P<plugins>\S+)")


# --------------------------------------------------------------------------- helpers

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + f".tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read_text(path):
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def new_partial(final_dir, create=True):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    base = f"{final_dir}.partial-{stamp}-{os.getpid()}"
    cand, idx = base, 1
    while os.path.exists(cand):
        cand, idx = f"{base}-{idx}", idx + 1
    if create:
        os.makedirs(cand)
    return cand


def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
    except OSError as exc:
        if exc.errno in (errno.EXDEV, errno.EPERM, errno.EACCES, getattr(errno, "ENOTSUP", -1)) or os.name == "nt":
            shutil.copy2(src, dst)
        else:
            raise


def build_dotnet_project(proj_name):
    proj_dir = os.path.join(REPO, "dotnet", proj_name)
    r = subprocess.run(
        ["dotnet", "build", proj_dir, "-c", "Release", "--nologo", "-v", "q"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.exit(f"dotnet build {proj_name} failed ({r.returncode}):\n{r.stdout}{r.stderr}")
    return os.path.join(proj_dir, "bin", "Release", "net9.0", f"{proj_name}.dll")


def run_cmd(cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0 and check:
        sys.exit(f"command failed ({r.returncode}): {' '.join(str(x) for x in cmd)}\n{r.stdout}{r.stderr}")
    return r


def parse_hex_id(token):
    s = token.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    return int(s, 16) & 0x00FFFFFF


# --------------------------------------------------------------------------- precheck & Papyrus compile

def has_function(source, name):
    return re.search(rf"^\s*(?:[\w\[\]:]+\s+)?(?:Function|Event)\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


def parent_of(source):
    m = re.search(r"^\s*Scriptname\s+[\w:]+\s+extends\s+([\w:]+)", source, re.M | re.I)
    return m.group(1) if m else None


def declares(sources, base, name, depth=8):
    seen = set()
    while base and base.lower() not in seen and len(seen) < depth:
        seen.add(base.lower())
        src = sources.get(base.lower(), "")
        if has_function(src, name):
            return True
        base = parent_of(src)
    return False


def precheck_zip(zip_path):
    sources = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            parts = name.replace("\\", "/").split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and parts[2].lower().endswith(".psc"):
                sources[parts[2][:-4].lower()] = zf.read(name).decode("utf-8", errors="replace")
    natives = {}
    for script, bases in NATIVES.items():
        natives[script] = {f"{b}.{fn}": declares(sources, b, fn) for b, fns in bases.items() for fn in fns}
    missing = [k for script_map in natives.values() for k, ok in script_map.items() if not ok]
    return {"natives": natives, "missing": missing, "ok": len(missing) == 0}


def cmd_precheck(args):
    res = precheck_zip(args.content_resources)
    for script, fmap in res["natives"].items():
        for key, ok in fmap.items():
            print(f"{'PASS' if ok else 'FAIL'}  {script}: {key}")
    if args.out:
        save_json(args.out, res)
    print("precheck: ok" if res["ok"] else f"precheck: {len(res['missing'])} missing declaration(s)")
    return 0 if res["ok"] else 1


def extract_papyrus_sources(zip_path, work_dir):
    src_dir = os.path.join(work_dir, "Source")
    os.makedirs(src_dir, exist_ok=True)
    copied = 0
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            parts = name.replace("\\", "/").split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"
            ):
                with zf.open(name) as src_f, open(os.path.join(src_dir, parts[2]), "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
                copied += 1
    if not os.path.isfile(os.path.join(src_dir, "Starfield_Papyrus_Flags.flg")) or copied < 2:
        sys.exit(f"{zip_path}: missing Scripts/Source/*.psc or Starfield_Papyrus_Flags.flg")
    return src_dir


def compile_chain_script(compiler_exe, zip_path, work_dir, out_scripts_dir):
    src_dir = extract_papyrus_sources(zip_path, work_dir)
    os.makedirs(out_scripts_dir, exist_ok=True)
    cmd = [
        compiler_exe,
        f"{CHAIN_SCRIPT}.psc",
        "-f=Starfield_Papyrus_Flags.flg",
        f"-i={HERE};{src_dir}",
        f"-o={out_scripts_dir}",
    ]
    r = run_cmd(cmd, cwd=HERE, check=False)
    pex_path = os.path.join(out_scripts_dir, f"{CHAIN_SCRIPT}.pex")
    if r.returncode != 0 or not os.path.isfile(pex_path):
        sys.exit(f"Papyrus compile failed for {CHAIN_SCRIPT}.psc ({r.returncode})\n{r.stdout}{r.stderr}")
    return pex_path


# --------------------------------------------------------------------------- binary ESM reader & count diff

def iter_subrecords(raw_bytes):
    pos = 0
    end = len(raw_bytes)
    large_len = None
    while pos + 6 <= end:
        sig = raw_bytes[pos:pos + 4]
        sz = struct.unpack_from("<H", raw_bytes, pos + 4)[0]
        pos += 6
        if sig == b"XXXX" and sz == 4 and pos + 4 <= end:
            large_len = struct.unpack_from("<I", raw_bytes, pos)[0]
            pos += 4
            continue
        if large_len is not None:
            sz = large_len
            large_len = None
        yield sig, raw_bytes[pos:pos + sz]
        pos += sz


def read_tes4_masters(buf):
    if len(buf) < 24 or buf[:4] != b"TES4":
        raise ValueError("not a TES4 / ESM binary")
    hsize = struct.unpack_from("<I", buf, 4)[0]
    hflags = struct.unpack_from("<I", buf, 8)[0]
    hdr_data = buf[24:24 + hsize]
    if hflags & 0x00040000:
        hdr_data = zlib.decompress(hdr_data[4:])
    masters = []
    for sig, sdata in iter_subrecords(hdr_data):
        if sig == b"MAST" and sdata:
            masters.append(sdata.rstrip(b"\x00").decode("utf-8", errors="replace"))
    return hsize, masters


def resolve_fid(raw_fid, masters_lower, self_mod_lower):
    if raw_fid == 0:
        return None
    idx = (raw_fid >> 24) & 0xFF
    local = raw_fid & 0x00FFFFFF
    owner = masters_lower[idx] if idx < len(masters_lower) else self_mod_lower
    return (owner, local)


def _read_vmad_str(data, pos):
    n = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    return data[pos:pos + n].decode("cp1252", errors="replace"), pos + n


def _parse_vmad_prop_value(data, pos, ptype, obj_fmt, ver, masters_lower, self_mod_lower):
    if ptype == 1:
        if obj_fmt == 2:
            raw_fid = struct.unpack_from("<I", data, pos + 4)[0]
        else:
            raw_fid = struct.unpack_from("<I", data, pos)[0]
        return resolve_fid(raw_fid, masters_lower, self_mod_lower), pos + 8
    if ptype == 2:
        s, pos = _read_vmad_str(data, pos)
        return s, pos
    if ptype == 3:
        return struct.unpack_from("<i", data, pos)[0], pos + 4
    if ptype == 4:
        return struct.unpack_from("<f", data, pos)[0], pos + 4
    if ptype == 5:
        return bool(data[pos]), pos + 1
    if ptype == 7:
        mcount = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        struct_dict = {}
        for _ in range(mcount):
            pname, pval, pos = _parse_vmad_property(data, pos, obj_fmt, ver, masters_lower, self_mod_lower)
            struct_dict[pname] = pval
        return struct_dict, pos
    if ptype in (11, 12, 13, 14, 15, 17):
        elem_type = 7 if ptype == 17 else (ptype - 10)
        acount = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        arr = []
        for _ in range(acount):
            val, pos = _parse_vmad_prop_value(data, pos, elem_type, obj_fmt, ver, masters_lower, self_mod_lower)
            arr.append(val)
        return arr, pos
    raise ValueError(f"unsupported VMAD property type {ptype}")


def _parse_vmad_property(data, pos, obj_fmt, ver, masters_lower, self_mod_lower):
    pname, pos = _read_vmad_str(data, pos)
    ptype = data[pos]
    pos += 1 + (1 if ver >= 4 else 0)
    pval, pos = _parse_vmad_prop_value(data, pos, ptype, obj_fmt, ver, masters_lower, self_mod_lower)
    return pname, pval, pos


def parse_refr_vmad(sdata, masters_lower, self_mod_lower):
    """Extract XAPR activation-chain edges and scripted load-door presence from REFR VMAD."""
    out = {
        "xapr_edges": 0,
        "xapr_delays_nonzero": 0,
        "xapr_parent_only": False,
        "has_legacy_single_chain": False,
        "has_script_load_door": False,
    }
    if len(sdata) < 6:
        return out
    try:
        ver, obj_fmt, scount = struct.unpack_from("<hHH", sdata, 0)
        pos = 6
        for _ in range(scount):
            sname, pos = _read_vmad_str(sdata, pos)
            if ver >= 4:
                pos += 1
            pcount = struct.unpack_from("<H", sdata, pos)[0]
            pos += 2
            props = {}
            for _ in range(pcount):
                pname, pval, pos = _parse_vmad_property(sdata, pos, obj_fmt, ver, masters_lower, self_mod_lower)
                props[pname.lower()] = pval
            sl = sname.lower()
            if sl == CHAIN_SCRIPT.lower():
                targets = props.get("targets") or []
                delays = props.get("delays") or []
                valid_targets = [t for t in targets if t is not None]
                out["xapr_edges"] += len(valid_targets)
                out["xapr_delays_nonzero"] += sum(1 for d in delays if isinstance(d, (int, float)) and d > 1e-6)
                if props.get("parentactivateonly") is True:
                    out["xapr_parent_only"] = True
            elif sl == LEGACY_CHAIN_SCRIPT.lower():
                out["xapr_edges"] += 1
                out["has_legacy_single_chain"] = True
            elif sl in LOAD_DOOR_SCRIPTS:
                out["has_script_load_door"] = True
    except (struct.error, ValueError, IndexError):
        return out
    return out


def parse_refr_record(rflags, raw_payload, masters_lower, self_mod_lower, in_persistent):
    if rflags & 0x00000020:
        return {"deleted": True}
    data = zlib.decompress(raw_payload[4:]) if (rflags & 0x00040000) else raw_payload
    pos_xyz = (0.0, 0.0, 0.0)
    xesp = None
    xloc = None
    xlkr = []
    native_xapr = 0
    native_xapr_delays = 0
    native_xapd_parent_only = False
    xtel = False
    vmad_info = {
        "xapr_edges": 0,
        "xapr_delays_nonzero": 0,
        "xapr_parent_only": False,
        "has_legacy_single_chain": False,
        "has_script_load_door": False,
    }

    for sig, sdata in iter_subrecords(data):
        if sig == b"DATA" and len(sdata) >= 12:
            pos_xyz = struct.unpack_from("<fff", sdata, 0)
        elif sig == b"XESP" and len(sdata) >= 8:
            p_raw, ep_flags = struct.unpack_from("<II", sdata, 0)
            p_res = resolve_fid(p_raw, masters_lower, self_mod_lower)
            if p_res is not None:
                xesp = (p_res, ep_flags)
        elif sig == b"XLOC" and len(sdata) >= 12:
            lvl = sdata[0]
            k_raw = struct.unpack_from("<I", sdata, 4)[0]
            lflags = sdata[8]
            xloc = (lvl, resolve_fid(k_raw, masters_lower, self_mod_lower), lflags)
        elif sig == b"XLKR" and len(sdata) >= 8:
            for off in range(0, (len(sdata) // 8) * 8, 8):
                u_raw, t_raw = struct.unpack_from("<II", sdata, off)
                t_res = resolve_fid(t_raw, masters_lower, self_mod_lower)
                u_res = resolve_fid(u_raw, masters_lower, self_mod_lower)
                if t_res is not None:
                    xlkr.append((u_res, t_res))
        elif sig == b"XAPD" and len(sdata) >= 1:
            native_xapd_parent_only = bool(sdata[0] & 1)
        elif sig == b"XAPR" and len(sdata) >= 8:
            p_raw, dly = struct.unpack_from("<If", sdata, 0)
            if p_raw != 0:
                native_xapr += 1
                if dly > 1e-6:
                    native_xapr_delays += 1
        elif sig == b"XTEL" and len(sdata) >= 28:
            d_raw = struct.unpack_from("<I", sdata, 0)[0]
            if d_raw != 0:
                xtel = True
        elif sig == b"VMAD":
            vmad_info = parse_refr_vmad(sdata, masters_lower, self_mod_lower)

    # Exclude synthetic LinkCustom02 XLKR when attached solely for legacy DefaultActivateLinkedRefOnActivate,
    # and exclude FO4 MultirefLOD so XLKR counts reflect pure interactive reference links.
    filtered_xlkr = []
    for u_res, t_res in xlkr:
        if u_res == MULTIREF_LOD_FO4:
            continue
        if vmad_info["has_legacy_single_chain"] and u_res == LEGACY_LINK_CUSTOM02:
            continue
        filtered_xlkr.append((u_res, t_res))

    return {
        "deleted": False,
        "persistent": bool(in_persistent or (rflags & 0x400)),
        "initially_disabled": bool(rflags & 0x800),
        "pos": pos_xyz,
        "xesp": xesp,
        "xloc": xloc,
        "xlkr": filtered_xlkr,
        "xapr": native_xapr + vmad_info["xapr_edges"],
        "xapr_delays": native_xapr_delays + vmad_info["xapr_delays_nonzero"],
        "xapr_parent_only": native_xapd_parent_only or vmad_info["xapr_parent_only"],
        "xtel": xtel,
        "xtel_script_bridged": vmad_info["has_script_load_door"],
    }


def lookup_fo4_interior_edids(fo4_esm_path, target_fo4_ids):
    """Internal helper: maps FO4 interior CELL local FormID -> internal EDID string without emitting game text."""
    wanted = {fid & 0x00FFFFFF for fid in target_fo4_ids}
    found = {}
    with open(fo4_esm_path, "rb") as f:
        buf = f.read()
    hsize, masters = read_tes4_masters(buf)
    masters_lower = [m.lower() for m in masters]
    self_lower = os.path.basename(fo4_esm_path).lower()

    def walk(pos, end, in_cell_top):
        while pos + 24 <= end and len(found) < len(wanted):
            sig = buf[pos:pos + 4]
            sz = struct.unpack_from("<I", buf, pos + 4)[0]
            if sig == b"GRUP":
                glabel = buf[pos + 8:pos + 12]
                gtype = struct.unpack_from("<i", buf, pos + 12)[0]
                if gtype == 0 and glabel != b"CELL":
                    pos += sz
                    continue
                if gtype in (6, 8, 9):
                    pos += sz
                    continue
                walk(pos + 24, pos + sz, in_cell_top or (gtype == 0 and glabel == b"CELL"))
                pos += sz
                continue
            rflags, rfid = struct.unpack_from("<II", buf, pos + 8)
            if in_cell_top and sig == b"CELL":
                owner, local = resolve_fid(rfid, masters_lower, self_lower)
                if owner == self_lower and local in wanted:
                    payload = buf[pos + 24:pos + 24 + sz]
                    if rflags & 0x00040000:
                        payload = zlib.decompress(payload[4:])
                    for ssig, sdata in iter_subrecords(payload):
                        if ssig == b"EDID":
                            found[local] = sdata.rstrip(b"\x00").decode("utf-8", errors="replace")
                            break
            pos += 24 + sz

    walk(24 + hsize, len(buf), False)
    return found


def scan_esm_stack(esm_paths, target_interiors, target_ext_grids, cell_span_m=100.0):
    """Scan a load-order list of ESMs and return merged active REFR records per interior cell and exterior grid."""
    target_int_set = {(m.lower(), cid & 0x00FFFFFF) for m, cid in target_interiors}
    target_grid_set = {(int(gx), int(gy)) for gx, gy in target_ext_grids}

    ext_cell_to_grid = {}
    top_cells = set()
    refrs = {}  # (owner_mod, local_id) -> (bucket_kind, bucket_key, parsed_dict)

    for path in esm_paths:
        with open(path, "rb") as f:
            buf = f.read()
        hsize, masters = read_tes4_masters(buf)
        masters_lower = [m.lower() for m in masters]
        self_lower = os.path.basename(path).lower()

        def walk(pos, end, ctx_world, in_ext_subblock, current_cell, in_pers):
            while pos + 24 <= end:
                sig = buf[pos:pos + 4]
                sz = struct.unpack_from("<I", buf, pos + 4)[0]
                if sig == b"GRUP":
                    glabel = buf[pos + 8:pos + 12]
                    gtype = struct.unpack_from("<i", buf, pos + 12)[0]
                    if gtype == 0:
                        if glabel == b"CELL" and not target_int_set:
                            pos += sz
                            continue
                        if glabel == b"WRLD" and not target_grid_set:
                            pos += sz
                            continue
                        if glabel not in (b"CELL", b"WRLD"):
                            pos += sz
                            continue
                        walk(pos + 24, pos + sz, None, False, None, False)
                    elif gtype == 1:
                        w_fid = resolve_fid(struct.unpack_from("<I", glabel, 0)[0], masters_lower, self_lower)
                        walk(pos + 24, pos + sz, w_fid, False, None, False)
                    elif gtype in (2, 3):
                        walk(pos + 24, pos + sz, None, False, None, False)
                    elif gtype in (4, 5):
                        walk(pos + 24, pos + sz, ctx_world, True, None, False)
                    elif gtype == 6:
                        c_fid = resolve_fid(struct.unpack_from("<I", glabel, 0)[0], masters_lower, self_lower)
                        if c_fid in target_int_set or c_fid in ext_cell_to_grid or c_fid in top_cells:
                            walk(pos + 24, pos + sz, ctx_world, in_ext_subblock, c_fid, False)
                    elif gtype in (8, 9):
                        c_fid = resolve_fid(struct.unpack_from("<I", glabel, 0)[0], masters_lower, self_lower)
                        if c_fid in target_int_set or c_fid in ext_cell_to_grid or c_fid in top_cells:
                            walk(pos + 24, pos + sz, ctx_world, in_ext_subblock, c_fid, gtype == 8)
                    pos += sz
                    continue

                rflags, rfid = struct.unpack_from("<II", buf, pos + 8)
                rec_key = resolve_fid(rfid, masters_lower, self_lower)
                payload = buf[pos + 24:pos + 24 + sz]

                if sig == b"CELL" and rec_key is not None:
                    if ctx_world is not None and not in_ext_subblock:
                        if target_grid_set:
                            top_cells.add(rec_key)
                    elif ctx_world is not None and in_ext_subblock:
                        cdata = zlib.decompress(payload[4:]) if (rflags & 0x00040000) else payload
                        for ssig, sdata in iter_subrecords(cdata):
                            if ssig == b"XCLC" and len(sdata) >= 8:
                                gx, gy = struct.unpack_from("<ii", sdata, 0)
                                if (gx, gy) in target_grid_set:
                                    ext_cell_to_grid[rec_key] = (gx, gy)
                                break
                elif sig == b"REFR" and rec_key is not None and current_cell is not None:
                    parsed = parse_refr_record(rflags, payload, masters_lower, self_lower, in_pers)
                    if parsed["deleted"]:
                        refrs.pop(rec_key, None)
                    elif current_cell in target_int_set:
                        refrs[rec_key] = ("interior", current_cell, parsed)
                    elif current_cell in ext_cell_to_grid:
                        refrs[rec_key] = ("exterior", ext_cell_to_grid[current_cell], parsed)
                    elif current_cell in top_cells:
                        px, py, _ = parsed["pos"]
                        g = (int(math.floor(px / cell_span_m)), int(math.floor(py / cell_span_m)))
                        if g in target_grid_set:
                            refrs[rec_key] = ("exterior", g, parsed)
                        else:
                            refrs.pop(rec_key, None)

                pos += 24 + sz

        walk(24 + hsize, len(buf), None, False, None, False)

    by_bucket = {}
    for rec_key, (bkind, bkey, parsed) in refrs.items():
        by_bucket.setdefault((bkind, bkey), []).append((rec_key, parsed))
    return by_bucket


def tally_refs(ref_items):
    counts = {
        "refs": len(ref_items),
        "xesp": 0,
        "xesp_opposite": 0,
        "xesp_popin": 0,
        "initially_disabled": 0,
        "xloc": 0,
        "xloc_with_key": 0,
        "xlkr": 0,
        "xapr": 0,
        "xapr_delays": 0,
        "xapr_parent_only_refs": 0,
        "xtel": 0,
        "xtel_script_bridged": 0,
    }
    for _, p in ref_items:
        if p["initially_disabled"]:
            counts["initially_disabled"] += 1
        if p["xesp"] is not None:
            counts["xesp"] += 1
            if p["xesp"][1] & 1:
                counts["xesp_opposite"] += 1
            if p["xesp"][1] & 2:
                counts["xesp_popin"] += 1
        if p["xloc"] is not None:
            counts["xloc"] += 1
            if p["xloc"][1] is not None:
                counts["xloc_with_key"] += 1
        counts["xlkr"] += len(p["xlkr"])
        counts["xapr"] += p["xapr"]
        counts["xapr_delays"] += p["xapr_delays"]
        if p["xapr_parent_only"]:
            counts["xapr_parent_only_refs"] += 1
        if p["xtel"]:
            counts["xtel"] += 1
        if p["xtel_script_bridged"]:
            counts["xtel_script_bridged"] += 1
    return counts


def build_target_groups(cells_arg=None, preset=None, fo4_esm=None, port_ids_path=None, default_int_mod="fo4port.esm"):
    if preset == "cf5-targets":
        fo4_to_port_cell = {}
        if fo4_esm and port_ids_path and os.path.isfile(fo4_esm) and os.path.isfile(port_ids_path):
            all_fo4_cids = [cid for g in CF5_PRESET_GROUPS for cid in g["fo4_interiors"]]
            edids = lookup_fo4_interior_edids(fo4_esm, all_fo4_cids)
            with open(port_ids_path, encoding="utf-8") as f:
                pids = json.load(f)
            pids_ci = {k.lower(): v for k, v in pids.items()}
            for cid, edid in edids.items():
                key = f"cell:fo4port_{edid}".lower()
                if key in pids_ci:
                    fo4_to_port_cell[cid] = int(pids_ci[key])
        groups = []
        for g in CF5_PRESET_GROUPS:
            ints = []
            for idx, fo4_cid in enumerate(g["fo4_interiors"]):
                port_cid = fo4_to_port_cell.get(fo4_cid, g["default_port_interiors"][idx])
                ints.append(("fo4port.esm", port_cid, fo4_cid))
            groups.append({
                "group": g["group"],
                "interiors": ints,
                "exteriors": list(g["exterior_grids"]),
            })
        return groups

    if not cells_arg:
        raise ValueError("specify either --preset cf5-targets or --cells <spec>")

    groups = []
    for raw_part in cells_arg.split(";"):
        raw_part = raw_part.strip()
        if not raw_part:
            continue
        if "=" in raw_part:
            gname, rhs = raw_part.split("=", 1)
            tokens = [t.strip() for t in rhs.split("+") if t.strip()]
        else:
            gname = None
            tokens = [t.strip() for t in raw_part.split(",") if t.strip()]
        # Merge "ext:x" + "y" split if comma-separated without semicolons
        merged_tokens = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.lower().startswith("ext:") and "," not in tok and i + 1 < len(tokens):
                merged_tokens.append(tok + "," + tokens[i + 1])
                i += 2
            else:
                merged_tokens.append(tok)
                i += 1
        ints = []
        exts = []
        for tok in merged_tokens:
            tl = tok.lower()
            if tl.startswith("ext:"):
                gx_s, gy_s = tl[4:].split(",", 1)
                exts.append((int(gx_s), int(gy_s)))
            elif ":" in tok:
                mod_s, hex_s = tok.split(":", 1)
                ints.append((mod_s.strip().lower(), parse_hex_id(hex_s), None))
            else:
                ints.append((default_int_mod.lower(), parse_hex_id(tok), None))
        if gname is None:
            for m, cid, fo4_cid in ints:
                groups.append({"group": f"{m}:{cid:06X}", "interiors": [(m, cid, fo4_cid)], "exteriors": []})
            for gx, gy in exts:
                groups.append({"group": f"ext({gx},{gy})", "interiors": [], "exteriors": [(gx, gy)]})
        else:
            groups.append({"group": gname.strip(), "interiors": ints, "exteriors": exts})
    return groups


def diff_counts(before_esms, after_esms, groups):
    all_ints = [(m, cid) for g in groups for (m, cid, _) in g["interiors"]]
    all_exts = [xy for g in groups for xy in g["exteriors"]]

    before_buckets = scan_esm_stack(before_esms, all_ints, all_exts)
    after_buckets = scan_esm_stack(after_esms, all_ints, all_exts)

    group_rows = []
    cell_rows = []
    totals_before = {k: 0 for k in ("refs",) + FAMILIES}
    totals_after = {k: 0 for k in ("refs",) + FAMILIES}

    for g in groups:
        g_before_refs = []
        g_after_refs = []
        member_ids = []
        for m, cid, fo4_cid in g["interiors"]:
            b_items = before_buckets.get(("interior", (m, cid)), [])
            a_items = after_buckets.get(("interior", (m, cid)), [])
            g_before_refs.extend(b_items)
            g_after_refs.extend(a_items)
            cid_hex = f"0x{cid:06X}"
            fo4_hex = f"0x{fo4_cid:06X}" if fo4_cid is not None else None
            member_ids.append(cid_hex)
            tb, ta = tally_refs(b_items), tally_refs(a_items)
            cell_rows.append({
                "group": g["group"],
                "kind": "CELL_INT",
                "target_id": f"{m}:{cid:06X}",
                "source_fo4_cell_id": fo4_hex,
                "before": tb,
                "after": ta,
                "delta": {f: ta[f] - tb[f] for f in FAMILIES},
            })
        for gx, gy in g["exteriors"]:
            b_items = before_buckets.get(("exterior", (gx, gy)), [])
            a_items = after_buckets.get(("exterior", (gx, gy)), [])
            g_before_refs.extend(b_items)
            g_after_refs.extend(a_items)
            grid_label = f"ext({gx},{gy})"
            member_ids.append(grid_label)
            tb, ta = tally_refs(b_items), tally_refs(a_items)
            cell_rows.append({
                "group": g["group"],
                "kind": "CELL_EXT",
                "target_id": grid_label,
                "grid": [gx, gy],
                "before": tb,
                "after": ta,
                "delta": {f: ta[f] - tb[f] for f in FAMILIES},
            })

        gb = tally_refs(g_before_refs)
        ga = tally_refs(g_after_refs)
        for k in totals_before:
            totals_before[k] += gb[k]
            totals_after[k] += ga[k]
        group_rows.append({
            "group": g["group"],
            "cells": member_ids,
            "before": gb,
            "after": ga,
            "delta": {f: ga[f] - gb[f] for f in FAMILIES},
        })

    total_delta = {f: totals_after[f] - totals_before[f] for f in FAMILIES}
    non_decreasing = all(
        row["after"][f] >= row["before"][f]
        for row in group_rows
        for f in FAMILIES
    )
    return {
        "schema_version": 1,
        "before_plugins": [os.path.basename(p) for p in before_esms],
        "after_plugins": [os.path.basename(p) for p in after_esms],
        "groups": group_rows,
        "cells": cell_rows,
        "totals": {
            "before": totals_before,
            "after": totals_after,
            "delta": total_delta,
        },
        "non_decreasing": non_decreasing,
    }


def format_diff_table(rep):
    lines = [
        "| Group | Cells | XESP (B -> A) | XLOC (B -> A) | XLKR (B -> A) | XAPR (B -> A) | XTEL (B -> A) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for g in rep["groups"]:
        b, a, d = g["before"], g["after"], g["delta"]
        cells_txt = ", ".join(g["cells"])
        cols = [
            f"{b[f]} -> {a[f]} ({d[f]:+d})"
            for f in FAMILIES
        ]
        lines.append(f"| `{g['group']}` | `{cells_txt}` | " + " | ".join(cols) + " |")
    tb, ta, td = rep["totals"]["before"], rep["totals"]["after"], rep["totals"]["delta"]
    tcols = [f"**{tb[f]} -> {ta[f]} ({td[f]:+d})**" for f in FAMILIES]
    lines.append("| **Total** | **all target cells** | " + " | ".join(tcols) + " |")
    return "\n".join(lines)


def cmd_diff_counts(args):
    default_mod = os.path.basename(args.after[0]).lower() if len(args.after) == 1 else "fo4port.esm"
    groups = build_target_groups(
        cells_arg=args.cells,
        preset=args.preset,
        fo4_esm=args.fo4,
        port_ids_path=args.port_ids,
        default_int_mod=default_mod,
    )
    rep = diff_counts(args.before, args.after, groups)
    print(format_diff_table(rep))
    if args.out:
        save_json(args.out, rep)
    ok = rep["non_decreasing"]
    if args.require_positive_delta and sum(rep["totals"]["delta"].values()) <= 0:
        ok = False
    td = rep["totals"]["delta"]
    print(
        f"{'PASS' if ok else 'FAIL'}  diff-counts: "
        f"XESP={td['xesp']:+d}, XLOC={td['xloc']:+d}, XLKR={td['xlkr']:+d}, "
        f"XAPR={td['xapr']:+d}, XTEL={td['xtel']:+d}"
    )
    return 0 if ok else 1


# --------------------------------------------------------------------------- reconvert (single-cell PC card recipe)

def _resolve_manifest(port_dir, explicit_manifest):
    if explicit_manifest:
        if not os.path.isfile(explicit_manifest):
            sys.exit(f"manifest not found: {explicit_manifest}")
        return explicit_manifest
    parent_dir = os.path.dirname(os.path.abspath(port_dir))
    for cand in (
        os.path.join(port_dir, "manifest.json"),
        os.path.join(parent_dir, "manifest.json"),
        os.path.join(parent_dir, "door_anim", "manifest_flags.json"),
        os.path.join(parent_dir, "door_anim", "manifest_sounds.json"),
        os.path.join(parent_dir, "door_anim", "manifest_plan.json"),
    ):
        if os.path.isfile(cand):
            return cand
    sys.exit(f"manifest.json not found in {port_dir} or parent directory; pass --manifest <manifest.json>")


def cmd_reconvert(args):
    final = os.path.abspath(args.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: reconvert into a new folder")
    port_dir = os.path.abspath(args.port_dir)
    port_esm = os.path.join(port_dir, "FO4Port.esm")
    port_ids_path = os.path.join(port_dir, "formids.json")
    for req in (args.fo4, args.starfield, port_esm, port_ids_path):
        if not os.path.isfile(req):
            sys.exit(f"missing input file: {req}")

    manifest_path = _resolve_manifest(port_dir, args.manifest)
    fo4_cid = parse_hex_id(args.cell)
    edid_map = lookup_fo4_interior_edids(args.fo4, [fo4_cid])
    if fo4_cid not in edid_map:
        sys.exit(f"interior CELL 0x{fo4_cid:06X} not found in {os.path.basename(args.fo4)}")
    cell_edid = edid_map[fo4_cid]

    with open(port_ids_path, encoding="utf-8") as f:
        port_ids = json.load(f)
    pids_ci = {k.lower(): int(v) for k, v in port_ids.items()}
    port_cell_key = f"cell:fo4port_{cell_edid}".lower()
    if port_cell_key not in pids_ci:
        sys.exit(f"CELL 0x{fo4_cid:06X} is not in {port_ids_path}")
    port_cell_id = pids_ci[port_cell_key]

    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)

    # 1. Export target cell from Fallout4.esm (schema v3).
    fo4_export_dll = build_dotnet_project("Fo4Export")
    export_json = os.path.join(work, f"cell_{fo4_cid:06X}.json")
    run_cmd(["dotnet", fo4_export_dll, args.fo4, "export", cell_edid, export_json])

    # 2. Copy baseline formids.json + optional sidecars into out so FormIDs stay 100% stable.
    shutil.copy2(port_ids_path, os.path.join(out, "formids.json"))
    for sidecar in ("lighting.json", "locations.json"):
        src_sc = os.path.join(port_dir, sidecar)
        if os.path.isfile(src_sc):
            shutil.copy2(src_sc, os.path.join(out, sidecar))
    src_promote = os.path.join(port_dir, "promote.json")
    if os.path.isfile(src_promote):
        with open(src_promote, encoding="utf-8") as f:
            pdoc = json.load(f)
        if pdoc.get("starfield_esm"):
            pdoc["starfield_esm"] = os.path.abspath(args.starfield)
        save_json(os.path.join(out, "promote.json"), pdoc)

    # 3. Run PluginSpike with --interactive-fidelity and --port-reference=<baseline FO4Port.esm>.
    spike_dll = build_dotnet_project("PluginSpike")
    env = os.environ.copy()
    env["STARFIELD_DATA"] = os.path.dirname(os.path.abspath(args.starfield))
    for hook in ("FO4PORT_DOOR_MODEL", "FO4PORT_DOOR_BASE", "FO4PORT_DOORTEST"):
        env.pop(hook, None)
    run_cmd(
        [
            "dotnet",
            spike_dll,
            out,
            manifest_path,
            export_json,
            "--interactive-fidelity",
            f"--port-reference={port_esm}",
        ],
        env=env,
    )

    # 4. Run InteractiveFidelity check on the re-converted FO4Port.esm.
    ifid_dll = build_dotnet_project("InteractiveFidelity")
    reconverted_esm = os.path.join(out, "FO4Port.esm")
    check_json = os.path.join(out, "fidelity_check.json")
    chk = run_cmd(
        [
            "dotnet",
            ifid_dll,
            "check",
            reconverted_esm,
            "--starfield",
            args.starfield,
            "--port-reference",
            port_esm,
            "--report",
            check_json,
        ],
        check=False,
    )
    sys.stdout.write(chk.stdout)
    if chk.returncode != 0:
        sys.stderr.write(chk.stderr)
        sys.exit(f"InteractiveFidelity check failed ({chk.returncode}); attempt kept in {out}")

    # 5. Diff before/after counts on the re-converted cell (counts and hex IDs only).
    groups = [{
        "group": f"cell_0x{fo4_cid:06X}",
        "interiors": [("fo4port.esm", port_cell_id, fo4_cid)],
        "exteriors": [],
    }]
    diff_rep = diff_counts([port_esm], [reconverted_esm], groups)
    save_json(os.path.join(out, "diff_counts.json"), diff_rep)

    # Remove temporary export JSON (which holds FO4 record dumps) so <out> stays game-text-free.
    shutil.rmtree(work)
    os.replace(out, final)

    print(format_diff_table(diff_rep))
    td = diff_rep["totals"]["delta"]
    ok = diff_rep["non_decreasing"] and sum(td.values()) > 0
    print(
        f"{'PASS' if ok else 'FAIL'}  reconvert 0x{fo4_cid:06X} -> FO4Port.esm:0x{port_cell_id:06X}: "
        f"XESP={td['xesp']:+d}, XLOC={td['xloc']:+d}, XLKR={td['xlkr']:+d}, "
        f"XAPR={td['xapr']:+d}, XTEL={td['xtel']:+d}"
    )
    return 0 if ok else 1


# --------------------------------------------------------------------------- stage / verify / fold

def input_pins(port_esm, port_ids, core_esm, core_ids):
    return {
        "FO4Port.esm": sha256(port_esm),
        "port_formids.json": sha256(port_ids),
        "FO4TerrainCore.esm": sha256(core_esm),
        "core_formids.json": sha256(core_ids),
    }


def cmd_stage(args):
    final = os.path.abspath(args.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    for req in (args.fo4, args.starfield, args.port, args.port_ids, args.core, args.core_ids, args.compiler, args.content_resources):
        if not os.path.isfile(req):
            sys.exit(f"missing input file: {req}")

    pre = precheck_zip(args.content_resources)
    if not pre["ok"]:
        sys.exit(f"precheck failed; missing declarations: {pre['missing']}")

    before_pins = input_pins(args.port, args.port_ids, args.core, args.core_ids)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)

    if args.interior_cells or args.exterior_cells:
        int_cells = [s.strip() for s in (args.interior_cells or "").split(",") if s.strip()]
        ext_cells = []
        if args.exterior_cells:
            for pair in args.exterior_cells.split(";"):
                if pair.strip():
                    gx_s, gy_s = pair.strip().split(",", 1)
                    ext_cells.append([int(gx_s), int(gy_s)])
    else:
        int_cells = [f"{cid:06X}" for g in CF5_PRESET_GROUPS for cid in g["fo4_interiors"]]
        ext_cells = [[gx, gy] for g in CF5_PRESET_GROUPS for (gx, gy) in g["exterior_grids"]]

    params_path = os.path.join(work, "fidelity_params.json")
    save_json(
        params_path,
        {
            "plugin": PLUGIN,
            "fo4_esm": os.path.abspath(args.fo4),
            "starfield_esm": os.path.abspath(args.starfield),
            "core_esm": os.path.abspath(args.core),
            "core_formids": os.path.abspath(args.core_ids),
            "port_esm": os.path.abspath(args.port),
            "port_formids": os.path.abspath(args.port_ids),
            "out_dir": out,
            "interior_cells": int_cells,
            "exterior_cells": ext_cells,
        },
    )

    ifid_dll = build_dotnet_project("InteractiveFidelity")
    b_res = run_cmd(["dotnet", ifid_dll, "build", params_path])
    sys.stdout.write(b_res.stdout)

    plugin_path = os.path.join(out, PLUGIN)
    check_report_path = os.path.join(out, "fidelity_check.json")
    c_res = run_cmd(
        [
            "dotnet",
            ifid_dll,
            "check",
            plugin_path,
            "--starfield",
            args.starfield,
            "--core",
            args.core,
            "--port",
            args.port,
            "--report",
            check_report_path,
        ],
        check=False,
    )
    sys.stdout.write(c_res.stdout)
    if c_res.returncode != 0:
        sys.stderr.write(c_res.stderr)
        sys.exit(f"InteractiveFidelity check failed ({c_res.returncode}); attempt kept in {out}")

    pex_path = compile_chain_script(args.compiler, args.content_resources, work, os.path.join(out, "Data", "Scripts"))
    shutil.copy2(os.path.join(HERE, f"{CHAIN_SCRIPT}.psc"), os.path.join(out, f"{CHAIN_SCRIPT}.psc"))

    groups = build_target_groups(preset="cf5-targets", fo4_esm=args.fo4, port_ids_path=args.port_ids)
    counts_rep = diff_counts([args.core, args.port], [args.core, args.port, plugin_path], groups)
    save_json(os.path.join(out, "before_after_counts.json"), counts_rep)

    now_pins = input_pins(args.port, args.port_ids, args.core, args.core_ids)
    drift = [f"{k}: {before_pins[k]} -> {now_pins[k]}" for k in before_pins if before_pins[k] != now_pins[k]]
    if drift:
        sys.exit("input changed during stage (" + "; ".join(drift) + f"); attempt kept in {out}")

    shutil.rmtree(work)

    plan = {
        "kind": "interactive-fidelity",
        "plugin": PLUGIN,
        "plugin_sha256": sha256(plugin_path),
        "scripts": {CHAIN_SCRIPT: sha256(pex_path)},
        "checked_against_sha256": {
            "FO4Port.esm": before_pins["FO4Port.esm"],
            "FO4TerrainCore.esm": before_pins["FO4TerrainCore.esm"],
        },
        "formids_sha256": {
            "port_formids.json": before_pins["port_formids.json"],
            "core_formids.json": before_pins["core_formids.json"],
        },
        "totals_delta": counts_rep["totals"]["delta"],
    }
    save_json(os.path.join(out, "plan.json"), plan)

    readme_text = (
        f"Converter interactive fidelity stage ({datetime.date.today().isoformat()}). docs/slice/converter-interactive-fidelity.md\n"
        f"{PLUGIN} (sha256 {plan['plugin_sha256']}) + Data/Scripts/{CHAIN_SCRIPT}.pex.\n"
        f"Masters: Starfield.esm, FO4TerrainCore.esm, FO4Port.esm.\n"
        f"Checked against SHA-256: {json.dumps(plan['checked_against_sha256'])}.\n"
        f"Measured delta across CF-5 target cells: {json.dumps(plan['totals_delta'])}.\n"
        f"Fold into a clean core set with make_interactive_fidelity.py fold, then verify before install.\n"
    )
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme_text)

    os.replace(out, final)
    print(format_diff_table(counts_rep))
    print(f"staged {final}: {PLUGIN}, {CHAIN_SCRIPT}.pex, fidelity_check.json, before_after_counts.json, plan.json, README.txt")
    return 0


def load_plan(plan_path):
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    req = ("plugin", "plugin_sha256", "scripts", "checked_against_sha256")
    missing = [k for k in req if k not in plan]
    if missing or plan.get("kind") != "interactive-fidelity":
        sys.exit(f"{plan_path} is not an interactive-fidelity plan (missing {missing})")
    return plan


def verify_dir(exp_dir, plan, port_esm=None, core_esm=None):
    problems = []

    def check_hash(label, path, expected):
        if not path or not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        else:
            actual = sha256(path)
            if actual != expected:
                problems.append(f"{label}: {path} sha256 {actual} != expected {expected}")

    check_hash("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    for sname, ssha in plan["scripts"].items():
        check_hash(f"script {sname}", os.path.join(exp_dir, "Data", "Scripts", f"{sname}.pex"), ssha)

    pinned = plan["checked_against_sha256"]
    for mname, given in (("FO4Port.esm", port_esm), ("FO4TerrainCore.esm", core_esm)):
        in_dir = os.path.join(exp_dir, mname)
        check_hash(f"master {mname}", in_dir if os.path.isfile(in_dir) else given, pinned[mname])

    # If verifying a standalone stage directory itself (holds plan.json and no FO4TerrainCore.esm), reject extra .esm/.pex files.
    if os.path.isfile(os.path.join(exp_dir, "plan.json")) and not os.path.isfile(os.path.join(exp_dir, "FO4TerrainCore.esm")):
        esms = sorted(fn for fn in os.listdir(exp_dir) if fn.lower().endswith(".esm"))
        if esms != [plan["plugin"]]:
            problems.append(f"stage esm set: expected {[plan['plugin']]}, found {esms}")
        scripts_dir = os.path.join(exp_dir, "Data", "Scripts")
        if os.path.isdir(scripts_dir):
            pexs = sorted(fn for fn in os.listdir(scripts_dir) if fn.lower().endswith(".pex"))
            want_pexs = sorted(f"{s}.pex" for s in plan["scripts"])
            if pexs != want_pexs:
                problems.append(f"stage pex set: expected {want_pexs}, found {pexs}")

    return problems


def cmd_verify(args):
    plan = load_plan(args.plan)
    problems = verify_dir(args.exp_dir, plan, args.port, args.core)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def core_plugins_order(core_dir, readme_text, dropped_esms_lower):
    present = sorted(
        fn for fn in os.listdir(core_dir)
        if fn.lower().endswith(".esm") and fn.lower() not in dropped_esms_lower
    )
    if not present:
        sys.exit(f"fold refused: {core_dir} holds no .esm")
    m = INSTALL_LINE_RE.search(readme_text)
    if not m:
        return present
    listed = [p for p in m.group("plugins").split(",") if p and p.lower() not in dropped_esms_lower]
    if sorted(listed) != present:
        sys.exit(f"fold refused: {core_dir} README lists {listed} but folder holds {present}")
    return listed


def install_command(plugins):
    return f"scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(plugins)} --pack"


def build_folded_readme(core_readme, stage_readme, plugins, plugin_name):
    def widen_line(line):
        m = INSTALL_LINE_RE.search(line)
        if not m:
            return line
        return line[:m.start("plugins")] + ",".join(plugins) + line[m.end("plugins"):]

    lines = [widen_line(ln) for ln in core_readme.splitlines()]
    lines += [
        "",
        f"==== {plugin_name} folded in ({datetime.date.today().isoformat()}) ====",
        stage_readme.rstrip("\n"),
        "",
        f"Install (game closed): every plugin listed so exp_install.py activates {plugin_name} after its masters:",
        "  " + install_command(plugins),
    ]
    return "\n".join(lines) + "\n"


def cmd_fold(args):
    final = os.path.abspath(args.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(args.stage, "plan.json"))
    plugin_name = plan["plugin"]

    dropped_esms = set()
    dropped_pexs = set()
    if args.clean_prior:
        dropped_esms.add(plugin_name.lower())
        for sname in plan["scripts"]:
            dropped_pexs.add(f"data/scripts/{sname.lower()}.pex")
    else:
        if os.path.exists(os.path.join(args.core_dir, plugin_name)):
            sys.exit(f"fold refused: {args.core_dir} already holds {plugin_name} (pass --clean-prior or use a clean core set)")
        for sname in plan["scripts"]:
            if os.path.exists(os.path.join(args.core_dir, "Data", "Scripts", f"{sname}.pex")):
                sys.exit(f"fold refused: {args.core_dir} already holds Data/Scripts/{sname}.pex")

    core_readme = read_text(os.path.join(args.core_dir, "README.txt"))
    stage_readme = read_text(os.path.join(args.stage, "README.txt"))
    plugins = core_plugins_order(args.core_dir, core_readme, dropped_esms) + [plugin_name]

    out = new_partial(final, create=True)
    # Hardlink/copy every file from core_dir EXCEPT README.txt (and stripped prior fidelity files when --clean-prior).
    for dp, _, fns in os.walk(args.core_dir):
        rel_dir = os.path.relpath(dp, args.core_dir)
        dst_dir = out if rel_dir == "." else os.path.join(out, rel_dir)
        os.makedirs(dst_dir, exist_ok=True)
        for fn in fns:
            src_file = os.path.join(dp, fn)
            rel_posix = os.path.relpath(src_file, args.core_dir).replace("\\", "/").lower()
            if rel_posix == "readme.txt" or rel_posix in dropped_esms or rel_posix in dropped_pexs:
                continue
            link_or_copy(src_file, os.path.join(dst_dir, fn))

    # Write README.txt as a brand-new file so core_dir/README.txt is never mutated through a hardlink.
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_folded_readme(core_readme, stage_readme, plugins, plugin_name))

    shutil.copy2(os.path.join(args.stage, plugin_name), os.path.join(out, plugin_name))
    for sname in plan["scripts"]:
        dst_pex = os.path.join(out, "Data", "Scripts", f"{sname}.pex")
        os.makedirs(os.path.dirname(dst_pex), exist_ok=True)
        shutil.copy2(os.path.join(args.stage, "Data", "Scripts", f"{sname}.pex"), dst_pex)

    problems = verify_dir(out, plan, args.port, args.core)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} verification problem(s); attempt kept in {out}")

    os.replace(out, final)
    print(f"folded {final}: {plugin_name} + {len(plan['scripts'])} script(s); verify: ok")
    print("install (game closed): " + install_command(plugins))
    return 0


# --------------------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description="CF-5 part 1 converter interactive fidelity driver")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_pre = sub.add_parser("precheck", help="check FO4SF_ActivateChain.psc declarations against ContentResources.zip")
    sp_pre.add_argument("--content-resources", required=True)
    sp_pre.add_argument("--out")
    sp_pre.set_defaults(func=cmd_precheck)

    for name in ("diff-counts", "measure"):
        sp_dc = sub.add_parser(name, help="diff before/after subrecord counts on target cells")
        sp_dc.add_argument("--before", nargs="+", required=True)
        sp_dc.add_argument("--after", nargs="+", required=True)
        sp_dc.add_argument("--cells", help="target cell spec, e.g. FO4Port.esm:00BA4B or g1=FO4Port.esm:0011F3+ext:-13,12")
        sp_dc.add_argument("--preset", choices=("cf5-targets",))
        sp_dc.add_argument("--fo4", help="optional Fallout4.esm to resolve preset interior cell IDs dynamically")
        sp_dc.add_argument("--port-ids", help="optional port formids.json to resolve preset interior cell IDs")
        sp_dc.add_argument("--out", help="optional JSON report output path")
        sp_dc.add_argument("--require-positive-delta", action="store_true")
        sp_dc.set_defaults(func=cmd_diff_counts)

    sp_rc = sub.add_parser("reconvert", help="re-export and re-convert one interior cell with interactive fidelity and diff counts")
    sp_rc.add_argument("--fo4", required=True, help="path to Fallout4.esm")
    sp_rc.add_argument("--starfield", required=True, help="path to Starfield.esm")
    sp_rc.add_argument("--port-dir", required=True, help="baseline port folder holding FO4Port.esm and formids.json")
    sp_rc.add_argument("--manifest", help="optional manifest.json path (defaults to <port-dir>/manifest.json or parent)")
    sp_rc.add_argument("--cell", required=True, help="FO4 interior cell hex FormID, e.g. 0x000BB078")
    sp_rc.add_argument("--out", required=True, help="new output folder")
    sp_rc.set_defaults(func=cmd_reconvert)

    sp_st = sub.add_parser("stage", help="build FO4SFInteractiveFidelity.esm, compile script, check, and measure counts")
    sp_st.add_argument("--out", required=True)
    sp_st.add_argument("--fo4", required=True)
    sp_st.add_argument("--starfield", required=True)
    sp_st.add_argument("--port", required=True)
    sp_st.add_argument("--port-ids", required=True)
    sp_st.add_argument("--core", required=True)
    sp_st.add_argument("--core-ids", required=True)
    sp_st.add_argument("--compiler", required=True)
    sp_st.add_argument("--content-resources", required=True)
    sp_st.add_argument("--interior-cells", help="comma-separated FO4 interior cell hex IDs (default: CF-5 preset)")
    sp_st.add_argument("--exterior-cells", help="semicolon-separated x,y Starfield exterior grids (default: CF-5 preset)")
    sp_st.set_defaults(func=cmd_stage)

    sp_vf = sub.add_parser("verify", help="verify staged or folded interactive-fidelity folder against plan.json")
    sp_vf.add_argument("--exp-dir", required=True)
    sp_vf.add_argument("--plan", required=True)
    sp_vf.add_argument("--port")
    sp_vf.add_argument("--core")
    sp_vf.set_defaults(func=cmd_verify)

    sp_fd = sub.add_parser("fold", help="fold staged interactive-fidelity plugin + script into a core experiment folder")
    sp_fd.add_argument("--stage", required=True)
    sp_fd.add_argument("--core-dir", required=True)
    sp_fd.add_argument("--out", required=True)
    sp_fd.add_argument("--port")
    sp_fd.add_argument("--core")
    sp_fd.add_argument("--clean-prior", action="store_true", help="replace an earlier folded FO4SFInteractiveFidelity.esm")
    sp_fd.set_defaults(func=cmd_fold)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
