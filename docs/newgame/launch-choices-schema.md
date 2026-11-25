# `launch_choices.json` Schema (`schema_version = 2`) & Pre-Launch Table Contract

> **Scope:** Cross-layer specification for `%LOCALAPPDATA%\FO4SF\launch_choices.json` (and POSIX `$XDG_STATE_HOME/FO4SF/launch_choices.json`), bridging the Python launcher (`src/fo4sf/launcher/launch_choices.py`), the shared start-place table (`src/fo4sf/core/start_places.json` / `start_places.py`), and the SFSE plugin (`sfse/FO4SFPipboyMenu/src/setup_places.h` & `main.cpp`).

---

## 1. Purpose & Lifecycle (Restart-Only, Consume-and-Delete)

1. **Pre-launch handoff:** Before `Starfield.exe` launches, `launcher.py` writes `launch_choices.json` atomically (`.tmp` + `flush` + `fsync` + `os.replace`) containing only **restart-only** launch selections (`mode`, `start_variant`, `survival`, `place_id`, `min_difficulty`, timestamp, and launch `nonce`).
2. **Post-data-load validation (`main.cpp`):** On `PostDataLoad`, `FO4SFPipboyMenu.dll` reads `launch_choices.json`, checks `schema_version == 2`, verifies timestamp freshness, loads `SFSE/Plugins/FO4SFStartPlaces.json` (or `BuiltinFallbackStartPlaces()`), collects live loaded plugins from `TESDataHandler::compiledFileCollection` (`CollectLoadedPluginNames()`), and runs `ValidateLaunchChoicesAgainstStartTable(...)`.
   - If validation fails (malformed JSON, `schema_version != 2`, expired timestamp, `available == false`, mode/story/`start_variant` mismatch, or missing required plugin), the plugin logs `start_variant` and refusal reason and immediately disarms/deletes `launch_choices.json`.
   - Whether accepted or disarmed, `start_ready.json` is written atomically (`nonce` populated only when accepted).
3. **New-Game-only hydration & consume-and-delete (`F2`):** `HydrateLaunchChoicesIfNewGameMainThread()` hydrates `FO4SFCoreValues.esm` globals (`0x000870..0x000879`) **only** on a genuine New Game (`!loadGameSeen`, `StartChoiceDone < 0.5`, `GameDaysPassed <= 0.5`, `PlayerLevel <= 1`, `FO4SF_NewGame` resolved, handshake `FO4SF_StartCardOpen == -1.0`), re-validates against `ValidateLaunchChoicesAgainstStartTable(...)`, commits the globals, and immediately deletes `launch_choices.json`.

---

## 2. `launch_choices.json` (`schema_version = 2`) Field Reference

All `16` runtime keys listed below are the **only** keys permitted by Python `RESTART_ONLY_KEYS` (`write_launch_choices` refuses any unknown key such as `difficulty`, `special`, `traits`, `appearance`, or `skills`):

| Field | JSON Type | Required / Allowed Values | Meaning & Store Target |
|---|---|---|---|
| `schema_version` | `int` | Must be `2` | Payload schema version. Legacy `schema_version = 1` payloads are rejected in C++ (`ParseLaunchChoicesJsonText`). |
| `mode` | `string` | `"story"` \| `"warfare"` | Selected campaign branch tag. Must agree with `game_mode` and `start_places.json` row `mode`. |
| `game_mode` | `int` | `1` (Story) \| `2` (Warfare) | Integer mode written to `FO4SF_GameMode` (`0x000870`). |
| `start_variant` | `string` | Story: `"normal"` \| `"quick"`; Warfare: `"none"` (C++ also accepts `""`) | Opening flow variant for Story starts (e.g. Pre-War `"normal"` vs. Vault 111 `"quick"`). Must match the target row's `start_variant` in `start_places.json`. |
| `survival` | `bool` | `true` \| `false` | Player Survival toggle (`true` requires `FO4SFHardcore.esm` active in launcher). |
| `survival_start` | `int` | `0` \| `1` | Written to `FO4SF_SurvivalStart` (`0x000871`). |
| `survival_locked` | `int` | `0` \| `1` | Written to `FO4SF_SurvivalLocked` (`0x000872`); `1` only when `mode == "warfare"` and `survival == true`. |
| `story_id` | `string` | Non-empty Story ID (`"fo4_commonwealth"`, etc.) in Story; `"none"` in Warfare | Narrative campaign identifier; must match `row.storyId` in `start_places.json` when `mode == "story"`. |
| `story_choice_idx` | `int` | `>= 0` in Story; `-1` in Warfare | Story index written to `FO4SF_StoryLine` (`0x000878`). |
| `warfare_faction_slot` | `int` | `-1` in Story; `0..7` in Warfare | Faction slot written to `FO4SF_WarfareFaction` (`0x000874`). |
| `warfare_start_idx` | `int` | `-1` in Story; `>= 0` in Warfare | Canonical row index in `warfare_starts.json` written to `FO4SF_WarfareStartIndex` (`0x000875`). |
| `place_id` | `string` | Non-empty `id` in `start_places.json` | Selected start-place row ID (e.g. `"fo4_prewar_sanctuary"`, `"fo4_vault111"`, `"minutemen_sanctuary"`, `"gunners_plaza"`, `"raiders_corvega"`). |
| `start_place_row` | `int` | `>= 0` | Available-row ordinal written to `FO4SF_StartPlaceRow` (`0x000879`). |
| `min_difficulty` | `int` | `0..3` | Minimum difficulty floor written to `FO4SF_StartDifficulty` (`0x000873`; if `-1`/omitted, resolved via `ResolveLaunchMinDifficulty`). |
| `created_at` | `int64` | Positive Unix epoch seconds | Freshness check: must satisfy `created_at <= now + 300` and `now - created_at <= 21600` (6 hours). |
| `nonce` | `string` | Non-empty token | Per-launch token echoed into `start_ready.json` so `StartCover` matches the active run. |

---

## 3. `start_places.json` (`schema_version = 1`) Alignment & `start_variant`

`src/fo4sf/core/start_places.json` (staged to `Data/SFSE/Plugins/FO4SFStartPlaces.json`) remains `schema_version = 1` and carries `"start_variant"` on every row:

- **`"story"` rows:** `"start_variant"` MUST be `"normal"` or `"quick"`:
  - Fallout 4: `"fo4_prewar_sanctuary"` (`"normal"`, `FO4SFPrewar.esm`, `required_plugins`: `FO4SFPrewar_Sanctuary.esm`, `FO4SFPrewar.esm`, `FO4SFNewGame.esm`, `FO4SFCoreValues.esm`, `available: true`) precedes `"fo4_vault111"` (`"quick"`, `FO4Port.esm`, `available: true`).
  - Fallout 3 (`available: false`): `"fo3_vault101_birth"` (`"normal"`, CG01–CG04) + `"fo3_vault101"` (`"quick"`, Exit Tunnel).
  - Fallout: New Vegas (`available: false`): `"fnv_goodsprings"` (`"normal"`, Waking Up) + `"fnv_goodsprings_door"` (`"quick"`, Exit Door).
  - Fallout 76 / 1 / 2 / Tactics (`available: false`): `"fo76_vault76"`, `"fo1_vault13"`, `"fo2_arroyo"`, `"fot_bunkeralpha"` (`"normal"`).
- **`"warfare"` rows:** `"start_variant"` MUST be `""`.

---

## 4. Validation Rules (Python & C++ Parity)

### 4.1 Python (`start_places.py` & `launch_choices.py`)
- `sp.load_start_places()` enforces `"start_variant"` (`("normal", "quick")` for `"story"`, `""` for `"warfare"`), `ALLOWED_STORY_START_IDS = ("fo4_prewar_sanctuary", "fo4_vault111")`, required single-line `unavailable_reason` on `available: false` rows, and optional `known_plugins` / `known_marker_edids` / `known_exterior_cells` checks.
- `launch_choices.resolve_and_build_launch_choices()` emits `"schema_version": 2` and `"start_variant"` (`row.start_variant` for Story, `"none"` for Warfare), filters available rows against active/loaded session plugins and cells, and refuses any unknown key in `write_launch_choices()`.

### 4.2 C++ (`setup_places.h` & `main.cpp`)
- `ParseLaunchChoicesJsonText()` enforces `schemaVersion == 2` and validates mode structure generically without hard-coded `place_id` allowlists:
  - `"story"`: `modeVal == 1`, non-empty `storyId != "none"`, `storyChoiceIdx >= 0`, `startVariant` in `{"normal", "quick"}`.
  - `"warfare"`: `modeVal == 2`, `0 <= warfareFactionSlot <= 7`, `warfareStartIdx >= 0`, `startVariant` empty or `"none"`.
- `ValidateLaunchChoicesAgainstStartTable(payload, rows, loadedPlugins, enforcePlugins, reasonOut)`:
  - Matches `payload.placeId` in `rows`; refuses if absent, `!row.available`, `row.mode != payload.modeTag`, or (for `"story"`) `row.storyId != payload.storyId` or `(!row.startVariant.empty() && row.startVariant != payload.startVariant)`.
  - When `enforcePlugins == true`, performs case-insensitive membership checks across `loadedPlugins` for every entry in `row.requiredPlugins` (or `row.plugin` if `requiredPlugins` is empty).
- `LoadLaunchChoicesFile(...)` provides overloads validating against explicit `(rows, loadedPlugins)` (`enforcePlugins = true`), explicit `rows`, or `BuiltinFallbackStartPlaces()` (existing 2..4-arg signature).

---

## 5. Reserved Future Field — `"route"` (Rule 12 — NOT Implemented in Runtime)

The top-level key **`"route"`** is **reserved** in this specification for a future multi-game progression setting:

- **Reserved key:** `"route"`
- **Reserved values:** `"chronological"` | `"pick_a_game"` | `"full_experience"`
- **Runtime status (Rule 12):** **PENDING OWNER DECISION — NOT IMPLEMENTED IN RUNTIME.**
  - `launch_choices.py`, `scripts/launcher.py`, `settings.py`, `gui.py`, `setup_places.h`, and `main.cpp` **MUST NOT** emit `"route"`, add `"route"` to `RESTART_ONLY_KEYS`, expose a CLI/GUI selector for it, or branch on it in `FO4SFPipboyMenu.dll` or Papyrus until explicitly approved by the owner.
