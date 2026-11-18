#!/usr/bin/env python3
"""CLI wrapper for one-command bundle install, dynamic post-check, and byte-identical rollback.

Examples:
    python scripts/game/bundle_install.py install --bundle-dir <staged_bundle> --starfield <game_dir> --work-dir <backup_dir> [--dry-run]
    python scripts/game/bundle_install.py postcheck --starfield <game_dir>
    python scripts/game/bundle_install.py rollback --work-dir <backup_dir> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.bundle_installer import (  # noqa: E402
    BundleInstallRefused,
    install_bundle,
    rollback_bundle,
    run_postcheck,
)
from fo4sf.launcher import paths as launcher_paths  # noqa: E402


def _default_plugins_txt() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return ""
    return os.path.join(local, "Starfield", "Plugins.txt")


def _default_launcher_settings() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return ""
    return os.path.join(local, "fo4sf", "launcher_settings.json")


def _default_my_games() -> str:
    detected = launcher_paths.detect()
    mg, _how = detected.get("my_games", ("", ""))
    return mg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser("install", help="Back up state, install bundle, run post-check, and write receipt.")
    p_ins.add_argument("--bundle-dir", required=True, help="Staged bundle folder containing .esm plugins and optional Data/.")
    p_ins.add_argument("--starfield", required=True, help="Target Starfield game directory.")
    p_ins.add_argument("--work-dir", required=True, help="Backup and receipt directory for this swap.")
    p_ins.add_argument("--plugins", default="", help="Optional comma-separated plugin list (defaults to bundle_plan.json).")
    p_ins.add_argument("--plugins-txt", default="", help="Override Plugins.txt path (defaults to LOCALAPPDATA/Starfield/Plugins.txt).")
    p_ins.add_argument("--my-games", default="", help="Override Documents/My Games/Starfield directory for INI/Save snapshot.")
    p_ins.add_argument("--launcher-settings", default="", help="Override launcher_settings.json path.")
    p_ins.add_argument("--prepacked", default="", help="Optional prepacked Main.ba2 path.")
    p_ins.add_argument("--prepacked-dir", default="", help="Optional prepacked split-archive directory.")
    p_ins.add_argument(
        "--split-archives",
        nargs="?",
        const="plugin",
        choices=("none", "size", "plugin"),
        default="none",
        help="Split >4 GiB BA2 archives (bare --split-archives defaults to 'plugin').",
    )
    p_ins.add_argument("--max-archive-bytes", type=int, default=3 * (1024 ** 3))
    p_ins.add_argument("--with-sfse-sidecar", action="store_true", help="Copy bundle sfse_sidecar/SFSE/Plugins DLLs if present.")
    p_ins.add_argument("--min-free-gb", type=float, default=24.0, help="Minimum free GiB required after staging (default: 24.0).")
    p_ins.add_argument("--require-hardlinks", action="store_true", help="Refuse if owner-files cannot be hardlinked on the same volume.")
    p_ins.add_argument("--dry-run", action="store_true", help="Run all preflight and save-safety checks without writing any files.")

    p_post = sub.add_parser("postcheck", help="Run the dynamic receipt/archive/Plugins.txt post-check on an installed folder.")
    p_post.add_argument("--starfield", required=True)
    p_post.add_argument("--plugins-txt", default="")

    p_rb = sub.add_parser("rollback", help="Uninstall bundle, restore byte-identical files from --work-dir, and verify hashes.")
    p_rb.add_argument("--work-dir", required=True, help="Backup directory containing install_receipt.json.")
    p_rb.add_argument("--starfield", default="", help="Optional override for Starfield directory.")
    p_rb.add_argument("--plugins-txt", default="", help="Optional override for Plugins.txt.")
    p_rb.add_argument("--dry-run", action="store_true", help="Verify backup integrity and print planned comparisons without modifying disk.")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "install":
            ptxt = args.plugins_txt or _default_plugins_txt()
            mg = args.my_games if args.my_games else _default_my_games()
            lset = args.launcher_settings if args.launcher_settings else _default_launcher_settings()
            install_bundle(
                bundle_dir=args.bundle_dir,
                starfield_dir=args.starfield,
                work_dir=args.work_dir,
                plugins_txt_path=ptxt,
                my_games_dir=mg,
                launcher_settings_path=lset,
                plugins_csv=args.plugins,
                prepacked_ba2=args.prepacked,
                prepacked_dir=args.prepacked_dir,
                split_archives=args.split_archives,
                max_archive_bytes=args.max_archive_bytes,
                with_sfse_sidecar=args.with_sfse_sidecar,
                min_free_gb=args.min_free_gb,
                dry_run=args.dry_run,
                require_hardlinks=args.require_hardlinks,
                repo_root=str(ROOT),
            )
            return 0

        if args.cmd == "postcheck":
            ptxt = args.plugins_txt or _default_plugins_txt()
            res = run_postcheck(args.starfield, ptxt)
            print(json.dumps({"ok": res["ok"], "plugins": res["plugins"], "archives": res["archives"]}, indent=1))
            return 0

        if args.cmd == "rollback":
            rollback_bundle(
                work_dir=args.work_dir,
                starfield_dir=args.starfield,
                plugins_txt_path=args.plugins_txt,
                dry_run=args.dry_run,
                repo_root=str(ROOT),
            )
            return 0
    except BundleInstallRefused as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
