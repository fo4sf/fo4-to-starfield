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
Idle priority. A complete run writes the build manifest.

### Recorded restore
`snapshot` keeps Plugins.txt byte for byte, every top-level plugin and archive in Data (plugins hashed; Starfield's
own archives by size and time) and the three install records verbatim. `restore` plans in the swap scripts' order
(bridge off, experiment off, port off; port on, experiment on, `exp_install.py order`, bridge on), reinstalling from
the source folder each record names. It restores Plugins.txt bytes only when every differing line names a plugin an
installer owns. It never deletes a file itself, leaves unowned new files alone (reported), refuses while
Starfield.exe runs, refuses on any conflict before changing anything (an owner's Plugins.txt edit, a vanished
unowned file, a port record with no staging folder unless `--port-staging`), and checks the result against the
snapshot afterwards. The install thread's swap scripts on the PC are not replaced or touched; this is the same
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
`--require-sfse`), and free space minus the floor (default 40 GB) against the need. The table ships empty; entries
come from a real install with `sources-add --manifest <build manifest> --label <text>`, never typed in. On the owner's
PC today detect refuses on DLC (only Automatron and Wasteland Workshop are installed), which is the intended answer.

### measure
`launcher.py measure <folder>` gives a folder's real disk cost with hard links counted once and the part shared with
other folders split out, so "deleting this frees N GB" is a number, not a guess (staged builds hard-link Data from the
work folders). This is the measuring half of the unresolved full-build disk budget.

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
