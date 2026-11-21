# Companions, Crew, and Warfare Squads (`FO4SFCompanions.esm`) — Architecture & PC Card

`FO4SFCompanions.esm` implements multi-slot companion, crew, and Warfare fireteam recruitment, tactical commands, three-chokepoint follower teleportation, companion affinity perks, and GAMMA-inspired squad upkeep over Starfield's kept `SQ_Followers` (`0x0000D773`) and `SQ_Groups` (`0x001A9565`) quests without overriding any vanilla record.

For the underlying *S.T.A.L.K.E.R. Anomaly* / *GAMMA* squad balance synthesis and the `GLOB`-tunable cap/cost model, see [gamma-squad-balance.md](../research/gamma-squad-balance.md).

---

## 1. Deliverables & Layout

| Component | Path | Purpose |
|---|---|---|
| Research & balance proposal | `docs/research/gamma-squad-balance.md` | Anomaly/GAMMA cap/cost/anti-trivialization rules & `GLOB` proposal |
| Plugin generator & checker | `dotnet/CompanionsCore/Program.cs` | `build`, `check`, `fixture` (`full`/`minimal`), `selftest` (7 tamper controls) |
| Quest & squad controller | `scripts/companions/FO4SF_CompanionsQuest.psc` | Recruitment gates, tactical wheel, 4-NPC fireteam radio, 3 teleport chokepoints, affinity & upkeep |
| Stager, folder, verifier & log CLI | `scripts/companions/make_companions_core.py` | `precheck`, `stage`, `fold` (`--hardlink`), `verify`, `log`, `console` |
| Ride-along installer | `scripts/companions/companions_core_install.py` | Reversible install/uninstall via `Data/FO4SFCompanions.install.json` |
| Log parser & reference math | `src/fo4sf/companions/core_log.py` | `FO4SFCOMP` parser, `.1.log` + `.0.log` reload stitching, cap/cost math |
| Unit & contract tests | `tests/test_companions_core.py` | Balance doc rules, cap/gate/upkeep math, 3 teleport chokepoints, `.NET` selftest, stage/fold/verify |

---

## 2. Deterministic FormID Contract (`FO4SFCompanions.esm`)

`FO4SFCompanions.esm` lists **`[Starfield.esm]` as its sole master** and overrides **0** records (`SQ_Followers` `0x0000D773`, `SQ_Groups` `0x001A9565`, `DefaultMaster_FollowPackage` `0x000301C5`, and `SQ_Followers_Wait` `0x0029D080` are referenced, never overridden).

| Local ID | Type | EditorID | Default / Role |
|---|---|---|---|
| `0x000800` | `QUST` | `FO4SF_CompanionsQuest` | `StartGameEnabled`, `RefCollectionAlias ActiveSquad` (`Optional \| AllowReserved`), stages `10..60` |
| `0x000801` | `GLOB` | `FO4SF_SquadBaseCap` | `2` (base active squad slots) |
| `0x000802` | `GLOB` | `FO4SF_SquadMaxCap` | `4` (earned Warfare fireteam max slots) |
| `0x000803` | `GLOB` | `FO4SF_MercHireCost` | `250` (upfront mercenary contract fee when goodwill is absent) |
| `0x000804` | `GLOB` | `FO4SF_MercRewardShare` | `0.15` (`15%` contract payout share per hired merc, capped at `60%`) |
| `0x000805` | `GLOB` | `FO4SF_ActiveSquadCount` | `0` (live active squad count) |
| `0x000806` | `GLOB` | `FO4SF_SquadStance` | `0` = Defensive, `1` = Aggressive, `2` = Hold Fire / Passive |
| `0x000807` | `AVIF` | `FO4SF_CompanionAffinity` | `0..1000` (`250` Warm, `500` Trusted, `750` Admired, `1000` Idolized -> perk) |
| `0x000808` | `AVIF` | `FO4SF_SquadLoyalty` | `0..100` (default `75`; `< 20` triggers desertion) |
| `0x000809` | `AVIF` | `FO4SF_RecruitRankTier` | `0..4` (`Rookie`..`Legend` rank-hierarchy gate) |
| `0x00080A` | `AVIF` | `FO4SF_SquadOrderState` | `0` = Follow, `1` = Wait / Hold Position, `2` = Regroup |
| `0x00080B` | `AVIF` | `FO4SF_CompanionNerveBonus` | `0..100` (`+5%` per CHA above `5` + leadership bonus) |
| `0x000810` | `PERK` | `FO4SF_CompPerk_UnitedWeStand` | Granted at Affinity `1000` (`+20` ballistic resistance ability) |
| `0x000811` | `PERK` | `FO4SF_CompPerk_RobotSympathy` | Robot companion affinity perk (`+15` energy resistance ability) |
| `0x000812` | `PERK` | `FO4SF_Perk_SquadCommander` | Unlocks `4`-slot fireteam cap & rank-gate authorization |
| `0x000813` | `PERK` | `FO4SF_Perk_LoneWandererSolo` | Optional solo perk setting active squad cap to `0` |
| `0x000815` | `MESG` | `FO4SF_CompanionWheelMsg` | 8-button individual tactical wheel (`Follow`, `Wait`, `Inspect`, `Stance`, `Trade`, `Affinity`, `Dismiss`, `Close`) |
| `0x000816` | `MESG` | `FO4SF_FireteamCommandMsg` | 8-button squad-wide radio menu (`All Follow`, `All Hold`, `Aggressive`, `Defensive`, `Hold Fire`, `Sync/Teleport`, `Inspect 4 Slots`, `Close`) |
| `0x000817` | `MESG` | `FO4SF_RecruitPromptMsg` | 3-button recruitment prompt (`Goodwill`, `Hire Contract`, `Cancel`) |
| `0x000818` | `FACT` | `FO4SF_SquadAllyFaction` | `Ally` relation to `PlayerFaction` (`0x0001C21C`) |
| `0x000820` | `MISC` | `FO4SF_SquadRadioToken` | Console-free Tactical Fireteam Radio (drop in inventory to open `FO4SF_FireteamCommandMsg`) |
| `0x000830` | `CELL` | `FO4SF_SquadTestCell` | Interior staging room (`coc FO4SF_SquadTestCell`) with arrival marker & floor |
| `0x000831..0x000838` | `NPC_` / `ACHR` | `FO4SF_Fireteam_*` / `FO4SF_FireteamRef_*` | 4 persistent mortal/Protected Warfare recruits: *Rifleman Alpha*, *Medic Bravo*, *Heavy Charlie*, *Scout Delta* |
| `0x000839..0x00083A` | `NPC_` / `ACHR` | `FO4SF_StoryCompanion_Minuteman` / `FO4SF_StoryCompanionRef` | Persistent Essential story companion archetype for affinity testing |

---

## 3. Three Follower Teleportation Chokepoints

`FO4SF_CompanionsQuest.psc` registers `RegisterForPlayerTeleport()` (`Event OnPlayerTeleport()`), `Actor.OnLocationChange`, and a `2.0 s` travel/leash poll so following (`FO4SF_SquadOrderState != 1`) squadmates warp into a `2x2` wedge behind the player (and via `SQ_FollowersScript.TeleportFollowers`) across all three required transitions while `Waiting` members stay where ordered:

1. **Load Doors & Cell Transitions (`reason=load_door_cell_change`):** Triggered whenever `player.GetParentCell()` changes across interior/exterior doors (`FO4SF_LoadDoor`) or following distance exceeds `120 m`.
2. **Vault 111 Exit Lift (`reason=vault_lift_or_interior_exit`):** Triggered when `FO4SFNewGame.esm` (`0x800`) crosses `stage >= 40` or the player transitions from an interior lift shaft onto the exterior Commonwealth hilltop.
3. **Pip-Boy Fast Travel (`reason=pipboy_fast_travel`):** Triggered when `GameDaysPassed` (`0x000039`) jumps `>= 0.005` game days across a cell/location jump (`FO4SF_PipboyTravel.Go`).

---

## 4. PC Verification Card — 4-NPC Fireteam Command & Persistence Test (Claude PC)

### Offline Precheck, Stage, Hardlink Fold, and Verify (Game Closed)
```powershell
python scripts/companions/make_companions_core.py precheck --content-resources "<starfield_dir>/Tools/ContentResources.zip" --out "<work_dir>/precheck.json"
python scripts/companions/make_companions_core.py stage --out "<work_dir>/stage" --starfield "<starfield_dir>/Data/Starfield.esm" --compiler "<starfield_dir>/Tools/Papyrus Compiler/PapyrusCompiler.exe" --content-resources "<starfield_dir>/Tools/ContentResources.zip"
python scripts/companions/make_companions_core.py verify --exp-dir "<work_dir>/stage" --plan "<work_dir>/stage/plan.json" --starfield "<starfield_dir>/Data/Starfield.esm"
```
Expected offline terminal line: `verify: ok`.

### In-Game 4-NPC Fireteam & Save-Quit-Reload Steps
1. **Install** (game closed) via ride-along installer or folded core set:
   ```powershell
   python scripts/companions/companions_core_install.py install --dir "<work_dir>/stage" --starfield "<starfield_dir>"
   ```
2. **Enter Staging Room & Print Exact Stage Commands:**
   - Launch Starfield, load a test save, and enter the staging room:
     ```text
     coc FO4SF_SquadTestCell
     ```
   - Confirm *Rifleman Alpha*, *Medic Bravo*, *Heavy Charlie*, *Scout Delta*, and *Minuteman Liaison* stand in front of the arrival marker. Print the live quest FormID commands:
     ```powershell
     python scripts/companions/make_companions_core.py console
     ```
3. **Run Stages `10..40` (Base Cap Gate -> 4-NPC Fireteam Commands -> 3 Teleport Chokepoints -> Affinity Perk):**
   - `setstage <XX>000800 10` — Verifies rank-hierarchy refusal (`reason=rank_too_high`), recruits *Rifleman Alpha* (`1/2`) and hires *Medic Bravo* (`2/2`, deducting `250` Credits), then attempts *Heavy Charlie* (`#3`) and proves base cap `2` refuses recruitment (`reason=cap_reached`).
   - `setstage <XX>000800 20` — Unlocks `4`-slot leadership cap (`FO4SF_Perk_SquadCommander`), recruits *Heavy Charlie* (`3/4`) and *Scout Delta* (`4/4`), and executes squad-wide `All Hold Position` (`4/4` waiting), `All Follow / Regroup` (`4/4` following), `Stance` sweep (`Aggressive` -> `Hold Fire` -> `Defensive`), and `Inspect Fireteam` across all 4 slots.
   - *(Interactive Wheel & Trade Check):* Activate (`E`) *Rifleman Alpha* to open `Companion Tactical Wheel` (`FO4SF_CompanionWheelMsg`), test **Trade Gear & Ammo** (`OpenInventory`) and **Inspect**, or drop `Tactical Fireteam Radio` (`FO4SF_SquadRadioToken`) from inventory to open `Warfare Fireteam Radio` (`FO4SF_FireteamCommandMsg`).
   - `setstage <XX>000800 30` — Places slot 4 (*Scout Delta*) on `Wait`, runs all three teleport chokepoints (`load_door_cell_change`, `vault_lift_or_interior_exit`, `pipboy_fast_travel`), and verifies the `3` following members warp into formation while the `1` waiting member stays put (`skipped_waiting=1`), then resumes follow on *Scout Delta*.
   - `setstage <XX>000800 40` — Advances *Minuteman Liaison* affinity `0 -> 250 -> 500 -> 750 -> 1000` (*Idolized* -> grants `FO4SF_CompPerk_UnitedWeStand`), verifies mercenary contract payout split (`ComputeNetContractPayout`), and verifies friendly-fire loyalty decay (`75 -> 60`).
4. **Named Throwaway Save -> Quit -> Relaunch -> Reload:**
   - Create the named throwaway save:
     ```text
     save FO4SF_Throwaway_CompanionsSquad_DeleteMe
     ```
   - Quit Starfield completely to desktop, relaunch, and load **`FO4SF_Throwaway_CompanionsSquad_DeleteMe`** (`Actor.OnPlayerLoadGame` automatically logs `reload_audit when=reload` and `when=reload+2s`).
5. **Post-Reload Audit, Clean Dismiss, and Throwaway Save Deletion:**
   - Run post-reload console stages:
     - `setstage <XX>000800 50` (explicit post-reload persistence audit `when=stage50`)
     - `setstage <XX>000800 60` (cleanly dismisses all 4 fireteam members -> `active=0`)
   - Quit Starfield **without saving**.
   - **Delete `FO4SF_Throwaway_CompanionsSquad_DeleteMe`** (`FO4SF_Throwaway_CompanionsSquad_DeleteMe*.sfs`) from the Starfield `Saves` folder.
   - Run the stitched log verifier:
     ```powershell
     python scripts/companions/make_companions_core.py log
     ```
   - Uninstall ride-along files when finished:
     ```powershell
     python scripts/companions/companions_core_install.py uninstall --starfield "<starfield_dir>"
     ```

### Expected `make_companions_core.py log` Output (`PASS` Lines)
```text
PASS base_cap_and_gates
PASS fireteam_4npc_commands
PASS teleport_3_chokepoints
PASS affinity_perk_grant
PASS upkeep_and_loyalty
PASS save_reload_persistence
PASS clean_dismiss
VERDICT: PASS
```
