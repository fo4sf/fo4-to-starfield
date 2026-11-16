# Fallout 4 -> Starfield Papyrus Bridge (`FO4SF_Shim_*` & `FO4SF_NativeBridge`)

Offline bridge library, AST source rewriter, and compiler census extension (`CF-5` part 2) that compile Fallout 4's non-identical Papyrus scripts into Starfield v4.2 `.pex` bytecode without modifying game files on disk or storing game script content in Git.

- **Bridge shim sources:** `scripts/papyrus/shims/*.psc` (`16` scripts: `1` `Native` bridge + `8` `FO4SF_Shim_*` static libraries + `7` pure-Papyrus adapter types for deleted engine classes)
- **Source rewriter:** `src/fo4sf/papyrus/shim_rewriter.py`
- **Compiler census driver:** `scripts/papyrus/compile_census.py --with-shims --non-identical-only`
- **Unit tests:** `tests/test_papyrus_bridge.py` and `tests/test_compile_census.py` (synthetic snippets only)

---

## 1. Architecture & Call-Site Coverage

Across all `7,854` `.psc` files in Fallout 4 (`91` `Native` engine headers declaring `1,416` API items + `7,763` non-native game scripts making `74,723` engine/base calls and event overrides):

| Tier | Share of `74,723` Calls | Bridge Mechanism | Files |
| :--- | ---: | :--- | :--- |
| **Identical in Starfield** | `97.32%` (`72,724`) | Compiles and binds unchanged against Starfield's `Native` base classes (`Actor`, `ObjectReference`, `Quest`, `Game`, `Utility`, etc.), including `Self` calls on `Protected SelfOnly` methods. | Starfield base `.psc` |
| **Pure-Papyrus Shim & Rewrite** | `2.54%` (`1,901`) | Rewritten by `shim_rewriter.py` onto `8` `FO4SF_Shim_*` libraries + `7` pure-Papyrus adapter classes + Starfield widened event headers. Compiles to standard v4.2 `.pex` with zero C++ dependency. | `FO4SF_Shim_*.psc` + `7` adapters |
| **SFSE Native Bridge** | `0.13%` (`98` calls across `5` functions) | Declared on `FO4SF_NativeBridge.psc` (`Dismember` `83`, `GetLinkedRefChildren` `6`, `ShowPipboyPlugin` `4`, `ResetSpeechChallenges` `4`, `IsDismembered` `1`, plus `3` zero-call completeness stubs). | `FO4SF_NativeBridge.psc` |

### Why Fallout 4's `91` `Native` Headers Must Be Excluded on Import
Starfield deleted `7` Fallout 4 `Native` classes (`Sound`, `SoundCategory`, `SoundCategorySnapshot`, `EncounterZone`, `Component`, `Holotape`, `OutputModel`). When raw Fallout 4 sources sit at the tail of `-i`, `PapyrusCompiler.exe` silently resolves `Sound.Play` against Fallout 4's `Native` `Sound.psc` — passing compilation (`674` apparent failures instead of `826+`) while failing to bind at runtime in Starfield.

`compile_census.py --with-shims` excludes all `91` `Native` Fallout 4 `.psc` files from `<out>/shimmed_fo4` and places pure-Papyrus non-`Native` adapter scripts (`extends Form`) in `scripts/papyrus/shims/` ahead of Starfield sources, routing audio, encounter-zone, and scrap-component calls to Starfield's `WwiseEvent`, `Location`, and `Resource` APIs.

### Converted-Quest Known-Bug Boundary
Mechanical compilation via `FO4SF_Shim_*` makes original quest and scene scripts *compile and bind* on Starfield, **including any stage/condition/NPC bugs shipped in the original games**. Per `docs/plan/core-and-assets-plan.md` (`CF-5`, `CF-7`, and Section `4.3`), every converted-quest slice must pair shimmed `.pex` compilation with its per-quest known-bug ledger (names and plain descriptions only, clean-room fixes, zero third-party mod files, and reproduction steps on the quest's PC card).

---

## 2. Shim Family Inventory (`scripts/papyrus/shims/`)

1. **`FO4SF_NativeBridge.psc` (`Native`):** `Dismember`, `IsDismembered`, `GetLinkedRefChildren`, `ShowPipboyPlugin`, `ResetSpeechChallenges`, `SetEyeTexture`, `IsActivateChild`, `TetherToHorse`.
2. **`FO4SF_Shim_ActorAI.psc`:** `GetActorBase` (`GetBaseObject() as ActorBase`), `SetInvulnerable` / `IsInvulnerable` (`Game.GetInvulnerableAV()`), `ChangeAnimArchetype` wrappers, companion state wrappers (`DisallowCompanion`, `AllowCompanion`, `SetAvailableToBeCompanion`, `SetCompanion`, `FollowerFollow`, `FollowerWait`), `IsBleedingOut`, `PathToReference`, `StartCannibal`.
3. **`FO4SF_Shim_AudioWeather.psc`:** `Sound` / `SoundCategory` / `SoundCategorySnapshot` -> `WwiseEvent` playback/stop/RTPC helpers + `Weather.FindWeather` / `GetClassification` adapters.
4. **`FO4SF_Shim_QuestScene.psc`:** `Location` `IsCleared` / `SetCleared` / `HasEverBeenCleared` -> `IsExplored` / `SetExplored` / `HasEverBeenExplored`, `Game.GetCommonProperties`, `Keyword.SendStoryEventAndWait`, and `21` `ScriptObject` `SelfOnly` external-receiver relays (`RelayGotoState`, `RelayStartTimer`, `RelayStartTimerGameTime`, `RelayRegisterForCustomEvent`, `RelaySendCustomEvent`, `RelayRegisterForRemoteEvent`, etc.).
5. **`FO4SF_Shim_ObjectRef.psc`:** `PlaceActorAtMe`, `SetMotionType`, `SellItem`, `DeleteWhenAble`, `getLinkedRefArray`, `RemoveComponents` / `GetObjectComponentCount` (`Resource` bridge).
6. **`FO4SF_Shim_PlayerUI.psc`:** `IsInMenuMode` -> `Utility.IsGameMenuPaused()`, `WaitMenuMode` -> `Utility.WaitMenuPause()`, `ShowSPECIALMenu`, `ShowPerkVaultBoyOnHUD`, `ForceDisableSSRGodraysDirLight` -> `Game.ForceDisableSSRDirLight`, `EnablePipboyHDRMask`, `SetInsideMemoryHUDMode`, `ShowOnPipboy`.
7. **`FO4SF_Shim_Workshop.psc`:** `OpenWorkshopSettlementMenu`, `OpenWorkshopSettlementMenuEx`, `RecalculateResources`, `WaitForWorkshopResourceRecalc`.
8. **`FO4SF_Shim_PowerArmor.psc`:** `IsInPowerArmor`, `SwitchToPowerArmor`.
9. **`FO4SF_Shim_SurvivalRad.psc`:** `GetAssociatedSkill` and survival/rad actor-value helpers.
10. **Deleted-Type Pure-Papyrus Adapters (`7`):** `Sound.psc`, `SoundCategory.psc`, `SoundCategorySnapshot.psc`, `EncounterZone.psc`, `Component.psc`, `Holotape.psc`, `OutputModel.psc`.

---

## 3. PC Card (Offline Compiler Verification — No Game Needed)

Starfield does not need to be running; nothing in `<STARFIELD_DIR>` or `<FO4_DIR>` is modified.

### Prerequisites
- `<STARFIELD_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe`
- `<SF_SOURCES_DIR>`: `Scripts\Source\*.psc` + `Starfield_Papyrus_Flags.flg` extracted from `<STARFIELD_DIR>\Tools\ContentResources.zip`
- `<FO4_SOURCES_DIR>`: Fallout 4 `.psc` root (containing `Fragments\` and base `.psc` files) extracted from `<FO4_DIR>\Data\Scripts\Source\Base\Base.zip`

### Step 1 — Unit Tests & Guard
```powershell
python -m unittest tests.test_papyrus_bridge tests.test_compile_census tests.test_papyrus_strings
python scripts/guard.py
```
- **PASS:** Unit tests report `OK` (`0` failures) and `guard.py` prints `guard: ok`.

### Step 2 — Compile All `16` Bridge Shims + All Non-Identical Fallout 4 Scripts Against Starfield
```powershell
python -I -B scripts/papyrus/compile_census.py `
  --compiler "<STARFIELD_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --starfield-sources "<SF_SOURCES_DIR>" `
  --fo4-sources "<FO4_SOURCES_DIR>" `
  --with-shims --non-identical-only --jobs 12 `
  --out "<STAGE_DIR>\census-with-shims"
```
- **PASS:**
  1. Console prints `Bridge shims: 16/16 compiled clean against Starfield; rewrote 794/7763 non-native FO4 scripts (non-identical baseline failed: 833)` and writes all `16` `.pex` files under `<STAGE_DIR>\census-with-shims\shim_pex\`.
  2. **Logic rate (`groups.logic`):** `756 / 756` (`100.0%`) of non-identical logic scripts compile clean (`0` errors across all quest, actor, workshop, companion, power-armor, survival, perk, and magic-effect logic scripts).
  3. **Scene/topic rate (`groups.scene`):** `71 / 77` (`92.2%`) of non-identical scene/topic scripts compile clean (`827 / 833` total; `7,757 / 7,763 = 99.92%` across all non-native Fallout 4 scripts); the **only** `6` failing scripts in the archive are the unshipped `Fragments:TopicInfos:TIF_GJDialogue_*` files whose parent script (`GameJam:GJDialogueScript`) was omitted from Fallout 4's source archive (`unknown_function = 0`, `signature_mismatch = 0`, `self_only_function = 0`, `wrong_argument_count = 0`, `type_mismatch = 0`).
