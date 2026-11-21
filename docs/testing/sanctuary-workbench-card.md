# PC Test Card: Sanctuary Workbench (`0250FE`) & `M1`–`M6` Mission Walk (`<= 5` min, Console-Free)

> **NEW GAME needed (`A16` / `R15`):** Candidate 2b requires a **NEW GAME** in Story mode (`FO4SF_GameMode == 1`, `FO4SF_TestModeEnabled == 0`). Do not open the console (`~` stays closed).

## Pin Table (Hex FormIDs & Coordinates)

| Plugin | Local FormID | Type & EditorID | Role |
|---|---|---|---|
| `FO4SFCoreValues.esm` | `0x000860` / `0x000870` | `GLOB FO4SF_TestModeEnabled` / `GLOB FO4SF_GameMode` | `0x0860 == 0` suppresses `"FO4SF"` screen banners (`1h`) & `FollowTest`; `0x0870` gates Story (`1`) vs Warfare (`2`) |
| `FO4SFMission.esm` | `0x000800` | `QUST FO4SF_Min00` | Concord mission (`10, 20, 30, 35, 40, 200`): silent start at `FO4SFNewGame` `stage 200` |
| `FO4SFMission.esm` | `0x000801` / `0x000802` | `NPC_ FO4_PrestonGarvey` / `ACHR FO4SF_Min00_PrestonREF` | `HumanRace` (`0x00347D`) Preston (**placeholder** face/outfit/weapon) + `SCEN 0x000900` (`INFO 0x092A` -> `stage 35` -> `stage 40 by=info`) |
| `FO4SFMission.esm` | `0x000810` / `0x000811` | `NPC_ FO4_Codsworth` / `ACHR FO4SF_CodsworthREF` | Brushed-steel `.mat` fix (`M6`), `RACE 0x000818` (`AllowPcDialog`), `VTYP 0x000819` (`AllowDefaultDialog`) |
| `FO4SFMission.esm` | `0x000814` | `QUST FO4SF_CodsworthKeeper` | Story-only fixed-spot keeper for Codsworth & Preston (`Preston's group moving to Sanctuary` is **`NOT BUILT`**) |
| `FO4SFMission.esm` | `0x000816` | `QUST FO4SF_Codsworth01` | `MQ102`-lite 4-choice Sanctuary talk (`SCEN 0x000940`; objective cleared automatically if Concord starts first, `B12`) |
| `FO4SFMission.esm` | `0x000817` | `QUST FO4SF_Sanctuary01` | First settlement hand-over (`M5`, started at `FO4SF_Min00` `stage 200`) |
| `FO4TerrainCore.esm` | `0x0A2ECD` / `0x005C50` | `ACTI` / `REFR` (`Fallout4.esm:0250FE`, `CELL 0x000D30`) | Sanctuary carport Workshop workbench at merged `(-2329.250, -1420.193, 112.086)` m |

---

## Card Workbench — Sanctuary Workbench (`0250FE`) & Mission Turn-In (`M1`–`M6`, `B6`, `B9`, `B12`)

- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`, `<log-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data`.
- **Plugin List (`Plugins.txt`, `--profile player`, `22` plugins + `FO4SFMapMarkers.esm`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (plus `*FO4SFMapMarkers.esm`).

### Install & Log Check Commands (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/testing/check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass
```

### Console-Free Steps (`<= 5` Minutes After Hilltop `stage 200`)
1. **Sanctuary `Codsworth01` check (`~45 s`):** Walk to Codsworth (`0x000811`) in Sanctuary, press `E` to open `DialogueMenu`, and select Choice 4 (`codsworth talk end -> min00 stage 10` -> `stage 10 by=info`).
2. **Concord `stage 20` `Quit to Desktop` reload (`~90 s`):** Trigger the Concord street fight (`stage 20 by=Trigger`), save mid-fight, select **`Quit to Desktop`**, relaunch Starfield, reload that save (`reload mission stage=20 relocate_fails=0`), and clear the raiders (`stage 30 by=Trigger`).
3. **Preston `DialogueMenu` turn-in (`~45 s`):** Press `E` on Preston (`0x000802`) and complete all 3 exchanges (`0x000900`, Choice 3 `0x092A` -> `stage 35 by=info` -> `preston talk end info=0x092A -> stage 40` -> `stage 40 by=info` -> `stage 200 by=Trigger`).
4. **Sanctuary Workbench (`0250FE` / `0x005C50`, `~90 s`):** Follow `FO4SF_Sanctuary01` (`0x000817`) back to the Sanctuary carport (`(-2329.25, -1420.19, 112.09)` m) and press `E` on workbench `0x005C50` (`sanctuary01 stage 100 by=bench`, `min01 bench activated -> stage 100`).

### Undo Command (Game Closed)
```bash
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.1.log` + `fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<n> concord_pointed=true
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> reload mission stage=20 relocate_fails=0
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> min01 objective 10 bench
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 bench_bound ref=<ref> loaded=True
FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=bench
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=true
```
