"""Compile only the scripted-door candidate into a NEW private evidence directory.

This creates no plugin, installer plan, game configuration or installable stage.
The supplied Creation Kit sources and compiled PEX must remain outside Git.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "FO4SF_LoadDoor.psc"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(resources, work):
    # Reuse the existing CK import allowlist without compiling the telemetry
    # bridge's glob or changing its stage/INI routines.
    path = HERE.parent / "bridge" / "make_bridge.py"
    spec = importlib.util.spec_from_file_location("load_door_bridge_imports", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return Path(module.extract_sources(str(resources), str(work)))


def compile_candidate(compiler, resources, out):
    compiler, resources, out = map(lambda p: Path(p).resolve(), (compiler, resources, out))
    # Fail before creating output on invalid inputs; never consume an old PEX.
    for path in (compiler, resources, SOURCE):
        if not path.is_file():
            raise ValueError(f"missing input: {path}")
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "status": "incomplete", "runtime_accepted": False,
              "installable": False}
    receipt = out / "compile.json"

    def save():
        receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    try:
        # Pin the archive before extraction, not after a possibly changed read.
        original_inputs = {str(p): digest(p) for p in (compiler, resources)}
        imports = extract(resources, out / "work")
        scripts = out / "Data" / "Scripts"
        scripts.mkdir(parents=True)
        # Compile a frozen source copy, not a file another agent can change mid-call.
        local_source = out / SOURCE.name
        local_source.write_bytes(SOURCE.read_bytes())
        inputs = [compiler, resources, local_source, *sorted(imports.iterdir())]
        before = {str(p): digest(p) for p in inputs}
        if any(before[p] != value for p, value in original_inputs.items()):
            raise ValueError("compiler input changed during source extraction")
        cmd = [str(compiler), SOURCE.name, "-f=Starfield_Papyrus_Flags.flg",
               f"-i={out};{imports}", f"-o={scripts}"]
        report.update(command=cmd, inputs=before)
        save()
        result = subprocess.run(cmd, cwd=out, capture_output=True, text=True, timeout=120)
        (out / "compiler.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (out / "compiler.stderr.txt").write_text(result.stderr, encoding="utf-8")
        report["exit_code"] = result.returncode
        if result.returncode or "Compilation succeeded" not in result.stdout:
            raise ValueError("Papyrus compiler did not report successful compilation")
        pex = scripts / "FO4SF_LoadDoor.pex"
        if not pex.is_file() or pex.stat().st_size == 0:
            raise ValueError("Papyrus compiler produced no nonempty PEX")
        if before != {str(p): digest(p) for p in inputs}:
            raise ValueError("compiler input changed during compilation")
        report.update(status="compiled", output_sha256=digest(pex), output_bytes=pex.stat().st_size)
        save()
        return report
    except BaseException as error:
        report.update(status="failed", error=str(error))
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--content-resources", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = compile_candidate(args.compiler, args.content_resources, args.out)
    print(json.dumps({k: result[k] for k in ("status", "output_sha256", "output_bytes", "installable", "runtime_accepted")}))


if __name__ == "__main__":
    main()
