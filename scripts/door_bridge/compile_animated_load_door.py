"""Compile FO4SF_AnimatedLoadDoor (with its parent FO4SF_LoadDoor as an import) into a NEW private evidence directory.

The same rules as compile_load_door.py, whose helpers it reuses: no plugin, installer plan, game configuration or
installable stage is created; the Creation Kit sources and the compiled PEX stay outside Git. Both PEX files are
written (the child needs the parent at run time) and pinned in compile.json.

  python scripts/door_bridge/compile_animated_load_door.py --compiler <CK>\\Tools\\Papyrus Compiler\\PapyrusCompiler.exe
      --content-resources <Starfield>\\Tools\\ContentResources.zip --out <new folder>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import compile_load_door as base

HERE = Path(__file__).resolve().parent
SOURCES = (HERE / "FO4SF_LoadDoor.psc", HERE / "FO4SF_AnimatedLoadDoor.psc")


def compile_animated(compiler, resources, out):
    compiler, resources, out = map(lambda p: Path(p).resolve(), (compiler, resources, out))
    for path in (compiler, resources, *SOURCES):
        if not path.is_file():
            raise ValueError(f"missing input: {path}")
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "status": "incomplete", "runtime_accepted": False, "installable": False}
    receipt = out / "compile.json"

    def save():
        receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    try:
        original = {str(p): base.digest(p) for p in (compiler, resources)}
        imports = base.extract(resources, out / "work")
        scripts = out / "Data" / "Scripts"
        scripts.mkdir(parents=True)
        local = []
        for src in SOURCES:                      # frozen copies, not files another agent can change mid-call
            (out / src.name).write_bytes(src.read_bytes())
            local.append(out / src.name)
        inputs = [compiler, resources, *local, *sorted(imports.iterdir())]
        before = {str(p): base.digest(p) for p in inputs}
        if any(before[p] != v for p, v in original.items()):
            raise ValueError("compiler input changed during source extraction")
        runs = []
        for src in local:
            cmd = [str(compiler), src.name, "-f=Starfield_Papyrus_Flags.flg", f"-i={out};{imports}", f"-o={scripts}"]
            result = subprocess.run(cmd, cwd=out, capture_output=True, text=True, timeout=120)
            stem = src.stem
            (out / f"{stem}.stdout.txt").write_text(result.stdout, encoding="utf-8")
            (out / f"{stem}.stderr.txt").write_text(result.stderr, encoding="utf-8")
            runs.append({"command": cmd, "exit_code": result.returncode})
            report.update(runs=runs, inputs=before)
            save()
            if result.returncode or "Compilation succeeded" not in result.stdout:
                raise ValueError(f"Papyrus compiler did not report successful compilation of {src.name}")
        outputs = {}
        for src in local:
            pex = scripts / (src.stem + ".pex")
            if not pex.is_file() or pex.stat().st_size == 0:
                raise ValueError(f"Papyrus compiler produced no nonempty {pex.name}")
            outputs[pex.name] = {"sha256": base.digest(pex), "bytes": pex.stat().st_size}
        if before != {str(p): base.digest(p) for p in inputs}:
            raise ValueError("compiler input changed during compilation")
        report.update(status="compiled", outputs=outputs)
        save()
        return report
    except BaseException as error:
        report.update(status="failed", error=str(error))
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--content-resources", required=True)
    parser.add_argument("--out", required=True)
    a = parser.parse_args()
    r = compile_animated(a.compiler, a.content_resources, a.out)
    print(json.dumps({k: r[k] for k in ("status", "outputs", "installable", "runtime_accepted")}))


if __name__ == "__main__":
    main()
