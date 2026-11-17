# Save-Safety Rules Across Candidate Builds

Starfield serializes active plugin indices, bound Papyrus script properties, running quest stages, and filled alias tables directly into `.sfs` savegames. Swapping plugins or `.pex` binaries underneath an existing save is safe only when every baked identifier and property contract stays compatible.

`src/fo4sf/save_safety.py` and `scripts/game/save_safety_check.py` inspect binary `TES4` headers, `GRUP`/`QUST` records, `VMAD` subrecords (record, stage-fragment, and alias adapters), and compiled `.pex` (`0xFA57C0DE`) property tables (loose `Data/Scripts/*.pex` and packed `<plugin> - Main.ba2` archives) to classify any build swap as `SAFE`, `SAFE_APPEND`, or `BREAKING`.

---

## 1. Save-Compatibility Rules

### A. Plugin Load-Order & Presence (`TES4` / `Plugins.txt` / `bundle_plan.json`)

| Change Between `--before` and `--after` | Verdict | Category | Engine Impact on Existing `.sfs` Saves |
| :--- | :--- | :--- | :--- |
| Identical `.esm` list in identical relative order | `SAFE` | — | Every plugin keeps its load-order index; FormIDs resolve unchanged. |
| New `.esm` plugin(s) appended **strictly at the end** | `SAFE_APPEND` | `appended_plugin` | Existing plugin indices stay unchanged. Advisory: newly added `StartGameEnabled` quests may require `OnPlayerLoadGame` handling or a New Game to initialize. |
| Existing `.esm` plugin **removed** | `BREAKING` | `removed_plugin` | Orphans every baked FormID, placed reference, actor value, and quest instance owned by that plugin. |
| Existing `.esm` plugins **reordered** relative to each other | `BREAKING` | `reordered_plugin` | Shifts upper FormID load-order bytes across non-master runtime lookups and baked save references. |
| New `.esm` plugin **inserted before** an existing plugin | `BREAKING` | `inserted_plugin_shifts_indices` | Pushes every surviving plugin after the insertion point to a higher load-order slot, invalidating its prior FormIDs. |

### B. `VMAD` & Compiled `.pex` Script Properties

| Change Between `--before` and `--after` | Verdict | Category | Engine Impact on Existing `.sfs` Saves |
| :--- | :--- | :--- | :--- |
| Unchanged `VMAD` bindings and `.pex` property tables (bytecode-only function edits) | `SAFE` | — | Existing Papyrus object instances bind cleanly on load. |
| New optional property **added** to a script (`VMAD` / `.pex`) | `SAFE` (advisory) | `added_script_property` | Safe to load; `Auto Const` reads from the plugin record, while non-const properties on already-instantiated save objects keep their default/`None` until re-seeded. |
| Bound `VMAD` script or property **removed / renamed** | `BREAKING` | `changed_script_property` | Drops or orphans serialized script state on active quests, aliases, or placed references. |
| `VMAD` property **type changed** (`Object`, `String`, `Int`, `Float`, `Bool`, `Struct`, or array `11..17`) | `BREAKING` | `changed_script_property` | Papyrus VM rejects or corrupts the baked property binding on load. |
| Compiled `.pex` script deleted, or `.pex` `Property` **deleted / retyped** | `BREAKING` | `changed_script_property` | Causes `Cannot open store` or type-mismatch errors against serialized save instances. |

### C. Quest (`QUST`) Stages & Aliases

| Change Between `--before` and `--after` | Verdict | Category | Engine Impact on Existing `.sfs` Saves |
| :--- | :--- | :--- | :--- |
| New `QUST` record added, or new `INDX` stage appended | `SAFE` | — | Existing running quests keep their stage bitmasks and alias tables. |
| Existing `QUST` record **removed** | `BREAKING` | `changed_quest_or_alias` | Orphans active quest timers, objectives, and script instances in the save. |
| Existing `INDX` quest stage **removed** | `BREAKING` | `changed_quest_or_alias` | Breaks quests currently sitting on or checking completion of that stage. |
| `QUST` alias count **reduced**, or `ALST`/`ALLS` alias ID **removed / renumbered / changed kind** | `BREAKING` | `changed_quest_or_alias` | Corrupts forced/filled alias slots and alias script bindings stored by numeric alias ID. |

---

## 2. Offline Check & Installer Warning

Run the standalone binary check offline between any two staged bundles or against an installed game directory:

```powershell
python -I scripts/game/save_safety_check.py --before "<prev-bundle-or-game-dir>" --after "<next-bundle-dir>"
```

`scripts/game/exp_install.py install` also runs this check (via `--check-save-swap <prev-dir>` / `--prev-exp-dir <prev-dir>`, or automatically against the active/preserved `FO4SFExp.install.json` receipt for the same profile) and prints a single-line warning whenever a swap is `BREAKING`:

```text
WARNING: swapping builds will invalidate existing saves (inserted_plugin_shifts_indices=2); start a New Game or back up saves first.
```

---

## 3. Offline Comparison Results on Real Builds

Measured offline with `scripts/game/save_safety_check.py` across the baseline core set and candidate builds:

| Comparison (`--before` -> `--after`) | Before Counts | After Counts | Plugin Diff | Verdict & Finding |
| :--- | :--- | :--- | :--- | :--- |
| **5-Plugin Core Baseline** -> **19-Plugin Core Candidate (`cd03411a`)** | `5` plugins, `683,925` records, `4` `QUST` (`3` aliases), `148` `VMAD` props, `6` `.pex` (`95` props) | `19` plugins, `684,449` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `19` `.pex` (`365` props) | `0` removed, `0` reordered, **`2` inserted**, `12` appended | **`BREAKING`** (`inserted_plugin_shifts_indices=2`): `FO4SFVaultGearDoor.esm` (index 4) and `FO4SFExitLift.esm` (index 5) insert before `FO4SFNewGame.esm`, shifting its FormID index; `0` removed/retyped script properties or quest stages. |
| **5-Plugin Core Baseline** -> **21-Plugin Core Candidate + Pip-Boy (`cd03411a`)** | `5` plugins, `683,925` records, `4` `QUST` (`3` aliases), `148` `VMAD` props, `6` `.pex` (`95` props) | `21` plugins, `684,471` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `20` `.pex` (`365` props) | `0` removed, `0` reordered, **`2` inserted**, `14` appended | **`BREAKING`** (`inserted_plugin_shifts_indices=2`): same 2 pre-`FO4SFNewGame.esm` insertions (`FO4SFVaultGearDoor.esm`, `FO4SFExitLift.esm`), plus 14 appended slice/Pip-Boy plugins. Requires New Game. |
| **Previous Candidate (`0ee8ad5e`, 19 plugins)** -> **Current Candidate (`cd03411a`, 19 plugins)** | `19` plugins, `684,449` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `19` `.pex` (`365` props) | `19` plugins, `684,449` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `19` `.pex` (`365` props) | `0` removed, `0` reordered, `0` inserted, `0` appended | **`SAFE`**: identical 19-plugin load order, identical `QUST` stages/aliases, and identical `380` `VMAD` / `365` `.pex` properties (`swap_warning=None`). |
| **19-Plugin Candidate (`0ee8ad5e` / `cd03411a`)** -> **21-Plugin Candidate + Pip-Boy (`cd03411a`)** | `19` plugins, `684,449` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `19` `.pex` (`365` props) | `21` plugins, `684,471` records, `16` `QUST` (`4` aliases), `380` `VMAD` props, `20` `.pex` (`365` props) | `0` removed, `0` reordered, `0` inserted, **`2` appended** | **`SAFE_APPEND`**: all 19 prior plugins stay at indices `0..18`; `FO4SFPipboyProbe.esm` (index 19) and `FO4SFPipboyTravel.esm` (index 20) append cleanly at the end (`swap_warning=None`). |
