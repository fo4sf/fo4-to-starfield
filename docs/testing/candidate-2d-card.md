# Candidate 2d — Track 1 Fallout 4 Playable-Path & Safe-Default Session Card (`Round 7` / `W1` / `W4` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Unproven Round-7 Notice:** Candidate 2d (`--profile player`: **`13` Track-1 playable-path plugins** with `W1` safe defaults — `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`; `--profile test`: **`22` plugins** including Track 2 experimental core, still WITHOUT `FO4SFRouteLoot.esm`) requires a **NEW GAME**. **Nothing changed in Round 7 (`W1` direct Vault 111 `FadeHold=false` start bypassing `T3`, `U1` `0x00080E`/`0x00080F` native activator collision + `PipboyWorldCenter` relocation, `13`-plugin Track-1 player bundle decoupling, `Arm=0` / `BootOnFirstOpen=0` safe INI defaults) nor any unrun Round-6 fix (`T5`, `T6` `0x1814`, Concord walk, lift/surface landing) has run in the game yet** — every change below is **`TEST-STATION` (OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs this card. Only `MapBlockStarMap=0` (`20 Nov`) and `T4` under `--fade-hold` (`21 Nov`) have passed in game.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Hex Table (`2c`'s `0B...` IDs NO LONGER APPLY!)

> **IMPORTANT (`21 Nov` Shift Warning):** Because `FO4SFRouteLoot.esm` is OFF and Track 2 experimental slices moved out of `--profile player`, **all Candidate `2c` `0B...` and `12...` FormIDs no longer apply.** Use the exact `2d` runtime hex slots below when `Starfield.esm` (`00`), `BlueprintShips-Starfield.esm` (`01`), and `FO4Port.esm` (`02`) precede the bundle and `FO4SFBridge.esm` is held OFF:

| Hex Slot (`<XX>`) | `13`-Plugin `--profile player` (Track 1 Default) | `22`-Plugin `--profile test` (Track 2 Experimental) | Key Runtime FormIDs (`<XX>000...`) |
|---|---|---|---|
| `03` | `FO4ActorRaider.esm` | `FO4ActorRaider.esm` | Raider actor bases (`03F04800`, `03F04801`) |
| `04` | `FO4TerrainCore.esm` | `FO4TerrainCore.esm` | `04005C50` Sanctuary workbench ref (`0x005C50`), `040A2ECD` workbench base |
| `05` | `FO4TerrainCore_Mars.esm` | `FO4TerrainCore_Mars.esm` | Commonwealth Mars registration |
| `06` | `FO4SFCoreValues.esm` | `FO4SFCoreValues.esm` | `06000801` `Radiation Health Cap`, `06000865` `FO4SF_PipboyAcquired`, `06000870..06000879` start globals, `06000890..06000897` `H00` switches |
| `07` | `FO4SFVaultGearDoor.esm` | `FO4SFVaultGearDoor.esm` | Vault 111 gear door rig |
| `08` | `FO4SFExitLift.esm` | `FO4SFExitLift.esm` | Vault 111 animated exit lift |
| `09` | `FO4SFMission.esm` | `FO4SFMission.esm` | `09000800` `FO4SF_Min00`, `09000802` Preston ref, `09000811` Codsworth ref, `09000814` `FO4SF_CodsworthKeeper`, `09000816` `FO4SF_Codsworth01`, `09000817` `FO4SF_Sanctuary01` |
| `0A` | `FO4SFNewGame.esm` | `FO4SFNewGame.esm` | `0A000800` `FO4SF_NewGame`, **`0A00080F` `FO4SF_PipboyCorpsePickupRef`**, `0A000818`/`0A000819` gear-door console, `0A000820`/`0A000821` Vault 111 pistol + ammo |
| `0B..0F` | `0B` `Workshop`, `0C` `PowerArmor`, `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel` (`10` `MapMarkers`) | `0B` `Rads`, `0C` `Hardcore`, `0D` `Workshop`, `0E` `PowerArmor`, `0F` `Progression` | Track 1 ends at `0F` (+ `10` `FO4SFMapMarkers.esm`) |
| `10..18` | *Omitted in `--profile player`* | **`10` `FO4SFListDialogue.esm` (`10000810`)**, `11` `Combat`, `12` `Reputation`, `13` `Companions`, `14` `ALife`, `15` `FortHagen`, `16` `CoreCandidate`, `17` `PipboyProbe`, `18` `PipboyTravel` | Card A quest is **`10000810`** in `22`-plugin `--profile test` (or `11000810` only if `--with-route-loot` is passed) |

### Console Batch & `P3` Zero-`M`/`N`/`V` Rules (`P2` / `P3`)

1. **Never type `M`, `N`, or `V` in interactive Console, and never pass stripped mod `GLOB`/`QUST` EditorIDs:** Every ```` ```console ```` block below contains **zero `M`, `N`, or `V` letters**. Any command containing `M`, `N`, or `V` (including `Activate`, `getglobalvalue`, `sqv`, `moveto`, or `coc`) sits inside a `<starfield-dir>/<bat-id>.txt` batch file run via `bat <bat-id>` (whose filename also omits `m`, `n`, and `v`).
2. **Confirm load indices without `M`, `N`, or `V`:**
   - `FO4SFCoreValues.esm` (`06`): `help "Health Cap" 4` -> `AVIF: (06000801) 'Radiation Health Cap'` (or read `step=core_value_resolve ... form=0x06000865` in `FO4SFPipboyMenu.log`).
   - `FO4SFNewGame.esm` (`0A`): `help "Gear Door" 4` or `help "Pip-Boy 3000" 4 ACTI` -> `ACTI: (0A00080E) 'Pip-Boy 3000'` (confirms `0A` for `0A00080F.Activate 14`).
   - `FO4SFListDialogue.esm` (`10`, test profile only): `help "List Dialogue" 4 QUST` -> `QUST: (10000810) 'FO4SF Silent-Player List Dialogue'`.

---

## Card 2d-1 — Swap to Track 1 `13`-Plugin Candidate 2d (`W1` Safe Defaults) & Exact Undo (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Prior Candidate `2d` (`21`-plugin `#833` `d62af443`) or `2c` player bundle is installed with `sidecar-install` (`Data/FO4SFSidecar.install.json` present) and `FO4SFBridge.esm` held off. Run `sidecar-undo` and `plugin_toggle.py on` before uninstalling.
- **Stage Placeholders:** `<cand2d-player-bundle>`, `<cand2c-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`sfse_sidecar/reputation/` is reference-only and **not installed**; shipped `FO4SFPipboyMenu.ini` sets `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0` per `W1`).
- **Track 1 `--profile player` Plugin List (`Plugins.txt`, `13` plugins WITHOUT `FO4SFRouteLoot.esm`, WITHOUT Track 2 experimental core + `*FO4SFMapMarkers.esm`, `FO4SFBridge.esm` held OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-session-bridge-off
```

### Exact Undo Command (Game Closed — Clean Uninstall Back to Pre-Session State)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required Startup PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=menu_guard registered=<menus> count=<n>/38
step=map_config map_key=<vk> map_page=3 menus=<menus> block_starmap=0 store=<store> markers=<cnt> travel=<script>.<fn> survival=<0|1> heading_at=<sign>+<off>
```

### Negative / FAIL Conditions
- CLI: `this bundle was built at `, `sidecar install refused:`, `plugins held off by plugin_toggle.py`, `FO4SFRouteLoot.esm` or `FO4SFBridge.esm` active in `Plugins.txt`, or `block_starmap=1` in startup `FO4SFPipboyMenu.log`.

---

## Card 2d-2 — Playable Path Steps 1 & 2: Direct Vault 111 Story Start (`T3`/`W1`), Pip-Boy Pickup (`U1`), Gear Door, Lift & Surface Landing (`T4`/`T1`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2d-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2d-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2d-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2d-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step In-Game Walkthrough (Stop on First Break and Record Evidence)

1. **Step 1 — New Game -> Direct Vault 111 Story Start (`T3` / `W1` `FadeHold=false`):**
   - Click **Main Menu -> New Game** without touching `~` Console.
   - **Expected (`OFFLINE ONLY — UNPROVEN IN GAME`):** With `FadeHold=false`, `FO4SF_NewGameQuest` skips `FO4SF_StartRoomCell` (`0x00081C`) and `FO4SF_NewGameModeMsg` (`0x000806`), enters `FO4Port_Vault111Cryo` directly (`mode choice mode=story survival=0`, `start record ... backdrop=none`, `fade in by=start`, `stage 10 by=Trigger`), and **`2.0 s` later** `FO4SF_NewGameLooks` draws the single **`"Character Appearance"`** box (`0 = Quick start`, `1 = Create character` [`NOT OURS`]).
   - Pick **`Quick start`** (button `0`) -> `looks done: Quick start`, `stage 20 by=Trigger`, `pod settle ok=true`, `pistol filter added`, `pipboy activator registered`, `console activator registered`.
   - **Step 1 remaining break & exact next fix:** If `"Character Appearance"` still sits undrawn in Vault 111 until Console cycles (`T3`), the `Message.Show()` hold is engine-wide post-load rather than `FO4SF_StartRoomCell`-specific -> next fix is moving first-box show onto a post-`LoadingMenu` SFSE/Scaleform trigger or deferring appearance until an in-world mirror/console activator.

2. **Step 2 — Vault 111 -> Surface Arrival (`U1` / `T4` / `T1`):**
   - Walk down the Vault 111 corridor and pick up the fallback Vault 111 pistol (`0A000820`) + `48` rounds (`0A000821`) -> `pistol picked`.
   - Approach the Pip-Boy beside the Vault-Tec skeleton (`0A00080F`, now using `Starfield.esm:0x1CCAC2` native activator collision at `PipboyWorldCenter`, `Scale = 1.0`). Aim at the activator prompt **`Take Pip-Boy 3000`** and press **`E`** -> `pipboy pickup equipped flag=1 worn=true`.
   - **`U1` Single-Line Console Fallback (ONLY if `0A00080F` still shows no prompt or fails on `E` — `R15` record as `U1 FAIL` and continue to test lift/surface):** Put **`0A00080F.Activate 14`** into `<starfield-dir>/u1pick.txt` and run `bat u1pick` in Console (zero `M`/`N`/`V` typed interactively; confirm `0A` via `help "Pip-Boy 3000" 4 ACTI`).
   - Activate the gear-door console (`0A000819`) -> `cog door console activated`, `stage 30 by=vault_console` (gear door opens visually).
   - Step onto the exit lift platform (`0x000801`): confirm `Continue` first prints `elevator continue refused: special unconfirmed`, then complete the 2-page `28`-pt `FO4SF_NewGameSpecial` fallback (`elevator attribute_allocation fallback=FO4SF_NewGameSpecial`), and press **`Continue`** to ride the animated lift (`ascent carried confirmed`) onto the Commonwealth hilltop (`stage 40 by=Trigger`, `landed z=<z> confirmed=True fallback=false`, `stage 200 by=Trigger`, zero `Starfield.exe+0x41efd6` crash with `FO4SFRouteLoot.esm` OFF).
   - **Step 2 remaining breaks & exact next fix:** (a) If `0A00080F` still fails crosshair activation, inspect `pipboy activator registered ref=... pos=...` vs player coordinates and raise `0A00080F` onto an unobstructed desk/pedestal or proximity trigger; (b) if `FO4SFRouteLoot.esm` is ever re-enabled later, isolate `T1` via the `--split bases-only` vs `--split ext-overrides-only` builds first.

```console
help "Health Cap" 4
help "Pip-Boy 3000" 4 ACTI
bat u1pick
```

```bat
; <starfield-dir>/u1pick.txt (U1 fallback ONLY if E on floor Pip-Boy fails; replace 0A if slot differs)
0A00080F.Activate 14
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`)
```log
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=none
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> looks done: <how>
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
FO4SF_NEWGAME rt=<rt> status stage=20 pos=<x> <y> <z> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> pipboy activator registered ref=<ref> id=<id> pos=<x> <y> <z>
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt> equipped=<equipped> base=<base>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<b0> after=<b1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> elevator continue refused: special unconfirmed
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> readback=<r0> <r6>
FO4SF_NEWGAME rt=<rt> elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=<ed> confirmed=true
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
```

### Negative / FAIL Conditions
- First `"Character Appearance"` box sitting undrawn until Console cycles (`T3`), double appearance box (`T4`), `FO4SF_NewGameQuest` going silent after `stage 20`, no activation prompt on `0A00080F` (`U1`), gear door stuck closed (`OPEN-02`), or exterior arrival crash (`T1`).

---

## Card 2d-3 — Playable Path Steps 3, 4 & 5: Sanctuary, Codsworth, Concord Walk, Preston Dialogue (`T6`), Mission Completion & Save/Reload (`TEST-STATION`)

- **Stage Placeholders:** `<cand2d-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2d-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2d-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2d-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step In-Game Walkthrough (Continues Directly from Card 2d-2 Hilltop Landing)

1. **Step 3 — Sanctuary Hills, Codsworth (`09000816`), Sanctuary Workbench (`09000817`), and Walk to Concord:**
   - Walk down the Vault 111 trail into Sanctuary Hills (`mission gate mode=1 started=true`, `codsworth01 init stage=10`, `sanctuary01 init stage=10 bench_ref=0x005C50`).
   - Find Codsworth (`09000811`) at his house (`hold codsworth by=keeper`) and press **`E`**: verify `0x1814` `BeginOnPlayerActivate` choices draw in `DialogueMenu` (zero `"No Dialogue Action on Player in First Phase"`). Pick Choice 4 (Concord lead) -> `codsworth talk end -> min00 stage 10`, `codsworth01 complete`.
   - Activate the Sanctuary workbench (`04005C50` / `0x005C50`) -> `min01 bench activated -> stage 100`, `sanctuary01 bench_activated=true`.
   - Walk south across the Sanctuary bridge, past Red Rocket, into Concord.
   - **Step 3 remaining breaks & exact next fix:** Codsworth's Sanctuary house-sweep patrol (`OPEN-05`) is `NOT BUILT` in cut-down `FO4SF_Codsworth01`; if `0x1814` dialogue still fails to list choices on Codsworth, inspect `FO4SF_Codsworth01_Scene` phase flags against a vanilla Starfield `BeginOnPlayerActivate` scene (`T6`) or wire `#792`'s 4-option wheel.

2. **Step 4 — Preston & Concord Dialogue (`09000800` `FO4SF_Min00`, `T6`):**
   - Approach the Museum of Freedom (`found preston`, `stage 20 by=Trigger`).
   - Clear the exterior Concord street raiders (note: interior Museum raiders, rooftop Power Armor/minigun, and Wave-2 sewer Deathclaw are `NOT BUILT` in the cut-down `FO4SF_Min00` slice) -> `stage 30 by=Trigger`.
   - Save once mid-Concord to throwaway save `Throwaway_Track1_DeleteMe`, **`Quit to Desktop`**, relaunch, and load `Throwaway_Track1_DeleteMe` (`reload mission stage=30` or `stage=20`, verifying `WFC-01` & `WFC-05` persistence).
   - Press **`E`** on Preston Garvey (`09000802`) at the museum entrance -> confirm `preston talk scene triggered stage=30` opens `DialogueMenu` with `0x1814` player choices visible; complete all `3` exchanges -> `preston talk end info=0x092A -> stage 40`, `stage 40 by=info`, `reward credits=100`, `complete stage=200`.
   - **Step 4 remaining breaks & exact next fix:** If Preston shows `"No Dialogue Action on Player in First Phase"`, record exact `preston talk scene ended` log line and switch Concord/Codsworth scenes onto PR `#792`'s proven 4-option dialogue wheel SWF / vanilla Starfield scene template; Museum interior + Preston's Sanctuary walk (`B11`) remain `NOT BUILT` for the next mission slice.

3. **Step 5 — First Missions In Order & Final Save/Reload Check:**
   - Confirm in order: *Out of Time* (`0A000800` stage `200`), *Sanctuary* (`09000817` stage `100`), *Codsworth* (`09000816` stage `100`), and *When Freedom Calls* (`09000800` stage `200`).
   - Save to `Throwaway_Track1_DeleteMe` after `complete stage=200`, `Quit to Desktop`, relaunch and load, walk `50 m` away and back to confirm Preston remains held (`off <= 25.0`, `WFC-05`), then delete `Throwaway_Track1_DeleteMe`.
   - **Step 5 remaining breaks & exact next fix:** *Jewel of the Commonwealth* (`MQ103`) and later FO4 main-spine quests are not yet converted (tracked in `docs/testing/quest-test-plan.md`); next mission slice adds `ConcordMuseum01` interior stages + `MQ103` handoff.

```console
help "Calls" 4 QUST
sqs 09000800
sqs 09000816
sqs 09000817
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> codsworth01 init stage=10
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=true
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=<rf>
FO4SF_MISSION rt=<rt> preston talk scene triggered stage=30
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> complete stage=200
```

### Negative / FAIL Conditions
- `"No Dialogue Action on Player in First Phase"` on Codsworth or Preston (`T6`), `preston talk retry` exhausting retries (`stage 40 by=fallback` or `by=other`), raider kill counter stalling (`WFC-01`), Preston turning hostile on stray hits (`WFC-03`), or Preston snapping `~2,955 m` away after reload (`WFC-05`).

---

## Card 2d-4 — Playable Path Step 6: Essential Pip-Boy Pages (`STAT`, `INV`, `DATA` Quests, Outdoor `M` `MAP`) Under `W1` Safe Defaults (`TEST-STATION`)

- **Shipped `W1` Safe INI (`FO4SFPipboyMenu.ini`):** `Stage=2`, `Movie=FO4SF_Fo4Shell`, `MapBlockStarMap=0` (hide-only, proven outdoor safe `20 Nov`), `Arm=0` (instant open, zero unseen `2.0 s` wrist delay), `BootOnFirstOpen=0` (no flat boot text strips), `Key=0x76` (`F7`), `MapKey=0x4D` (`M`), `Pause=1`.
- **Stage Placeholders:** `<cand2d-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2d-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2d-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2d-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
```

### Step 6 In-Game Checks (Outdoors in Sanctuary or Concord After Step 2)

1. **Instant `F7` Open (`STAT`, `INV`, `DATA` Quests):** Press **`F7`**: confirm `FO4SF_Fo4Shell` opens immediately (`Arm=0`, `BootOnFirstOpen=0`) with `members=49 of=49`, verify `STAT` draws, switch to `INV` (Fallout items only, zero Starfield Med Pack fallback) and `DATA` (quest page shows *When Freedom Calls*), then press **`Tab`** to close cleanly. Repeat `3` cycles with zero crash.
2. **Outdoor `M` Key (`MAP` Page, `MapBlockStarMap=0`):** Press **`F`** (confirm `blocked input=handscanner`), then press **`M`** outdoors: confirm `step=map_suppress n=<k> name=GalaxyStarMapMenu sent=hide`, our Commonwealth MAP page opens (`step=map_markers ... read_back=match`, player marker at Sanctuary/Concord), **`Tab`** closes (`step=map_unregister ok=1`), and pressing **`M`** a second time reopens cleanly (`0` crashes).
3. **Step 6 remaining breaks & exact next fix:** (a) `PopulateInCall` / `InvDataAnswers` / `StatActions` live data-wiring flags remain gated `0` until the base player loop passes in game -> next step flips `PopulateInCall=1` on a focused card (`Card B` step `1b`); (b) `T7` first-person Pip-Boy arm raise (`Arm=1`) and `$ConsoleFont` boot movie (`BootOnFirstOpen=1`) are non-blocking and moved to **After Merge** (`docs/ui/pipboy-arm-visibility-study.md` sleeve-slot `3`/`8`/`35` occlusion fix).

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49
step=map_key n=<k> vk=0x4d was_open=0 page=3 sent=request_open
step=map_suppress n=<k> name=GalaxyStarMapMenu sent=hide
step=map_markers n=<k> discovered=<d_cnt> undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
step=map_unregister ok=1
```

### Negative / FAIL Conditions
- Access violation at `Starfield.exe+0x2540dc6` on outdoor `M` (`T2`), `GalaxyStarMapMenu` remaining open over our map, `2.0 s` unwanted raise stall (`Arm=1` leaked), or garbled boot strips (`BootOnFirstOpen=1` leaked).

---

## Card 2d-5 — Optional Track 2 (`--profile test`, `22` Plugins Without `FO4SFRouteLoot.esm`): Pre-World `--fade-hold` / Warfare (`T5`) & Card A (`T6` `10000810`) (`TEST-STATION`)

> **Track 2 Scope Note:** Run ONLY after Track 1 Cards 2d-1..2d-4 (or in a separate Track 2 session). This bundle (`<cand2d-test-bundle>`, `22` plugins, **OFF by default** in Track 1) stages `--fade-hold` pre-world setup, `FO4SFListDialogue.esm` (`10000810`), and Track 2 core slices while still keeping `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF.

- **Stage Placeholders:** `<cand2d-test-bundle>`, `<starfield-dir>`, `<quest-hex>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Track 2 `--profile test` Plugin List (`Plugins.txt`, `22` plugins WITHOUT `FO4SFRouteLoot.esm`, `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (`<cand2d-test-bundle>`, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-test-bridge-off
```

### Part 5A (`T5` Warfare Post-Streaming Fade-In under `--fade-hold`)
1. Start a **New Game** -> if `T3` still holds the first box in `FO4SF_StartRoomCell`, open/close `~` Console once (`R15` record `T3` still open) -> pick **`Warfare`** -> **`Easy`** (`0`) -> **`Minutemen`** (`0`) -> **`Sanctuary Hills`** (`0`) -> **`Survival: No`** (`0`) -> confirm `40`-pt `S.P.E.C.I.A.L.` (`FO4SFProgression.esm`) -> **`Quick start`** (button `0`).
2. Confirm `warfare move ok=True marker=FO4Core_CommonwealthMapMarkerSanctuary`, `stage 210 by=Trigger`, and `warfare fade reassert tick=2` lift the black fade and loading spinner automatically within `~2–4 s` (`mission gate mode=2 started=false`).

### Part 5B (`T6` Card A `0x1814` Choice List — `10000810` in `22`-Plugin Test Order)
1. Confirm `<quest-hex>` via `help "List Dialogue" 4 QUST` (`10000810` when `FO4SFCoreValues.esm` is `06` and `FO4SFRouteLoot.esm` is omitted).
2. Run `bat carda0`, then `bat carda1` (`stage 10`) and press **`E`** on `Relay Operator` (`0x000808`): verify `0x1814` (`SCPI = null`) displays the full Phase 1 choice list (pick failing checks `21`/`31`), then `bat carda2` (`stage 15`), press **`E`**, pick passing checks `20`/`22`/`30`/`40`/`50` and Goodbye `60`, and finish with `bat carda3` (`stage 70`).

```console
help "List Dialogue" 4 QUST
sqs 10000810
bat carda0
bat carda1
bat carda2
bat carda3
```

```bat
; <starfield-dir>/carda0.txt (10000810 in 22-plugin test order without FO4SFRouteLoot.esm; confirm via help "List Dialogue" 4 QUST)
sqv 10000810
startquest 10000810
coc FO4SF_ListTalkCell

; <starfield-dir>/carda1.txt
setstage 10000810 10

; <starfield-dir>/carda2.txt
setstage 10000810 15

; <starfield-dir>/carda3.txt
setstage 10000810 70
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `FO4SFListDialogue.0.log`)
```log
FO4SF_NEWGAME rt=<rt> warfare pick faction=0 start=minutemen_sanctuary difficulty=<diff>
FO4SF_NEWGAME rt=<rt> start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=<0|1> difficulty=<diff> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> warfare move ok=True marker=FO4Core_CommonwealthMapMarkerSanctuary dist=<d> z=<z>
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_NEWGAME rt=<rt> warfare fade reassert tick=2
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> eval phase=baseline_low speech=<sp> speech50=fail science=<sc> science40=fail strength=<st> strength7=fail bg_vaultdweller=locked trait_goodnatured=locked end=true
FO4SFLIST rt=<rt> choice_stage stage=21 tag=Speech_50 outcome=fail end=true
FO4SFLIST rt=<rt> eval phase=qualified_high speech=<sp> speech50=pass science=<sc> science40=pass strength=<st> strength7=pass bg_vaultdweller=pass trait_goodnatured=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=20 tag=Speech_50 outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=60 tag=Plain_Goodbye outcome=exit end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
```

### Negative / FAIL Conditions
- **Part 5A (`T5`):** Black screen / loading spinner lasting `> 10 s` after `stage 210 by=Trigger` or `warfare move ok=False`.
- **Part 5B (`T6`):** `"No Dialogue Action on Player in First Phase"` on `Relay Operator` or missing `summary ok=true`.

---

## After Merge (`W4` — Deferred, Not Rushed Into This Candidate)

| Item | Current State (`W1`) | Concise Next Step After `main` Merge |
|---|---|---|
| **`T1` Route-Loot Split** (`FO4SFRouteLoot.esm`) | OFF by default in both `player` and `test`. | Run `--split bases-only` vs `--split ext-overrides-only` in one quick Warfare session to isolate `+0x41efd6` (`+0x1f0`) before re-enabling container loot. |
| **`T3` Pre-World Start-Box Queue** (`--fade-hold`) | OFF in `--profile player` (`FadeHold=false`). | Trace what holds the first `Message.Show()` after `LoadingMenu` on a fresh New Game, or retire message-box start selection in favor of Variant `(b)` `FO4SF_SetupMenu`. |
| **`T6` Dialogue Choice Host** (`0x1814` vs `#792`) | `0x1814` staged in `FO4SFMission.esm` (`player`) and `FO4SFListDialogue.esm` (`test`), unproven in game. | If `0x1814` fails in Cards 2d-3/2d-5, diff against a live Starfield `BeginOnPlayerActivate` scene or route 4-slot FO4 scenes through `#792`'s 4-option dialogue wheel SWF. |
| **`T7` Pip-Boy Arm Raise & Boot Movie** (`N1`) | `Arm=0`, `BootOnFirstOpen=0` safe defaults. | Test bare-forearm `Chronomark` (`0x00080D`) visibility with slots `3`/`8`/`35` unequipped (`docs/ui/pipboy-arm-visibility-study.md`) + `$ConsoleFont` boot SWF on an owner-eyes session; rebase `#780` for 3D wrist render target. |
| **`T8` Start-Room HUD & `0`-XP Secret Area** | `SetCharGenHUDMode(2)`, `ShowFirstPersonGeometry(false)`, `iXPRewardDiscoverSecretArea = 0` staged, unproven in game. | Verify zero `"40 XP"` toast in Vault 111 during Card 2d-2 and zero health bar in `--fade-hold` start room during Card 2d-5. |
| **Variant `(b)` Full Set-Up Screen (`S1`–`S4`)** | `FO4SF_SetupScreen.swf` + `setup-options-proposal.md` built offline, OFF by default. | Bind approved `OPT-*` settings from `docs/newgame/setup-options-proposal.md` after owner review and test `FO4SF_SetupMenu` directly once `T3` is bypassed by Scaleform UI. |
