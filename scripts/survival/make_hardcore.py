"""Stage, fold, verify, and inspect FO4SFHardcore.esm and FO4SF_HardcoreQuest.pex (docs/survival/hardcore-toggle.md).

usage:
  python make_hardcore.py precheck --content-resources <ContentResources.zip> [--out <precheck.json>]
  python make_hardcore.py stage --out <stage dir> --starfield <Starfield.esm> --compiler <PapyrusCompiler.exe>
                                --content-resources <ContentResources.zip> [--default-hardcore 0|1]
  python make_hardcore.py verify --exp-dir <dir> --plan <stage/plan.json> [--starfield <Starfield.esm>]
  python make_hardcore.py fold --stage <stage dir> --core-dir <core exp dir> --out <folded dir>
                               [--starfield <Starfield.esm>] [--hardlink]
  python make_hardcore.py log [--file <FO4SFHardcore.0.log>]
"""
from __future__ import annotations

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
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
from fo4sf.survival import hardcore_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "HardcoreToggle")
PLUGIN = "FO4SFHardcore.esm"
SCRIPT = "FO4SF_HardcoreQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
LOG_NAME = "FO4SFHardcore.0.log"
INSTALL_LINE = re.compile(r"exp_install\.py install\b.*--plugins (?P<plugins>\S+)")

REQUIRED = {
    "Actor": [
        "GetValue", "SetValue", "ModValue", "DamageValue", "RestoreValue",
        "AddItem", "RemoveItem", "GetItemCount",
        "OnItemEquipped", "OnPlayerLoadGame",
    ],
    "ObjectReference": [
        "OnItemAdded", "OnItemRemoved",
    ],
    "GlobalVariable": ["GetValue", "SetValue"],
    "GameplayOption": ["GetValue", "NotifyGameplayOptionUpdateFinished"],
    "FormList": ["GetSize", "GetAt"],
    "Game": ["GetPlayer", "GetFormFromFile"],
    "Debug": ["OpenUserLog", "TraceUser"],
    "Utility": ["GetCurrentRealTime", "GetCurrentGameTime"],
    "Quest": ["GetStageDone", "IsRunning"],
    "ScriptObject": [
        "StartTimer", "CancelTimer", "RegisterForRemoteEvent",
        "AddInventoryEventFilter", "RemoveAllInventoryEventFilters",
        "RegisterForGameplayOptionChangedEvent", "OnGameplayOptionChanged",
        "RegisterForPlayerSleep", "OnPlayerSleepStart", "OnPlayerSleepStop",
    ],
}


def env_game_path(*parts):
    base = os.environ.get("FO4SF_STARFIELD_DIR", "")
    return os.path.join(base, *parts) if base else ""


def user_logs(name=LOG_NAME):
    home = os.path.expanduser("~")
    return [
        os.path.join(home, *base, "My Games", "Starfield", "Logs", "Script", "User", name)
        for base in (("OneDrive", "Documents"), ("Documents",))
    ]


def default_log():
    found = [p for p in user_logs() if os.path.isfile(p)]
    return found[0] if found else user_logs()[0]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_text(path):
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_sources(zip_path):
    sources = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and name.lower().endswith(".psc"):
                sources[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    return sources


def precheck_sources(sources):
    req = {f"{b}.{f}": declares(sources, b, f) for b, fs in REQUIRED.items() for f in fs}
    return {"required": req, "missing": [k for k, ok in req.items() if not ok]}


def precheck(a):
    if not a.content_resources:
        sys.exit("precheck needs --content-resources <ContentResources.zip> (or FO4SF_STARFIELD_DIR)")
    r = precheck_sources(read_sources(a.content_resources))
    for k, ok in r["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} required native(s) missing; do not stage"))
    return 0 if not r["missing"] else 1


def compile_script(compiler, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run(
        [compiler, SCRIPT + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
        cwd=HERE, capture_output=True, text=True,
    )
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    ok = r.returncode == 0 and "Compilation succeeded" in r.stdout and os.path.isfile(pex)
    if not ok:
        err = next((l.strip() for l in (r.stdout + "\n" + r.stderr).splitlines() if ".psc(" in l.lower() or "error" in l.lower()), "compiler failed")
        sys.exit(f"Papyrus compile of {SCRIPT}.psc failed: {err}")
    return pex


def template_line(text):
    m = re.search(r"^templates \((\w+)\): (.*)$", text, re.M)
    return f"{m.group(1)}: {m.group(2)}" if m else ""


def stage_files(out):
    files = {}
    for name in sorted(os.listdir(out)):
        if name.lower().endswith(".esm"):
            files[name] = sha256(os.path.join(out, name))
    data_root = os.path.join(out, "Data")
    if os.path.isdir(data_root):
        for root, dirs, names in os.walk(data_root):
            dirs.sort()
            for n in sorted(names):
                p = os.path.join(root, n)
                files[os.path.relpath(p, out).replace(os.sep, "/")] = sha256(p)
    return files


def refuse_forbidden_out_dir(out_dir):
    full = os.path.abspath(out_dir)
    cur = full
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            sys.exit(f"refused: output folder inside Git worktree is forbidden ({full})")
        if os.path.isfile(os.path.join(cur, "Starfield.exe")):
            sys.exit(f"refused: output folder inside game install is forbidden ({full})")
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


def stage(a):
    for flag, val in (("--starfield", a.starfield), ("--compiler", a.compiler), ("--content-resources", a.content_resources)):
        if not val:
            sys.exit(f"stage needs {flag} (or FO4SF_STARFIELD_DIR)")
    final = os.path.abspath(a.out)
    refuse_forbidden_out_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")

    before = sha256(a.starfield)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)

    pre = precheck_sources(read_sources(a.content_resources))
    if pre["missing"]:
        sys.exit(f"base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")

    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    opts = ["--default-hardcore", str(a.default_hardcore)]
    wrote = run(tool + ["build", a.starfield, out] + opts).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)

    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    shutil.copy2(PSC, os.path.join(out, SCRIPT + ".psc"))
    shutil.rmtree(work)

    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")

    outputs = stage_files(out)
    plan = {
        "kind": "hardcore-toggle",
        "version": 1,
        "plugin": PLUGIN,
        "plugin_sha256": outputs[PLUGIN],
        "plugins": [PLUGIN],
        "scripts": {SCRIPT: sha256(pex)},
        "outputs": outputs,
        "inputs": {"Starfield.esm": {"sha256": before}},
        "options": {"default_hardcore": a.default_hardcore},
        "templates": template_line(wrote),
        "sq_env_boundary": "0x248D20 untouched (zero overrides; read-only IsRunning() check)",
        "shared_core_values": {
            "FO4SF_HardcoreEnabled": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_HardcoreEnabled'):03X}",
            "FO4SF_Hunger": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_Hunger'):03X}",
            "FO4SF_Thirst": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_Thirst'):03X}",
            "FO4SF_SleepDeprivation": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_SleepDeprivation'):03X}",
            "FO4SF_Stimpak": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_Stimpak'):03X}",
            "FO4SF_SurvivalStart": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_SurvivalStart'):03X}",
            "FO4SF_SurvivalLocked": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_SurvivalLocked'):03X}",
            "FO4SF_TestModeEnabled": f"{CORE_VALUES_PLUGIN}:0x{core_form_id('FO4SF_TestModeEnabled'):03X}",
        },
        "log": "<My Games>/Starfield/Logs/Script/User/FO4SFHardcore.0.log",
    }
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Fallout Hardcore & Survival GPOF Toggle ({datetime.date.today().isoformat()}). docs/survival/hardcore-toggle.md
{PLUGIN} (sha256 {plan['plugin_sha256']}):
  GPOF FO4SF_GPO_Hardcore (0x800, default {a.default_hardcore}) in GPOG FO4SF_GPOG_Hardcore (0x801);
  Shared in {CORE_VALUES_PLUGIN}: FO4SF_HardcoreEnabled (0x840), FO4SF_HardcoreFastTravelBlocked (0x841),
       FO4SF_Hunger/Thirst/SleepDeprivation (0x842..0x844), FO4SF_HungerStage/ThirstStage/SleepStage (0x845..0x847),
       FO4SF_Stimpak (0x851), SPECIAL AVIFs, FO4SF_TestModeEnabled (0x860);
  Local AVIF, Aid & Ammo: AVIF FO4SF_AmmoWeightBurden (0x806), MGEF FO4SF_HungerReliefEffect/ThirstReliefEffect (0x810..0x811),
       ALCH FO4SF_RationFood (0x820), FO4SF_PurifiedWater (0x821),
       AMMO FO4SF_CaliberLight/Rifle/Heavy (0x825..0x827) in FLST FO4SF_WeightedAmmoList (0x828);
  QUST FO4SF_HardcoreQuest (0x830, StartGameEnabled, stages 5 and 10..50 gated by FO4SF_TestModeEnabled) + Data/Scripts/{SCRIPT}.pex.
Masters Starfield.esm ({before}) and {CORE_VALUES_PLUGIN}; adds records, overrides none (SQ_ENV 0x248D20 untouched).
Ride-along install (game closed):
  python scripts/survival/hardcore_install.py install --dir <stage dir> --starfield <game dir>
Fold into core experiment set:
  python scripts/survival/make_hardcore.py fold --stage <stage dir> --core-dir <core dir> --out <folded dir> --hardlink
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, Data/Scripts/{SCRIPT}.pex, offline_check.txt, plan.json, README.txt")
    return 0


def load_plan(stage_or_plan_path):
    path = os.path.join(stage_or_plan_path, "plan.json") if os.path.isdir(stage_or_plan_path) else stage_or_plan_path
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_hardcore.py first")
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "plugins", "scripts", "outputs", "inputs") if k not in plan]
    if missing or plan.get("kind") != "hardcore-toggle" or plan.get("plugins") != [PLUGIN]:
        sys.exit(f"{path} is not a hardcore-toggle plan (kind={plan.get('kind')!r}, missing={missing})")
    return plan


def verify_stage(stage_dir, plan, data_dir=None):
    problems = []
    if plan.get("kind") != "hardcore-toggle" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not hardcore-toggle (kind={plan.get('kind')!r}, plugins={plan.get('plugins')!r})"]
    now = stage_files(stage_dir)
    for rel, h in plan["outputs"].items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != h:
            problems.append(f"{rel} changed after stage (sha256 {now[rel]}, plan {h})")
    extra = sorted(set(now) - set(plan["outputs"]))
    if extra:
        problems.append(f"files not in plan.json: {extra}")
    if data_dir is not None:
        sf = os.path.join(data_dir, "Starfield.esm")
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm in {data_dir}")
        elif sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since stage: re-stage")
    return problems


def verify_dir(exp_dir, plan, starfield=None):
    problems = []

    def same(label, path, want):
        if not path or not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 {sha256(path)} != plan {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    for s, want in plan["scripts"].items():
        same("script", os.path.join(exp_dir, "Data", "Scripts", s + ".pex"), want)
    if starfield:
        same("Starfield.esm", starfield, plan["inputs"]["Starfield.esm"]["sha256"])
    return problems


def verify(a):
    plan = load_plan(a.plan)
    problems = verify_dir(a.exp_dir, plan, a.starfield or None)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def core_plugins(core_dir, readme):
    present = sorted(f for f in os.listdir(core_dir) if f.lower().endswith(".esm"))
    if not present:
        sys.exit(f"fold refused: {core_dir} holds no .esm")
    m = INSTALL_LINE.search(readme)
    if not m:
        return present
    listed = m.group("plugins").split(",")
    if sorted(listed) != present:
        sys.exit(f"fold refused: {core_dir} README installs {listed} but folder holds {present}")
    return listed


def install_command(plugins):
    return f"scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(plugins)} --pack"


def folded_readme(core_readme, stage_readme, plugins, plugin, stage_label):
    def widen(line):
        m = INSTALL_LINE.search(line)
        return line[:m.start("plugins")] + ",".join(plugins) + line[m.end("plugins"):] if m else line

    return "\n".join(
        [widen(line) for line in core_readme.splitlines()]
        + [
            "",
            f"==== {plugin} folded in ({datetime.date.today().isoformat()}) from {stage_label} ====",
            stage_readme.rstrip("\n"),
            "",
            f"Install (game closed): EVERY plugin listed so exp_install.py activates {plugin} too:",
            "  " + install_command(plugins),
        ]
    ) + "\n"


def _hardlink_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def fold(a):
    final = os.path.abspath(a.out)
    refuse_forbidden_out_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.stage, "plan.json"))
    stage_probs = verify_stage(a.stage, plan)
    if stage_probs:
        sys.exit("fold refused: stage failed verification: " + "; ".join(stage_probs))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"fold refused: {a.core_dir} already holds {plan['plugin']}")

    core_readme = read_text(os.path.join(a.core_dir, "README.txt"))
    stage_readme = read_text(os.path.join(a.stage, "README.txt"))
    plugins = core_plugins(a.core_dir, core_readme) + [plan["plugin"]]

    out = new_partial(final, create=False)
    copy_fn = _hardlink_or_copy if a.hardlink else shutil.copy2
    shutil.copytree(a.core_dir, out, copy_function=copy_fn)

    readme_dst = os.path.join(out, "README.txt")
    if os.path.exists(readme_dst):
        os.remove(readme_dst)
    with open(readme_dst, "w", encoding="utf-8") as f:
        f.write(folded_readme(core_readme, stage_readme, plugins, plan["plugin"], os.path.basename(os.path.abspath(a.stage))))

    shutil.copy2(os.path.join(a.stage, plan["plugin"]), os.path.join(out, plan["plugin"]))
    for s, want_sha in plan["scripts"].items():
        src_pex = os.path.join(a.stage, "Data", "Scripts", s + ".pex")
        dst_pex = os.path.join(out, "Data", "Scripts", s + ".pex")
        if os.path.exists(dst_pex):
            if sha256(dst_pex) == want_sha:
                continue
            sys.exit(f"fold refused: core set already has different Data/Scripts/{s}.pex (attempt kept in {out})")
        os.makedirs(os.path.dirname(dst_pex), exist_ok=True)
        shutil.copy2(src_pex, dst_pex)

    problems = verify_dir(out, plan, a.starfield or None)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); nothing published (attempt kept in {out})")

    os.replace(out, final)
    print(f"folded {final}: {os.path.basename(os.path.abspath(a.core_dir))} + {plan['plugin']} + {len(plan['scripts'])} script(s); verify ok")
    print("install (game closed): " + install_command(plugins))
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = hardcore_log.summarize(f)
    print("\n".join(hardcore_log.report(s)))
    return 0 if s["passed"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("precheck")
    p_pre.add_argument("--content-resources", default=env_game_path("Tools", "ContentResources.zip"))
    p_pre.add_argument("--out", default="")

    p_st = sub.add_parser("stage")
    p_st.add_argument("--out", required=True)
    p_st.add_argument("--starfield", default=env_game_path("Data", "Starfield.esm"))
    p_st.add_argument("--compiler", default=env_game_path("Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    p_st.add_argument("--content-resources", default=env_game_path("Tools", "ContentResources.zip"))
    p_st.add_argument("--default-hardcore", type=int, choices=(0, 1), default=0)

    p_ver = sub.add_parser("verify")
    p_ver.add_argument("--exp-dir", required=True)
    p_ver.add_argument("--plan", required=True)
    p_ver.add_argument("--starfield", default="")

    p_fold = sub.add_parser("fold")
    p_fold.add_argument("--stage", required=True)
    p_fold.add_argument("--core-dir", required=True)
    p_fold.add_argument("--out", required=True)
    p_fold.add_argument("--starfield", default="")
    p_fold.add_argument("--hardlink", action="store_true")

    p_log = sub.add_parser("log")
    p_log.add_argument("--file", default=default_log())

    a = ap.parse_args(argv)
    dispatch = {"precheck": precheck, "stage": stage, "verify": verify, "fold": fold, "log": log}
    return dispatch[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
