"""Read-only probe for the engine-mechanics reference: which Papyrus scripts and functions each game ships.

    python scripts/research/engine_probe.py --sf-zip "<Starfield>\\Tools\\ContentResources.zip"
        --sf-tools "<Starfield>\\Tools" --fo4-data "<Fallout 4>\\Data" [--fo4-data <depot Data> ...]
        --out D:\\Modding\\research\\engine_probe.json

Reads zip member lists and .psc text in memory (nothing is extracted or changed). Records, per game: whether vanilla
script sources exist (Starfield ContentResources.zip; FO4 CK Data\\Scripts\\Base.zip,
Data\\Scripts\\Source\\Base\\Base.zip or loose Source\\Base),
the function and event NAMES declared in the core scripts, which of the queried script and function names exist, and
the compiler flags files. Only names go into the output, never script bodies. The output file must not be inside an
input folder.
"""
import argparse
import json
import os
import re
import sys
import zipfile

CORE = ("actor", "game", "objectreference", "quest", "referencealias", "form", "utility", "debug", "scriptobject",
        "activemagiceffect", "weapon", "armor", "perk", "location", "cell", "ui", "math", "followersscript",
        "companionactorscript")
QUERY_SCRIPTS = ("CompanionActorScript", "FollowersScript", "SQ_FollowersScript", "SQ_CompanionsScript",
                 "SQ_CrewScript", "AffinityEventScript", "WorkshopParentScript", "WorkshopScript", "PipboyScript",
                 "MQ101Script", "UI", "InputEnableLayer", "Institute_Papyrus_Flags")
QUERY_FUNCS = ("SwitchToPowerArmor", "IsInPowerArmor", "SetRace", "RewardPlayerXP", "GetPlayerFollowers",
               "SetPlayerTeammate", "IsPlayerTeammate", "SendAffinityEvent", "TryToModAffinity", "SetCommandState",
               "StartVATS", "IsInVATS", "IsPipboyOpen", "ShowPipboyPlugin", "OpenWorkshopSettlementMenu",
               "AddPerk", "SetValue", "ModValue", "GetValue", "StartCombat", "EvaluatePackage", "SetStage",
               "SetObjectiveDisplayed", "ForceRefTo", "ShowRaceMenu", "SetInChargen", "FadeOutGame",
               "IsMenuOpen", "SetTimeScale", "GetCurrentGameTime", "PlayIdle", "PlaySubGraphAnimation",
               "ChangeAnimArchetype", "SetSubGraphFloatVariable", "Say", "SayCustom", "SendStoryEvent",
               "PlaceAtMe", "MoveTo", "SetPosition", "IsInMenuMode", "FastTravel", "RequestAutoSave")
DECL = re.compile(r"^\s*(?:[\w:\[\]]+\s+)?(function|event)\s+([\w:]+)\s*\(([^)]*)\)([^;\r\n]*)", re.I)


def declarations(text):
    """Function and event names declared in one .psc, with native/global markers; no bodies."""
    out = []
    for line in text.splitlines():
        m = DECL.match(line)
        if m:
            tail = m.group(4).lower()
            out.append({"kind": m.group(1).lower(), "name": m.group(2),
                        "native": "native" in tail, "global": "global" in tail})
    return out


def scan_zip(path):
    """Script names in a source zip, and declarations of the core scripts."""
    res = {"path": path, "exists": os.path.isfile(path)}
    if not res["exists"]:
        return res
    scripts, core = {}, {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if not name.lower().endswith(".psc"):
                continue
            base = os.path.splitext(os.path.basename(name))[0]
            scripts.setdefault(base.lower(), name)
            if base.lower() in CORE and base.lower() not in core:
                text = z.read(info).decode("utf-8", "replace")
                core[base.lower()] = {"member": name, "decls": declarations(text)}
    res.update(psc_count=len(scripts), scripts=scripts, core=core)
    return res


def scan_dir(path):
    """Loose .psc under a folder (FO4 CK's extracted Data\\Scripts\\Source\\Base)."""
    res = {"path": path, "exists": os.path.isdir(path)}
    if not res["exists"]:
        return res
    scripts, core = {}, {}
    for root, _dirs, files in os.walk(path):
        for f in files:
            if not f.lower().endswith(".psc"):
                continue
            base = os.path.splitext(f)[0].lower()
            full = os.path.join(root, f)
            scripts.setdefault(base, os.path.relpath(full, path))
            if base in CORE and base not in core:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    core[base] = {"member": os.path.relpath(full, path), "decls": declarations(fh.read())}
    res.update(psc_count=len(scripts), scripts=scripts, core=core)
    return res


def source_zips(data):
    """Every Data\\Scripts\\Source\\<name>\\*.zip (the FO4 CK's Base, DLC01-06, CreationClub) with its .psc count."""
    root, out = os.path.join(data, "Scripts", "Source"), {}
    if os.path.isdir(root):
        for sub in sorted(os.listdir(root)):
            folder = os.path.join(root, sub)
            if os.path.isdir(folder):
                for f in sorted(os.listdir(folder)):
                    if f.lower().endswith(".zip"):
                        with zipfile.ZipFile(os.path.join(folder, f)) as z:
                            out[f"{sub}/{f}"] = sum(1 for n in z.namelist() if n.lower().endswith(".psc"))
    return out


def native_gap(fo4_src, sf_src):
    """Per core script: names FO4 declares that Starfield's same script does not, and the reverse count."""
    if not fo4_src.get("exists") or not sf_src.get("exists"):
        return None
    gap = {}
    for name, c in fo4_src.get("core", {}).items():
        sf_names = {d["name"].lower() for d in sf_src.get("core", {}).get(name, {}).get("decls", [])}
        fo4_names = {d["name"].lower(): d["name"] for d in c["decls"]}
        gap[name] = {"fo4_only": sorted(v for k, v in fo4_names.items() if k not in sf_names),
                     "sf_only_count": len(sf_names - set(fo4_names)),
                     "shared_count": len(sf_names & set(fo4_names)),
                     "sf_has_script": name in sf_src.get("core", {})}
    return gap


def query(src):
    """Which queried scripts and functions a scanned source has."""
    if not src.get("exists"):
        return None
    names = {d["name"].lower(): d for c in src.get("core", {}).values() for d in c["decls"]}
    return {"scripts": {s: s.lower() in src.get("scripts", {}) for s in QUERY_SCRIPTS},
            "functions": {f: f.lower() in names for f in QUERY_FUNCS}}


def inside(child, parent):
    child, parent = os.path.abspath(child).lower(), os.path.abspath(parent).lower()
    return child == parent or child.startswith(parent.rstrip("\\/") + os.sep)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sf-zip", required=True)
    ap.add_argument("--sf-tools")
    ap.add_argument("--fo4-data", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    inputs = [os.path.dirname(a.sf_zip)] + ([a.sf_tools] if a.sf_tools else []) + a.fo4_data
    if any(inside(a.out, p) for p in inputs if p):
        print("refused: --out is inside an input folder", file=sys.stderr)
        return 2
    sf = scan_zip(a.sf_zip)
    fo4 = []
    for d in a.fo4_data:
        z = scan_zip(os.path.join(d, "Scripts", "Base.zip"))
        if not z["exists"]:
            z = scan_zip(os.path.join(d, "Scripts", "Source", "Base", "Base.zip"))
        loose = scan_dir(os.path.join(d, "Scripts", "Source", "Base"))
        fo4.append({"data": d, "base_zip": z, "source_base": loose, "source_zips": source_zips(d),
                    "native_gap": native_gap(z if z["exists"] else loose, sf)})
    flags = sorted(f for f in os.listdir(a.sf_tools) if f.lower().endswith(".flg")) if a.sf_tools and \
        os.path.isdir(a.sf_tools) else []
    doc = {"starfield": sf, "starfield_query": query(sf), "starfield_flags_files": flags,
           "fo4": [{**e, "query": query(e["base_zip"]) or query(e["source_base"])} for e in fo4]}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(f"starfield sources: {sf.get('psc_count', 'missing')} .psc; flags files: {flags}")
    q = doc["starfield_query"] or {}
    print("starfield scripts present:", sorted(k for k, v in q.get("scripts", {}).items() if v))
    print("starfield functions absent:", sorted(k for k, v in q.get("functions", {}).items() if not v))
    for e in doc["fo4"]:
        print(f"fo4 {e['data']}: Base.zip {e['base_zip']['exists']} ({e['base_zip'].get('psc_count', 0)} .psc), "
              f"Source\\Base {e['source_base']['exists']}, source zips {e['source_zips']}")
        for name, g in sorted((e["native_gap"] or {}).items()):
            print(f"  {name}: shared {g['shared_count']}, fo4-only {len(g['fo4_only'])}, sf-only {g['sf_only_count']}"
                  + (f": {' '.join(g['fo4_only'])}" if g["fo4_only"] else ""))
        if e["query"]:
            print("  fo4 functions absent:", sorted(k for k, v in e["query"]["functions"].items() if not v))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
