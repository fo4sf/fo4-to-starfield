# Standalone A-Life mod: engineering status and v1.0 release checklist

This page says what the Starfield A-Life Modder SDK has built and verified **offline** today, and lists the
bounded **in-game** checks that must pass before a v1.0 release is uploaded. Offline checks are not in-game
acceptance: nothing below the "in-game" heading has been run in Starfield yet.

Labels: **verified offline** (a command and its output exist), **built, unverified** (code exists, no
acceptance evidence), **open** (not started).

## 1. Components

| Component | Files | Status |
|---|---|---|
| Config schema, validator, writer payload export | `src/fo4sf/alife/schema.py` | verified offline: `tests/test_alife_sdk_schema.py` |
| Graph import and contraction | `src/fo4sf/alife/graph_builder.py` | verified offline: `tests/test_alife_sdk_schema.py` |
| Offline simulator (balance preview) | `src/fo4sf/alife/sim_math.py` | verified offline: deterministic per seed; mirrors the runtime rules as documented, not measured against the game |
| Presets | `src/fo4sf/alife/presets/*.json` | verified offline: validate; vanilla preset references only `Starfield.esm` records |
| Plugin writer | `dotnet/ALifeMod` | verified offline: `selftest` (synthetic master build, check, tamper/refusal cases) and `check` against the real `Starfield.esm` |
| Runtime scripts | `scripts/alife/FO4SF_ALifeSimQuest.psc`, `FO4SF_ALifeAPI.psc`, `FO4SF_ALifeBeaconEffect.psc` | verified offline: compile with the game's Papyrus compiler against `ContentResources.zip`, property parity with the writer (`tests/test_alife_runtime_psc.py`); behaviour unverified in game |
| Builder / packager CLI | `scripts/alife/build_alife_mod.py` | verified offline: `tests/test_alife_mod_packager.py` (init, validate, simulate, output refusal guard, synthetic verify-dist, log-audit); real `package` runs are recorded by the release verifier, not in Git |
| Modder documentation | `docs/alife/MODDER-GUIDE.md` | written; API table follows the script, which is the source of truth |

The FO4SF slice 1 controller (`scripts/alife/make_alife.py`, `dotnet/ALife`, `FO4SF_ALifeControllerQuest.psc`,
`tests/test_alife.py`) is separate and unchanged by the SDK.

## 2. Offline gate (every release candidate)

Run from the repository root on the exact commit to be released. Record the commit, outputs and hashes in the
release notes (not in Git if they contain machine paths).

- [ ] `python -m unittest tests.test_alife_sdk_schema tests.test_alife_runtime_psc tests.test_alife_mod_writer tests.test_alife_mod_packager` passes (with `FO4SF_DOTNET_TESTS=1` where dotnet is present).
- [ ] `dotnet run --project dotnet/ALifeMod -- selftest <scratch dir>`: 0 compiler warnings, 0 failures.
- [ ] `python -m unittest tests.test_alife tests.test_papyrus_strings` still passes (slice 1 untouched).
- [ ] `python scripts/guard.py` prints `guard: ok`; no machine paths, user names, private links or game text in the diff.
- [ ] `build_alife_mod.py validate` and `simulate --ticks 1000` pass for both presets; the simulation shows spawns, battles and captures for every faction that has a base, and no faction owns every capturable node by tick 200.
- [ ] `build_alife_mod.py package --pack-ba2` of the vanilla preset into a fresh folder outside any repository succeeds, and `verify-dist` passes on it.
- [ ] The packaged plugin's TES4 masters are exactly `["Starfield.esm"]` and it has the Master flag (and the Small flag if `light_master`).
- [ ] All three `.pex` compile with 0 errors and are inside `<Plugin> - Main.ba2`.
- [ ] `package` of the FO4SF Commonwealth preset with `--extra-data-dir` succeeds and `verify-dist` passes (the FO4SF build path).

## 3. In-game gate before v1.0 (bounded Starfield QA)

Each check is one short, scripted session on a clean profile with only `Starfield.esm` and the packaged mod
(installed through a mod manager or the documented manual steps), Papyrus user logging on. Each check passes only
on its own evidence: the `StarfieldALife.0.log` judged with `build_alife_mod.py log-audit` plus the noted
observation. Game control for this project stays with the owner's designated test agent; these checks are not run
by the SDK tools.

| # | Check | Pass when |
|---|---|---|
| G1 | Load and init | new game (or an existing save) reaches gameplay; log has `init`, `options`, no `error`; `log-audit` exit 0 |
| G2 | Gameplay options | Settings -> Gameplay shows the A-Life group with its three options; toggling Enabled off and on logs `options`/`api` and pauses/resumes ticks |
| G3 | Field Transponder | the player holds one; using it shows the status message box and it is still in the inventory afterwards |
| G4 | Offline life | far from every node for 10 minutes of play time: `squad_spawn`, `order`, `node_arrive` lines; no squad materializes |
| G5 | Materialize at 450 m | walking toward a marching squad: one `materialize` with the squad's member count; actors stand on the ground (no falling, no buried actors) |
| G6 | 3D movement | the materialized squad moves along waymarkers toward its goal for at least 2 minutes; no more than one `stuck_relink` per minute |
| G7 | Dematerialize at 620 m | walking away: one `dematerialize` with the surviving member count; the actors are gone; the squad keeps marching offline |
| G8 | Interior hand-off | entering an interior with a squad online dematerializes it; leaving again does not duplicate it |
| G9 | Offline battle and capture | over a long offline session: at least one `battle`, `battle_end`, `squad_defeated` and `capture`, consistent with `simulate` order of magnitude |
| G10 | Save and reload | saving with squads offline and online, then reloading: `load_game`, no duplicated squads, ticks continue, options still applied |
| G11 | API from another mod | a small test plugin calling `IsRunning`, `SpawnSquadAtNode`, `OrderRaid`, `SetNodeOwner` gets the documented return values and the `api` log lines |
| G12 | Performance | one hour of play: no Papyrus stack dumps or suspended-stack warnings attributable to A-Life in the Papyrus log; frame time unaffected by the offline tier |
| G13 | Uninstall path | disabling A-Life, saving and removing the plugin loads the save without A-Life actors left in the world |

The FO4SF Commonwealth build is a separate target with its own masters; it needs G1 to G10 in that load order
before it is called working there.

## 4. Release packaging

- [ ] Build the release with `--pack-ba2` from a clean checkout of the tagged commit; keep its `manifest.sha256.json`.
- [ ] Zip the contents of the packaged folder (not the folder above it), so `Data/` is at the archive root.
- [ ] The release page states the masters (`Starfield.esm` only for the vanilla build), the game version tested in the in-game gate, the known limitations below, and links `MODDER-GUIDE.md`.
- [ ] No game assets, saves, settings or private paths are in the archive (the archive holds only the files listed in the manifest, built from the SDK).

## 5. Known limitations (state them in the release)

- In-game behaviour (sections 3 G1-G13) is unverified until those checks pass; offline evidence covers the data,
  the plugin structure and the script compile only.
- Squad movement in 3D relies on the cloned NPC template's AI following a linked reference; templates without such
  behaviour stand still (the log shows `stuck_relink`).
- The offline simulator mirrors the documented runtime rules; real tick timing in game (menus, loading, real-time
  clamps) differs, so balance numbers are a preview, not a promise.
- At most 128 nodes, 128 edges, 8 factions and 16 squads per plugin (Papyrus array and design limits).
- The generated plugin overrides the target worldspace record (`WRLD`) and its persistent `CELL` to place its waymarker pool (`0x000810`+); load it before worldspace-lighting/weather mods or merge persistent-cell overrides if another mod edits the same worldspace record.
- Because the standalone plugin avoids taking `SFBGS007.esm` as an extra master, its `GPOG` gameplay-options group is a standalone leaf; until G2 confirms it appears in Settings -> Gameplay without a parent link, all toggles remain accessible via `FO4SF_ALifeAPI` console commands (`cgf "FO4SF_ALifeAPI.Enable"`, `.Disable`, `.Status`).
- Uninstalling a scripted mod from a running save is never fully clean; tell players to disable and save first.
