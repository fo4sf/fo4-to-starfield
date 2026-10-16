# Building the whole Commonwealth from the Red Rocket slice (plan, 2026-10-15)

Author: Claude. Status: plan; the slice items in section 1 are in flight, nothing in sections 2-6 has run.
Labels as in the terrain docs: **verified** = read on files or in game, **supported** = hypothesis with evidence,
**unresolved**. Offline checks are not in-game acceptance.

## 0. What already exists (so the scale-up is not "more cells")

- **Exterior terrain and statics: done at Commonwealth scale.** `FO4Core_Commonwealth` is one 64 x 64-cell overlay
  (6.4 km) that covers the whole playable Commonwealth (FO4 references reach cells x -53..33, y -49..41, inside the
  BTD); core64c places **648,358 references of 11,769 models over 1,708 FO4 cells (up to 6,049 in one cell)**: every
  Fallout4.esm exterior object that converts (docs/terrain/core64c.md, **verified**). Walk gate PASS on core64c and
  core64d (254 m Red Rocket <-> Sanctuary, |dz| <= 0.14 m). DLC placements are not included (no DLC plugins in the depot).
- **Interiors: in `FO4Port.esm`** (the conversion pipeline's own plugin; Vault 111, Red Rocket interior, the batch_full
  cells). The exterior and the interiors are two plugins; what joins them is the door gate (section 2).
- **Semantic objects: the R05 path exists for one class.** `make_core64c.py stage --cluster` turns named placed
  references into native records written by `TerrainOverlays` (CONT + REFR); in game the first-aid kit's reference
  loads at its planned position (bridge probe reply, nine runs) and its menu opens (activate step, twice). Codex's
  #150 keeps the source reference's id through the promotion (required: a rebuild must never renumber references).
- **Actors: the converted raider fights** (StartCombat, two runs) in a vanilla interior; NPC pathing was measured on
  converted interior navmesh (npc_nav n-series). Nothing has pathed on the exterior overlay yet.
- **Runner**: bridge position reads, activate step, teleport captures, door_trip, walk, npc_nav, combat reads.

FormID budget (**verified** arithmetic): 648,358 exterior references + a few thousand bases fit one plugin with room
for the interiors' references several times over (a plugin holds 16,777,216 records); no regional split is needed.

## 1. Finish the slice first (gates, in order)

| # | Item | Owner | Gate |
|---|---|---|---|
| 1 | #150 identity-keeping promotion merged; core64e rebuilt (`rebuild_core64e.sh`: stage --cluster, write, check, formids), acceptance queue re-planned on it | Codex (QA) -> Claude | `check` passes incl. "declared source reference slots retained"; the kit's REFR id = its original slot; `r05_medkit_1016` PASS + menu read |
| 2 | Door gate: `cave_ofst_1015` (Codex's OFST/CLSZ world-level variant, staged) in the next window; if NOLOAD again, a temporary door inside core64c's own build (no add-on exterior cell override: both forms failed in game) | Claude (run), Codex (#129 rebase) | the door trip loads the cave and returns |
| 3 | R06 navmesh-loss inventory with real numbers (FO4 NAVM per cell vs the plugins) | Grok | the report PR + totals on #32; says whether the exterior overlay carries any NAVM |
| 4 | Ref reads through the bridge (`cgf "FO4SF_Probe.Pos" <ref>` instead of console OCR) for doors, probes, NPCs | Claude | sandbox suite; one door_trip and one npc_nav queue read without OCR |
| 5 | #134 merged after 1 | Claude | - |

## 2. Doors and interiors (the first Commonwealth-wide class)

Every exterior DOOR reference of core64c that links to an interior already in `FO4Port.esm` gets its XTEL link (the
slice's `ReferenceLinks` writes it) once the door gate passes. Order: the doors whose interiors exist, by distance from
Red Rocket; a `door_trip` queue per batch of doors (the runner's door_route already walks a list). Interiors that are
not converted yet are left as locked doors (vanilla "inaccessible" behaviour), never as holes.
The backlog of interiors not converted yet (190 behind 350 load doors), ranked and dry-run converted:
[interior-backlog.md](interior-backlog.md).

## 3. Semantic objects across the core (generalising R05)

A cluster generator replaces the hand-written `r05_medkit.json`: it reads the band exports (each exported reference
carries its FO4 base signature; `exterior.py classify`) and emits, per class, the promotion list for all 1,708 cells:

| Class | Native record | Count source | Acceptance |
|---|---|---|---|
| CONT (containers) | CONT + REFR at the original slot, inventory from a fixed vanilla table per container kind (FO4 leveled lists do not resolve) | band exports | activate step on a sample per kind |
| MISC / ALCH / AMMO / BOOK (loose items) | MISC (ALCH as MISC first) | band exports | a pick-up step (activate; inventory count read) |
| ACTI / TERM | Activator / Terminal with one text line | band exports | activate step |
| Enable parents, triggers | XESP on REFRs; primitives | R05 plan sections 1-3 | the R05 slice-2 pair test |
| Persistent-on-border | the vanilla persistent-cell shape | R05 plan | door_trip probes |

Each class is one build (core64e -> f -> g), one `check` extension (counts per class, ids retained), one queue; the
inventory and text tables are owner decisions, recorded in the cluster files.

## 4. Navmesh and actors

R06's numbers decide the path: if the exterior overlay has no NAVM, the options are (a) convert FO4's exterior NAVM
per cell into the overlay's cells (the interior converter exists), (b) a generated navmesh from the landed statics,
(c) rely on Starfield's procedural pathing on planet terrain (unknown whether it exists for overlays: **unresolved**).
Gate: an npc_nav queue on the exterior (Red Rocket -> Sanctuary, the walked route) before any actor placement.

Status 2026-10-16: R06 (Grok, #163) found **0 NAVM** in FO4TerrainCore.esm against FO4's 7,047 NAVM / 3,439,338
triangles over 1,069 of the overlay's cells, so (a) is the path, and its pieces exist: `src/fo4sf/navmesh.py convert`
(experiment 2d) and the NAVM/NAVI writer, now in `TerrainOverlays` (`overlays_params` `navmesh`, `make_core64c.py
stage --navmesh navmesh.json`): on exp2d's input it writes the same 156 NAVM / 68,132 triangles / 8,208 edge links and
every NAVM parses back. Grok runs the converter over the whole core; the build is core64 + objects + navmesh, then
the exterior npc_nav gate.
Actors then follow the raider pattern: converted NPC bases, spawn points from FO4's placed ACHR/LVLN, combat reads.

## 5. Environment

Water (FO4 water planes -> Starfield water), lights (exterior LIGH refs), weather/time (the sky_light ladder works),
map markers and locations (one Location per overlay now; FO4 map markers -> LCTN/REFR), LOD for the far ring
(commonwealth-scale.md option d). None gates playability of the core; each is one queue with a screenshot.

## 6. Quests, scripts, DLC

R07 (Codex): the quest census says which quests/scripts reference the converted cells; nothing scripted ships before
the census. DLC placements need the DLC plugins in the depot (not present): a separate decision.

## Order of work from here

1 -> 2 -> 3 (CONT first, because the path exists) -> 4 -> 5 -> 6. Every step: build offline, `check`, one queue in a
declared window, screenshot on #32, journal.
