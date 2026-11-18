"""Stage, fold, verify, and read logs for FO4SFPowerArmor.esm (docs/powerarmor/power-armor-core.md).

Subcommands:
  precheck --content-resources <ContentResources.zip> [--out <precheck.json>]
  stage    --out <stage_dir> --starfield <Starfield.esm> --compiler <PapyrusCompiler.exe>
           --content-resources <ContentResources.zip> [--control <FURN edid>] [--override-dfob] [--no-test-cell]
  fold     --core-dir <clean_core_dir> --stage <stage_dir> --out <folded_dir>
           [--hardlink] [--clean-prior] [--starfield <Starfield.esm>]
  verify   --dir <stage_or_folded_dir> [--plan <plan.json>] [--starfield <Starfield.esm>] [--no-test-cell]
  log      --file <FO4SFPACore.0.log> [--papyrus <Papyrus.0.log>]

Nothing here launches Starfield or modifies the game folder; scripts/powerarmor/power_armor_core_install.py
or scripts/game/exp_install.py handles installation only when explicitly run with the game closed.
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
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
from fo4sf.powerarmor import core_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "PowerArmorCore")
PLUGIN = "FO4SFPowerArmor.esm"
SCRIPT = "FO4SF_PowerArmorCoreQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
DEFAULT_CONTROL = "NPCChairTech03_Free_270"
FOLDED_PLAN_NAME = "power_armor_core_plan.json"
SPECIAL_AGILITY_ID = core_form_id("FO4SF_Special_Agility")
TEST_MODE_GLOBAL_ID = core_form_id("FO4SF_TestModeEnabled")
INSTALL_LINE = re.compile(r"exp_install\.py install\b.*--plugins (?P<plugins>\S+)")

REQUIRED = {
    "Actor": [
        "SetRace",
        "GetRace",
        "GetSitState",
        "EquipItem",
        "UnequipItem",
        "IsEquipped",
        "OnItemEquipped",
        "OnItemUnequipped",
        "OnSit",
        "OnPlayerLoadGame",
    ],
    "ObjectReference": [
        "GetValue",
        "SetValue",
        "ModValue",
        "AddItem",
        "RemoveItem",
        "GetItemCount",
        "MoveTo",
        "DisableNoWait",
        "EnableNoWait",
        "IsDisabled",
        "GetPositionX",
        "GetPositionY",
        "GetPositionZ",
        "GetDistance",
        "GetParentCell",
        "HasKeyword",
    ],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "GlobalVariable": ["GetValue"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer", "RegisterForRemoteEvent"],
    "Form": ["GetFormID"],
    "Math": ["Sqrt"],
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_sources(zip_path):
    """Return {lowercase script stem: source text} for Scripts/Source/*.psc in ContentResources.zip."""
    sources = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and name.lower().endswith(".psc"):
                sources[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    return sources


def precheck_sources(sources):
    req = {f"{base}.{fn}": declares(sources, base, fn) for base, fns in REQUIRED.items() for fn in fns}
    return {"required": req, "missing": [k for k, ok in req.items() if not ok]}


def precheck(a):
    if not a.content_resources or not os.path.isfile(a.content_resources):
        sys.exit("precheck requires --content-resources <ContentResources.zip>")
    res = precheck_sources(read_sources(a.content_resources))
    for k, ok in res["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
    print("precheck: ok" if not res["missing"] else f"precheck: {len(res['missing'])} required declaration(s) missing; do not stage")
    return 0 if not res["missing"] else 1


def compile_text(compiler, text, src_dir, out_dir, script=SCRIPT):
    """Compile Papyrus source text to <out_dir>/<script>.pex; return (ok, error_summary)."""
    with tempfile.TemporaryDirectory(prefix="fo4sf-pa-core-compile-") as work:
        with open(os.path.join(work, script + ".psc"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.makedirs(out_dir, exist_ok=True)
        shell = ["cmd.exe", "/c"] if os.name == "nt" and str(compiler).lower().endswith((".cmd", ".bat")) else []
        r = subprocess.run(
            [*shell, compiler, script + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={work};{src_dir}", f"-o={out_dir}"],
            cwd=work,
            capture_output=True,
            text=True,
        )
    ok = r.returncode == 0 and "Compilation succeeded" in r.stdout and os.path.exists(os.path.join(out_dir, script + ".pex"))
    if ok:
        return True, ""
    lines = [ln.strip() for ln in (r.stdout + r.stderr).splitlines() if ".psc(" in ln or "error" in ln.lower()]
    return False, (" | ".join(lines[:8]) if lines else "no compiler output")


def stage_files(out_dir):
    """Return {relative_slash_path: sha256} for all top-level .esm files and all files under Data/."""
    files = {}
    for name in sorted(os.listdir(out_dir)):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p) and name.lower().endswith(".esm"):
            files[name] = sha256(p)
    data_root = os.path.join(out_dir, "Data")
    if os.path.isdir(data_root):
        for root, dirs, names in os.walk(data_root):
            dirs.sort()
            for n in sorted(names):
                p = os.path.join(root, n)
                files[os.path.relpath(p, out_dir).replace(os.sep, "/")] = sha256(p)
    return files


def load_plan(stage_or_plan_path):
    path = (
        stage_or_plan_path
        if os.path.isfile(stage_or_plan_path)
        else os.path.join(stage_or_plan_path, "plan.json")
    )
    if not os.path.isfile(path):
        alt = os.path.join(stage_or_plan_path, FOLDED_PLAN_NAME)
        if os.path.isfile(alt):
            path = alt
        else:
            sys.exit(f"{path} missing: stage with make_power_armor_core.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_starfield_esm(starfield_arg):
    if not starfield_arg:
        return None
    if os.path.isdir(starfield_arg):
        cand = os.path.join(starfield_arg, "Starfield.esm")
        if os.path.isfile(cand):
            return cand
        cand2 = os.path.join(starfield_arg, "Data", "Starfield.esm")
        return cand2
    return starfield_arg


def verify_stage(stage_dir, plan, data_or_sf=None, no_test_cell=False):
    """Verify a standalone stage directory against its plan.json and optional Starfield.esm / Data directory."""
    problems = []
    if plan.get("kind") != "power-armor-core" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not power-armor-core (kind={plan.get('kind')!r}, plugins={plan.get('plugins')!r})"]
    if no_test_cell and not plan.get("no_test_cell", False):
        problems.append("plan.json was staged without --no-test-cell")
    now = stage_files(stage_dir)
    for rel, want in plan.get("outputs", {}).items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != want:
            problems.append(f"{rel} changed after stage (sha256 {now[rel]} != plan {want})")
    extra = sorted(set(now) - set(plan.get("outputs", {})))
    if extra:
        problems.append(f"unexpected files in stage: {extra}")
    if PLUGIN not in plan.get("outputs", {}):
        problems.append(f"{PLUGIN} not pinned in plan.json")
    esm_path = os.path.join(stage_dir, PLUGIN)
    if (no_test_cell or plan.get("no_test_cell", False)) and os.path.isfile(esm_path):
        with open(esm_path, "rb") as ef:
            if b"FO4SF_PATestCell" in ef.read():
                problems.append(f"{PLUGIN} contains FO4SF_PATestCell despite no_test_cell=True")
    sf = resolve_starfield_esm(data_or_sf)
    if sf is not None:
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm at {sf}")
        elif sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm sha256 differs from stage input: re-stage")
    return problems


def verify_folded(folded_dir, plan, starfield_arg=None, no_test_cell=False):
    """Verify a folded core+PA directory against its pinned power-armor-core plan."""
    problems = []
    if plan.get("kind") != "power-armor-core" or plan.get("plugin") != PLUGIN:
        return [f"plan is not power-armor-core (kind={plan.get('kind')!r}, plugin={plan.get('plugin')!r})"]
    if no_test_cell and not plan.get("no_test_cell", False):
        problems.append("folded plan was staged without --no-test-cell")
    esm_path = os.path.join(folded_dir, PLUGIN)
    want_esm = plan["outputs"].get(PLUGIN)
    if not os.path.isfile(esm_path):
        problems.append(f"plugin {PLUGIN} missing in {folded_dir}")
    elif sha256(esm_path) != want_esm:
        problems.append(f"plugin {PLUGIN} sha256 {sha256(esm_path)} != plan {want_esm}")
    elif no_test_cell or plan.get("no_test_cell", False):
        with open(esm_path, "rb") as ef:
            if b"FO4SF_PATestCell" in ef.read():
                problems.append(f"{PLUGIN} contains FO4SF_PATestCell despite no_test_cell=True")

    for sname, want_pex in plan.get("scripts", {}).items():
        rel = f"Data/Scripts/{sname}.pex"
        pex_path = os.path.join(folded_dir, "Data", "Scripts", sname + ".pex")
        if not os.path.isfile(pex_path):
            problems.append(f"script {rel} missing in {folded_dir}")
        elif sha256(pex_path) != want_pex:
            problems.append(f"script {sname}: {pex_path} sha256 {sha256(pex_path)} != expected {want_pex}")

    readme_path = os.path.join(folded_dir, "README.txt")
    if not os.path.isfile(readme_path):
        problems.append("README.txt missing in folded directory")
    else:
        readme_txt = read_text(readme_path)
        matches = list(INSTALL_LINE.finditer(readme_txt))
        if not matches:
            problems.append("README.txt lacks exp_install.py --plugins install line")
        else:
            present = sorted(f for f in os.listdir(folded_dir) if f.lower().endswith(".esm"))
            for m in matches:
                listed = m.group("plugins").split(",")
                if PLUGIN not in listed:
                    problems.append(f"README.txt install line omits {PLUGIN}: {listed}")
                if sorted(listed) != present:
                    problems.append(f"README.txt --plugins {listed} != present .esm files {present}")
                    break

    sf = resolve_starfield_esm(starfield_arg)
    if sf is not None:
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm at {sf}")
        elif sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm sha256 differs from stage input: re-stage")
    return problems


def stage(a):
    for label, val in (("--starfield", a.starfield), ("--compiler", a.compiler), ("--content-resources", a.content_resources)):
        if not val or not os.path.isfile(val):
            sys.exit(f"stage requires an existing file for {label} (got {val!r})")
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (existing stage directories are never overwritten)")

    before = sha256(a.starfield)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)

    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    opts = (
        ["--control", a.control]
        + (["--override-dfob"] if a.override_dfob else [])
        + (["--no-test-cell"] if a.no_test_cell else [])
    )
    wrote = run(tool + ["build", a.starfield, out] + opts).stdout
    checked = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + checked)

    psc_text = read_text(PSC)
    pre = precheck_sources(read_sources(a.content_resources))
    if pre["missing"]:
        sys.exit(f"base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    src_dir = extract_sources(a.content_resources, work)
    scripts_dir = os.path.join(out, "Data", "Scripts")
    ok, err = compile_text(a.compiler, psc_text, src_dir, scripts_dir, SCRIPT)
    if not ok:
        sys.exit(f"Papyrus compile of {SCRIPT}.psc failed: {err}")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(psc_text)
    shutil.rmtree(work)

    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during stage; attempt kept in {out}")

    outputs = stage_files(out)
    pex_rel = f"Data/Scripts/{SCRIPT}.pex"
    plan = {
        "kind": "power-armor-core",
        "version": 1,
        "plugin": PLUGIN,
        "plugins": [PLUGIN],
        "masters": ["Starfield.esm", CORE_VALUES_PLUGIN],
        "core_values": {
            "plugin": CORE_VALUES_PLUGIN,
            "SpecialAgilityAV": f"0x{SPECIAL_AGILITY_ID:06X}",
            "TestModeGlobal": f"0x{TEST_MODE_GLOBAL_ID:06X}",
        },
        "scripts": {SCRIPT: outputs[pex_rel]},
        "outputs": outputs,
        "inputs": {"Starfield.esm": {"sha256": before}},
        "control": a.control,
        "override_dfob": bool(a.override_dfob),
        "no_test_cell": bool(a.no_test_cell),
        "log": "<My Games>/Starfield/Logs/Script/User/FO4SFPACore.0.log",
    }
    cell_desc = "no test cell" if a.no_test_cell else "CELL FO4SF_PATestCell (coc FO4SF_PATestCell)"
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            f"Power Armor Core ({datetime.date.today().isoformat()}). docs/powerarmor/power-armor-core.md\n"
            f"{PLUGIN} (sha256 {outputs[PLUGIN]}, masters Starfield.esm + {CORE_VALUES_PLUGIN}): {cell_desc}, "
            f"RACE FO4SF_PowerArmorRace -> BPTD FO4SF_PowerArmorBodyPartData (6 limb condition AVIFs) + "
            f"Skin FO4SF_PowerArmorSkin, FURN FO4SF_PowerArmorFrameFurn (control {a.control}), "
            f"MISC FO4SF_FusionCore, 4 disjoint PA ARMOs, 2 FNV Salvaged NCR worn heavy ARMOs (-1 AGI -> {CORE_VALUES_PLUGIN}:0x{SPECIAL_AGILITY_ID:04X}), "
            f"QUST FO4SF_PowerArmorCoreQuest (stages 10/20/30/40 gated by 0x{TEST_MODE_GLOBAL_ID:04X}). "
            f"override_dfob={bool(a.override_dfob)}, no_test_cell={bool(a.no_test_cell)}.\n"
            f"Checked against Starfield.esm {before}.\n"
            f"Ride-along install (game closed):\n"
            f"  python scripts/powerarmor/power_armor_core_install.py install --dir <this folder> --starfield <game>\n"
            f"Remove:\n"
            f"  python scripts/powerarmor/power_armor_core_install.py uninstall --starfield <game>\n"
            f"Read user log:\n"
            f"  python scripts/powerarmor/make_power_armor_core.py log --file <FO4SFPACore.0.log>\n"
        )
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, offline_check.txt, plan.json, README.txt (override_dfob={bool(a.override_dfob)}, no_test_cell={bool(a.no_test_cell)})")
    return 0


def link_or_copy_file(src, dst, hardlink):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if hardlink:
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def clone_core_tree(core_dir, out_dir, hardlink, clean_prior):
    """Clone core_dir to out_dir without linking README.txt (so writing <out>/README.txt never mutates core_dir/README.txt)."""
    os.makedirs(out_dir, exist_ok=True)
    skip_top = {"README.txt", FOLDED_PLAN_NAME}
    if clean_prior:
        skip_top.add(PLUGIN)
    skip_rel = {f"Data/Scripts/{SCRIPT}.pex"} if clean_prior else set()

    for root, dirs, names in os.walk(core_dir):
        dirs.sort()
        rel_root = os.path.relpath(root, core_dir)
        dst_root = out_dir if rel_root == "." else os.path.join(out_dir, rel_root)
        os.makedirs(dst_root, exist_ok=True)
        for name in sorted(names):
            if rel_root == "." and name in skip_top:
                continue
            rel_path = name if rel_root == "." else f"{rel_root.replace(os.sep, '/')}/{name}"
            if rel_path in skip_rel:
                continue
            link_or_copy_file(os.path.join(root, name), os.path.join(dst_root, name), hardlink)


def core_plugins(core_dir, readme_txt, clean_prior):
    present = sorted(
        f for f in os.listdir(core_dir)
        if f.lower().endswith(".esm") and not (clean_prior and f == PLUGIN)
    )
    if not present:
        sys.exit(f"fold refused: {core_dir} holds no core .esm files")
    m = INSTALL_LINE.search(readme_txt)
    if not m:
        return present
    listed = [p for p in m.group("plugins").split(",") if not (clean_prior and p == PLUGIN)]
    if sorted(listed) != present:
        sys.exit(f"fold refused: {core_dir} README lists {listed} but directory holds {present}")
    return listed


def install_command(plugins):
    return f"scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(plugins)} --pack"


def build_folded_readme(core_readme, stage_readme, plugins, stage_label):
    def widen(line):
        m = INSTALL_LINE.search(line)
        return line[:m.start("plugins")] + ",".join(plugins) + line[m.end("plugins"):] if m else line

    return "\n".join(
        [widen(ln) for ln in core_readme.splitlines()]
        + [
            "",
            f"==== {PLUGIN} folded in ({datetime.date.today().isoformat()}) from {stage_label} ====",
            stage_readme.rstrip("\n"),
            "",
            f"Install (game closed): every plugin in --plugins must be listed so {PLUGIN} is activated:",
            "  " + install_command(plugins),
        ]
    ) + "\n"


def fold(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    stage_dir = os.path.abspath(a.stage)
    core_dir = os.path.abspath(a.core_dir)
    plan = load_plan(os.path.join(stage_dir, "plan.json"))
    stage_problems = verify_stage(stage_dir, plan, a.starfield)
    if stage_problems:
        for p in stage_problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: stage failed verification ({len(stage_problems)} problem(s))")

    if not a.clean_prior and os.path.exists(os.path.join(core_dir, PLUGIN)):
        sys.exit(f"fold refused: {core_dir} already holds {PLUGIN} (pass --clean-prior to replace)")
    if not a.clean_prior and os.path.exists(os.path.join(core_dir, "Data", "Scripts", SCRIPT + ".pex")):
        sys.exit(f"fold refused: {core_dir} already holds Data/Scripts/{SCRIPT}.pex (pass --clean-prior to replace)")

    core_readme = read_text(os.path.join(core_dir, "README.txt"))
    stage_readme = read_text(os.path.join(stage_dir, "README.txt"))
    plugins = core_plugins(core_dir, core_readme, a.clean_prior) + [PLUGIN]

    out = new_partial(final, create=False)
    clone_core_tree(core_dir, out, hardlink=bool(a.hardlink), clean_prior=bool(a.clean_prior))
    link_or_copy_file(os.path.join(stage_dir, PLUGIN), os.path.join(out, PLUGIN), hardlink=bool(a.hardlink))
    for sname in plan["scripts"]:
        src_pex = os.path.join(stage_dir, "Data", "Scripts", sname + ".pex")
        dst_pex = os.path.join(out, "Data", "Scripts", sname + ".pex")
        if os.path.exists(dst_pex):
            sys.exit(f"fold refused: destination already has Data/Scripts/{sname}.pex (attempt kept in {out})")
        link_or_copy_file(src_pex, dst_pex, hardlink=bool(a.hardlink))

    with open(os.path.join(out, FOLDED_PLAN_NAME), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(build_folded_readme(core_readme, stage_readme, plugins, os.path.basename(stage_dir)))

    problems = verify_folded(out, plan, a.starfield)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); attempt kept in {out}")

    os.replace(out, final)
    print(f"folded {final}: {PLUGIN} + {len(plan['scripts'])} script(s); verify: ok")
    print("install (game closed): " + install_command(plugins))
    return 0


def verify(a):
    target = os.path.abspath(a.dir)
    if a.plan:
        plan = load_plan(a.plan)
        is_folded = os.path.isfile(os.path.join(target, FOLDED_PLAN_NAME)) or len(
            [f for f in os.listdir(target) if f.lower().endswith(".esm")]
        ) > 1
    elif os.path.isfile(os.path.join(target, FOLDED_PLAN_NAME)):
        plan = load_plan(os.path.join(target, FOLDED_PLAN_NAME))
        is_folded = True
    else:
        plan = load_plan(os.path.join(target, "plan.json"))
        is_folded = False

    no_test_cell = bool(getattr(a, "no_test_cell", False))
    problems = (
        verify_folded(target, plan, a.starfield, no_test_cell=no_test_cell)
        if is_folded
        else verify_stage(target, plan, a.starfield, no_test_cell=no_test_cell)
    )
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def log_cmd(a):
    if not a.file or not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    papyrus = None
    if a.papyrus and os.path.isfile(a.papyrus):
        with open(a.papyrus, encoding="utf-8", errors="replace") as f:
            papyrus = f.read().splitlines()
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = core_log.summarize(f, papyrus=papyrus)
    print("\n".join(core_log.report(s)))
    return 0 if s["verdict"].startswith("PASS:") else 1


def default_sf_paths():
    sf_dir = os.environ.get("STARFIELD_DIR", "")
    if not sf_dir:
        return "", "", ""
    return (
        os.path.join(sf_dir, "Data", "Starfield.esm"),
        os.path.join(sf_dir, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"),
        os.path.join(sf_dir, "Tools", "ContentResources.zip"),
    )


def main(argv=None):
    sf_esm, sf_comp, sf_cr = default_sf_paths()
    user_docs = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script")
    default_log = os.path.join(user_docs, "User", "FO4SFPACore.0.log")
    default_papyrus = os.path.join(user_docs, "Papyrus.0.log")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=sf_cr)
    pc.add_argument("--out", default=None)

    st = sub.add_parser("stage")
    st.add_argument("--out", required=True)
    st.add_argument("--starfield", default=sf_esm)
    st.add_argument("--compiler", default=sf_comp)
    st.add_argument("--content-resources", default=sf_cr)
    st.add_argument("--control", default=DEFAULT_CONTROL)
    st.add_argument("--override-dfob", action="store_true", help="opt-in override of Starfield's 5 empty PowerArmor*_DO DFOBs")
    st.add_argument("--no-test-cell", action="store_true", help="omit FO4SF_PATestCell and placed test chairs/frame")

    fd = sub.add_parser("fold")
    fd.add_argument("--core-dir", required=True)
    fd.add_argument("--stage", required=True)
    fd.add_argument("--out", required=True)
    fd.add_argument("--hardlink", action="store_true")
    fd.add_argument("--clean-prior", action="store_true")
    fd.add_argument("--starfield", default=None)

    vf = sub.add_parser("verify")
    vf.add_argument("--dir", required=True)
    vf.add_argument("--plan", default=None)
    vf.add_argument("--starfield", default=None)
    vf.add_argument("--no-test-cell", action="store_true", help="require stage/folded plugin to omit FO4SF_PATestCell")

    lg = sub.add_parser("log")
    lg.add_argument("--file", default=default_log)
    lg.add_argument("--papyrus", default=default_papyrus)

    a = ap.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "fold": fold, "verify": verify, "log": log_cmd}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
