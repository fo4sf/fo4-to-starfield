# Round 11 (`R11-W1`): Codsworth Camera (`D1`), Concord Raider Ammo & Balance (`D3`), Preston Choice Greying (`D5`), and `Min00`/`Codsworth01` Hardening (`A2.2`, `A2.4`, `A2.5`)

Scope: Track 2 slice `R11-W1` on top of merged `candidate-2g` (`fb22fa2b`). No `A4` Fallout 4 weapon records and no `A5` (`S1`–`S9`) quest changes are included here; every passing `2g` behavior (`C1`–`C6`, `R1`–`R7`) is preserved.

---

## 1. `D1` — Codsworth Choice-List Camera Under His Body (`still 03` vs `still 04`)

### Root Cause (Proven Offline from `Starfield.esm` + `MiniBotA` `skeleton.nif`)
1. `FO4SF_CodsworthRace` (`0x000818`) is duplicated from `Starfield.esm` `MiniBotARace` (`0x00227705`), a 0.5 m floor-crawling garden robot:
   - `meshes/actors/minibota/characterassets/skeleton.nif` (`Starfield - Meshes01.ba2`) has only four nodes: `MiniBotA_mrRigRoot (0,0,0)` -> `Root (0,0,0)` -> `COM (0,0,0.506 m)` -> `C_RightSideRef (0.1,0,0.506 m)`.
   - `MiniBotABodyPartData` (`0x00227704`) binds `Type = Head1` to `C_Chassis` (mounted on `COM` at `z = 0.506 m`) and defines **no `Type = LookAt` part** (contrast `HumanBodyPartData` `C_Head`/`C_Neck` and `ModelABodyPartData` Vasco `C_Head`/`C_EyeRis` at `COM z = 1.241 m`).
   - `MiniBotARace` also carries `Size = Small`, `DialogueQuest = DialogueMiniBot (0x00225314)`, `TiltFrontBack = true`, lacks `HeadAxisBit0` and flag bit `0x0080000000000000`, and leaves its 61-byte `DAT2Unknown3` framing block all zeros (whereas both `HumanRace` and `ModelARace` populate it).
2. `codsworth.nif` (Fallout 4 Mr. Handy) floats **0.85 m higher** (`z ≈ 1.36 m`), with his thruster cone and splayed arms spanning `z = 0.50–0.90 m`.
3. During Phase 0 (`DialogueSceneAction`, `still 03`), Starfield keeps the player's normal eye-level 1st-person camera at `1.85 m` (`camera_guard`), framing Codsworth cleanly from outside. When Phase 1 (`TOPLEVELNEST` `PlayerDialogueSceneAction`, `still 04`) starts, Starfield engages its dialogue camera (`SCEN.Flags` `0x0800` is set on 1,956/2,202 vanilla `PlayerDialogue` scenes including Preston `still 08` and does **not** disable Starfield's dialogue camera) and aims at `Head1 = C_Chassis` (`z = 0.506 m`), placing the camera beneath Codsworth's floating dome looking down at his thruster/legs and the dirt.

### Fix Applied
1. **Plugin (`dotnet/Mission/Program.cs`, `FO4SF_CodsworthRace` `0x000818`):**
   - Upgraded `FO4SF_CodsworthRace` from floor-bot metadata to standing dialogue framing while preserving `MiniBotA` skeleton/ARMA and `Height = 1.0`: `Size = Medium`, `DialogueQuest = Null`, `HeadAxisBit0 | 0x0080000000000000` set, `TiltFrontBack` cleared, and `DAT2Unknown3` copied from `ModelARace` (`0x005629`) when available.
2. **Script (`scripts/mission/FO4SF_Codsworth01Quest.psc`):**
   - In `Scene.OnPhaseBegin`, whenever `auiPhaseIndex >= 2` (1-based `TOPLEVELNEST` choice phase on first entry and on every `INTV = 1` loop-back), calls Starfield's native `Game.StopDialogueCamera(False, True)` (same Bethesda API used in `DefaultTopicInfoStopDialogueCamera.psc` and `QF_MQ101_00003448.psc`) and logs `codsworth talk dialogue_camera stopped phase=<n>`, keeping the player in the clean eye-height 1st-person view seen in `still 03`.

### Offline Proof vs Game-Only Verification
- **Provable offline:** `FO4SF_CodsworthRace` binary fields (`Size.Medium`, null `DialogueQuest`, flags, `DAT2Unknown3`) via `Mission check`/`selftest` and `test_r11_d1_d3_min00.py`; Papyrus compilation of `Game.StopDialogueCamera(False, True)` against `ContentResources.zip` `Game.psc`; and script invocation on `OnPhaseBegin(2)`.
- **Game-only:** Actual rendered viewport framing in `still 04` (confirming Starfield holds 1st-person eye height throughout `DialogueMenu` choices and loop-back without dipping under Codsworth's chassis).

---

## 2. `D3` (Part 1) — Concord Raider Ammo (`30, 70, 30, 30, 20`) & Stand-In Fight Balance

### Root Cause of `30, 70, 30, 30, 20` (Proven Offline from `Starfield.esm` + `FO4SF_Min00Quest.psc`)
- `WEAP 0x0026D96B Coachman` has `AttackDamage = 52`, `AmmoType = 0x002B4AFB AmmoShotshell`, and `AmmoList = 0x002B4B15 LLW_Ammo_Coachman` -> `0x00279274 LL_Ammo_Shotshell` (`LVLF = 0x0003`, entries `{10, 15, 20, 25, 30}`).
- On spawn, Starfield auto-rolled `LL_Ammo_Shotshell` onto the 5 Concord raiders (`30, 10, 30, 30, 20`), while `QuestReferenceAlias.Items` (`AmmoShotshell x60`) on persistent `ForcedReference` `ACHR`s was not applied by the engine.
- `ArmRaiderForCombat()` previously checked `if r.GetItemCount(RaiderAmmo) < 12 -> r.AddItem(RaiderAmmo, 60, True)`:
  - Raider 1 rolled `10 < 12` -> `10 + 60 = 70`.
  - Raiders 0, 2, 3 rolled `30 >= 12` -> skipped `AddItem` -> `30`.
  - Raider 4 rolled `20 >= 12` -> skipped `AddItem` -> `20`.

### Fix Applied (Stand-In Records Only — Zero `A4` FO4 Guns)
1. **Deterministic ammo (`scripts/mission/FO4SF_Min00Quest.psc` `ArmRaiderForCombat`):**
   - Replaces the `< 12 -> +60` threshold with exact-delta normalization (`AddItem(60 - cur)` / `RemoveItem(cur - 60)`), guaranteeing **`ammo=60`** on every raider (`0..4`) regardless of `LL_Ammo_Shotshell` spawn rolls.
2. **Stand-in fight balance (`dotnet/Mission/Program.cs` + `FO4SF_Min00Quest.psc`):**
   - Binds Starfield stand-in sidearm `WEAP 0x0476C4 Eon` (`AttackDamage = 10`, 5.2× lower burst than `Coachman`'s `52`) and `AMMO 0x04AD3E Ammo777mm` (exact `36` rounds via exact-delta normalization) on `FO4SF_Min00` VMAD (`RaiderSidearm` / `RaiderSidearmAmmo`) and calls `EquipBalancedRaiderSidearm()` immediately after `ArmRaiderForCombat()` logs `ammo=60`. `EquipBalancedRaiderSidearm()` unequips and removes `Coachman` and `AmmoShotshell` from the raider's inventory and equips `Eon` with `abPreventRemoval = True` so Starfield's `SelectBestWeapon` combat AI cannot switch back to `Coachman` during the fight or after a mid-fight reload (falling back cleanly to `Coachman` + `60` shells only if `RaiderSidearm` is `None`).
   - Integration note: `src/fo4sf/core/cross_plugin_check.py` `KNOWN_EXTERNAL_RECORDS["Starfield.esm"]` should include `0x0476C4: ("WEAP", "Eon")` when `R11-W1` integrates so `validate_staged_esms` recognizes `FO4SF_Min00Quest.RaiderSidearm`.
   - At `205 HP` (Level 1), `Coachman` (`52` dmg) downs a player in **4 hits**; `Eon` (`10` dmg) requires **21 hits** (5.2× survival window for a cover-using player without god mode until `A4`/`A5` replace the stand-in fight).
3. **Player weapon & Preston's role in the current stand-in fight:**
   - **Player weapon:** The player is expected to pick up the Vault 111 stand-in pistol (10mm / Starfield stand-in in Vault 111) before leaving the vault; in `2g` the tester skipped the vault pistol and arrived unarmed.
   - **Preston's role:** Preston carries `WEAP 0x2773C8 Orion` with `50` `AmmoLaser`, is held at the museum door (`HoldPreston` -> `SetRestrained(True)`) while calm, is automatically released by `ReleaseInFight("mission")` whenever `Preston.GetCombatState() != 0`, and never targets the player (`IgnoreFriendlyHits(True)` + `StopCombat` guard).

### Offline Proof vs Game-Only Verification
- **Provable offline:** Exact `30, 10, 30, 30, 20` -> `60, 60, 60, 60, 60` ammo normalization, `Coachman`/`AmmoShotshell` removal, and `Eon` (`abPreventRemoval = True`, `36` `Ammo777mm`) swap logic in `test_r11_d1_d3_min00.py`, plus `RaiderSidearm`/`RaiderSidearmAmmo` VMAD bindings in `Mission selftest`.
- **Game-only:** Live Concord TTK and player survival from cover at `205 HP` without `tgm`.

---

## 3. `D5` (Part 3) — Preston's Asked Question Not Greyed Out in `DialogueMenu`

### Root Cause Analysis (`2g` Binary + Runtime Differences) & Fix (`dotnet/Mission/Program.cs`)
- **Identical `2g` binary layout:** Binary inspection of `candidate-2g` `FO4SFMission.esm` shows Codsworth's `INFO 0x095A` ("Where can I go?", Row 2) and Preston's `INFO 0x0918` ("What happens now?", Row 0) had the identical subrecord layout in `2g` (neither emitted `ENAM` or `INAM`), yet `0x095A` visibly greyed out in `Still 04`.
- **Two verified runtime differences between `run2` (Codsworth) and `run3` (Preston):**
  1. **Scaleform `DialogueMenu.swf` Row-0 silver selection bar (`AlreadySaid_Selected` vs `AlreadySaid_Unselected`):** `Starfield - Interface.ba2` `dialoguemenu.swf` defines `Normal_Selected`, `Normal_Unselected`, `AlreadySaid_Selected`, and `AlreadySaid_Unselected`. On `TOPLEVELNEST` loop-back, the bright silver highlight bar defaults to **Row 0**. In Codsworth (`Still 04`), the tester asked **Row 2**, which sat unselected in `AlreadySaid_Unselected` grey while Row 0 held the silver highlight bar; in Preston (`run3`), the tester asked **Row 0** ("What happens now?"), which sits directly under the bright silver highlight bar (`AlreadySaid_Selected`, dark text on silver) until the cursor moves down to Row 1 (the test card should move highlight off Row 0 to inspect Row 0's `AlreadySaid_Unselected` grey state).
  2. **`run3` concurrent double-`Start()` race (`rt=343.299` vs `rt=343.686`):** Preston was activated directly on `09000802`, triggering native `DEVT` plus `OnActivate` `scn.Start()` `0.4 s` later (eliminated by our `A2.2` guard), whereas Codsworth was activated via the `0x970` proxy (single `scn.Start()`).
- **Binary parity fix (`BuildTopScene`):** Inspection of `Starfield.esm` shows **20,731 / 20,731 (100%)** of vanilla `PlayerDialogue` player-choice `INFO` records (`pcInfo`) emit explicit `ENAM` (`DialogResponseFlags { Flags = 0, ResetHours = 0 }`, `DoNotGrayOut = 0x1000` clear) and `INAM` (`SubtitlePriority = Low`), matching looping multi-response vanilla chains (e.g. `MQ101_035_SarahMorganScene` `0x001D07BE` -> `0x001D07BC`, 3 responses, `INTV = 2`). `BuildTopScene()` now emits explicit `ENAM = { Flags = 0, ResetHours = 0f }` (never setting `DoNotGrayOut` or `SayOnce`) and `INAM = SubtitlePriorityLevel.Low` on `greetInfo`, `pcInfo` (`0x918..0x91A`, `0x958..0x95B`), and `npcInfo` (`0x928..0x92A`, `0x968..0x96B`), verified in `Mission check`/`selftest` and `test_r11_d1_d3_min00.py`.
- **Game-only:** Confirming Scaleform `DialogueMenu` dims Preston's `"What happens now?"` (`AlreadySaid_Unselected`) after selecting it, looping back to `phase=2`, and moving the highlight bar off Row 0 onto Row 1.

---

## 4. `A2.2` — `FO4SF_Min00Quest.psc` Fallback vs Late Greeting & `2f` vs `2g` `PrestonTalkScene`

### Fix (`scripts/mission/FO4SF_Min00Quest.psc:645-875`)
1. **Race 1 (observed in `2g` `run3` at `rt=343.486` vs `343.662`):** Native `DEVT` opened `DialogueMenu` *before* `OnActivate` finished `ResolvePrestonSceneLogged()`, and `OnActivate` then unconditionally reset `prestonSceneMenuOpened = False` and armed Timer 3. Fixed by re-checking `prestonTalkBoxOpen || prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonFallbackActive || prestonTalkLogged` after `ResolvePrestonSceneLogged()` and before arming Timer 3.
2. **Race 2 (`1.45 s` post-phase-1 fallback vs late native greeting):**
   - `FallbackPrestonToMessageBox` now returns immediately if `prestonDialogueMenuOpen || prestonSceneMenuOpened || prestonTalkBoxOpen || prestonFallbackActive || prestonTalkLogged`, latches `prestonFallbackActive = True` **before** calling `scn.Stop()`, and re-checks `DialogueMenu` state before showing the MessageBox.
   - `RunPrestonTalk` refuses to open if `prestonDialogueMenuOpen || prestonSceneMenuOpened` is true.
   - `Scene.OnPhaseBegin` and `OnMenuOpenCloseEvent("DialogueMenu", True)` unconditionally call `scn.Stop()` and log `preston scene suppressed reason=single_talk` if `prestonFallbackActive || prestonTalkBoxOpen || prestonTalkLogged || EffectiveStage() >= 35`.
   - Result: **never both** `DialogueMenu` and `MessageBox` can coexist.

### Honest Explanation of `2f` (`PrestonTalkScene == None`) vs `2g` (`via=property`)
- Byte-for-byte inspection of `candidate-2f` and `candidate-2g` `FO4SFMission.esm` `QUST 0x000800` `VMAD` confirms both files contain the **identical 26-byte property record** for `PrestonTalkScene` (`0x03000900`).
- Therefore, why `PrestonTalkScene` evaluated to `None` at runtime in `2f` while resolving `via=property` in `2g` **cannot be proven from the ESM bytes or logs alone**; `ResolvePrestonScene()` keeps the `Game.GetFormFromFile(0x000900, "FO4SFMission.esm")` fallback as permanent defense-in-depth.

---

## 5. `A2.4` — Keeper Timer 2 Never Drops Proximity Mission Starts (`FO4SF_Min00Quest.psc`)

- Previously `KeepCodsworth()` only rescheduled Timer 2 while `codsworthFails < 10 || codsworthHolds > 0` or `prestonFails < 10 || prestonHolds > 0`; if both placement budgets hit 10 with zero holds, Timer 2 stopped and `CheckA4ProximityStarts` / `CheckA7ProximityStarts` / `CheckA7cdProximityStarts` stopped polling.
- Added `elseif KeeperOnly -> StartTimer(CodsworthCheck, 2)` right after the placement-budget branch so `KeeperOnly` Timer 2 stays alive unconditionally for later-mission proximity starts even after both placement budgets exhaust (while non-keeper Timer 2 behavior remains unchanged).

---

## 6. `A2.5` — Ground-Z & Sanctuary Wall Clearance in `EnsureSafeCodsworthCameraDistance` (`FO4SF_Codsworth01Quest.psc`)

- Previously `EnsureSafeCodsworthCameraDistance()` called `player.SetPosition(cx + ux * 1.85, cy + uy * 1.85, pz)` with no ground or wall check.
- Binary inspection of `Fallout4.esm` (`WRLD 0x0000003C`) around Codsworth's merged Sanctuary spot `(-2346.709, -1406.163, 111.734)` shows the Player House exterior wall lies `~1.15–1.68 m` NW along inward normal `(-0.6428, +0.7660)` (`PlayerHouse_Ruin_BathroomHook02` at `d = 1.68 m, hdg = 335.8 deg`; `BathroomSink01` at `d = 2.40 m, hdg = 356.4 deg`).
- `EnsureSafeCodsworthCameraDistance()` now:
  1. Validates vertical alignment (`|pz - cz| <= 1.5 m`); otherwise skips `SetPosition` and logs `codsworth talk camera_guard skipped reason=ground_z_mismatch`.
  2. Clamps target Z within `[cz - 0.35, cz + 0.60]` so the player stays on Codsworth's ground plane.
  3. Checks the Sanctuary Player House wall half-plane (`wallProj = candDx * (-0.6428) + candDy * 0.7660 > 1.0` within `5 m` of Codsworth's Sanctuary spot) and redirects any wall-bound step-back onto the closest unobstructed Sanctuary yard/driveway azimuth (`SW`, `SE`, or `NE`) at exact `1.85 m`, logging `wall_avoid=true|false`.
- **Game-only:** Confirming live collision clearance in Sanctuary from every approach angle around Codsworth.
