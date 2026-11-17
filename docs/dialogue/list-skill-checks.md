# Silent-Player List Dialogue & Deterministic Skill / SPECIAL / Background / Trait Checks (`CF-7`)

Implements the second half of the unified Fallout dialogue host (`CF-7`, Phase B item `1d`) **beside** PR `#792`'s 4-option wheel (`Interface/FO4SF_DialogueWheel.swf`), keeping Starfield's native `DialogueMenu` (`DialogueListData.aChoices` shuttle) intact (`0` replacement of `Interface/DialogueMenu.swf`, `0` edits to `#792`'s files).

- **Plugin writer & checker:** `dotnet/ListDialogue/Program.cs` (`FO4SFListDialogue.esm`, sole master `Starfield.esm`, `0` foreign overrides)
- **Tag formatter, deterministic NV evaluator & bug-ledger validator:** `src/fo4sf/dialogue/list_checks.py`
- **Log parser:** `src/fo4sf/dialogue/list_log.py`
- **Quest verifier script:** `scripts/dialogue/FO4SF_ListDialogueQuest.psc`
- **Stager, clean-core folder, verifier & ride-along installer:** `scripts/dialogue/make_list_dialogue.py` and `scripts/dialogue/list_dialogue_install.py` (`Data/FO4SFListDialogue.install.json`)
- **Unit tests:** `tests/test_list_dialogue.py`

---

## 1. Coexistence Beside PR `#792` & Record Architecture

1. **Host `DialogueMenu` Preserved (`0` `DialogueMenu.swf` Override):**
   - PR `#792` proved that replacing `Interface/DialogueMenu.swf` crashes the game, whereas Starfield's native `DialogueMenu` natively binds `DialogueListData.aChoices[i].sChoiceText` and fires `DialogueMenu_OnDialogueSelect` (`selectedIndex = uEntryID`).
   - `list_checks.select_dialogue_mode(...)` routes 4-slot untagged Fallout 4 wheel turns to `#792`'s `wheel_4` (`Interface/FO4SF_DialogueWheel.swf`) and routes silent-player list conversations (`> 4` choices, or any choice carrying `[Skill N]`, `[SPECIAL N]`, `[Background]`, or `[Trait]` prefix tags) directly to Starfield's native `list_host`.
   - Both `make_list_dialogue.py` and `list_dialogue_install.py` refuse any stage containing `Interface/DialogueMenu.swf`.

2. **Prefix Tags & Deterministic New Vegas-Style `CTDA` Checks (`FO4SFListDialogue.esm`):**
   - `0x800 AVIF FO4SF_Skill_Speech`, `0x801 AVIF FO4SF_Skill_Science`, `0x802 PERK FO4SF_BG_VaultDweller`, `0x803 PERK FO4SF_Trait_GoodNatured`, plus `Starfield.esm` `Strength` and `Intelligence` `AVIF`s.
   - `0x812 DIAL FO4SF_ListChoicesTopic` on `0x811 DLBR FO4SF_ListTopBranch` (`0x810 QUST FO4SF_ListDialogueQuest`) carries **`8` player `INFO` records (`> 4` options)** spoken to clean-room speaker `FO4SF_ListSpeakerNpc` (`0x806`, placed at `0x808` in interior room `FO4SF_ListTalkCell` `0x807`):
     - **`[Speech 50]` PASS (`0x820`, `GetValue >= 50` on `PlayerRef`)** -> `SetParentQuestStage(OnEnd = 20)`
     - **`[Speech 50]` FAIL (`0x821`, `GetValue < 50` on `PlayerRef`)** -> `SetParentQuestStage(OnEnd = 21)` *(deterministic New Vegas dual-branching: zero RNG `%` roll)*
     - **`[Science 40]` PASS (`0x822`, `GetValue >= 40`)** -> `SetParentQuestStage(OnEnd = 22)`
     - **`[Strength 7]` PASS (`0x823`, `GetValue >= 7`)** -> `SetParentQuestStage(OnEnd = 30)`
     - **`[Strength 7]` FAIL (`0x824`, `GetValue < 7`)** -> `SetParentQuestStage(OnEnd = 31)`
     - **`[Vault Dweller]` (`0x825`, `HasPerk == 1`, `INFO.Perk` linked)** -> `SetParentQuestStage(OnEnd = 40)`
     - **`[Good Natured]` (`0x826`, `HasPerk == 1`, `INFO.Perk` linked)** -> `SetParentQuestStage(OnEnd = 50)`
     - **Plain Goodbye (`0x827`, unconditional `Goodbye` flag)** -> `SetParentQuestStage(OnEnd = 60)`

---

## 2. Converted-Dialogue Known-Bug Audit Protocol (`CF-7` Rule)

Per `docs/plan/core-and-assets-plan.md` (`#806` `#issuecomment-6932576663`), converting original quest/dialogue trees mechanically also copies their shipped stage/condition bugs. `list_checks.validate_bug_ledger(...)` enforces that every converted dialogue slice carries a clean-room ledger (names & plain functional descriptions only; zero third-party mod filenames or copied assets):

| Bug Class ID | Plain Functional Description | Disposition in `FO4SFListDialogue` | How to Reproduce & Verify |
| :--- | :--- | :--- | :--- |
| `DLG-HOSTILE-SPEAKER` | Stand-in or converted NPCs lacking an allied faction relation turn hostile on stray hits and block greeting activation (observed in early Concord runs). | **Fixed** (`FO4SF_ListSpeakerFaction` `0x805` allied to `PlayerFaction` `0x01C21C`). | Enter `FO4SF_ListTalkCell` and activate `Relay Operator` (`0x808`); speaker greets calmly without combat bark. |
| `DLG-SUBJECT-VS-PLAYER-CTDA` | Skill/attribute `GetValue` conditions mistakenly left on `Subject` evaluate the NPC speaker's stats instead of the player's, locking or mis-evaluating `[Skill N]` checks in shipped quests. | **Fixed** (`PlayerValueCheck` & `PlayerHasPerkCheck` explicitly bind `RunOnType.Reference` -> `PlayerRef` `0x000014`). | Run Stage `10` (`Speech=25`) -> verify `[Speech 50]` FAIL row shows (`stage 21`); run Stage `15` (`Speech=55`) -> verify `[Speech 50]` PASS row shows (`stage 20`) while NPC stats never change. |
| `DLG-STUCK-EXIT` | Multi-option list topics lacking an unconditional `Goodbye` exit row trap the player inside `DialogueMenu` when all threshold checks fail. | **Fixed** (`0x827` unconditional `Goodbye` row always present). | At Stage `10` (all checks failing/locked), select `"Step away from the relay station."` -> `DialogueMenu` exits cleanly (`stage 60`). |
| `DLG-PER-QUEST-TOPIC-TYPOS` | Original-game per-quest stage-index typos or unreachable topic conditions inside individual Fallout 3 / New Vegas / Fallout 4 quests. | **Left to per-quest volume slices** (tracked per quest via `validate_bug_ledger` when each quest is converted). | Each converted quest's PC card lists its specific fixed/left quest bugs and stage repros. |

---

## 3. PC Card for Claude (PC)

### Step 1 — Offline Unit Tests, Precheck, Stage, Clean-Core Fold & Verify (Game Closed)
```powershell
$env:FO4SF_DOTNET_TESTS = '1'
python -m unittest tests.test_list_dialogue
python scripts/guard.py

python scripts/dialogue/make_list_dialogue.py precheck `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/dialogue/make_list_dialogue.py stage `
  --out "<STAGE_DIR>\list-dialogue-stage" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --compiler "<STARFIELD_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/dialogue/make_list_dialogue.py fold `
  --stage "<STAGE_DIR>\list-dialogue-stage" `
  --core-dir "<CLEAN_CORE_DIR>" `
  --out "<STAGE_DIR>\folded-list-dialogue" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --hardlink

python scripts/dialogue/make_list_dialogue.py verify `
  --exp-dir "<STAGE_DIR>\folded-list-dialogue" `
  --plan "<STAGE_DIR>\list-dialogue-stage\plan.json" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm"
```
- **Offline PASS lines:**
  - `Ran ... tests ... OK` and `guard: ok`
  - `precheck: ok`
  - `FO4SFListDialogue.esm: header Master, masters [Starfield.esm], 8 list INFOs ([Skill N], [SPECIAL N], [Background], [Trait]), deterministic CTDA checks verified` and `all checks pass`
  - `verify: ok`

### Step 2 — Ride-Along In-Game Verification (Coexists With Installed Core & `#792`)
1. With Starfield closed, install the ride-along package (`Data/FO4SFListDialogue.install.json` leaves `FO4SFExp.install.json` and `FO4SFConcordTalk.install.json` untouched):
   ```powershell
   python scripts/dialogue/list_dialogue_install.py install --dir "<STAGE_DIR>\list-dialogue-stage" --starfield "<STARFIELD_DIR>"
   ```
2. Launch Starfield into a throwaway session (`<XX>` = `FO4SFListDialogue.esm`'s 2-hex load index) and enter the test room:
   ```text
   coc FO4SF_ListTalkCell
   setstage <XX>000810 10
   ```
3. Activate `Relay Operator` (`E`): verify Starfield's native `DialogueMenu` opens a silent-player numbered list showing the failing `[Speech 50]` & `[Strength 7]` variants (`[Vault Dweller]` & `[Good Natured]` hidden) plus the exit option; select `[Speech 50]` fail (`stage 21`) and exit (`stage 60`).
4. Qualify the player sheet for all deterministic checks, talk again, select `[Speech 50]` pass (`stage 20`), `[Science 40]` (`stage 22`), `[Strength 7]` (`stage 30`), `[Vault Dweller]` (`stage 40`), and `[Good Natured]` (`stage 50`), then reset (`stage 70`):
   ```text
   setstage <XX>000810 15
   setstage <XX>000810 70
   ```
5. Quit without saving, inspect the log, and uninstall:
   ```powershell
   python scripts/dialogue/make_list_dialogue.py log
   python scripts/dialogue/list_dialogue_install.py uninstall --starfield "<STARFIELD_DIR>"
   ```
- **In-Game PASS lines (`make_list_dialogue.py log`, exit code `0`):**
  - `PASS  baseline_low_deterministic_fails`
  - `PASS  qualified_high_deterministic_passes`
  - `PASS  reset_restored_sheet`
  - `PASS  summary_ok`
  - `verdict: PASS`
