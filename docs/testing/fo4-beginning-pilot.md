# Fallout 4 Beginning Pilot Checklist (`B1`–`B8`, `V1`)

Goal: evaluate the console-free Story-mode Fallout 4 opening walk — **Mode Choice & Cryo Pod -> Vault Pistol, Pip-Boy & Gear-Door Console -> Lift `40`-Point S.P.E.C.I.A.L., Map Setup & Ascent -> Commonwealth Hilltop Landing -> Sanctuary Codsworth `MQ102`-Lite Talk -> Concord Street Raider Fight -> Preston `DialogueMenu` Turn-In -> Sanctuary Workbench (`0250FE`) Hand-Over** — with zero developer console commands (`~` stays closed) and `FO4SF_TestModeEnabled == 0`.

## Status Labels
- **`REACHABLE`**: Encountered in normal console-free play with `FO4SF_TestModeEnabled == 0`.
- **`TEST-STATION`**: Works only via a test station, test cell, or `FO4SF_TestModeEnabled == 1` command (e.g., `FO4SF_COMPreston.FollowTest`).
- **`RECORDS ONLY`**: ESM records or converted assets exist offline without runtime gameplay wiring.
- **`TOOLING`**: Offline bundle verifier and log judge (`src/fo4sf/beginning_pilot.py`, `scripts/testing/check_beginning_pilot.py`).
- **`NOT BUILT`**: Explicitly cut from this round and absent in gameplay.

> [!IMPORTANT]
> **Museum Quest Content Cut From This Round (`NOT BUILT`):**
> The Museum of Freedom interior quest chain is **cut from this round** and labeled **`NOT BUILT`**:
> - **`laser musket`** (`NOT BUILT`)
> - **`balcony talk`** (`NOT BUILT`)
> - **`power armor + fusion core`** on the museum roof (`NOT BUILT` for `REACHABLE`; test-cell station only)
> - **`minigun`** (`NOT BUILT`)
> - **`second wave`** raiders (`NOT BUILT`)
> - **`deathclaw`** civic-access emergence (`NOT BUILT`)
>
> **Explicit Placeholders:**
> - **Vault weapon (`M2`):** Starfield pistol + ammunition stand-in (**placeholder** until converted FO4 10mm weapons ship).
> - **Codsworth (`M6`):** Starfield `OutpostRobotMiniBotA_Garden` skeleton reskinned with `codsworth.nif` (brushed-steel `.mat` fix) on `FO4SF_CodsworthRace` + `FO4SF_CodsworthVoice` (`25` staged `.wem` files).
> - **Preston Garvey (`M4`):** Starfield `HumanRace` (`0x00347D`, `UC_NA_PapaKatz` template) + `GenericMaleEvenToned` + `Outfit_FreestarRanger_Vest_with_Hat` (`0x208E39`) + `Orion` (`0x2773C8`) **placeholder** face, outfit, and weapon; `100` Starfield `Credits` (`0x00000F`) **placeholder** reward until Bottlecaps ship.

---

## 1. End-to-End Beginning Matrix (`B1`–`B8`)

| Step | Label | Required Log State Lines (`fo4sf_newgame.0.log` / `fo4sf_mission.0.log`) | Negative / `FAIL` Conditions |
| :--- | :--- | :--- | :--- |
| **`B1_pod`** | **`REACHABLE`** | `mode choice ... mode=story`, `pod settle ok=true`, `hold-off pass 2 stopped=X of N` | `mode=warfare`, missing `mode choice`, `pod settle ok=false`, or `running_after=true` on pass 2 |
| **`B2_gear_door`** | **`REACHABLE`** | `pistol picked`, `pipboy pickup equipped flag=1` -> `cog door console activated` -> `stage 30` | Missing `cog door console activated`, `cog door opened directly`, console before Pip-Boy pickup, or missing `pistol picked` |
| **`B3_exit_lift`** | **`REACHABLE`** | `special set` summing to `40`, `ascent play accepted=true`, `map setup done markers=<n>`, `ascent carried confirmed` | `special skipped`, S.P.E.C.I.A.L. sum `!= 40`, missing `map setup done`, or `exit failed reason=lift_*` |
| **`B4_surface_landing`** | **`REACHABLE`** | `FinishSurface` `stage 40` -> `landed ... fallback=false` -> `stage 200` | `fell z=`, `fallback=true`, `surface missed`, or `exit failed reason=` |
| **`B5_codsworth_sanctuary`** | **`REACHABLE`** | `mission gate mode=1 started=true` (after `stage 200`), Codsworth held (`off <= 25 m`), `codsworth talk end -> min00 stage 10`, `min00 given by=codsworth\|concord` | Mission log `rt` earlier than `stage 200`, `mission gate mode=2 started=false`, Codsworth keeper failure, or missing `min00 given by=` |
| **`B6_concord_raiders`** | **`REACHABLE`** | `stage 10` -> `stage 20` (survives `reload mission stage=20 relocate_fails=0`; stragglers rescued or `raider cleared absent`) -> `stage 30` | `init raiders=0`, relocation failure budget `>= 10`, or Preston dead / targeting player |
| **`B7_preston_turnin`** | **`REACHABLE`** | `preston talk end info=0x092A -> stage 40`, `stage 40`, `reward credits=100`, `stage 200` | **`stage 40 by=fallback`** (counts as **`FAIL`** for `REACHABLE`), missing `preston talk end`, or `credits < 100` |
| **`B8_sanctuary_bench`** | **`REACHABLE`** | `min01 stage 10 objective bench` -> `min01 bench activated -> stage 100` | Sanctuary workbench `0x005C50` (`0250FE`) fails to open build mode or never logs `min01 bench activated -> stage 100` |

---

## 2. Known-Bug Ledger Coverage (`#820`)

- **`WFC-01` (Exterior Raider Straggler / Unloaded-3D Stall):** **Fixed (`M3`)** — mission `OnPlayerLoadGame` resets `relocateFails = 0`, raiders carry `DefaultCombatMasterPackage` (`0x042240`) + `DefaultSandboxCurrentLocation` (`0x089605`), subterranean/drifted raiders are rescued (`wfc01 rescue`), and `> 60 s` unreachable stragglers auto-clear (`wfc01 raider cleared absent`).
- **`WFC-02` (Direct Approach to Preston):** **Fixed / Retained** — `FindRadius = 20.0 m` + `OnActivate` starts combat across loaded raiders.
- **`WFC-03` (Friendly Fire Hostility):** **Fixed / Retained** — `FO4SF_MinutemenFaction` (`0x081F`) `Ally` to `PlayerFaction` + `IgnoreFriendlyHits(True)` + `StopCombat()`.
- **`WFC-04` (Museum Balcony / Upstairs Door Lockout):** **Deferred (`NOT BUILT`)** — museum interior quest chain cut from this round.
- **`WFC-05` (Post-Completion / Reload Actor Drift):** **Fixed / Mitigated** — `FO4SF_CodsworthKeeper` (`0x0814`) starts on landing in Story mode and maintains merged coordinates across reloads.
- **`WFC-06` (Wave-2 Sewer Grate Deathclaw Snag):** **Deferred (`NOT BUILT`)** — second wave and Deathclaw cut from this round.
- **`WFC-07` (Silent `OnStageSet` Drop):** **Fixed / Retained** — `QuestTypeSideQuest` (`0x047600`) + synchronous `AdvanceTo` -> `Apply` idempotency, with developer `Debug.Notification` banners removed in normal play (`1h`).
- **`COMP-01`..`COMP-06` (`FO4SF_COMPreston` Follow Stand-In):** **Gated as `TEST-STATION`** behind `FO4SF_TestModeEnabled != 0` (`0x000860`); console-free companion recruitment/wait/trade/dismiss remains deferred.

---

## 3. Offline Verification Commands (`TOOLING`)

```bash
# 1. Verify offline that a staged bundle carries all B1..B8 plugins, scripts, meshes, and 25 Codsworth voices:
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <staged_bundle_dir>

# 2. Judge fo4sf_newgame.0.log and fo4sf_mission.0.log after a console-free Story walk:
python scripts/testing/check_beginning_pilot.py check-logs \
  --newgame-log <fo4sf_newgame.0.log> \
  --mission-log <fo4sf_mission.0.log> \
  --require-all-pass
```
