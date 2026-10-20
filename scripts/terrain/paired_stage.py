"""Pinned offline paired door staging. No installation, game input, or automatic rollback.

pin --spec spec.json --out request.json
run --request request.json --request-sha256 HASH --store STORE --state-sha256 HASH --out NEW
    [--retry-of FAILED_GENERATION --retry-sha256 INTENT_HASH]

The external state pin must survive independently of the store and generation folders.
Retry always creates a NEW generation; old partial outputs and reservations remain.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from types import SimpleNamespace

import port_marker_ids as ids
import port_marker_store as store
import vmad_patch as vp

REPO = Path(__file__).resolve().parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=1, allow_nan=False) + "\n").encode()


def read(path):
    path = Path(path)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"not a regular non-reparse file: {path}")
    raw = path.read_bytes()
    after = path.stat(follow_symlinks=False)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError(f"input changed during read: {path}")
    return raw


def inventory(path):
    """Content pins, including directory membership; output hardlinks are read only."""
    root = Path(path)
    info = root.stat(follow_symlinks=False)
    if getattr(info, "st_file_attributes", 0) & 0x400 or root.is_symlink():
        raise ValueError(f"reparse input: {root}")
    if root.is_file():
        return {".": sha(read(root))}
    if not root.is_dir():
        raise ValueError(f"not a file or directory: {root}")
    result = {"/": "directory"}
    for entry in sorted(root.iterdir()):
        for name, digest in inventory(entry).items():
            result[entry.name if name == "." else f"{entry.name}/{name}"] = digest
    return result


def publish(path, value):
    """Exclusive immutable publication; torn receipts are retained and refuse reuse."""
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    store._sync_directory(path.parent)


def writer_pins():
    # Track all repository build inputs, including shared C#/Python and lock files.
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                                    cwd=REPO).decode().split("\0")
    result = {name: sha(read(REPO / name)) for name in files if name and (
        name.startswith(("scripts/", "src/", "dotnet/")) or
        name in ("global.json", "NuGet.Config", "Directory.Build.props"))
        and not any(part in ("bin", "obj") for part in Path(name).parts)}
    for name, executable in (("python", sys.executable), ("dotnet", shutil.which("dotnet"))):
        if not executable:
            raise ValueError(f"missing {name} runtime")
        result[f"runtime:{name}"] = {"path": str(Path(executable).resolve()), "sha256": sha(read(executable))}
    result["runtime:dotnet-info"] = subprocess.check_output([shutil.which("dotnet"), "--info"]).decode()
    return result


def specification(spec):
    required = {"work", "core", "port", "cluster", "sf_esm", "sf_data"}
    if not isinstance(spec, dict) or set(spec) - required - {"navmesh", "views"} or not required <= set(spec):
        raise ValueError("spec needs work/core/port/cluster/sf_esm/sf_data, optional navmesh/views")
    result = {}
    for key in required | {"navmesh"}:
        value = spec.get(key, "")
        if not value and key == "navmesh":
            result[key] = ""
            continue
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError(f"{key} must be an absolute path")
        result[key] = str(Path(value).resolve(strict=True))
    if type(spec.get("views", False)) is not bool:
        raise ValueError("views must be boolean")
    result["views"] = spec.get("views", False)
    if Path(result["sf_esm"]) != Path(result["sf_data"]) / "Starfield.esm":
        raise ValueError("sf_esm must be the pinned sf_data/Starfield.esm")
    return result


def pin(spec, out):
    spec = specification(spec)
    request = {"schema": 1, "spec": spec, "inputs": {
        key: inventory(value) for key, value in spec.items() if key != "views" and value},
        "writers": writer_pins()}
    publish(out, request)
    return sha(read(out))


def verify_request(request):
    if request.get("schema") != 1 or specification(request["spec"]) != request["spec"]:
        raise ValueError("unsupported or noncanonical request")
    expected = {key: inventory(value) for key, value in request["spec"].items()
                if key != "views" and value}
    if expected != request["inputs"] or writer_pins() != request["writers"]:
        raise ValueError("pinned inputs or writer sources changed; make a fresh request")


def pending_generations(directory):
    """Immutable registrations prevent silently abandoning a half-published pair.

    An explicit retry's registered intent supersedes its parent without deleting
    either. Only leaf intents can require recovery; completion is checked against
    the actual generation bytes, never an in-memory status or boolean flag.
    """
    registered = {}
    for path in Path(directory).glob("paired-intent-*.json"):
        registration = json.loads(read(path))
        generation = Path(registration["generation"])
        raw = read(generation / "intent.json")
        token = sha(raw)
        if path.name != f"paired-intent-{token}.json" or registration["sha256"] != token:
            raise store.RecoveryRequired("paired intent registration differs")
        intent = json.loads(raw)
        if Path(intent["generation"]) != generation or Path(intent["store"]) != Path(directory):
            raise store.RecoveryRequired("paired generation/store binding differs")
        registered[generation] = (generation, intent, token)
    superseded = set()
    for _generation, intent, _token in registered.values():
        previous = intent.get("retry_of")
        if previous:
            old = registered.get(Path(previous))
            if old is None or old[2] != intent["retry_sha256"] or old[1]["request_sha256"] != intent["request_sha256"]:
                raise store.RecoveryRequired("paired retry lineage differs")
            superseded.add(Path(previous))
    pending = []
    for name, (generation, _intent, token) in registered.items():
        if name in superseded:
            continue
        complete_path = generation / "complete.json"
        if not complete_path.exists():
            pending.append(generation)
            continue
        complete = json.loads(read(complete_path))
        if complete["intent_sha256"] != token or any(
                inventory(generation / side) != complete[side] for side in ("core", "port")):
            raise store.RecoveryRequired("completed paired generation drifted; preserve and review")
    return pending


class Pair:
    """A live in-process capability, never reconstructed from output metadata alone."""
    def __init__(self, writer, plan, cluster, base, mapping, port_name, core_out):
        self.writer, self.plan, self.cluster = writer, plan, cluster
        self.base, self.mapping, self.port_name = base, mapping, port_name
        self.core_out = Path(core_out).resolve()

    def verify(self):
        self.writer._verify()
        if self.writer.raw != self.plan.state:
            raise ValueError("paired reservation plan changed")

    def before_core(self, args):
        self.verify()
        if Path(args.out).resolve() != self.core_out or Path(args.out).exists():
            raise ValueError("paired core needs its fresh generation folder")
        if json.loads(read(args.cluster)) != self.cluster:
            raise ValueError("paired cluster changed")

    def require_core(self, directory):
        self.verify()
        if Path(directory).resolve() != self.core_out:
            raise ValueError("wrong paired core")
        plugin, doors = vp.core_doors(str(directory))
        if {ids.source_key(e["src"]) for e in doors} != {
                ids.source_key(e["src"]) for e in self.cluster["doors"]}:
            raise ValueError("core writer changed selected door sources")
        # Validate the actual writer's destinations against exactly the same Plan.
        vp.port_edits(plugin, doors, self.port_name, vp.Plugin(self.base).hedr()[2],
                      vp.merge_offset(str(directory)), **self.port_args(include_base=True))
        return doors

    def port_args(self, include_base=False):
        self.verify()
        result = dict(marker_plan=self.plan, expected_sha256=self.plan.sha256,
                      base_map_raw=self.mapping, base_map_sha256=sha(self.mapping))
        if include_base:
            result["base_raw"] = self.base
        return result


def run(request_path, request_sha256, directory, expected_sha256, out,
        *, retry_of=None, retry_sha256=None):
    raw = read(request_path)
    if sha(raw) != request_sha256:
        raise ValueError("request hash mismatch")
    request = json.loads(raw)
    verify_request(request)
    spec = request["spec"]
    target, directory = Path(out).absolute(), Path(directory).absolute()
    # Neither generation nor store may intersect any input or the repository.
    protected = [Path(v) for k, v in spec.items() if k != "views" and v] + [REPO, directory]
    for path in protected:
        if target.is_relative_to(path) or path.is_relative_to(target):
            raise ValueError("generation overlaps input, repository or store")
    if target.exists() or target.parent.resolve() != target.parent:
        raise ValueError("generation must be fresh with a canonical parent")
    for path in protected[:-1]:
        if directory.is_relative_to(path) or path.is_relative_to(directory):
            raise ValueError("store overlaps input or repository")
    previous = None
    if bool(retry_of) != bool(retry_sha256):
        raise ValueError("retry requires prior generation and its independent intent hash")
    if retry_of:
        previous = Path(retry_of).resolve(strict=True)
        old = read(previous / "intent.json")
        prior = json.loads(old)
        if (sha(old) != retry_sha256 or prior["request_sha256"] != request_sha256
                or Path(prior["store"]) != directory or prior["request"] != request):
            raise ValueError("retry intent/request mismatch")
        if (previous / "complete.json").exists():
            raise ValueError("completed generation is not a failed retry")
        if (previous / "reserved.json").exists() and json.loads(read(previous / "reserved.json"))["sha256"] != expected_sha256:
            raise ValueError("retry needs the independently preserved latest reserved-state pin")
    with store.session(directory, expected_sha256) as writer:
        verify_request(request)
        pending = pending_generations(directory)
        if pending != ([previous] if previous else []):
            raise store.RecoveryRequired("unfinished paired generation requires its explicit pinned retry")
        target.mkdir()
        intent = {"schema": 1, "generation": str(target), "request_sha256": request_sha256, "request": request,
                  "store": str(directory), "state_before": expected_sha256,
                  "retry_of": str(previous) if previous else None, "retry_sha256": retry_sha256}
        publish(target / "intent.json", intent)
        token = sha(read(target / "intent.json"))
        publish(directory / f"paired-intent-{token}.json", {"generation": str(target), "sha256": token})
        try:
            if previous:
                publish(target / "retained-partial.json", {"path": str(previous), "files": inventory(previous)})
            cluster = json.loads(read(spec["cluster"]))
            doors = cluster.get("doors")
            if not isinstance(doors, list) or not doors:
                raise ValueError("paired generation requires an explicit nonempty door cluster")
            name = vp.plugin_in(spec["port"])
            base = read(Path(spec["port"]) / name)
            mapping = read(Path(spec["port"]) / "formids.json")
            plan = writer.reserve(base, mapping, [door["src"] for door in doors], plugin=name)
            publish(target / "reserved.json", {"sha256": plan.sha256, "state": json.loads(plan.state),
                                                "assignments": plan.assignments})
            cluster = copy.deepcopy(cluster)
            for door in cluster["doors"]:
                door["destination"]["id"] = f"{plan.assignments[ids.source_key(door['src'])]:06X}"
            cluster["doors_port"] = dict(cluster.get("doors_port") or {}, plugin=name,
                                        marker_state_sha256=plan.sha256, base_sha256=sha(base),
                                        base_map_sha256=sha(mapping))
            publish(target / "cluster.json", cluster)
            core_out, port_out = target / "core", target / "port"
            pair = Pair(writer, plan, cluster, base, mapping, name, core_out)
            import make_core64c as core
            stage = SimpleNamespace(work=spec["work"], core=spec["core"], out=str(core_out),
                                    sf_esm=spec["sf_esm"], cluster=str(target / "cluster.json"),
                                    navmesh=spec["navmesh"], views=spec["views"], paired=pair)
            if core.cmd_stage(stage) != 0:
                raise ValueError("core stage failed")
            publish(core_out / "paired-input.json", {"state_sha256": plan.sha256,
                                                     "intent_sha256": sha(read(target / "intent.json"))})
            verify_request(request)
            pair.require_core(core_out)
            check = SimpleNamespace(work=spec["work"], core=spec["core"], out=str(core_out),
                                    sf_data=spec["sf_data"], fo4="", fo4_data="", archive2="", scratch="", paired=pair)
            if core.cmd_check(check) != 0:
                raise ValueError("core raw check failed")
            checked_core = inventory(core_out)
            args = SimpleNamespace(port=spec["port"], core=str(core_out), out=str(port_out), paired=pair)
            if vp.cmd_port(args) != 0:
                raise ValueError("port publication failed")
            if vp.cmd_check(args) != 0:
                raise ValueError("port raw check failed")
            checked_port = inventory(port_out)
            pair.require_core(core_out)
            verify_request(request)
            pair.verify()
            completion = {"schema": 1, "intent_sha256": sha(read(target / "intent.json")),
                          "state_sha256": plan.sha256, "core": checked_core, "port": checked_port}
            if completion["core"] != inventory(core_out) or completion["port"] != inventory(port_out):
                raise ValueError("artifacts changed while collecting completion pins")
        except BaseException as error:
            publish(target / "failure.json", {"type": type(error).__name__, "message": str(error),
                                              "state_sha256": sha(writer.raw)})
            raise
    # The lease's exit verification must succeed before advertising any pair.
    publish(target / "complete.json", completion)
    return completion


def verify(out, completion_sha256, directory, expected_sha256):
    """Read-only revalidation, never rerun a writer or upgrade an old verdict."""
    target = Path(out)
    raw = read(target / "complete.json")
    if sha(raw) != completion_sha256:
        raise ValueError("completion hash mismatch")
    complete = json.loads(raw)
    intent = read(target / "intent.json")
    if complete["schema"] != 1 or complete["intent_sha256"] != sha(intent):
        raise ValueError("completion intent mismatch")
    intent = json.loads(intent)
    if (Path(intent["store"]) != Path(directory).absolute() or Path(intent["generation"]) != target.absolute()
            or complete["state_sha256"] != expected_sha256):
        raise ValueError("wrong store or latest external state pin")
    with store.session(directory, expected_sha256):
        verify_request(intent["request"])
        for side in ("core", "port"):
            if inventory(target / side) != complete[side]:
                raise ValueError(f"{side} differs from checked generation")
    return complete


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    p = commands.add_parser("pin")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p = commands.add_parser("run")
    for name in ("request", "request-sha256", "store", "state-sha256", "out"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--retry-of")
    p.add_argument("--retry-sha256")
    p = commands.add_parser("verify")
    for name in ("out", "completion-sha256", "store", "state-sha256"):
        p.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    if args.operation == "pin":
        print(pin(json.loads(read(args.spec)), args.out))
    elif args.operation == "run":
        run(args.request, args.request_sha256, args.store, args.state_sha256, args.out,
            retry_of=args.retry_of, retry_sha256=args.retry_sha256)
        print("Paired offline checks complete; installation and native acceptance remain separate.")
    else:
        verify(args.out, args.completion_sha256, args.store, args.state_sha256)
        print("Paired checked bytes and pins unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
