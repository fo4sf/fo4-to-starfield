"""Launcher backbone CLI (docs/ai/launcher-backbone.md). Offline except `restore --apply`.

    python scripts/launcher.py manifest --out <manifest.json> [--fo4-data <dir> ...] [--starfield <game dir>]
                                        [--output <build dir or file> ...] [--hash-archives] [--hash-limit-mb N]
    python scripts/launcher.py manifest-diff <a.json> <b.json>
    python scripts/launcher.py build <recipe.json> [--set name=value ...] [--dry-run] [--force step,...]
                                     [--until step] [--keep-going] [--min-free-gb N --disk <path> ...] [--idle]
    python scripts/launcher.py same-ids <build A> <build B> [--plugins a.esm,b.esm] [--report <out.json>]
    python scripts/launcher.py snapshot --starfield <game dir> --out <snapshot.json> [--plugins-txt <path>] [--watch <file> ...]
    python scripts/launcher.py restore --snapshot <snapshot.json> [--port-staging <dir>] [--apply]

manifest   what a build was made from and what it made (read only).
build      runs a recipe of the repo's make scripts with resumable, recorded steps (src/fo4sf/launcher/driver.py).
same-ids   do two builds give the same FormIDs? IDENTICAL / SAME_IDS exit 0; IDS_DIFFER / INCOMPLETE exit 1.
snapshot   records Starfield's Plugins.txt, Data plugins and archives and the three install records (read only).
restore    prints what would bring the install back to a snapshot; --apply does it through the existing installers
           and refuses while the game runs or on any conflict.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf.launcher import driver, files, manifest, restore, same_ids  # noqa: E402


def cmd_manifest(a):
    m = manifest.build_manifest(repo=REPO, fo4_data=a.fo4_data, starfield=a.starfield, output_paths=a.output,
                                hash_archives=a.hash_archives,
                                hash_limit=None if a.hash_limit_mb is None else int(a.hash_limit_mb * 2 ** 20))
    files.save_json(a.out, m)
    if "fo4" in m:
        print(f"Fallout 4: {len(m['fo4']['masters'])} masters, {len(m['fo4']['archives'])} archives; "
              f"DLC missing: {', '.join(m['fo4']['dlc_missing']) or 'none'}")
    if "game" in m:
        print(f"Starfield: SFSE {'yes' if m['game']['sfse'] else 'no'}, Creation Kit "
              f"{'yes' if m['game']['creation_kit'] else 'no'}")
    print(f"tools: commit {m['tools']['repo_commit']} dirty={m['tools']['repo_dirty']}; {a.out}")
    return 0


def cmd_manifest_diff(a):
    diffs = manifest.compare_inputs(files.load_json(a.a), files.load_json(a.b))
    for d in diffs:
        print("  " + d)
    print("same inputs and pins" if not diffs else f"{len(diffs)} differences")
    return 0 if not diffs else 1


def cmd_build(a):
    recipe, _env = driver.load_recipe(a.recipe, a.set, repo=REPO)
    force = [s for s in (a.force or "").split(",") if s]
    report = driver.build(recipe, REPO, dry_run=a.dry_run, force=force, until=a.until, min_free_gb=a.min_free_gb,
                          disk_paths=a.disk, idle=a.idle, break_lock=a.break_lock, keep_going=a.keep_going)
    if a.dry_run:
        return 0
    print(f"{recipe['name']}: {'COMPLETE' if report['complete'] else 'NOT complete'} {report['counts']}")
    return 0 if report["complete"] else 1


def cmd_same_ids(a):
    plugins = [p for p in (a.plugins or "").split(",") if p] or None
    rep = same_ids.check(a.a, a.b, plugins)
    for line in same_ids.summary_lines(rep):
        print(line)
    if a.report:
        files.save_json(a.report, rep)
    return 0 if rep["verdict"] in same_ids.VERDICT_OK else 1


def cmd_snapshot(a):
    s = restore.take(a.starfield, a.plugins_txt or None, a.watch)
    files.save_json(a.out, s)
    print(f"snapshot: {len(s['data_top'])} Data files, installs "
          f"{[k for k, v in s['records'].items() if v] or 'none'}; {a.out}")
    return 0


def cmd_restore(a):
    target = files.load_json(a.snapshot)
    if not a.apply:
        cur = restore.take(target["starfield"], target["plugins_txt"], tuple(target.get("watched") or ()))
        p = restore.plan(target, cur, REPO, a.port_staging or None)
        for st in p["steps"]:
            print(f"  {st['what']}: {' '.join(st['argv'][1:])}")
        print(f"  Plugins.txt: {p['plugins_txt']}")
        for n in p["notes"]:
            print("  note: " + n)
        for c in p["conflicts"]:
            print("  CONFLICT: " + c)
        print("dry run (nothing changed); --apply to restore" if not p["conflicts"] else "conflicts: --apply refuses")
        return 0 if not p["conflicts"] else 1
    try:
        left = restore.apply(target, REPO, port_staging=a.port_staging or None)
    except restore.RestoreRefused as e:
        print(f"restore refused: {e}")
        return 1
    for d in left:
        print("  still differs: " + d)
    print("restored" if not left else "NOT fully restored")
    return 0 if not left else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("manifest")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4-data", action="append", default=[])
    s.add_argument("--starfield", default="")
    s.add_argument("--output", action="append", default=[])
    s.add_argument("--hash-archives", action="store_true")
    s.add_argument("--hash-limit-mb", type=float, default=None,
                   help="hash non-plugin outputs up to this size (default: hash everything)")
    s = sub.add_parser("manifest-diff")
    s.add_argument("a")
    s.add_argument("b")
    s = sub.add_parser("build")
    s.add_argument("recipe")
    s.add_argument("--set", action="append", default=[])
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", default="")
    s.add_argument("--until", default=None)
    s.add_argument("--keep-going", action="store_true")
    s.add_argument("--min-free-gb", type=float, default=0.0)
    s.add_argument("--disk", action="append", default=[])
    s.add_argument("--idle", action="store_true", help="Windows: run steps at Idle priority")
    s.add_argument("--break-lock", action="store_true")
    s = sub.add_parser("same-ids")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--plugins", default="")
    s.add_argument("--report", default="")
    s = sub.add_parser("snapshot")
    s.add_argument("--starfield", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--plugins-txt", default="")
    s.add_argument("--watch", action="append", default=[])
    s = sub.add_parser("restore")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--port-staging", default="")
    s.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"manifest": cmd_manifest, "manifest-diff": cmd_manifest_diff, "build": cmd_build,
                "same-ids": cmd_same_ids, "snapshot": cmd_snapshot, "restore": cmd_restore}[a.cmd](a)
    except driver.RecipeError as e:
        print(f"recipe: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
