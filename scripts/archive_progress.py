"""Lossless private evidence capsules. No deletion or game/configuration changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


MANIFEST = "__progress_manifest__.json"
CHUNK = 1024 * 1024


def ordinary(path, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"links/reparse points are not archival sources: {path}")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError(f"unexpected file type: {path}")
    return info


def signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def checked_path(path, directory=False):
    path = Path(os.path.abspath(path))
    for ancestor in reversed(path.parents):
        ordinary(ancestor, directory=True)
    ordinary(path, directory=directory)
    return path


def stream_hash(stream):
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
        size += len(chunk)
    return size, digest.hexdigest()


def files_under(source):
    # Check the supplied path before resolving, including linked ancestors.
    source = checked_path(source, directory=True)
    found = []
    for base, directories, files in os.walk(source, followlinks=False,
                                           onerror=lambda error: (_ for _ in ()).throw(error)):
        for name in directories:
            path = Path(base) / name
            ordinary(path, directory=True)
            member_name(path.relative_to(source).as_posix())
        for name in files:
            path = Path(base) / name
            ordinary(path)
            relative = path.relative_to(source).as_posix()
            member_name(relative)
            found.append((relative, path))
    return sorted(found)


def inspect_file(path):
    before = ordinary(path)
    with path.open("rb") as stream:
        if signature(os.fstat(stream.fileno())) != signature(before):
            raise ValueError(f"source changed before reading: {path}")
        size, digest = stream_hash(stream)
        after_handle = os.fstat(stream.fileno())
    after = ordinary(path)
    if signature(before) != signature(after_handle) or signature(before) != signature(after):
        raise ValueError(f"source changed while reading: {path}")
    return {"size": size, "sha256": digest, "mtime_ns": before.st_mtime_ns}


def inventory(source):
    return {name: inspect_file(path) for name, path in files_under(source)}


def member_name(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("invalid capsule member name")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in (".", "..") for part in name.split("/")):
        raise ValueError("invalid capsule member path")
    if path.as_posix() != name or path.parts[0].casefold() == MANIFEST.casefold():
        raise ValueError("noncanonical or reserved capsule member path")


def verify(archive):
    archive = checked_path(archive)
    with zipfile.ZipFile(archive) as capsule:
        names = capsule.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate capsule members")
        manifest = json.loads(capsule.read(MANIFEST))
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise ValueError("unsupported capsule manifest")
        records = manifest.get("files")
        if not isinstance(records, dict) or set(names) != {*records, MANIFEST}:
            raise ValueError("capsule member inventory does not match manifest")
        for name, record in records.items():
            member_name(name)
            if not isinstance(record, dict) or type(record.get("size")) is not int:
                raise ValueError("invalid capsule file record")
            with capsule.open(name) as stream:
                size, digest = stream_hash(stream)
            if size != record["size"] or digest != record.get("sha256"):
                raise ValueError(f"capsule bytes do not match manifest: {name}")
    return manifest


def check_source(archive, source):
    manifest = verify(archive)
    if os.path.normcase(os.path.abspath(source)) != os.path.normcase(manifest["source"]):
        raise ValueError("source root differs from capsule provenance")
    if inventory(source) != manifest["files"]:
        raise ValueError("source changed since archiving; cleanup is not verified")
    return manifest


def create(source, archive):
    source = Path(os.path.abspath(source))
    archive = Path(os.path.abspath(archive))
    if source == archive or source in archive.parents:
        raise ValueError("archive must be outside the source tree")
    # Refuse linked destination ancestors as well; publishing must stay in the named root.
    checked_path(archive.parent, directory=True)
    if os.path.lexists(archive):
        raise FileExistsError(archive)
    records = inventory(source)
    if not records:
        raise ValueError("no files to preserve")
    manifest = {"version": 1, "source": str(source), "files": records}
    fd, temporary = tempfile.mkstemp(prefix=".progress-", suffix=".zip", dir=archive.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as capsule:
            for name, path in files_under(source):
                if name not in records:
                    raise ValueError("source inventory changed during archiving")
                capsule.write(path, name)
            capsule.writestr(MANIFEST, json.dumps(manifest, sort_keys=True, indent=2))
        verify(temporary)
        # Hash again, including inventory and timestamps: a changed/added/deleted file refuses publication.
        if inventory(source) != records:
            raise ValueError("source changed during archiving")
        with open(temporary, "r+b") as stream:
            os.fsync(stream.fileno())
        # Same-volume, no-overwrite publication. Unsupported hard links fail with the source untouched.
        os.link(temporary, archive)
    finally:
        os.unlink(temporary)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("create")
    build.add_argument("--source", required=True)
    build.add_argument("--archive", required=True)
    audit = sub.add_parser("verify")
    audit.add_argument("--archive", required=True)
    audit.add_argument("--source", help="also verify that the original tree still matches")
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create(args.source, args.archive)
        elif args.source:
            result = check_source(args.archive, args.source)
        else:
            result = verify(args.archive)
        print(json.dumps({"verified_files": len(result["files"]),
                          "original_bytes": sum(row["size"] for row in result["files"].values()),
                          "archive": os.path.abspath(args.archive), "source_deleted": False}))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"archive refused: {error}\n")


if __name__ == "__main__":
    main()
