"""Stage, verify, wire Pip-Boy pages, and evaluate multi-session logs for FO4SFReputation.esm.

Subcommands:
  stage       Build & check FO4SFReputation.esm, compile FO4SF_ReputationQuest.pex, emit Pip-Boy Stage=5 INI +
              Stage=2 TSV/JSON manifests, and write SHA-256 plan.json atomically.
  verify      Verify every staged file's byte count & SHA-256 against plan.json and validate Pip-Boy kit INI rules.
  pipboy-ini  Inject [Page STAT/KARMA] and [Page DATA/REPUTATION] into FO4SFPipboyMenu.ini and validate kit layout.
  log         Stitch FO4SFReputation.1.log + FO4SFReputation.0.log across save/quit/reload and verify orthogonality
              plus reload state parity (exits 0 on PASS, 1 otherwise).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "newgame"))
sys.path.insert(0, str(REPO / "scripts" / "ui"))
sys.path.insert(0, str(REPO / "src"))

from make_newgame import extract_sources, new_partial  # noqa: E402
import make_pipboy_kit  # noqa: E402
from fo4sf.reputation import (  # noqa: E402
    PLUGIN_MASTERS,
    PLUGIN_NAME,
    build_shell_manifest,
    format_log_summary,
    format_shell_tsv,
    inject_pipboy_kit_pages,
    resolve_log_chain,
    stitch_and_evaluate_logs,
)

PROJECT_DIR = REPO / "dotnet" / "ReputationCore"
SCRIPT_NAME = "FO4SF_ReputationQuest"
PSC_PATH = HERE / f"{SCRIPT_NAME}.psc"
SHIPPED_PIPBOY_INI = REPO / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini"
LOG_BASENAME = "FO4SFReputation.0.log"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hex_int(raw: str) -> int:
    s = raw.strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s, 16)


def default_starfield_paths() -> Dict[str, Optional[Path]]:
    sf_root = os.environ.get("STARFIELD_DIR", "").strip()
    if not sf_root:
        return {"starfield": None, "compiler": None, "resources": None}
    root = Path(sf_root)
    return {
        "starfield": root / "Data" / "Starfield.esm",
        "compiler": root / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe",
        "resources": root / "Tools" / "ContentResources.zip",
    }


def user_log_candidates(filename: str = LOG_BASENAME) -> List[Path]:
    home = Path(os.path.expanduser("~"))
    return [
        home / "OneDrive" / "Documents" / "My Games" / "Starfield" / "Logs" / "Script" / "User" / filename,
        home / "Documents" / "My Games" / "Starfield" / "Logs" / "Script" / "User" / filename,
    ]


def default_user_log() -> Path:
    cands = user_log_candidates()
    for p in cands:
        if p.is_file():
            return p
    return cands[0]


def validate_kit_ini_text(ini_text: str) -> List[Dict[str, object]]:
    kit = make_pipboy_kit.parse_kit(ini_text)
    return list(kit["pages"])


def run_dotnet_reputation(verb: str, *verb_args: str) -> str:
    dll = PROJECT_DIR / "bin" / "Release" / "net9.0" / "ReputationCore.dll"
    src_cs = PROJECT_DIR / "Program.cs"
    needs_build = (not dll.is_file()) or (src_cs.is_file() and src_cs.stat().st_mtime > dll.stat().st_mtime)
    if needs_build:
        b = subprocess.run(
            ["dotnet", "build", "-c", "Release", str(PROJECT_DIR)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if b.returncode != 0:
            raise RuntimeError(f"dotnet build failed ({b.returncode}):\n{b.stdout}\n{b.stderr}")
    cmd = ["dotnet", "exec", str(dll), verb, *verb_args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"ReputationCore {verb} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r.stdout


def compile_papyrus(compiler: Path, resources: Path, psc_source: Path, scripts_out_dir: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="rep_psc_") as work_str:
        work = Path(work_str)
        imports_dir = Path(extract_sources(str(resources), str(work / "imports")))
        frozen_psc = work / psc_source.name
        frozen_psc.write_bytes(psc_source.read_bytes())
        scripts_out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(compiler),
            psc_source.name,
            "-f=Starfield_Papyrus_Flags.flg",
            f"-i={work};{imports_dir}",
            f"-o={scripts_out_dir}",
        ]
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or "Compilation succeeded" not in r.stdout:
            raise RuntimeError(
                f"PapyrusCompiler failed ({r.returncode}):\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
            )
        pex = scripts_out_dir / f"{psc_source.stem}.pex"
        if not pex.is_file() or pex.stat().st_size == 0:
            raise RuntimeError(f"PapyrusCompiler produced no nonempty {pex.name}")
        return r.stdout


def cmd_stage(args: argparse.Namespace) -> int:
    defaults = default_starfield_paths()
    sf_esm = Path(args.starfield) if args.starfield else defaults["starfield"]
    compiler = Path(args.compiler) if args.compiler else defaults["compiler"]
    resources = Path(args.content_resources) if args.content_resources else defaults["resources"]

    for label, p in (("Starfield.esm", sf_esm), ("PapyrusCompiler.exe", compiler), ("ContentResources.zip", resources)):
        if p is None or not p.is_file():
            sys.stderr.write(f"error: missing {label} (pass explicit flag or set STARFIELD_DIR)\n")
            return 1

    assert sf_esm is not None and compiler is not None and resources is not None
    out_dir = Path(args.out).resolve()
    if out_dir.exists():
        sys.stderr.write(f"error: output directory already exists: {out_dir}\n")
        return 1

    load_index = parse_hex_int(args.load_index)
    core_load_index = parse_hex_int(args.core_load_index)
    slot_count = int(args.slot_count)
    no_test_cell = bool(args.no_test_cell)
    if not (1 <= slot_count <= 15):
        sys.stderr.write("error: --slot-count must be in 1..15\n")
        return 1

    dotnet_flags: List[str] = ["--slot-count", str(slot_count)]
    if no_test_cell:
        dotnet_flags.append("--no-test-cell")

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(new_partial(str(out_dir)))
    try:
        # 1. Build & check FO4SFReputation.esm
        build_out = run_dotnet_reputation("build", str(sf_esm), str(partial), *dotnet_flags)
        esm_path = partial / PLUGIN_NAME
        check_out = run_dotnet_reputation("check", str(esm_path), str(sf_esm), *dotnet_flags)
        (partial / "offline_check.txt").write_text(build_out + check_out, encoding="utf-8")

        # 2. Compile FO4SF_ReputationQuest.psc -> Data/Scripts/FO4SF_ReputationQuest.pex
        compile_papyrus(compiler, resources, PSC_PATH, partial / "Data" / "Scripts")

        # 3. Generate Stage=5 Pip-Boy kit INI (FO4SFPipboyKit.ini, NEVER FO4SFPipboyMenu.ini) & Stage=2 AS3 shell manifests
        base_ini_text = SHIPPED_PIPBOY_INI.read_text(encoding="utf-8")
        merged_ini = inject_pipboy_kit_pages(
            base_ini_text,
            load_index=load_index,
            core_load_index=core_load_index,
            slot_count=slot_count,
        )
        validate_kit_ini_text(merged_ini)
        (partial / "FO4SFPipboyKit.ini").write_text(merged_ini, encoding="utf-8")
        (partial / "FO4SFPipboyReputation.tsv").write_text(format_shell_tsv(slot_count=slot_count), encoding="utf-8")
        (partial / "FO4SFPipboyReputation.json").write_text(
            json.dumps(build_shell_manifest(slot_count=slot_count), indent=2) + "\n", encoding="utf-8"
        )

        # 4. Write README.txt & SHA-256 plan.json
        readme = (
            "FO4SFReputation Stage Package\n"
            "=============================\n"
            f"- Plugin: {PLUGIN_NAME} (masters {', '.join(PLUGIN_MASTERS)}, slots={slot_count}, no_test_cell={no_test_cell})\n"
            f"- Script: Data/Scripts/{SCRIPT_NAME}.pex\n"
            "- Pip-Boy Stage=5 Kit INI: FO4SFPipboyKit.ini ([Page STAT/KARMA], [Page DATA/REPUTATION])\n"
            "- Pip-Boy Stage=2 Shell Bridge: FO4SFPipboyReputation.tsv, FO4SFPipboyReputation.json\n"
        )
        (partial / "README.txt").write_text(readme, encoding="utf-8")

        tracked: Dict[str, Dict[str, object]] = {}
        for fp in sorted(p for p in partial.rglob("*") if p.is_file()):
            rel = fp.relative_to(partial).as_posix()
            tracked[rel] = {
                "bytes": fp.stat().st_size,
                "sha256": sha256_file(fp),
            }

        plan = {
            "schema": 1,
            "plugin": PLUGIN_NAME,
            "masters": list(PLUGIN_MASTERS),
            "slot_count": slot_count,
            "no_test_cell": no_test_cell,
            "script": f"Data/Scripts/{SCRIPT_NAME}.pex",
            "pipboy_load_index_hex": f"0x{load_index:02X}",
            "pipboy_core_load_index_hex": f"0x{core_load_index:02X}",
            "starfield_esm": {
                "bytes": sf_esm.stat().st_size,
                "sha256": sha256_file(sf_esm),
            },
            "psc_source_sha256": sha256_file(PSC_PATH),
            "files": tracked,
        }
        (partial / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

        os.replace(partial, out_dir)
    except Exception as exc:
        if partial.exists():
            shutil.rmtree(partial, ignore_errors=True)
        sys.stderr.write(f"stage failed: {exc}\n")
        return 1

    print(f"staged {PLUGIN_NAME} ({len(tracked)} files) -> {out_dir}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage).resolve()
    plan_path = stage_dir / "plan.json"
    if not plan_path.is_file():
        sys.stderr.write(f"verify failed: missing {plan_path}\n")
        return 1

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write(f"verify failed: unreadable plan.json ({exc})\n")
        return 1

    files_map = plan.get("files")
    if not isinstance(files_map, dict) or not files_map:
        sys.stderr.write("verify failed: plan.json lacks non-empty files map\n")
        return 1

    required_rels = {
        PLUGIN_NAME,
        f"Data/Scripts/{SCRIPT_NAME}.pex",
        "FO4SFPipboyKit.ini",
        "FO4SFPipboyReputation.tsv",
        "FO4SFPipboyReputation.json",
        "offline_check.txt",
        "README.txt",
    }
    missing_keys = sorted(required_rels - set(files_map.keys()))
    if missing_keys:
        sys.stderr.write(f"verify failed: plan.json missing required artifacts: {missing_keys}\n")
        return 1

    problems: List[str] = []
    if args.no_test_cell and not plan.get("no_test_cell"):
        problems.append("plan was not staged with --no-test-cell")
    if args.slot_count is not None and int(plan.get("slot_count", 8)) != int(args.slot_count):
        problems.append(f"plan slot_count {plan.get('slot_count', 8)} != expected {args.slot_count}")

    for rel, meta in sorted(files_map.items()):
        fp = stage_dir / rel
        if not fp.is_file():
            problems.append(f"missing staged file: {rel}")
            continue
        actual_bytes = fp.stat().st_size
        actual_sha = sha256_file(fp)
        if actual_bytes != meta.get("bytes"):
            problems.append(f"size mismatch on {rel}: expected {meta.get('bytes')}, got {actual_bytes}")
        if actual_sha != meta.get("sha256"):
            problems.append(f"sha256 mismatch on {rel}: expected {meta.get('sha256')}, got {actual_sha}")

    actual_rels = {
        p.relative_to(stage_dir).as_posix()
        for p in stage_dir.rglob("*")
        if p.is_file() and p.name != "plan.json"
    }
    extra_rels = sorted(actual_rels - set(files_map.keys()))
    if extra_rels:
        problems.append(f"unexpected extra file(s) in stage: {extra_rels}")

    ini_path = stage_dir / "FO4SFPipboyKit.ini"
    if ini_path.is_file():
        try:
            validate_kit_ini_text(ini_path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"invalid Pip-Boy kit INI: {exc}")

    if args.starfield:
        sf_path = Path(args.starfield)
        if not sf_path.is_file():
            problems.append(f"missing Starfield.esm: {sf_path}")
        else:
            want_sf = plan.get("starfield_esm", {})
            if sha256_file(sf_path) != want_sf.get("sha256"):
                problems.append("Starfield.esm sha256 does not match plan.json")
            elif args.run_dotnet_check:
                try:
                    slot_count = int(args.slot_count if args.slot_count is not None else plan.get("slot_count", 8))
                    chk_flags = ["--slot-count", str(slot_count)]
                    if args.no_test_cell or plan.get("no_test_cell"):
                        chk_flags.append("--no-test-cell")
                    run_dotnet_reputation("check", str(stage_dir / PLUGIN_NAME), str(sf_path), *chk_flags)
                except Exception as exc:
                    problems.append(str(exc))

    if problems:
        for p in problems:
            sys.stderr.write(f"verify failed: {p}\n")
        return 1

    print("verify: ok")
    return 0


def cmd_pipboy_ini(args: argparse.Namespace) -> int:
    base_ini = Path(args.base_ini) if args.base_ini else SHIPPED_PIPBOY_INI
    if not base_ini.is_file():
        sys.stderr.write(f"error: base INI not found: {base_ini}\n")
        return 1

    load_index = parse_hex_int(args.load_index)
    core_load_index = parse_hex_int(args.core_load_index)
    slot_count = int(args.slot_count)
    try:
        merged_ini = inject_pipboy_kit_pages(
            base_ini.read_text(encoding="utf-8"),
            load_index=load_index,
            core_load_index=core_load_index,
            slot_count=slot_count,
        )
        pages = validate_kit_ini_text(merged_ini)
    except Exception as exc:
        sys.stderr.write(f"pipboy-ini failed: {exc}\n")
        return 1

    out_path = Path(args.out)
    if out_path.is_dir():
        out_path = out_path / "FO4SFPipboyKit.ini"
    if out_path.name.casefold() == "fo4sfpipboymenu.ini":
        sys.stderr.write("pipboy-ini failed: refusing to write kit pages into FO4SFPipboyMenu.ini (use FO4SFPipboyKit.ini)\n")
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(merged_ini, encoding="utf-8")

    if args.tsv_out:
        tsv_p = Path(args.tsv_out)
        tsv_p.parent.mkdir(parents=True, exist_ok=True)
        tsv_p.write_text(format_shell_tsv(slot_count=slot_count), encoding="utf-8")
    if args.json_out:
        js_p = Path(args.json_out)
        js_p.parent.mkdir(parents=True, exist_ok=True)
        js_p.write_text(json.dumps(build_shell_manifest(slot_count=slot_count), indent=2) + "\n", encoding="utf-8")

    print(f"wrote {out_path} ({len(pages)} validated kit pages, load_index=0x{load_index:02X})")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    primary = args.file if args.file else str(default_user_log())
    chain = resolve_log_chain(primary, prev_log=args.prev_file)
    try:
        report = stitch_and_evaluate_logs(
            chain,
            papyrus_log_path=args.papyrus_log,
            require_hooks=args.require_hooks,
        )
    except Exception as exc:
        sys.stderr.write(f"log error: {exc}\n")
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_log_summary(report))
    return 0 if report["verdict"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Build, verify, and inspect FO4SFReputation.esm packages and logs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="Stage FO4SFReputation.esm, PEX, and Pip-Boy manifests.")
    p_stage.add_argument("--out", required=True, help="New destination stage directory.")
    p_stage.add_argument("--starfield", help="Path to Starfield.esm (defaults to $STARFIELD_DIR/Data/Starfield.esm).")
    p_stage.add_argument("--compiler", help="Path to PapyrusCompiler.exe.")
    p_stage.add_argument("--content-resources", help="Path to ContentResources.zip.")
    p_stage.add_argument("--load-index", default="0x0A", help="Runtime load-order byte for FO4SFReputation.esm rows.")
    p_stage.add_argument("--core-load-index", default="0x02", help="Runtime load-order byte for FO4SFCoreValues.esm rows.")
    p_stage.add_argument("--slot-count", type=int, default=8, help="Faction slot count in 1..15 (default 8; 13 for FNV).")
    p_stage.add_argument("--no-test-cell", action="store_true", help="Omit FO4SF_RepTestCell and test vendor NPC.")
    p_stage.set_defaults(func=cmd_stage)

    p_ver = sub.add_parser("verify", help="Verify staged FO4SFReputation package against plan.json.")
    p_ver.add_argument("--stage", required=True, help="Staged directory containing plan.json.")
    p_ver.add_argument("--starfield", help="Optional Starfield.esm path for master hash check.")
    p_ver.add_argument("--run-dotnet-check", action="store_true", help="Also re-run ReputationCore check.")
    p_ver.add_argument("--slot-count", type=int, default=None, help="Expected faction slot count.")
    p_ver.add_argument("--no-test-cell", action="store_true", help="Require --no-test-cell player profile.")
    p_ver.set_defaults(func=cmd_verify)

    p_ini = sub.add_parser("pipboy-ini", help="Inject STAT/KARMA & DATA/REPUTATION pages into FO4SFPipboyMenu.ini.")
    p_ini.add_argument("--out", required=True, help="Output INI file path.")
    p_ini.add_argument("--base-ini", help="Input FO4SFPipboyMenu.ini (defaults to shipped INI).")
    p_ini.add_argument("--load-index", default="0x0A", help="Runtime load-order byte for FO4SFReputation.esm rows.")
    p_ini.add_argument("--core-load-index", default="0x02", help="Runtime load-order byte for FO4SFCoreValues.esm rows.")
    p_ini.add_argument("--slot-count", type=int, default=8, help="Faction slot count in 1..15.")
    p_ini.add_argument("--tsv-out", help="Optional path to also write FO4SFPipboyReputation.tsv.")
    p_ini.add_argument("--json-out", help="Optional path to also write FO4SFPipboyReputation.json.")
    p_ini.set_defaults(func=cmd_pipboy_ini)

    p_log = sub.add_parser("log", help="Stitch .1.log + .0.log and verify orthogonality and save/reload parity.")
    p_log.add_argument("--file", help="Path to FO4SFReputation.0.log.")
    p_log.add_argument("--prev-file", help="Optional explicit FO4SFReputation.1.log from pre-quit session.")
    p_log.add_argument("--papyrus-log", help="Optional Papyrus.0.log path to scan for script errors.")
    p_log.add_argument("--require-hooks", action="store_true", help="Require quest_hook, kill_hook, and theft_hook.")
    p_log.add_argument("--json", action="store_true", help="Emit JSON report.")
    p_log.set_defaults(func=cmd_log)

    return ap


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
