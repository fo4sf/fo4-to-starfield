"""Stage the planet probe (docs/planet/planet-probe.md): our own star system and planet, a 3 x 3-cell test world on
it with six test references, and the script that logs where they are in game. Offline, from the user's own files.

usage:
  python make_planet_probe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native and event FO4SF_PlanetProbeQuest.psc calls, looked up in Starfield's base
      sources (Scripts/Source of ContentResources.zip) with the scripts each extends; exit 1 when one is missing.
  python make_planet_probe.py census --data <Starfield Data> [--out <census.json>]
      read only: the records the probe copies and every fact the plan leans on (census.py), printed and saved.
  python make_planet_probe.py stage --data <Starfield Data> --out <dir> [--content-resources <zip>] [--compiler <exe>]
                                    [--world-biome planet|keep] [--no-merge-probe] [--mask-writer texconv|builtin]
      builds in a new <out>.partial-<time>-<pid>, renamed to <out> only when every step passed (an existing <out> is
      refused):
        1. the census (census.json; a record the probe copies that is missing or renamed stops the stage);
        2. FO4SFPlanet.esm: our star, its system / planet / orbit / surface locations and the planet (records.py),
           cloned from Starfield.esm's Sol and Jemison, checked against every star of Starfield.esm and the built-in
           Creations, then read back (check_master);
        3. the test world's terrain: Data/Terrain/FO4SF_PlanetProbeWorld.btd (flat ground at 10 m and a 25 m block,
           land textures from the user's terrain/landingoverlay01.btd) and its overlay mask;
        4. probe_params.json, then dotnet/PlanetProbe build and its Mutagen read-back (offline_check_mutagen.txt):
           FO4SFPlanetProbe.esm;
        5. FO4SFPlanetProbe_Reg.esm: our planet registering the test world (records.py build_registration);
        6. the biome map: Jemison's .biom out of the user's "Starfield - PlanetData.ba2", under our planet's name,
           in both candidate folders (biom.py);
        7. the Papyrus compile of FO4SF_PlanetProbeQuest.psc into Data/Scripts;
        8. FO4SFMergeProbe.esm (dotnet/MergeProbe: a persistent marker in vanilla LC172World), unless
           --no-merge-probe;
        9. the raw check of the probe plugin (probe.py check_plugin) and offline_check.json; plan.json (every staged
           file's SHA-256, the arrivals, the ids the log reader names) and README.txt.
  python make_planet_probe.py check --stage <dir> [--data <Starfield Data>]
      the install preflight: every staged file is the one plan.json pins, and the three plugins pass their raw checks
      again; with --data, Starfield.esm is still the file the stage cloned from. Exit 1 on any mismatch: re-stage.
  python make_planet_probe.py log [--file <FO4SFPlanetProbe.0.log>] [--stage <dir>] [--out <summary.json>]
      the run's user log as arrivals and a verdict per test reference (probe_log.py); exit 0 when an arrival on our
      planet has all four readings.
Nothing here installs anything: scripts/planet/planet_probe_install.py does, on the owner's line, game closed.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
from fo4sf import ba2, btd, overlay  # noqa: E402
from fo4sf.planet import biom, census, esm, probe, probe_log, records  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "PlanetProbe")
MERGE_PROJECT = os.path.join(REPO, "dotnet", "MergeProbe")
MERGE_PLUGIN = "FO4SFMergeProbe.esm"
MERGE_ID = 0x800
MERGE_OFFSET = 3.0                       # MergeProbe's default: the vanilla marker's position + (3, 0, 0)
SCRIPT = probe.SCRIPT
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
TERRAIN_ARCHIVE = "Starfield - Terrain01.ba2"
BTD_TEMPLATE = "terrain/landingoverlay01.btd"
STAY_S = 75                              # the last reading is 60 s after an arrival
# the natives and events the probe script uses, by the base script that must declare them (precheck)
NATIVES = {
    "Debug": ["OpenUserLog", "TraceUser"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "Location": ["IsChild", "GetCurrentPlanet", "IsLoaded", "CountActors"],
    "ObjectReference": ["GetWorldSpace", "GetParentCell", "GetCurrentLocation", "GetEditorLocation",
                        "GetCurrentPlanet", "GetPositionX", "GetPositionY", "GetPositionZ", "Is3DLoaded",
                        "IsDisabled", "GetDistance"],
    "Planet": ["GetGravity", "GetDayLength", "GetTemperature", "GetPressure", "GetType", "GetAtmosphereType",
               "GetLocation"],
    "Quest": ["GetFormID"],
    "ScriptObject": ["StartTimer", "OnTimer", "OnInit"],
    "Utility": ["GetCurrentRealTime"],
}


def run(cmd, cwd=None, check=True):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        if check:
            sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


# ------------------------------------------------------------------------------------------------ precheck
def has_function(source, name):
    """True when a base script's source declares Function <name> (native or not) or Event <name>."""
    return re.search(rf"^\s*(?:[\w\[\]:]+\s+)?(?:Function|Event)\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


def parent_of(source):
    m = re.search(r"^\s*Scriptname\s+[\w:]+\s+extends\s+([\w:]+)", source, re.M | re.I)
    return m.group(1) if m else None


def declares(sources, base, name, depth=8):
    """True when base's source, or one it extends, declares name (the compiler resolves an inherited call the same
    way: Quest extends Form)."""
    seen = set()
    while base and base.lower() not in seen and len(seen) < depth:
        seen.add(base.lower())
        source = sources.get(base.lower(), "")
        if has_function(source, name):
            return True
        base = parent_of(source)
    return False


def base_sources(zip_path):
    """{script name lower case: source} of Scripts/Source/*.psc (top level) in ContentResources.zip."""
    out = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and parts[2].lower().endswith(".psc"):
                out[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    return out


def precheck_sources(sources):
    found = {f"{b}.{f}": declares(sources, b, f) for b, fs in NATIVES.items() for f in fs}
    return {"natives": found, "missing": [k for k, ok in found.items() if not ok], "scripts": len(sources)}


def precheck(a):
    r = precheck_sources(base_sources(a.content_resources))
    for k, ok in r["natives"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {SCRIPT}: {k}")
    if a.out:
        write_json(a.out, r)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} missing; do not stage"))
    return 0 if not r["missing"] else 1


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file (make_newgame.py's)."""
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, name, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    r = run([compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
            cwd=HERE, check=False)
    pex = os.path.join(out_dir, name + ".pex")
    if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile of {name}.psc did not produce {name}.pex")
    return pex


# ------------------------------------------------------------------------------------------------ census
def census_cmd(a):
    rep = census.run(os.path.join(a.data, "Starfield.esm"), a.data)
    text = json.dumps(rep, indent=1)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


# ------------------------------------------------------------------------------------------------ stage
def new_partial(final):
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    os.makedirs(out)
    return out


def input_pins(data):
    """Starfield.esm's SHA-256 (the stage clones its records) and the size and time of the archives it reads."""
    sf = os.path.join(data, "Starfield.esm")
    pins = {"Starfield.esm": {"sha256": sha256(sf), "bytes": os.path.getsize(sf)}}
    for name in (TERRAIN_ARCHIVE, biom.ARCHIVE):
        p = os.path.join(data, name)
        st = os.stat(p)
        pins[name] = {"bytes": st.st_size, "mtime": int(st.st_mtime)}
    return pins


def world_biome(rep, choice):
    """(plugin, local id) of the biome the test world names, and why. "planet": New Atlantis's own biome when it is
    one of Jemison's (a vanilla world on that planet names it), else the planet's first biome; "keep": None (the
    template world's Mars biome stays, a discriminator like the climate)."""
    if choice == "keep":
        return None, "the template world's biome (Mars) kept"
    biomes = [int(b, 16) for b in rep.get("planet_biomes") or []]
    if not biomes:
        raise SystemExit("the census found no biome on the template planet")
    na = rep.get("new_atlantis") or {}
    na_biome = (na.get("world") or {}).get("biome")
    if na.get("biome_in_planet_biomes") and na_biome:
        return ("Starfield.esm", int(na_biome, 16)), "New Atlantis's biome, one of Jemison's"
    return ("Starfield.esm", biomes[0]), "Jemison's first biome (New Atlantis names none of its biomes)"


def stage_files(out):
    """{path relative to the stage, "/" separated: SHA-256} of the plugins and every file under Data/."""
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


def known_ids(rep):
    """{label: hex id} of the vanilla records the log reader names (Starfield.esm ids load at index 00)."""
    out = {"LC172World (Mars)": f"{census.LC172_WORLD:08X}", "NewAtlantis (Jemison)": f"{census.NEW_ATLANTIS:08X}",
           "Mars": f"{census.MARS_PLANET:08X}"}
    tp = rep.get("template_planet") or {}
    if tp.get("formid"):
        out["Jemison"] = tp["formid"] if len(tp["formid"]) == 8 else f"{int(tp['formid'], 16):08X}"
    tj = (rep.get("temp_jemison") or {}).get("world") or {}
    if tj.get("formid"):
        out["TempJemisonWorld"] = tj["formid"]
    return out


def arrivals(rep):
    """The session's arrivals in order: the LC172 control first (the merge seen in vanilla's own world, before the
    new star system is tried), then our planet, then the census's TempJemisonWorld and New Atlantis cells."""
    extra = census.arrivals(rep)
    out = [dict(extra[0], order=1)]
    out.append({"label": "probe", "coc": probe.SPAWN_EDID, "order": 2,
                "why": "our planet's test world: which of T1..T6 is in the player's world"})
    for i, e in enumerate(extra[1:], 3):
        out.append(dict(e, order=i))
    for e in out:
        e["stay_s"] = STAY_S
    return out


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    sf_path = os.path.join(a.data, "Starfield.esm")
    before = input_pins(a.data)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)

    # 1. census
    rep = census.run(sf_path, a.data)
    write_json(os.path.join(out, "census.json"), rep)
    stars = rep.get("plugin_stars") or {}
    other = [(s, sid, tuple(p) if p else None) for s, sid, p in stars.get("stars", [])]
    if stars.get("unreadable"):
        print(f"note: the star check could not read {stars['unreadable']} (their stars, if any, are not checked)")

    # 2. the planet master
    with esm.Plugin(sf_path) as sf:
        w, master_report = records.build_master(sf, {}, other)
    master_path = os.path.join(out, records.MASTER)
    w.write(master_path)
    problems, master_summary = records.check_master(master_path, star_name=master_report["star"]["name"],
                                                    planet_name=master_report["planet"]["name"])
    if problems:
        sys.exit(f"{records.MASTER} check: {problems}; attempt kept in {out}")
    write_json(os.path.join(work, "master_report.json"), master_report)
    with esm.Plugin(master_path) as m:
        planet = next(r for r in m.records("PNDT") if r.formid == (1 << 24) | records.PLANET)
        our_biomes = [b["biome"] for b in records.biomes(planet)]

    # 3. terrain and mask
    template = btd.read(ba2.Ba2(os.path.join(a.data, TERRAIN_ARCHIVE)).read(BTD_TEMPLATE))
    t = probe.make_btd(template)
    data = btd.write(t)
    back = btd.read(data)
    worst = float(abs(back.heights_m() - probe.heights()).max())
    if worst > (probe.HMAX - probe.HMIN) / 65535:
        sys.exit(f"BTD read back off by {worst} m; attempt kept in {out}")
    btd_path = os.path.join(out, *probe.BTD_REL.split("/"))
    os.makedirs(os.path.dirname(btd_path), exist_ok=True)
    with open(btd_path, "wb") as f:
        f.write(data)
    import overlay_records
    mask = overlay_records.write_mask(out, probe.WORLD_EDID, probe.N, a.mask_writer)
    if mask["pixels_differ"]:
        sys.exit(f"overlay mask check: {mask}; attempt kept in {out}")

    # 4. the probe plugin
    biome, biome_why = world_biome(rep, a.world_biome)
    prm = probe.params(records.DEFAULT_SYSTEM_ID, records.DEFAULT_PLANET_ID, overlay.fnam_values(t.heights_raw),
                       world_biome=biome)
    params_path = os.path.join(out, "probe_params.json")
    write_json(params_path, prm)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    run(tool + ["build", sf_path, params_path, out])
    check = run(tool + ["check", os.path.join(out, probe.PLUGIN), sf_path, params_path]).stdout
    with open(os.path.join(out, "offline_check_mutagen.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    if "all checks pass" not in check:
        sys.exit(f"PlanetProbe check did not pass; attempt kept in {out}")

    # 5. the registration
    reg = records.build_registration(master_path, probe.PLUGIN, probe.WORLD_ID)
    reg_path = os.path.join(out, records.REGISTRATION)
    reg.write(reg_path)
    reg_problems, reg_summary = records.check_registration(reg_path, probe.PLUGIN, probe.WORLD_ID, master_path)
    if reg_problems:
        sys.exit(f"{records.REGISTRATION} check: {reg_problems}; attempt kept in {out}")

    # 6. the biome map
    planet_name = master_report["planet"]["name"]
    biome_map = biom.copy_biome_map(a.data, records.DEFAULT_PLANET, planet_name, records.MASTER, out,
                                    expect_biomes=our_biomes, strict=False)
    if biome_map["biomes_match"] is False:
        print(f"note: the biome map lists {biome_map['biomes']}, the planet record {biome_map['planet_biomes']} "
              "(Jemison's own pair; kept, offline_check.json records it)")

    # 7. the script
    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, SCRIPT, src, os.path.join(out, "Data", "Scripts"))
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))

    # 8. the merge probe
    lc172 = rep.get("lc172") or {}
    marker = lc172.get("coc_marker") or {}
    merge = None
    if a.merge_probe:
        mtool = ["dotnet", "run", "-c", "Release", "--project", MERGE_PROJECT, "--"]
        run(mtool + ["build", sf_path, out])
        mcheck = run(mtool + ["check", os.path.join(out, MERGE_PLUGIN), sf_path]).stdout
        with open(os.path.join(out, "offline_check_merge.txt"), "w", encoding="utf-8") as f:
            f.write(mcheck)
        pos = marker.get("pos")
        merge = {"plugin": MERGE_PLUGIN, "id": f"{MERGE_ID:06X}",
                 "local": [pos[0] + MERGE_OFFSET, pos[1], pos[2]] if pos else None}

    # 9. the raw check, the plan
    raw_problems, raw_summary = probe.check_plugin(os.path.join(out, probe.PLUGIN), prm)
    write_json(os.path.join(out, "offline_check.json"),
               {"probe": {"problems": raw_problems, "summary": raw_summary},
                "master": {"problems": [], "summary": master_summary},
                "registration": {"problems": [], "summary": reg_summary}, "mask": mask, "biome_map": biome_map,
                "btd": {"file": probe.BTD_REL, "bytes": len(data), "worst_m": worst}})
    if raw_problems:
        sys.exit(f"{probe.PLUGIN} raw check: {raw_problems}; attempt kept in {out}")
    drift = [n for n, v in input_pins(a.data).items() if v != before[n]]
    if drift:
        sys.exit(f"an input changed during the build ({', '.join(drift)}), nothing published; attempt kept in {out}")
    shutil.rmtree(work)
    plugins = [records.MASTER, probe.PLUGIN, records.REGISTRATION] + ([MERGE_PLUGIN] if a.merge_probe else [])
    plan = {
        "kind": "planet-probe", "version": 1, "plugins": plugins, "archive": os.path.splitext(plugins[0])[0] + " - Main.ba2",
        "outputs": stage_files(out), "inputs": before, "script": {"name": SCRIPT, "pex_sha256": sha256(pex)},
        "options": {"world_biome": a.world_biome, "world_biome_id": probe.key(*biome) if biome else None,
                    "world_biome_why": biome_why, "merge_probe": a.merge_probe, "mask_writer": a.mask_writer},
        "system_id": f"{records.DEFAULT_SYSTEM_ID:#x}", "planet_id": records.DEFAULT_PLANET_ID,
        "star": master_report["star"]["name"], "planet": planet_name,
        "refs": [{"tag": r["tag"], "local_id": f"{r['id']:06X}", "kind": r["kind"], "persistent": r["persistent"],
                  "linked": r["linked"], "pos": r["pos"], "meaning": r["meaning"]} for r in prm["refs"]],
        "merge": merge, "lc172_coc": {"id": f"{probe.LC172_COC:06X}", "local": marker.get("pos"),
                                      "in_lcpr": marker.get("in_lcpr")},
        "arrivals": arrivals(rep), "known_ids": known_ids(rep),
        "log": f"<My Games>/Starfield/Logs/Script/User/{probe.LOG_NAME}.0.log"}
    write_json(os.path.join(out, "plan.json"), plan)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme(plan, final))
    os.replace(out, final)
    print(f"staged {final}: {', '.join(plugins)}, {len(plan['outputs'])} files, plan.json, README.txt")
    return 0


def readme(plan, final):
    arr = "\n".join(f"  {e['order']}. coc {e['coc']}   ({e['label']}: {e['why']}); stay {e['stay_s']} s"
                    for e in plan["arrivals"])
    return f"""Planet probe (Claude-cloud stage, {datetime.date.today().isoformat()}). docs/planet/planet-probe.md
Plugins, in load order: {', '.join(plan['plugins'])}; their Data files go into "{plan['archive']}".
Our star "{plan['star']}" (system id {plan['system_id']}) and planet "{plan['planet']}" (planet id {plan['planet_id']}),
cloned from the user's Starfield.esm (sha256 {plan['inputs']['Starfield.esm']['sha256']}): re-stage after a game update.
Install (game closed, on the owner's line in the Install thread):
  python scripts\\planet\\make_planet_probe.py check --stage "{final}" --data <Starfield>\\Data
  python scripts\\planet\\planet_probe_install.py install --dir "{final}" --starfield <Starfield>
In game, from a throwaway save (never the owner's own; do not save over one), once each, in this order:
{arr}
  At each: one screenshot after 10 s and one after 60 s.
Read the run:
  python scripts\\planet\\make_planet_probe.py log --stage "{final}"
Take it out (game closed):
  python scripts\\planet\\planet_probe_install.py uninstall --starfield <Starfield>
"""


# ------------------------------------------------------------------------------------------------ check
def load_plan(stage_dir):
    p = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(p):
        sys.exit(f"{p} missing: not a planet probe stage")
    with open(p, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != "planet-probe" or not plan.get("plugins") or not plan.get("outputs"):
        sys.exit(f"{p} is not a planet probe plan")
    return plan


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json, the raw checks again, Starfield.esm's pin."""
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
    missing = [p for p in plan["plugins"] if p not in plan["outputs"]]
    if missing:
        problems.append(f"plugins not pinned: {missing}")
    if problems:
        return problems
    prm_path = os.path.join(stage_dir, "probe_params.json")
    with open(prm_path, encoding="utf-8") as f:
        prm = json.load(f)
    problems += [f"{probe.PLUGIN}: {x}" for x in probe.check_plugin(os.path.join(stage_dir, probe.PLUGIN), prm)[0]]
    master = os.path.join(stage_dir, records.MASTER)
    problems += [f"{records.MASTER}: {x}" for x in records.check_master(
        master, star_name=plan.get("star", records.DEFAULT_STAR_NAME),
        planet_name=plan.get("planet", records.DEFAULT_PLANET_NAME))[0]]
    problems += [f"{records.REGISTRATION}: {x}" for x in records.check_registration(
        os.path.join(stage_dir, records.REGISTRATION), probe.PLUGIN, probe.WORLD_ID, master)[0]]
    if data:
        h = sha256(os.path.join(data, "Starfield.esm"))
        if h != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append(f"Starfield.esm changed since the stage (sha256 {h}): re-stage")
    return problems


def check(a):
    plan = load_plan(a.stage)
    problems = verify_stage(a.stage, plan, a.data)
    for x in problems:
        print("FAIL  " + x)
    print("check: " + ("ok" if not problems else f"{len(problems)} problem(s); do not install"))
    return 0 if not problems else 1


# ------------------------------------------------------------------------------------------------ log
def user_logs(name=probe.LOG_NAME + ".0.log"):
    """Where the game writes the probe's user log, in the order they are tried: Documents under OneDrive (the
    owner's PC: docs/spikes/combined-core-probes.md, scripts/game/snapshot.ps1), then plain Documents (as
    scripts/game/bridge_log.py's default_log)."""
    home = os.path.expanduser("~")
    return [os.path.join(home, *base, "My Games", "Starfield", "Logs", "Script", "User", name)
            for base in (("OneDrive", "Documents"), ("Documents",))]


def log(a):
    plan = load_plan(a.stage) if a.stage else None
    path = a.file
    if path is None:
        found = [p for p in user_logs() if os.path.isfile(p)]
        if not found:
            sys.exit("no probe log at " + " or ".join(user_logs()) + ": pass --file")
        path = found[0]
    elif not os.path.isfile(path):
        sys.exit(f"no probe log at {path}")
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    s = probe_log.summarize(lines, plan)
    s["log"] = path
    if a.out:
        write_json(a.out, s)
    print(f"log {path}")
    print(f"runs {s['runs']}, this run's probe load index {s.get('load_index')}")
    if s.get("chain"):
        shown = {k: probe_log.hexid(v) if k in probe_log.ID_KEYS and type(v) is int else v
                 for k, v in s["chain"].items() if k not in ("rt", "event")}
        print("chain " + " ".join(f"{k}={v}" for k, v in shown.items()))
    for arr in s["arrivals"]:
        pl = arr["player"] or {}
        print(f"arrival {arr['n']} ({arr['kind']}): world {pl.get('world', arr['world'])}, planet {pl.get('planet')}, "
              f"readings {arr['readings']}" + ("" if arr["complete"] else " (incomplete)"))
        if arr["planet"]:
            p = arr["planet"]
            print(f"  planet {p['id']}: gravity {p['gravity']} day {p['day']} temp {p['temp']} pressure {p['pressure']}")
    print("\n".join(probe_log.verdict_table(s)))
    for x in s["problems"]:
        print("PROBLEM  " + x)
    ok = any(arr["kind"] == "our planet" and arr["complete"] for arr in s["arrivals"])
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    data = os.path.join(STARFIELD, "Data")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    c = sub.add_parser("census")
    c.add_argument("--data", default=data)
    c.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--data", default=data)
    s.add_argument("--out", required=True)
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--world-biome", choices=("planet", "keep"), default="planet",
                   help="the biome the test world names: one of the planet's (default) or the template's Mars biome")
    s.add_argument("--no-merge-probe", dest="merge_probe", action="store_false",
                   help="leave FO4SFMergeProbe.esm out (the LC172 arrival then only reads vanilla's own marker)")
    s.add_argument("--mask-writer", choices=("texconv", "builtin"), default="texconv")
    k = sub.add_parser("check")
    k.add_argument("--stage", required=True)
    k.add_argument("--data", default=None)
    g = sub.add_parser("log")
    g.add_argument("--file", default=None,
                   help="the probe's user log (default: My Games under OneDrive\\Documents, else Documents)")
    g.add_argument("--stage", default=None)
    g.add_argument("--out", default=None)
    a = p.parse_args(argv)
    return {"precheck": precheck, "census": census_cmd, "stage": stage, "check": check, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
