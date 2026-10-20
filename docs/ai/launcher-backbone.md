# Launcher backbone: build manifest, resumable build, recorded restore, same-ids check

Written 2026-10-19 by Claude-cloud. Offline machinery for the GAMMA-style launcher (roadmap middle path: the
build-and-restore backbone and the same-ids check run alongside phases 1 to 3, the launcher itself comes fourth).
Nothing here has run on the PC yet: every result below is a **synthetic-fixture** result, not an in-game or PC one.

Code: `src/fo4sf/launcher/` (manifest, driver, restore, same_ids), CLI `scripts/launcher.py`, example recipe
`scripts/launcher_recipes/core_restage_same_ids.example.json`. Tests: `tests/test_launcher_*.py`.

## What each piece does

| Piece | Command | Reuses | Status |
|---|---|---|---|
| Build manifest | `launcher.py manifest --out m.json --fo4-data <Data> ... --starfield <game> --output <build>` | the checkpoint identity policy (docs/RESUMING-BUILDS.md) | synthetic tests |
| Manifest diff | `launcher.py manifest-diff a.json b.json` (paths ignored, identities and pins compared) | | synthetic tests |
| Build driver | `launcher.py build <recipe.json> --set k=v [--dry-run] [--min-free-gb 40 --disk D:\ ] [--idle]` | wraps make_core64c.py, make_mission.py, convert_batch.py, vmad_patch.py, light_patch.py, the dotnet writers as steps; their own checkpoints stay in charge inside a step | synthetic tests |
| Snapshot | `launcher.py snapshot --starfield <game> --out snap.json` (read only) | the three install records | synthetic tests |
| Restore | `launcher.py restore --snapshot snap.json` (plan; `--apply` acts) | deploy_starfield.py, exp_install.py, bridge_install.py do every file change | synthetic tests, incl. a real exp_install round trip |
| Build status | `launcher.py status <recipe.json> [--set k=v] [--json out.json]` (read only) | the driver's state.json | synthetic tests |
| Same-ids check | `launcher.py same-ids <build A> <build B>` | make_core64c.py's `formids_diff` (compare-ids) when both have formids.json | synthetic tests |

### Build manifest
Inputs: Fallout4.esm and the six DLC masters, found across several Data folders (Steam depots keep DLC apart),
always hashed; missing DLC listed by name (`dlc_missing`); every .ba2 by size and time (`--hash-archives` for
content). Pins: repo commit and dirty flag, Python, numpy, Pillow, dotnet SDK, the Mutagen version of every dotnet
project; Starfield.exe and sfse_loader.exe hashed, Starfield.esm by size and time, Creation Kit and Archive2 presence.
Outputs: every file under each output folder, plugins and json always hashed.

### Build driver
A recipe is a list of steps (argv, inputs, outputs, dependencies, timeout, retries, code paths). State lives in
`<state_dir>/state.json`, written atomically at every transition, with one log per run of a step. A step is reused
only if it last finished with exit 0, its outputs exist and its fingerprint (argv, cwd, input identities, code
content) is unchanged, and no step it depends on ran in this run. Statuses `done`, `reused`, `failed`, `timeout`,
`blocked`, `not_run` are kept apart; `reused` is never counted as new work and only an all-done-or-reused run is
complete (exit 0). A step left `running` by a crash is rerun. One driver per state folder (lock file; `--break-lock`
on purpose only). `--min-free-gb` blocks a step before it starts (the D: 40 GB rule); `--idle` runs steps at Windows
Idle priority. A step may declare `need_gb` (the space it writes); it is blocked unless free space covers the floor
plus that need (the example's stage step says 1 GB, from the measured 0.3 to 1 GiB a staged core costs).
A complete run writes the build manifest.

A step with no `code` list is fingerprinted by the import closure of its Python scripts inside the repo (static
imports, resolved against the script's folder and `src/`), not all of `src/fo4sf` as before: an edit to a module
the step never imports no longer reruns it, and a changed helper two imports down still does (framework question
B7). Steps that load code another way (dotnet projects, data files) list it under `code`, as the example recipe
does; those fingerprints are unchanged. No speed claim: no PC run measured the difference.

`launcher.py status <recipe>` is the read-only view of the same state (no lock taken, nothing written): each step's
last result, runs, seconds, the log of a step that did not finish well, whether a driver holds the folder, and what a
run now would do. A step recorded `running` while no driver holds the lock shows as `interrupted`. This is what the
launcher's progress screen and the install thread read instead of opening state.json by hand.

### Recorded restore
`snapshot` keeps Plugins.txt byte for byte, every top-level plugin and archive in Data (plugins hashed; Starfield's
own archives by size and time) and the three install records verbatim. `restore` plans in the swap scripts' order
(bridge off, experiment off, port off; port on, experiment on, `exp_install.py order`, bridge on), reinstalling from
the source folder each record names. It restores Plugins.txt bytes only when every differing line names a plugin an
installer owns. It never deletes a file itself, leaves unowned new files alone (reported), refuses while
Starfield.exe runs, refuses on any conflict before changing anything (an owner's Plugins.txt edit, a vanished
unowned file, a port record with no staging folder unless `--port-staging`), and checks the result against the
snapshot afterwards. An equal install record is not taken as proof: every file a record owns (loose files in
subfolders included) is hashed at snapshot time and must match the hash the record keeps, before and after, or the
restore refuses. That holds for the target too: a snapshot taken while an owned file was changed or missing is refused as a target, and an owned file whose record keeps no hash must come back with the bytes the snapshot saw (Codex review, 2026-10-20). Unhashed archives are compared by size and time. A complete install that keeps
`plugins_restore_pending` set (it owns the later uninstall's Plugins.txt restoration) is healthy and left alone; only
`complete: false` or `cleanup_pending` counts as an interrupted install to recover (Codex review, 2026-10-19). The install thread's swap scripts on the PC are not replaced or touched; this is the same
practice in code, so the launcher can later call it.

### Same-ids check
Level 1 plugin bytes; level 2 a raw record walk (no Mutagen, no load order): FormID set, type and editor id per
FormID, editor ids that moved to another FormID, record-header metadata, record bodies, TES4 header; level 3 the
converter's formids.json through compare-ids. Verdicts IDENTICAL, SAME_IDS (ids equal, explained diff listed),
IDS_DIFFER, INCOMPLETE; exit 0 only for the first two.

### detect (the launcher's first stage)
`launcher.py detect --fo4-data <Data> ... --starfield <game> --out-dir <drive> --need-gb N` answers "can this PC
build?", read only: Fallout4.esm and each DLC master matched by hash against `scripts/launcher_recipes/known_sources.json`
(unknown versions refused unless `--allow-unknown`), missing DLC named and refused unless `--allow-missing-dlc`,
Starfield.exe, Data and Archive2 required, Creation Kit and SFSE reported (refused only with `--require-ck` /
`--require-sfse`), any `sTestFileN` in Starfield's INIs refused (the game then ignores Plugins.txt), loose files in
the My Games Data folder reported when `--my-games` is given (passed as Windows resolves it, never guessed), and free
space minus the floor (default 40 GB) against the need. Entries come from a real install's build manifest (`sources-add`). On the owner's PC today detect refuses on DLC
(only Automatron and Wasteland Workshop are installed), which is the intended answer.

### measure
`launcher.py measure <folder>` gives a folder's real disk cost with hard links counted once and the part shared with
other folders split out, so "deleting this frees N GB" is a number, not a guess (staged builds hard-link Data from the
work folders). This is the measuring half of the unresolved full-build disk budget.

### Mod manifests (draft v0, plan task L2)
`src/fo4sf/launcher/mods.py`: a mod declares id, version, the core version range it needs, an optional exact Starfield
pin, its plugins, `requires` and `load_after`. `resolve` puts the core's plugins first, then mods in dependency order
with ties broken by id (the same order on every PC), and refuses with every reason at once: a missing requirement, a
cycle, a core or Starfield version mismatch, a duplicate id, a plugin claimed twice or claimed from the core. Not
wired to any install yet; the format is for the talk (it targets a core master that does not exist yet).

## First PC run (read-only and staged only; needs the install thread)

1. **Done 2026-10-19 14:40Z (verified, read only):** `same-ids` on the two staged core plugins
   `D:\Modding\staging\terrain_core64v6c\FO4TerrainCore.esm` (sha256 7030ceed...) and
   `...\terrain_core64v6e\FO4TerrainCore.esm` (0ab3cb29...), copied into the cloud session and deleted after.
   683,870 records each, the same FormID set, no editor id moved, no metadata or TES4 difference; 4 records differ:
   `010027A0 FO4Core_redrpeddoor` is DOOR in v6c and STAT in v6e (the side-door rig turned off, same FormID), and
   the bodies of REFRs `0100C94C`, `0100D9B8`, `0100D9B9` (Red Rocket door references). Verdict IDS_DIFFER, because a
   record that changes type under the same FormID is not the same id to a save; for these two builds that is the
   intended v6e change, not non-determinism (the inputs differ). 19 s for 194 MB in the cloud.
   The hard-linked Mars plugin and formids.json could not be copied (the folder tool refuses hard links), so level 3
   (compare-ids) ran only on the PC earlier ("identical", per the install thread).
2. **Done 2026-10-19 15:05 to 15:09Z on the PC (verified; install thread, Idle priority, nothing installed):** the
   example recipe at 0a8928e (launcher.py b783d89a, recipe 628ea6d1 checked) re-staged v6e from its own inputs into
   `D:\Modding\staging\det_v6e_b`. `core-restage-same-ids: COMPLETE {'done': 4}`, 235 s; check "268 of 268 checks
   ok, CHECK PASS"; compare-ids against terrain_core64v6e identical in every section (refs 624,369, bases 11,768,
   navmeshes 12,104, items 12,616, lights 6,249, doors 15, and the rest); same-ids **IDENTICAL** for
   FO4TerrainCore.esm and FO4TerrainCore_Mars.esm, every formids.json section identical. The stage ran with the
   scripts at 0a8928e rather than v6e's 5a93beb and still came out byte-identical. So on one PC, the same inputs give
   byte-identical core plugins. The first attempt stopped at check (265 of 266, "Starfield.esm needed for the vanilla
   record check"): the example's check step lacked --sf-data and --fo4; fixed in the example since. det_v6e_b (mostly
   hard links) and the worktree stay on D: because the PC refuses our deletes; about 62 GB free.
3. Later, on a second machine (or a clean second checkout path on the same PC), the same recipe: the cross-machine
   half of plan task L4.

## PC numbers, 2026-10-19 16:3xZ (verified, read only, ffe8f4e)

- **Known version table seeded** from the PC's manifest: Fallout4.esm 330,745,373 bytes sha256 ae7be31a...,
  DLCRobot.esm 8,012,051 e71e04ac..., DLCworkshop01.esm 633,592 82914c20... (Steam depots 377163, 435871, 435880). The
  "1.10.163" label is what the research notes say about this depot, not read from the file (unresolved).
- **detect on the PC:** NOT READY, refused only on the four missing DLC (Far Harbor, Contraptions, Vault-Tec,
  Nuka-World); Archive2 yes, Creation Kit yes, SFSE no; D: 42.0 GB free with 40 kept free, so 2.0 GB usable.
- **Real disk cost of staged core builds** (measure, hard links counted once):

| Folder | Files | Listed | Shared with other folders | Deleting frees |
|---|---|---|---|---|
| terrain_core64v6e | 52,550 | 4.45 GiB | 4.15 GiB | 0.30 GiB |
| det_v6e_b (the determinism re-stage) | 52,560 | 4.45 GiB | 3.50 GiB | 0.95 GiB |
| terrain_core64c_work_v6c2 (work folder) | 64,707 | 4.49 GiB | 4.09 GiB | 0.40 GiB |
| terrain_core64v6e_l125_mission_wfc10 | 52,604 | 4.47 GiB | 0.00 GiB | 4.47 GiB |

  A staged core shares nearly all its Data with the work folder, so a new staged build costs about 0.3 to 1 GiB, but
  the `_l125_mission` fold makes a full 4.5 GiB copy. Linking the fold's Data the way stage does would save about
  4 GiB per fold build (a make_mission.py change for its owner, not done here). For the owner's delete list: the
  fold folders free the most; det_v6e_b frees under 1 GiB.

## Alternatives for the owner's talk

1. **Driver: recipe over existing scripts (taken)** vs one Python build graph that imports the converters directly.
   The graph gives finer caching but rewrites the entry points the install thread uses every night; the recipe can
   be replaced step by step later. A third option, Make or another build tool, adds a dependency players must install.
2. **Restore: our installers plus a snapshot (taken)** vs a Mod Organizer 2 profile / virtual file system vs a
   Stock-Game copy of Starfield. MO2 keeps Data clean but is untested with Starfield at this size (unresolved); a
   Stock-Game copy costs well over 100 GB on a drive that keeps 40 GB free. The snapshot route can export to MO2 later.
3. **Same-ids: raw record walk in Python (taken)** vs a C# check with Mutagen vs Spriggit text dumps. Mutagen would
   parse every field but needs a load order and puts the check under GPL-3 binaries; the raw walk needs only the
   header layout both games share and runs in CI. Spriggit would give readable diffs; worth a look when a real diff
   needs explaining (licence not checked).
4. **Archive identity: size and time (taken)** vs full hashes. Hashing all FO4 and DLC archives is tens of GB of
   reads per build; `--hash-archives` exists for a release check.
5. **Where restore lives:** a launcher verb on the player's PC (taken) vs keeping the hand-run swap scripts. The
   scripts stay as they are until the owner decides; the launcher calls the same installers.

## Not done and unresolved
- No PC run yet; no cross-machine run (L4's real half).
- INIs are watched (`--watch`), reported if changed, never written: no installer changes an INI today.
- Release licensing (GPL-3 for shipped Mutagen binaries) is unaffected by this code (no C#), and stays a release task.
