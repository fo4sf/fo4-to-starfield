# One-Command Bundle Installer and Byte-Identical Rollback

`scripts/game/bundle_install.py` (`src/fo4sf/bundle_installer.py`) replaces ad-hoc per-run swap scripts (`prep.ps1` / `rollback.ps1`) with a single ownership-verified command for installing any staged bundle (such as the 19-plugin Core Candidate) and rolling back to a byte-identical prior state.

## What Was Fixed in the Post-Check

Earlier manual swap scripts hardcoded `$ba2 = "FO4TerrainCore - Main.ba2"` in both the pre-install owner list and the post-install check. When `exp_install.py install --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,... --pack` ran, `exp_install.py` named the packed archive after `plugins[0]` (`"FO4ActorRaider - Main.ba2"`), causing the post-check to fail looking for `"FO4TerrainCore - Main.ba2"` in `Data/`.

`bundle_install.py` fixes both halves:
1. **Pre-install backup (`owner-files/`):** Dynamically discovers every `.esm` and `.ba2` owned by the *prior* `Data/FO4SFExp.install.json` receipt and hardlinks each into `<work_dir>/owner-files/` alongside its SHA-256 and `mtime_ns`.
2. **Post-install check (`run_postcheck`):** Dynamically reads the *newly written* `Data/FO4SFExp.install.json` receipt, discovers all `.ba2` archives (`rec["archives"]` or `.ba2` keys in `rec["files"]`, whether `"FO4ActorRaider - Main.ba2"`, `"FO4TerrainCore - Main.ba2"`, or multi-archive splits), verifies each archive stem belongs to an active plugin in `rec["plugins"]`, verifies every installed file's on-disk SHA-256, and confirms `Plugins.txt` tick state and hold state.

## Safety Gates

- **Process & Launcher Lock Refusal:** Refuses immediately (`exit 2`) if `Starfield.exe`, `CreationKit.exe`, `sfse_loader.exe`, `FO4SFLauncher.exe`, or a launcher lockfile (`launcher.lock` / `fo4sf-launcher.lock`) is present.
- **Disk Floor Guard:** Computes total incoming `.esm` + `.ba2`/`Data/` bytes (while hardlinks keep the prior archive alive on disk) and refuses if free space would drop below `--min-free-gb` (default `24.0` GiB).
- **One-Line Save-Invalidation Warning:** Compares the prior active plugin list and binary TES4/`QUST`/`VMAD` signatures against the incoming bundle and prints a single `SAVE-WARNING:` line whenever removed/reordered plugins, quest stage/alias count deltas, or VMAD property changes invalidate existing saves.
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
