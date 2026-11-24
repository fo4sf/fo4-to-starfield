# Round 12/13 Test Card — `r12-start-menus` (Start Before Load — Story, Survival & Warfare)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Scope:** `r12-start-menus` (`Round 13 Task 7a / #860`) | **Mode:** `Story & Warfare` | **Baseline Target:** `candidate-2g-fix4` **`test` profile** (`22` plugins, **no** `FO4SFRouteLoot.esm`)
> - **Branch / Stack:** `gemini/r13-w3-860` stacked linearly on `#853` (`b8c359c2`), `#858` (`d5e91274`), and `#841/#842/#848` (`0c897036`) with merged `FO4SFPipboyMenu.dll` (`ctorRefs == 1`, `pipboy_map.cpp`, `D5`/`D7` watch hide, `launch_choices.json` New-Game-only consume-and-delete hydration)
> - **Version Tag (receipt only):** `r13-start-menus-v1`
> - **Stage Placeholders:** `<stage-dir>`, `<starfield-dir>`, `<exp-test-dir>`, `<localappdata>` (`manifest.json` `65,818 B` SHA-256 `f261f9b0991faa48993073494ea9adddcb73b998f3e2c053d38c57e294bd08cb`, `151` files verified)
> - **Disk Need:** `~20 MB` delta under `<starfield-dir>/Data` (`>= 60.0 GB` free required before staging/install; `Starfield.exe` closed)
> - **Starfield UI Stand-In Rule (`#32` / `7143411698`):** Starfield-hosted setup/Chargen/MessageBox/S.P.E.C.I.A.L. screens are **Starfield UI stand-ins — judge Starfield screens on function only** (clean open/close, button selection, no frozen veil, no Starfield world behind Warfare menus). Animations and custom gun sound banks are **out of scope**.
> - **Truth Policy (`R8` / `R15`):** All start flows and exterior Warfare spawns are **`OFFLINE ONLY — UNPROVEN IN GAME`** until the owner runs live verification against `candidate-2g-fix4` (`test` profile) and records `VIDEO`. Zero `FO4SF ` prefix in any user-facing `FULL` name.

---

## Precondition: Install `candidate-2g-fix4` `test` Profile First (Game Closed)

`player` profile (`13` plugins) omits `FO4SFHardcore.esm`, `FO4SFProgression.esm`, and `FO4SFReputation.esm`. Always install **`candidate-2g-fix4` `test` profile** (`22` plugins, **without** `FO4SFRouteLoot.esm`) before installing `r12-start-menus`:

```bash
# Step A (game closed): Install candidate-2g-fix4 test profile (22 plugins, no RouteLoot)
python scripts/game/exp_install.py install --exp-dir <exp-test-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack

# Step B: Turn StartCover ON explicitly before launching via launcher/CLI
python scripts/launcher.py settings --start-cover on
```

---

## Staged Artifacts & Rebuilt Native Binary Summary

| Artifact (`Data/...` or root) | Source / Build Status | Expected SHA-256 | Notes |
|---|---|---|---|
| `Data/FO4SFNewGame.esm` | Rebuilt via `make_newgame.py stage` + `dotnet/NewGame` (`--cog-door` + `--exit-lift`, `13,342 B`) | `543c8116f18d15303cf9f1b3e17607ae2573a6df94ddb0221dfc7650bdf64575` | Non-zero `LiftId` (`0x1618`), `LiftBaseId` (`0xe0e6`), `CogDoorId` (`0x126d`); `0` Commonwealth `WRLD`/`PNDT`/ext-`CELL` overrides |
| `Data/FO4SFNewGame - Main.ba2` | Packed via `probe_common.pack_gnrl_ba2` (`143` entries, `690,337 B`) | `9d27d03370021c3f3dd63cf125fce3d97d779b4f7b532131058977c929983229` | Verified entry hashes matching `FO4SF_NewGame*.pex` (incl. F3/F4/F5 fixes) & vault activator assets |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.dll` | One merged DLL rebuilt from `sfse/FO4SFPipboyMenu` (`main.cpp` + `setup_places.h` + `#858` `pipboy_map.cpp`, `1,492,992 B`) | `c0e232b95fb6a31f1959d02bb529701b41d4e2f6e62dc268739a6e75534b8767` | `build.json` (`2,485 B`, `5e5da261ca73fd00578f202c500d9121b6e538ffc31ab9e85f9660d3eab310f2`); `#858` `+0xB0` StarMap fix + New-Game-only consume-and-delete hydration (F2) + `min_difficulty` write (F11) |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.ini` | Stage=2 safe defaults (`MapBlockStarMap=0`, `MapSurvival=0`, `2,232 B`) | `6b5023155b6fadc6f51314a996bf54afa9724d090e46d0ec4bf9c9083a1faab5` | Preserves shipped defaults |
| `Data/SFSE/Plugins/FO4SFStartPlaces.json` | Copied from `src/fo4sf/core/start_places.json` (`14,871 B`) | `5e50cb0f8e942c0ec60542aa886ebc3bf655688bd74e0e2e8377d2b60afd6a63` | Story `fo4_vault111`-only; Warfare Sanctuary `[-12, 12]` (`0x01000D30`), Gunners Plaza, Corvega; `required_plugins` enforced (F9) |
| `Data/SFSE/Plugins/FO4SFWarfareStarts.json` | Copied from `src/fo4sf/core/warfare_starts.json` (`6,019 B`) | `db86caeac6fb28a213dc14fc2c13b62fb1e042ece9c3f3e264b829ff97f695a1` | Warfare anchor coordinates + Sanctuary `[-12, 12]` (`0x01000D30`) label fix (F12) |

---

## Pre-Launch Choices, Persistence, & Save Rules (F2, F3, F4, F5, F6, F9, F11)

1. **Launcher Write & Availability Checks (F9, F11):**
   - Pre-launch CLI (`python scripts/launcher.py launch-choices ... --write`) writes `<localappdata>/FO4SF/launch_choices.json` with `mode`, `survival`, `place`, `min_difficulty`, `nonce`, and UTC `created_at`.
   - `FO4SFHardcore.esm` MUST be active for `--survival on` (refused otherwise); each row requires its `required_plugins`.
2. **Consume-and-Delete & Zero Loaded-Save Steering (F2):**
   - `FO4SFPipboyMenu.dll` validates fresh `created_at` + non-empty `nonce` and hydrates `0x870..0x879` (including selected `min_difficulty` -> `0x873`, F11) **ONLY on a true New Game** (`!loadGameSeen` via `TESLoadGameEvent`, `!MainMenu`, `GameDaysPassed <= 0.5`, `PlayerLevel <= 1`, `FO4SF_StartChoiceDone < 0.5`).
   - `launch_choices.json` is **deleted immediately** upon consumption/disarm so loaded saves and non-launcher New Games are never steered.
3. **Warfare Direct Load & Exterior Menu Safety (F4, F5, F6):**
   - `SyncPrelaunchHandshake` (`FO4SF_StartCardOpen = -1.0`) waits bounded before `EnterVault` / `EnterPrelaunchWarfareMarker`. **Any `enter vault` log line in a Warfare (`mode=warfare`) run is FAIL.**
   - Player positions onto the merged Warfare exterior cell while black fade is held **before** S.P.E.C.I.A.L. and Looks open (`F5`: Starfield terrain visible behind Warfare S.P.E.C.I.A.L./Looks is **FAIL**).
   - **Honest F6 disclosure:** Both **`raiders_corvega`** and **`gunners_plaza`** map to **faction slot `7` (`FO4SF Outlaws`)**, **`0` FO4 NPCs are placed yet**, and starter gear uses **Starfield stand-in items** (`FO4SFCoreValues.esm:0x000851` Stimpak present; CoreValues FO4 weapon/ammo IDs `0x89D`/`0x8A1..0x8A4`/`0x8CF` are absent from `candidate-2g-fix4`, so `GrantWarfareCoreValuesKit` adds `0` FO4 weapon/ammo records).
4. **Autosave, Manual Test Saves, & Survival Reload Test (F3, F10):**
   - Story (`fo4_vault111`) writes a **stage-20 autosave** (`looks done`). Manual saves made **in this `r12-start-menus` session on `candidate-2g-fix4` `test` profile** may be loaded to verify `R12-T5-3` Survival persistence; never reuse saves from earlier profiles or rounds.
   - Before relaunching Starfield to load the Survival save (`R12-T5-3`), explicitly write `--survival off`:
     ```bash
     python scripts/launcher.py launch-choices --mode warfare --place minutemen_sanctuary --survival off --write
     ```
     PASS requires `survival reload persisted=1 locked=1` in `fo4sf_newgame.0.log` **AND zero `step=launch_choices_hydrated` lines** in `FO4SFPipboyMenu.log` after loading the save.

---

## Verification Rows (Every Row Has a `VIDEO` Column)

| Row | Focus / Pre-Launch Command & In-Game Scenario | Batch / Inspection (`P3` Clean) | Expected Result / PASS & FAIL Logs | Stand-In / Truth | Result | VIDEO |
|---|---|---|---|---|---|---|
| `R12-T5-1` | **Launcher + `StartCover` ON + Story Vault 111 (`Survival=OFF`)** | `python scripts/launcher.py launch-choices --mode story --place fo4_vault111 --survival off --write` -> Play (NEW GAME) | Only `fo4_vault111` claims available in Story; `StartCover` covers boot and lifts on `start_ready.json` (`post_data_load`); `launch_choices.json` deleted; direct Vault 111 cryo spawn + stage-20 autosave written | `OFFLINE ONLY — UNPROVEN IN GAME`; `#32` Starfield UI stand-in (judge on function only) | `PENDING` | `1 fps; audio: not judged; pass: StartCover lifts to clean Vault 111 cryo fade-in & first Chargen/box draws; fail: Starfield intro, stuck veil, or stale launch_choices.json` |
| `R12-T5-2` | **Story S.P.E.C.I.A.L. (40 pts), Traits (0–2), Pip-Boy & Vault Exit 1 Respec** | Continue Story `R12-T5-1` through Vault 111 console & exit lift onto Sanctuary surface | `EvaluateHardcore` PASS line logged (`test` profile); 40-pt S.P.E.C.I.A.L. + 0–2 Traits + 1 Respec prompt at Vault 111 exit preserved; `fade in by=` logged | `OFFLINE ONLY — UNPROVEN IN GAME`; `#32` Starfield UI stand-in (judge on function only) | `PENDING` | `1 fps; audio: not judged; pass: cryo -> terminal/Pip-Boy -> lift exit -> Commonwealth Sanctuary [-12, 12]; fail: UI freeze, missing lift/door, or softlock` |
| `R12-T5-3` | **Warfare Row 1: Minutemen at Sanctuary Hills `(-12, 12)` (`Survival=ON`) + Manual Save + `--survival off` Reload** | 1) `python scripts/launcher.py launch-choices --mode warfare --place minutemen_sanctuary --survival on --write` -> NEW GAME -> save manually<br>2) Close game, run `python scripts/launcher.py launch-choices --mode warfare --place minutemen_sanctuary --survival off --write` -> relaunch & load manual save | New Game: `step=launch_choices_hydrated`, **0 `enter vault` lines (F4=FAIL if seen)**, `direct_warfare` at Sanctuary core `(-1153.83, 1259.64, 110.26)` in `[-12, 12]` (`0x01000D30`), black fade held until exterior positioned before S.P.E.C.I.A.L./Looks (F5), `EvaluateHardcore` active; Save Reload: `survival reload persisted=1 locked=1` AND **0 `step=launch_choices_hydrated`** after load (F2/F3) | `OFFLINE ONLY — UNPROVEN IN GAME`; `#32` Starfield UI stand-in (judge on function only); stand-in gear noted | `PENDING` | `1 fps; audio: not judged; pass: exterior Warfare menus without Starfield terrain behind them (F5), Sanctuary landing, Survival stays ON after --survival off reload; fail: enter vault log, terrain behind menus, or Survival reset/hydrated on load` |
| `R12-T5-4` | **Warfare Row 2: Raiders at Corvega Assembly Plant (`Survival=OFF`, `min_difficulty=2`)** | `python scripts/launcher.py launch-choices --mode warfare --place raiders_corvega --survival off --write` -> NEW GAME, then console `bat s5a` | `step=launch_choices_hydrated` sets `FO4SF_StartDifficulty=2` (F11); **0 `enter vault` lines**; `direct_warfare` at Corvega `[-6, 5]` (`0x01000EAA`) via `FO4Core_CommonwealthAnchor`; uses **faction slot `7` (`FO4SF Outlaws`), `0` FO4 NPCs placed yet, Starfield stand-in gear + `0x000851` Stimpak** (F6) | `OFFLINE ONLY — UNPROVEN IN GAME`; `#32` Starfield UI stand-in; F6 slot 7 / `0` FO4 NPCs / stand-in kit | `PENDING` | `1 fps; audio: not judged; pass: direct exterior Corvega load (0 Vault 111) + clean bat s5a coords; fail: enter vault line, terrain behind S.P.E.C.I.A.L./Looks, or difficulty != 2` |
| `R12-T5-5` | **Warfare Row 3: Gunners at Gunners Plaza (`Survival=ON`, `min_difficulty=1`)** | `python scripts/launcher.py launch-choices --mode warfare --place gunners_plaza --survival on --write` -> NEW GAME, then console `bat s5b` | `step=launch_choices_hydrated` sets `FO4SF_StartDifficulty=1` (F11); **0 `enter vault` lines**; `direct_warfare` at Gunners Plaza `[-2, -11]` (`0x01000F9A`) via `FO4Core_CommonwealthAnchor`; uses **faction slot `7` (`FO4SF Outlaws`), `0` FO4 NPCs placed yet, Starfield stand-in gear + `0x000851` Stimpak** (F6); `EvaluateHardcore` active | `OFFLINE ONLY — UNPROVEN IN GAME`; `#32` Starfield UI stand-in; F6 slot 7 / `0` FO4 NPCs / stand-in kit | `PENDING` | `1 fps; audio: not judged; pass: direct exterior Gunners Plaza load (0 Vault 111) + clean bat s5b coords; fail: enter vault line, terrain behind menus, or difficulty != 1` |
| `R12-T5-6` | **Strict Plugin/Cell & Hardcore CLI Guard Validation** | `python scripts/launcher.py launch-choices --starfield <starfield-dir> --mode story` / `--survival on` with absent plugins (offline/pre-play check) | Story filters out `fo3_vault101`..`fot_bunkeralpha`; Warfare rows require `required_plugins` (`FO4SFNewGame.esm`, `FO4SFCoreValues.esm`, etc.); `--survival on` refused unless `FO4SFHardcore.esm` is active (F9) | Automated unittest + CLI verified offline; live game N/A | `PENDING` | `1 fps; audio: not judged; pass: N/A (CLI/offline negative check) or filtered UI row list matches Starfield active plugins; fail: Survival allowed without FO4SFHardcore.esm or missing-plugin row launchable` |

---

## Install, Status, Required Logs & Session Cleanup (Game Closed)

```bash
# 1. Verify staged probe files, BA2 entry hashes, P3 rules, and zero Commonwealth WRLD/PNDT overrides
python scripts/probes/make_r12_start_menus_probe.py verify --stage-dir <stage-dir>

# 2. Atomic install into Starfield (after candidate-2g-fix4 test profile is installed; checks Starfield.exe==0, >=60 GB free)
python scripts/probes/make_r12_start_menus_probe.py install --dir <stage-dir> --starfield <starfield-dir> --version-tag r13-start-menus-v1 --card docs/testing/r12-start-menus-card.md

# 3. Read-only installation status check (against candidate-2g-fix4 baseline hashes)
python scripts/probes/make_r12_start_menus_probe.py status --starfield <starfield-dir>

# 4. Cleanup launcher pre-launch files after session (delete both files before rollback/next run):
#    rm <localappdata>/FO4SF/launch_choices.json
#    rm <localappdata>/FO4SF/start_ready.json

# 5. One-command atomic rollback of staged probe + baseline uninstall
python scripts/probes/make_r12_start_menus_probe.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Interactive Console & Batches (`P3` Zero-`M`/`N`/`V`)

```console
bat s5a
bat s5b
```

```bat
; <starfield-dir>/s5a.txt (0 M/N/V — Corvega exterior coords)
getpos x
getpos y
getpos z
```

```bat
; <starfield-dir>/s5b.txt (0 M/N/V — Gunners Plaza exterior coords)
getpos x
getpos y
getpos z
```

### Required PASS & Guard Log Lines (`<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log`, `FO4SFHardcore.0.log`, `FO4SFPipboyMenu.log`)

```log
step=start_ready_written ok=1 file=start_ready.json stage=post_data_load
step=launch_choices_hydrated
EvaluateHardcore
direct_warfare
fade in by=
start record mode=
survival reload persisted=1 locked=1
```

(Warfare FAIL guard: `enter vault` must **NOT** appear in a Warfare `mode=warfare` run; Reload FAIL guard: `step=launch_choices_hydrated` must **NOT** appear after save load.)

---

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Integration Status in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass: FO4 Mr. Handy body + animations; 4-line Sanctuary talk `completed=true`, `fallback=0` | **`not applicable`** in Warfare (`mode=2` stops `LandingQuests`); **`gated`** in Story (`mode=1` keeps Vault 111 -> Sanctuary `FO4SF_Codsworth01` optional path intact on `test` profile) | Review CLEAR; Warfare does not trigger `LandingQuests` |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial: radroach idle & deathclaw tail/spines moved in game; walk/attack/death unverified | **`not applicable`** to Start Before Load menus/routing (`creature-slots.json` untouched by `FO4SFNewGame`) | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | Partial: add-on race keyword NPC played FO4 surrender idle; walk & 1stP gun unverified | **`gated`** (`--fo4-human-anims` stays OFF in `r12-start-menus` stage so human anim work never gates start validation) | Stacked on `#854` |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes | **`not applicable`** (`built in` CoreValues FO4 weapon/ammo records are absent in `candidate-2g-fix4`; Warfare rows grant Starfield stand-in gear + `0x000851` Stimpak) | Guns NOT ready until moving parts (`TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14`) ship in Task 2 |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD:** Hand-made bank (`v174` vs SF `v140`) & direct override silent | **`not applicable`** (out of scope here; all starter stand-in gear uses Starfield `SNDR` audio while custom banks stay **`gated`**) | Next probe tests per-item bank link |
