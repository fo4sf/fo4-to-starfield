# One-Command Bundle Installer and Byte-Identical Rollback

`scripts/game/bundle_install.py` (`src/fo4sf/bundle_installer.py`) replaces ad-hoc per-run swap scripts (`prep.ps1` / `rollback.ps1`) with a single ownership-verified command for installing any staged bundle (such as the 19-plugin Core Candidate) and rolling back to a byte-identical prior state.

## What Was Fixed in the Post-Check

Earlier manual swap scripts hardcoded `$ba2 = "FO4TerrainCore - Main.ba2"` in both the pre-install owner list and the post-install check. When `exp_install.py install --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,... --pack` ran, `exp_install.py` named the packed archive after `plugins[0]` (`"FO4ActorRaider - Main.ba2"`), causing the post-check to fail looking for `"FO4TerrainCore - Main.ba2"` in `Data/`.

`bundle_install.py` fixes both halves:
1. **Pre-install backup (`owner-files/`):** Dynamically discovers every `.esm` and `.ba2` owned by the *prior* `Data/FO4SFExp.install.json` receipt and hardlinks each into `<work_dir>/owner-files/` alongside its SHA-256 and `mtime_ns`.
2. **Post-install check (`run_postcheck`):** Dynamically reads the *newly written* `Data/FO4SFExp.install.json` receipt, discovers all `.ba2` archives (`rec["archives"]` or `.ba2` keys in `rec["files"]`, whether `"FO4ActorRaider - Main.ba2"`, `"FO4TerrainCore - Main.ba2"`, or multi-archive splits), verifies each archive stem belongs to an active plugin in `rec["plugins"]`, verifies every installed file's on-disk SHA-256, and confirms `Plugins.txt` tick state and hold state.

## Safety Gates

- **Process & Launcher Lock Refusal:** Refuses immediately (`exit 2`) if `Starfield.exe`, `CreationKit.exe`, `sfse_loader.exe`, `FO4SFLauncher.exe`, or a launcher lockfile (`launcher.lock` / `fo4sf-launcher.lock`) is present.
- **Disk Floor Guard:** Computes incoming `.esm`, `.ba2`/`Data/`, and sidecar bytes, plus `Archive2`'s `~1x` temporary `.ba2` when `--pack` builds a new archive and `owner-files` copy fallback bytes when `work_dir` and `starfield_dir` are on different volumes or `--require-hardlinks` is not set, refusing if free space would drop below `--min-free-gb` (default `24.0` GiB).
- **One-Line Save-Safety Check (`fo4sf.save_safety`):** Delegates directly to `fo4sf.save_safety` (`compare_inspected_builds` + `one_line_swap_warning`) to emit a `WARNING:` line when removed plugins, removed quest stages/aliases, or removed/retyped `VMAD`/`.pex` script properties break saves, or a `NOTE:` line (`unverified, waits for a game test`) when plugin load-order slots shift without breaking changes.
- **Pending Receipt Journaling:** Writes `<work_dir>/install_receipt.json` with `"status": "pending"` (recording `backed_up_configs`, `ini_manifest`, `meta_manifest`, and `owner_files_before`) before the first `plugin_toggle.py` or `exp_install.py uninstall` call, updating it to `"status": "complete"` only after `run_postcheck` passes. `rollback` recovers cleanly from both `"pending"` and `"complete"` receipts.
- **SFSE Sidecar Overwrite Protection:** `--with-sfse-sidecar` refuses to overwrite any existing DLL in `Data/SFSE/Plugins/` and prints a one-line manual-backup/replace instruction naming the conflicting file(s).
- **Dry-Run Mode (`--dry-run`):** Runs process checks, space checks, plugin/archive resolution, and save-swap analysis (or backup SHA-256 verification on `rollback --dry-run`) with zero disk writes.

## Commands

### Dry-Run Check
```bash
python scripts/game/bundle_install.py install \
  --bundle-dir <path/to/core-candidate-bundle> \
  --starfield <path/to/Starfield> \
  --work-dir <path/to/swap-receipt-dir> \
  --dry-run
```

### Live Install + Receipt
```bash
python scripts/game/bundle_install.py install \
  --bundle-dir <path/to/core-candidate-bundle> \
  --starfield <path/to/Starfield> \
  --work-dir <path/to/swap-receipt-dir>
```
Writes `<work_dir>/install_receipt.json`, `before-files/`, `owner-files/`, `hashes-before.txt`, and `hashes-after.txt`.

### Clean Uninstall / Byte-Identical Rollback
```bash
python scripts/game/bundle_install.py rollback \
  --work-dir <path/to/swap-receipt-dir>
```
Releases holds, runs `exp_install.py uninstall`, removes any tracked SFSE sidecars, links/copies back every file in `owner-files/` with original timestamps, restores byte-identical `Plugins.txt`, INI files, `FO4SFExp.install.json`, `FO4SF.toggle.json`, and `launcher_settings.json`, verifies `hashes-before.txt == hashes-rollback.txt`, and prints every artifact compared.
