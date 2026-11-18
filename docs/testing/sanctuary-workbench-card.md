# PC Test Card: Sanctuary Workbench (`0250FE`) & `M1`–`M6` Mission Walk (`<= 5` min, Console-Free)

**Target actor:** Claude (PC) — console-free in-game verification in Story mode (`FO4SF_GameMode == 1`, `FO4SF_TestModeEnabled == 0`) once the folded bundle containing `FO4SFMission.esm` + `Data\Scripts\FO4SF_*.pex` is installed with the game closed. Do not open the console (`~` stays closed).

## Pin Table (Hex FormIDs & Coordinates)

| Plugin | Local FormID | Type & EditorID | Role |
|---|---|---|---|
| `FO4SFCoreValues.esm` | `0x000860` / `0x000870` | `GLOB FO4SF_TestModeEnabled` / `GLOB FO4SF_GameMode` | `0x0860 == 0` suppresses `"FO4SF"` screen banners (`1h`) & `FollowTest`; `0x0870` gates Story (`1`) vs Warfare (`2`) |
| `FO4SFMission.esm` | `0x000800` | `QUST FO4SF_Min00` | Concord mission: silent start at `FO4SFNewGame` `stage 200`, objective `10` deferred until Codsworth or `<= 150 m` of Concord (`M1`) |
| `FO4SFMission.esm` | `0x000801` / `0x000802` | `NPC_ FO4_PrestonGarvey` / `ACHR FO4SF_Min00_PrestonREF` | Dedicated `HumanRace` (`0x00347D`) Preston (**placeholder** face/outfit/weapon) + `SCEN 0x000900` (`INFO 0x092A` -> `stage 40`) |
| `FO4SFMission.esm` | `0x000803..0x000807` | `ACHR FO4SF_Min00_Raider_*` | 5 Concord raiders on aliases `1..5` with `DefaultCombatMasterPackage` (`0x042240`) + `DefaultSandboxCurrentLocation` (`0x089605`) (`M3`) |
| `FO4SFMission.esm` | `0x000810` / `0x000811` | `NPC_ FO4_Codsworth` / `ACHR FO4SF_CodsworthREF` | Brushed-steel `.mat` fix (`M6`), `RACE 0x000818` (`AllowPcDialog`), `VTYP 0x000819` (`AllowDefaultDialog`) |
| `FO4SFMission.esm` | `0x000814` | `QUST FO4SF_CodsworthKeeper` | Story-only fixed-spot keeper for Codsworth & Preston |
| `FO4SFMission.esm` | `0x000816` | `QUST FO4SF_Codsworth01` | `MQ102`-lite 4-choice Sanctuary talk (`SCEN 0x000940` -> `codsworth talk end -> min00 stage 10`) |
| `FO4SFMission.esm` | `0x000817` | `QUST FO4SF_Sanctuary01` | First settlement hand-over (`M5`, started at `FO4SF_Min00` `stage 200`) |
| `FO4TerrainCore.esm` | `0x0A2ECD` / `0x005C50` | `ACTI` / `REFR` (`Fallout4.esm:0250FE`, `CELL 0x000D30`) | Sanctuary carport Workshop workbench at merged `(-2329.250, -1420.193, 112.086)` m (`22.4 m` SE of Codsworth) |

User log path: `<My Games>/Starfield/Logs/Script/User/fo4sf_mission.0.log`

---

## Procedure (`<= 5` Minutes, Zero Console Commands)

1. **Sanctuary `Codsworth01` check (`~45 s`, after `FO4SFNewGame` `stage 200`):**
   - Confirm no Concord objective was shown inside Vault 111 and no `"FO4SF"` developer banner appears on screen.
   - Walk to Codsworth (`0x000811`) in Sanctuary (verify bright brushed-steel body, not black, **OWNER TEST** per `R8`), press `E` to open `DialogueMenu`, and pick Choice 4 (head toward Concord). Confirm `FO4SF_Min00` objective `10` appears on the HUD.
2. **Concord `stage 20` save-quit-reload (`WFC-01` / `M3`, `~90 s`):**
   - Approach the Museum of Freedom door in Concord until `stage 20` starts the raider fight.
   - Save mid-fight at `stage 20`, quit to menu, reload that save, and clear the Concord street raiders (`dead` + any `> 60 s` unreachable raiders reaching `5/5` -> `stage 30`).
3. **Preston `DialogueMenu` turn-in -> `FO4SF_Sanctuary01` hand-over (`M4` & `M5`, `~45 s`):**
   - At `stage 30`, press `E` on Preston (`0x000802`) and complete his 3-exchange `DialogueMenu` scene (`0x000900`, Choice 3 -> `stage 40` -> `stage 200`). Confirm HUD objective `10` of `FO4SF_Sanctuary01` (`0x000817`) points back to Sanctuary.
4. **Sanctuary Workbench (`0250FE` / `0x005C50`) build-mode & completion check (`~90 s`):**
   - Follow the HUD marker back to the yellow Sanctuary carport (`(-2329.25, -1420.19, 112.09)` m).
   - Aim at the red Workshop workbench (`0x005C50`), confirm `WORKSHOP / BUILD [E]`, and press `E` once to open Starfield's native Workshop build menu and complete `FO4SF_Sanctuary01`. Press `Esc` once to exit build mode.

---

## Exact Log Verdicts (`fo4sf_mission.0.log`)

### PASS Criteria
- **Story Gate & Deferred Objective (`M1` & `M6`):**
  - First `FO4SF_MISSION` timestamp `rt` is after `FO4SF_NEWGAME` `stage 200`.
  - `FO4SF_MISSION rt=<t> mission gate mode=1 started=true`
  - `FO4SF_MISSION rt=<t> min00 given by=codsworth` (or `by=concord` if approaching Concord `<= 150 m` first)
  - `FO4SF_MISSION rt=<t> codsworth talk end -> min00 stage 10`
  - `FO4SF_MISSION rt=<t> codsworth01 complete choices=<1..4> concord_pointed=true`
- **Concord `stage 20` Reload & Anti-Stall (`M3` / `WFC-01`):**
  - `FO4SF_MISSION rt=<t> reload mission stage=20 relocate_fails=0`
  - If any raider clipped/drifted: `FO4SF_MISSION rt=<t> wfc01 rescue raider=<i> ...`; if unreachable `> 60 s`: `FO4SF_MISSION rt=<t> wfc01 raider cleared absent id=<formid> raider=<i> elapsed=<s > 60>`
  - `FO4SF_MISSION rt=<t> stage 30`
- **Preston `DialogueMenu` Turn-In (`M4`):**
  - `FO4SF_MISSION rt=<t> preston talk end info=0x092A -> stage 40`
  - `FO4SF_MISSION rt=<t> stage 40`, `reward credits=100`, `stage 200`
- **Sanctuary Workbench Hand-Over (`M5` / `2k`):**
  - `FO4SF_MISSION rt=<t> min01 stage 10 objective bench`
  - `FO4SF_MISSION rt=<t> sanctuary01 init stage=10 bench_ref=0x005C50`
  - `FO4SF_MISSION rt=<t> sanctuary01 bench_bound ref=<ObjectReference> loaded=true`
  - `FO4SF_MISSION rt=<t> min01 bench activated -> stage 100`
  - `FO4SF_MISSION rt=<t> sanctuary01 bench_activated=true ref=<ObjectReference> complete=true`

### FAIL Criteria
- Any mission line fires inside Vault 111 prior to `FO4SFNewGame` `stage 200`, or any `"FO4SF"` developer banner appears on screen with `FO4SF_TestModeEnabled == 0`.
- `FO4SF_MISSION rt=<t> stage 40 by=fallback` appears (counts as **`FAIL`** for `REACHABLE` on `M4`).
- Reloading at `stage 20` fails to log `reload mission stage=20 relocate_fails=0` or stalls past `65 s` near the museum door.
- Sanctuary workbench `0x005C50` fails to open Starfield build mode on `E` or fails to log `min01 bench activated -> stage 100`.
