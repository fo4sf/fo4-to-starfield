# Round 11 / 12 Test Card — `r11-s1-prewar` (Task 6: `S1` *War Never Changes* Pre-War Sanctuary + `PrewarVault111` + Stage 20 Handoff)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Scope:** `r11-s1-prewar` (`Round 12 Task 6` / `Round 11 S1` Stacked Pre-War PR) | **Mode:** `Story (Pre-War + Skip Pre-War) & Warfare` | **Baseline Target:** `candidate-2g-fix2`
> - **Branch / Base:** `gemini/round12-s1-prewar` stacked on `main` (`b2b19a03`) + Task 1 Slot 1 `FO4Port` (`292439a5`, `8163ca9a`) + Task 4 `FO4SFHome` (`908d2cae`) + Task 5 `r12-start-menus` (`9c221667`) + `#854` `--codsworth-handy`
> - **Version Tag:** `<R11_S1_PREWAR_VERSION_TAG>`
> - **Stage Placeholders:** `<stage-dir>`, `<starfield-dir>`, `<probes-root>` (`manifest.json` `356,214 B` SHA-256 `88147bd6ae679abc00c58eed9cea7c518bc46e617752ee65e6c5e3f786126311`, `34` files verified)
> - **Disk Need:** `~2.77 GiB` staged under `<stage-dir>` / `~375 MiB` net delta beyond `FO4Port` BA2s (`>= 60.0 GiB` free required before staging/install; `Starfield.exe` closed)
> - **Truth & Stand-In Policy (`R8` / `R15`):** All `S1` Pre-War exterior/interior flows and all `5` scripted beats `(a)-(e)` are **`OFFLINE ONLY — UNPROVEN IN GAME`** until the owner runs live verification and supplies session footage in `VIDEO`. Each beat `(a)-(e)` is explicitly labeled **`animation stand-in`**. Zero FO4 voices/meshes/archives/dialogue text/videos committed to Git.

---

## Staged Artifacts & Slot 1 -> Slot 2 -> Slot 3 Summary

| Artifact (`Data/...`) | Source / Lineage Status | Expected SHA-256 | Notes |
|---|---|---|---|
| `Data/FO4Port.esm` | Lossless Slot 2 append onto Slot 1 (`8163ca9a...`, `4,656,545 B`) | `99714f16434af3e84e7ca1662707ede7c0db990e56a9155a993655f9f90fa9b5` | `58,571` Slot 1 records `<= 0x00EFAA` byte-identical + `431` `FO4Port_PrewarVault111S1` records `>= 0x00EFAB` (`0x0100EFAB` + `2` `NAVM`s `0x0100F158..59`) |
| `Data/FO4Port - Main.ba2` / `- Textures.ba2` | Copied cleanly (`st_nlink == 1`) from `r11-p1-museum-v2/port` | `064c762499a1cc97...` / `f4664dd0a4fb49a3...` | `117,755,711 B` Main + `2,289,478,621 B` Textures |
| `Data/FO4SFHome.esm` + BA2s + `PlanetData/` | Copied cleanly from Task 4 `w-home` (`EarthPlanetData`) | `11ee81e0e7d14b98...` | `FO4SFHomeClearWeather` / `FO4SFHomeClimate` / `FO4SFHomeAtmosphere`, zero Starfield/Mars refs (`FO4TerrainCore_Home.esm` NOT loaded) |
| `Data/FO4SFPrewar_Sanctuary.esm` + `_Home.esm` | `SanctuaryHillsWorld` `5x5` bounded strip (`277,767 B` + `996 B`) | `1bc50575f4632efe...` / `c413eb5655240548...` | `25` FO4 cells -> `4x4` SF tile (`2,780` placed `REFR`s, `433` bases), `verify_zero_starfield_sky_refs` pass |
| `Data/Terrain/FO4SF_PrewarSanctuaryWorld.btd` | Loose SF `.btd` (`329,679 B`) | `340879276749b9f3...` | Paired with `FO4SFPrewar_Sanctuary - Main.ba2` (`8,211,671 B`, `1,054` entries) & `- Textures.ba2` (`346,891,757 B`, `788` entries) |
| `Data/FO4SFPrewar.esm` + `- Main.ba2` | `dotnet/Prewar` + `#854` Handy + `WwiseConsole` (`18,336 B` + `11,622,385 B`) | `f03d9bd43d784940...` / `e03ac0eca40c6ce8...` | `FO4SF_PrewarQuest` (`0x800`, non-`StartGameEnabled`), `FO4SF_PrewarCodsworthRace` (`#854`), `394` converted `.wem` files, `5` stand-in beats |
| `Data/FO4SFNewGame.esm` + `- Main.ba2` | Rebuilt Slot 3 via `make_newgame.py stage --prewar` (`13,432 B` + `86,071 B`) | `4366e15f90a157f6...` / `53b7614502afafab...` | Dispatches `fo4_prewar_sanctuary` -> `BeginPrewarSanctuary` OR preserves `fo4_vault111` (`Skip Pre-War`), plus `CompletePrewarHandoffStage20` |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.dll` + `.ini` | Reused Slot 2 DLL (`1,456,640 B`) + Stage=2 INI (`2,211 B`) | `c63c3e6a9e00aff4...` / `f77874668cdd3aeb...` | `MapBlockStarMap=0`, `MapSurvival=0`. **DLL nuance:** `c63c3e6a` `ParseLaunchChoicesJsonText` accepts `fo4_vault111`/Warfare in `launch_choices.json`, whereas `fo4_prewar_sanctuary` starts directly via default New Game / in-game `FO4SF_SetupMenu` (no DLL rebuild in Task 6) |
| `Data/SFSE/Plugins/FO4SFStartPlaces.json` | S1-enabled staged start table (`15,469 B`) | `2fa663e6d15a408c...` | Enables `fo4_prewar_sanctuary` (row `0`) + preserves `fo4_vault111` (`Vault 111 (Skip Pre-War)`, row `1`) |

---

## Verification Rows (Every Row Has a `VIDEO` Column)

| Row | Scenario & Beat Coverage | Batch / Trigger (`P3` Clean) | Expected Result / PASS Log (`animation stand-in` beats explicit) | Truth Label | Result | VIDEO |
|---|---|---|---|---|---|---|
| `R11-S1-1` | **Pre-War Sanctuary House Arrival (`fo4_prewar_sanctuary`) & `#854` Pre-War Codsworth** | Default Story New Game / `FO4SF_SetupMenu` row `0` -> `bat s1a` | Spawns at `FO4SF_PrewarHouseSpawnMarker` (`52.82, -2.46, 112.23`) under `FO4SFHomeClearWeather` clear temperate sky; `#854` Mr. Handy Codsworth (`FO4SF_PrewarCodsworthRace`) + Spouse + Vault-Tec Rep present; zero mirror/clipboard popups (`32` surviving scenes contract) | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (Pre-War Sanctuary sky, house, #854 Codsworth)` |
| `R11-S1-2` | **Sanctuary Bridge -> Military Gate -> Hilltop Beats (`(a)` Crowd, `(b)` Vertibirds)** | `bat s1b`, `bat s1c` (`< 200 m`/axis hops from house anchor) | Bounded `25`-cell strip (`4x4` tile, `2,780` `REFR`s) renders bridge, gate, and hill cleanly; Beat `(a)` **`animation stand-in`** (`4` `HumanRace` runners move across bridge to goal); Beat `(b)` **`animation stand-in`** (`2` `vertibird01.nif` props `TranslateTo` overhead) | `OFFLINE ONLY — UNPROVEN IN GAME` (Beats `(a)`, `(b)` = `animation stand-in`) | `PENDING` | `needed (bridge run, crowd + Vertibird stand-ins, gate)` |
| `R11-S1-3` | **Vault Platform Descent & Nuke Flash Beats (`(c)` Lift, `(d)` Flash) -> `PrewarVault111S1`** | `bat s1d` | Beat `(c)` **`animation stand-in`** (`vltelevatorexterior.nif` `-21.6 m / 9.8 s` `TranslateTo` + non-blocking `MoveTo`); Beat `(d)` **`animation stand-in`** (`ExplosionFlash 0x064C26` -> `ExplosionNukeImod 0x02458E` -> `FadetoBlackImod 0x01F60F` + shake); confirmed arrival inside `FO4Port_PrewarVault111S1` (`0x0100EFAB`) with `2` `NAVM`s | `OFFLINE ONLY — UNPROVEN IN GAME` (Beats `(c)`, `(d)` = `animation stand-in`) | `PENDING` | `needed (ExtVaultElevator descent + IMAD nuke flash + PrewarVault111 arrival)` |
| `R11-S1-4` | **Beat `(e)` Kellogg Pod Scene (`394` `.wem` pool / `4` scene lines) -> Stage `20` Handoff** | `bat s1e` | Player positioned at pod across glass from Spouse, Kellogg, and Institute agents (`animation stand-in`); `MQ101KelloggSceneMain` plays `4` converted `.wem` lines -> freeze fade -> `HandoffToVault111CryoStage20()` transitions cleanly into `FO4Port_Vault111Cryo` at `FO4SF_NewGame` stage `20` | `OFFLINE ONLY — UNPROVEN IN GAME` (Beat `(e)` = `animation stand-in`) | `PENDING` | `needed (Kellogg pod scene audio + freeze fade + post-war Vault111Cryo stage 20 wake)` |
| `R11-S1-5` | **Preserved `"Vault 111 (Skip Pre-War)"` (`fo4_vault111`) Regression & Warfare Parity** | Launcher -> `start.mode=story`, `start.place=fo4_vault111` (or `FO4SF_SetupMenu` row `1`) | Choosing `fo4_vault111` skips `S1` completely (`PrewarActiveGlobal=0`) and wakes directly in post-war `FO4Port_Vault111Cryo` (`Slot 1` museum/doors `<= 0x00EFAA` intact); `r12-start-menus` Warfare starts (`minutemen_sanctuary`, `raiders_corvega`, `gunners_plaza`) stay intact | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (Skip Pre-War direct Vault111Cryo spawn confirm)` |

---

## Install, Verify, Status & Exact Undo Commands (Game Closed)

```bash
# 1. Verify all 34 staged files, BA2 entry SHA-256s, lossless Slot 2 FO4Port, P3 rules, and clean plugins
python scripts/probes/stage_r11_s1_prewar.py verify --stage-dir <stage-dir> --core <starfield-dir>/Data/FO4TerrainCore.esm --card docs/testing/round11-s1-prewar-card.md

# 2. Atomic install into Starfield (refuses active FO4SFRouteLoot.esm or FO4TerrainCore_Home.esm)
python scripts/probes/stage_r11_s1_prewar.py install --dir <stage-dir> --starfield <starfield-dir> --version-tag <R11_S1_PREWAR_VERSION_TAG> --card docs/testing/round11-s1-prewar-card.md

# 3. Read-only install receipt status
python scripts/probes/stage_r11_s1_prewar.py status --starfield <starfield-dir>

# 4. Atomic rollback restoring Plugins.txt and prior FO4Port/FO4SFNewGame files by SHA-256
python scripts/probes/stage_r11_s1_prewar.py uninstall --starfield <starfield-dir>
```

### Interactive Console & `P3` Zero-`M`/`N`/`V` Batches (`bat/s1a.txt`..`s1e.txt`)

```console
bat s1a
bat s1b
bat s1c
bat s1d
bat s1e
```

```bat
; s1a.txt..s1e.txt (all hops strictly < 200 m/axis inside their own cell domain; 0 stripped FO4SF_* EDIDs)
getpos x
getpos y
getpos z
```

### Expected PASS Log Lines (`<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log`)

```log
s1 prewar_vault arrival confirmed
s1 stage20 handoff complete -> FO4SF_NewGame stage=20 cell=FO4Port_Vault111Cryo
fade in by=
```

---

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Integration / Dependency in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass: FO4 Mr. Handy body + animations; 4-line Sanctuary talk `completed=true`, `fallback=0` (close camera & greeting replay noted) | Consumed via `--codsworth-handy` (`E2`): `FO4SF_PrewarCodsworthRace` + `FO4SF_PrewarCodsworthSkin`/`AA` + `GeneratedSubgraphData` (`132` files) packed into `FO4SFPrewar - Main.ba2` | Independent review CLEAR; awaiting owner merge |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial: radroach idle & deathclaw tail/spines moved in game; walk/attack/death & bloatfly/mole rat/dog unverified | `S1` Pre-War spawns zero post-war creatures; `creature-slots.json` untouched so `S2`+ creatures remain decoupled | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | Partial: add-on race keyword NPC played FO4 surrender idle vs normal control; walk & 1stP gun unverified | All `S1` human NPCs (`Spouse`, `Vault-Tec Rep`, `Soldier`, `Doctor`, `Kellogg`, `Agents`, `CrowdRunners`) use vanilla `Starfield.esm` `HumanRace` (`0x00347D`) without `--fo4-human-anims` | Stacked on `#854` |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes (`TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14`) | `S1` is pre-war unarmed (zero weapons granted during `S1`; Kellogg pod pistol shot stays a scripted beat `(e)` audio/SFX stand-in until `Stage 20` -> `S2`) | Owner rule: guns NOT ready until parts move |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD:** Hand-made bank (`v174` vs SF `v140`) & direct override silent (add-on banks load on demand) | `S1` dialogue uses `WwiseConsole` `.wem` clips (`394` converted `.wem` files in `FO4SFPrewar - Main.ba2`), while weapon gunshot cues stay labelled stand-ins | Zero FO4 sound banks committed to Git |
