# Task 0 & Task 1 Lead Verification Cards (`gemini/core-integration`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card A — `G4` List-Dialogue Scene & Voice-Type Route Proof (`TEST-STATION`)

**Purpose:** Prove early in game that pressing `E` on a custom speaker using a duplicated `AllowDefaultDialog` (`0x1`) `VTYP` + `AllowPcDialog` (`0x200000`) `RACE` and an `SCEN` actor-dialogue phase with `ACTV` Topic actions opens Starfield's `DialogueMenu`, shows subtitle choices, and advances quest stages on selection. Downstream Story talks (`M4` Preston and `M6` Codsworth) remain **`RECORDS ONLY` / `NOT BUILT` for `REACHABLE`** until this `G4` route passes in game.

### Setup (`--profile test` bundle)
1. Install the `--profile test` bundle (which keeps `FO4SFListDialogue.esm` + `FO4SF_ListDialogueQuest.pex` active).
2. Load a clean test session and move to the list-dialogue station: `coc FO4SFListDialogueCell`.
3. Press `E` on the speaker (`FO4SF_ListDialogueSpeaker`, `0x000807`, carrying `FO4SF_ListDialogueVoice` `0x000809` with `VoiceType.Flag.AllowDefaultDialog`).
4. Select one of the skill/attribute choices (`Speech 50`, `Science 40`, or `Strength 7`) in `DialogueMenu`, then exit cleanly.

### Required PASS Log Lines (`FO4SFListDialogue.0.log`)
- `FO4SFLIST ... Init speaker_present=true arrival_present=true`
- `FO4SFLIST ... choice_stage stage=<20|30|40|50> tag=<...> outcome=<pass|fail> end=true`
  *(Note: `bundle_log.eval_dialogue` rejects `stage=10`, `eval phase=baseline_low`, `eval phase=qualified_high`, and `stage=60` `Plain_Goodbye` without a real `20..50` choice line.)*

### Owner / Visual Check
- Pressing `E` opens `DialogueMenu` immediately (does not silently ignore `E`).
- Choice rows render readable text and selecting a row advances the scene cleanly without locking camera/controls.

---

## Card B — `1a` / `1c` / `1d` F7 `STAT` Crash-Proof Isolation (`REACHABLE` Key / `TEST-STATION` Isolation)

**Purpose:** Prove in isolation (with `PopulateInCall=0`, `LateInvalidate=0`, `StatActions=0`, `InvDataAnswers=0`, `RequirePickup=0`) that replacing the `CreateFunction` `BGSCodeObj` holder with `Menu_mc.BGSCodeObj` plain `Object` (`CreateObject` fallback, never `CreateFunction`) eliminates the `PerksTab` `StopPerkSound` crash, and that the AVM2-generated 49-name `FO4SFPipboyMenu.ini` handles 10 open/close cycles cleanly.

### Part 1 — Negative Property-Lookup Proof (`48` names, `StopPerkSound` omitted)
1. Generate stage INI omitting `StopPerkSound`:
   `python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage> --out <stage-ini> --omit StopPerkSound --allow-omit StopPerkSound`
   *(Confirm without `--allow-omit` the tool exits `1` naming `Pipboy_StatsPage.swf:StopPerkSound`.)*
2. In game, press `F7` to open `STAT`, cycle tabs across `Status`, `SPECIAL`, and `Perks`, then press `Tab` or `Esc` to close.
3. **PASS:** Zero crash when `PerksTab` looks up missing `BGSCodeObj.StopPerkSound` (plain `Object` returns `undefined` instead of faulting).

### Part 2 — Full 49-Name `1a` + `1c` + `1d` Run (`10` Open/Close Cycles)
1. Generate full stage INI (`49` movie-called names, zero `[Kit]` / `[Page ...]` sections):
   `python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage> --out <stage-ini>`
2. Press `F7` -> cycle `STAT` subtabs -> press `E` on `STAT` (confirm `E` does **not** switch top-level pages) -> press `Tab`/`Esc` to close; repeat `10` times.
3. Open Console (`` ` ``) and type `m`, `v`, and `n`; confirm neither Pip-Boy nor VATS/night-vision triggers while a blocking menu is open.

### Required PASS Log Lines (`FO4SFPipboyMenu.log` & `FO4SFCombat.log`)
- `step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49`
- Per close (`1c` exact order):
  1. `step=code_obj_destruction movie=1 called=1`
  2. `step=map_unregister ok=1` *(when `MAP` was loaded)*
  3. `step=destroy`
- Zero `code_obj_late_call` lines (`LateInvalidate=0`), zero `watchdog_busy`, zero crash across `10` cycles.
- `1d`: `step=menu_guard registered=<n> count=37`, `step=process_user_event name=Cancel handled=<0|1> down=1`, and `ignored=menu_open menu=Console` when pressing `m`, `v`, or `n` in Console.

---

## Card C — `1g` Starfield Scanner & Map Menus Block (`TEST-STATION`)

**Purpose:** Verify that `GalaxyStarMapMenu`, `SurfaceMap`, and `MapMenu` are intercepted cleanly via per-slot null-menu creation (`kMaxMapMenus = 16`) without crashing Starfield when each map shortcut key is pressed once, and that `DisableHandScanner()` logs its input-layer block.

### Steps
1. On a player-profile or test-profile session outdoors, press the Star Map (`G` / `M` fallback), Surface Map, and Planet Map keys once each, and press `F` (scanner).
2. Confirm no Starfield star/surface/planet map opens, no crash occurs, and no `"FO4SF"` developer banner text (`1h`) appears on screen in `--profile player`.

### Required PASS Log Lines
- `FO4SFNewGame.0.log`: `blocked input=handscanner`
- `FO4SFPipboyMenu.log`: `step=starmap_blocked n=<k> blocked menu=<GalaxyStarMapMenu|SurfaceMap|MapMenu> route=create`

---

## Card D — `1i`, `1j`, `1k` Arm Idle, `STAT` Aid Actions, `INV`/`DATA` Answers & Lift `SpecialMenu` (`TEST-STATION`, Gated Off Until Card B Passes)

**Default Safety (`R3`):** Shipped `FO4SFPipboyMenu.ini` and default `make_pipboy_stage_ini.py` keep `PopulateInCall=0`, `Arm=0`, `StatActions=0`, `InvDataAnswers=0`, and `SpecialMenu=0` so Card B (`1a` isolation) runs untouched first. Once Card B passes in game, enable each switch one step at a time (`--populate-in-call 1`, `--arm 1`, `--stat-actions 1`, `--inv-data-answers 1`, `--special-menu 1`).

### Required PASS Log Lines (`FO4SFPipboyMenu.log`)
1. **`1b` (`PopulateInCall=1`):**
   - `step=populate page=<p> tab=<t> hp=<cur>/<max> ap=<cur>/<max> level=<lvl> special=<s>,<p>,<e>,<c>,<i>,<a>,<l> source=<...> paused=<0|1>` *(logged before `Menu_mc.InvalidateData`)*
2. **`1i` (`Arm=1`, both `F7` and `M`):**
   - Open: `step=arm_raise n=<k> idle=IdleExamineWatch form=<hex> accepted=1`
   - Close: `step=arm_lower n=<k> how=<idle|watch_resume> accepted=1`
3. **`1j` (`StatActions=1`):**
   - `step=code_call ... name=UseStimpak` -> `step=stat_use item=<hex> hp_before=<X> hp_after=<Y> used=1`
   - `step=code_call ... name=UseRadaway` -> `step=stat_use item=<hex> rads_before=<X> rads_after=<Y> used=1`
   - `step=stat_sound fn=<PlayPerkSound|StopPerkSound|PlaySmallTransition> clip=<id>` (`ShowPerksMenu` logs `step=stat_stub fn=ShowPerksMenu`).
4. **`1k` (`UI-2` `InvDataAnswers=1` & `UI-3` `SpecialMenu=1`):**
   - `INV` (`page=1`): `step=inv_fill count=<N> tab=<T> filter=<mask>`, `step=inv_select ...`, `step=inv_equip ...`, `step=inv_drop ...` *(Starfield's inventory, status, missions, and skills menus remain unblocked until `INV` and `DATA` pass in game).*
   - `DATA` (`page=2`): `step=quests_fill count=<Q> workshops=<W> stats=<S>`.
   - `FO4SF_SpecialMenu` (`SpecialMenu=1`, `SpecialMaxPoints=40`): `step=special_done name="<name>" s=<S> p=<P> e=<E> c=<C> i=<I> a=<A> l=<L>` writing `FO4SFCoreValues.esm` `0x000810`–`0x000816`.

---

## Explicitly `NOT BUILT` in `gemini/core-integration`
- **`1l` (`docs/ui/fo4-menus-hosting.md` & `docs/ui/fo4-hud-options.md`):** Design option notes only (`TOOLING` / docs; nothing built until owner picks).
