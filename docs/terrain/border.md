# The landing-area border ("BOUNDARY REACHED") in our world

Owner's decision (Oct 22): fix it for our world only, not with the global INI, because the project will hold more
than one game's world.

## What is known
- **verified** (PC run _f, Oct 22, #444): it is the engine's border-region system. With
  `SetINI "bBorderRegionsEnabled:General" 0` typed in the running game, the Vault 95 exit after a coc PASSes at 0.00 m;
  with it on, the exit FAILs STAYED and the popup shows. That is one run (n=1): with the border on the same exit
  passed 7/10, 6/10 and 3/3 in the rate runs below, so one pass shows the switch is worth testing, not that it
  caused the pass.
- **verified** (owner, Oct 22 18:55Z): no wall on foot north of Vault 111. They walked far north, past where Fallout
  4's own border would be, without the popup. An earlier note of a wall there was a misreading and is withdrawn.
  **verified** (owner, Oct 23 16:33Z): facing Sanctuary from Red Rocket, the boundary fires on the left (W/SW) only; every other
  direction is open until generated Mars land.
- **supported hypothesis** (research log 2026-10-12, "which teleports raise Boundary Reached"): of 145 setpos moves
  of at most 2 cells (200 m; a cell is 100 m) per axis, 144 landed; of 28 moves of 3 or more cells, 11 failed. "300 m hops are safe"
  was refuted there (core64b's hops were at most 187.4 m per axis), and no distance threshold is known.
- **supported hypothesis**: so the border is a limit on how far one teleport (MoveTo, coc, setpos) may move the player
  from where the engine last had them outside. It may be a fence at a position as well: the owner's Oct 23 report
  (W/SW of Red Rocket only) fits a fence on that side, untested until the walk below (Planet research T1). The Vault 95 exit after a coc from Red
  Rocket is one 2.26 km jump. A player who walks to a door and back is never more than a few metres away.
- **verified** (Fallout4.esm, read-only): FO4's own border is REGN `Border` (0x049BE0, flag 0x40, Commonwealth):
  x -107,076..106,396, y -103,493..108,385 game units, about -1,530..1,520 m and -1,478..1,548 m. Starfield never
  reads FO4 REGN records and we convert none, so it plays no part; walking past it is fine.
- **verified** (xEdit `wbDefinitionsSF1.pas`, dev-4.1.6): Starfield keeps Skyrim's REGN `Border Region` flag, but
  Starfield.esm has only 4 REGN records (docs/measurements/sf_esm.json), so planet borders are not REGN polygons.
  The WRLD record has no field named for a playable area or border; `HNAM` (1 byte) is unnamed.
- **verified** (web, Oct 22): every published mod that removes the border does it globally:
  - Border Regions Unlock (nexusmods.com/starfield/mods/14643) sets the INI at load through SFSE and
    Console Command Runner, and changes no records.
  - Remove Planetary Tile Boundary (mods/261) is an INI-only change.

  New-planet mods (SFStarEditor, custom biome guides) build handcrafted land as overlay worldspaces registered in the
  planet's `PNDT` master worldspace list, as we do. None documents a per-world border switch.

## Our world against the vanilla worlds the player walks far in
`C:\Modding\research\terrain\sf_wrld_dump.txt` (433 vanilla WRLD). Our world is a duplicate of LC172World
(dotnet/TerrainOverlays), so it carries LC172World's values:

| WRLD field | NewAtlantis | akilacity, NeonCity | LC172World (our template) | vanilla count |
|---|---|---|---|---|
| `DATA` flags | 0 | SmallWorld | SmallWorld | SmallWorld 424 of 433; 0 on NewAtlantis, TempJemisonWorld and 7 OverlayTrait / lc070 worlds |
| `HNAM` | 5 | 5 | **0** | 5: 379; 0: 54 (POI overlays, PCMShipLanding01..04, LC172, LC003) |

`uPlayableSpaceOverlayCellBuffer:Planet` is 5 as well. Whether `HNAM` is that buffer per world is a **hypothesis**.

## The test (dotnet/BorderProbe)
`BorderProbe show <Starfield.esm> <our plugins in load order>` prints the world's fields in each plugin.
`BorderProbe build ... --variant nosmall|hnam5|city` writes `FO4SFBorderProbe_<variant>.esm`. It overrides only the
world's winning WRLD record, and it masters every given plugin, so it loads after the last override (FO4SFMission
overrides the world).

Each variant gets one Vault 95 OUT leg with the border on (`door_rounds.py stage --legs out --only <Vault 95>`,
without `--border-off`), installed next to the current build. The control is the _f run's border-on leg on the same
build (FAIL STAYED with the popup). Each result is evidence about that variant at this exit only:
- PASS makes the variant a candidate. Before the core build takes it, it needs the wider checks: a second long coc
  exit elsewhere in the Commonwealth, a long map fast travel, and a vanilla planet
  landing that still shows its border (the override touches only our WRLD, but that has to be seen in game).
- FAIL STAYED with the popup counts against the variant at this exit; it does not rule the field out elsewhere.

### Results (PC, 2026-10-22, border on, v6i_plainshader with each probe)
- **city** (no SmallWorld, HNAM 5): Vault 95 OUT **PASS**, 0.00 m off in xy, 0.02 m in z; the Red Rocket spawn leg
  passed too (queue `doors_v95_probe_city`).
- **hnam5** (SmallWorld kept, HNAM 5): FAIL STAYED, still in the interior.
- **nosmall** (no SmallWorld, HNAM 0): PASS on its rerun (`doors_v95_probe_nosmall2`).

**Repeat test: neither field change reliably fixes the exit in these runs.** In the first runs FO4SFMapMarkers.esm,
with a copy of the core's WRLD (SmallWorld, HNAM 0), loaded after the probe, so the live WRLD was the control's in all
of them. The settling test (2026-10-22, queues `doors_v95_settle_*`) put each variant in the markers plugin's WRLD
copy, as the last override (BorderProbe show before and after the first run), no probe plugin, the same save, 3 runs
each:

| set | WRLD (last override) | runs |
|---|---|---|
| control | SmallWorld, HNAM 0 | PASS, PASS, PASS |
| nosmall | flags 0, HNAM 0 | PASS, PASS, FAIL |
| city | flags 0, HNAM 5 | FAIL, PASS, PASS |

Every PASS lands at the same spot (0.00 m off in xy, 0.02 m in z). Every FAIL is "STAYED": the player is still in the
interior, near its door, and the screenshot shows the BOUNDARY REACHED popup. The earlier control failure (`_f`,
without the markers plugin) and the hnam5 failure stay on record. What this shows: city and nosmall are not reliable
fixes. What it does not show: whether the fields change the failure rate (3 runs per set cannot tell), whether the
fourth combination (SmallWorld kept, HNAM 5) helps (it was never the last override), or what causes the intermittent
failure; the popup still points at the border mechanism. Those stay open until controlled repeats.
`make_core64c.py stage --world-border` stays in the code with `template` as the default; no core is built with it.
The next steps are the failure rate (10 control runs, with the FO4SF_LoadDoor trace) and the door's retry of a missed
MoveTo (docs/terrain/scripted-doors.md).

### Rate and retry runs (PC, 2026-10-22/23, control WRLD, queues `doors_v95_rate_r01..r10`, `doors_v95_retry_r01..r10`)
- Rate (bridge_t4, no retry): 7 PASS, 3 FAIL (r01, r02, r10). Retry (bridge_t5, `MoveRetries` 1): 6 PASS, 4 FAIL
  (r01, r04, r08, r10). No run traced `retry 1 of 1`, `after_retry` or `gave up`: the retry never fired.
- **verified** (FO4SF_LoadDoor trace, all 10 retry runs): the script's view is the same in every run, PASS or FAIL.
  The MoveTo lands in the exterior (cell 02001133, world the runtime instance `MarsPlanetWorld…` FF…) at the marker's
  unmerged position (-714.6, -1284.1, 61.3); `after_position` still reads that spot right after the SetPosition to
  the merged (-1914.6, -3984.1, 61.2). That 1200 / 2700 difference is the overlay offset, as expected
  (docs/terrain/scripted-doors.md, "unmerged position"). So no check inside the script right after the move can tell
  a failing trip from a passing one, which is why the retry never fired.
- **verified** (bridge feed and screenshots, all 7 FAILs): after the door the bridge feed stops (the newest line is
  76 to 78 s old at every read), and the screenshot shows the BOUNDARY REACHED popup over the Vault 95 interior.
  In the PASSes the next feed line is at the merged spot. The popup pauses the game and Papyrus with it, so the
  judge falls back to the last read before the door (inside, cell 06007D12) and calls it STAYED. "STAYED" in these
  runs means "the popup came up during the exit", not a measured bounce back inside.
- **unresolved**: which step raises the popup, the MoveTo's landing at the unmerged spot (2.9 km from the merged
  one) or the single SetPosition jump back. Both are jumps far past the "at most 2 cells per axis" teleport rule
  (docs/terrain/core64c.md). The diagnostic bridge waits `SettleSeconds` after the MoveTo and traces
  `phase=settled` before the SetPosition: with the game paused by the popup, a log that stops before `settled`
  blames the MoveTo, one that stops after it blames the SetPosition.
- The runs start from a coc at Red Rocket, 2.3 km from the Vault 95 door; a player who walked in through that door
  would not make that jump. The unmerged landing is a 2.9 km jump in both cases.

### The owner's play (PC, 2026-10-23, v6i_plainshader, bridge t4, before #512)
- The owner's account (Oct 23, 16:30 and 16:31 UTC), the ground truth: the Vault 95 door puts them outside, at the
  right place. They then hit BOUNDARY REACHED; pressing Tab (cancel) does not let them move, and the game teleports
  them back to where they were. "It is sending me to the right place."
- **verified** (bridge feed, fo4sf.0.log, read by Install): on both exits `after_move` and the following feed lines read
  the marker's written coordinates (-714.6, -1284.1, 61.3), cell Surface 02001133, with `requested_position`
  (-1914.6, -3984.1, 61.2); the feed did not read the requested position. Every other door that session read its
  requested position. The setpos hops typed in the same session all landed where they were typed.
- **unresolved**: how the right place on screen and the written coordinates in the feed fit together. In the runs, a
  PASS read the requested position and stood on the ground there. The owner's account rules out "the door lands in
  the wrong place" as the explanation.
- What it means: the popup can come up after a correct landing, while the player tries to move, not only during the
  trip. The bridge_t6 runs (#512's `PlaceDestination`) check the landing and the popup at landing (beyond.png); the
  owner's walk around the entrance after them checks moving. If the popup still comes up there, the per-world border
  toggle below is the route.

If a retry does not help, the next per-world route is to toggle `bBorderRegionsEnabled` only while the player is in our
world. That needs SFSE code, or `Utility.SetINIBool` from Papyrus: it exists (DebugOnly, and DebugOnly natives run
in our builds, docs/testing/probe-stage.md: GetFormEditorID returned `MQ101`), but whether the engine reads the new
value of this setting is untested. The SFSE switch below was built first; SetINIBool is the fallback to try if it
cannot be armed.

## Per-world switch (SFSE plugin FO4SFBorder, built 2026-10-23, not yet run in game)
The owner chose this route on 2026-10-23: the popup comes after a correct landing, and the map stays open land with
no walls ("L because the full vison"), so the border must be off in our world and on everywhere else.

- **The world test** is in Papyrus, because SFSE's plugin API (PluginAPI.h at commit 48535cc) has no Papyrus or
  console bridge. `FO4SF_MapMarkers` writes `border=off` to its user log (fo4sf_map.0.log) when the player stands in
  one of the core's own cells (the cell's load index is the core's: the runtime instance keeps the core's cell ids,
  door-rounds.md), or outdoors in the world they were in while in one (the generated land past our cells). Any other
  exterior writes `border=on`. Indoors keeps the last state. A line is written only on a change, and again at the
  first check of every new game session.
- **The switch** is `sfse/FO4SFBorder` (README there). It finds the setting `bBorderRegionsEnabled:General` by its
  name in Starfield.exe's memory, tails that log, and writes the setting's value byte on the main thread (SFSE Task
  interface). "on" restores the value it found. Kill switch: `Mode=0` in FO4SFBorder.ini (the default) writes nothing.
- **Unverified until the PC probe:** which byte is the value. Card A runs `Mode=1` (watch only): the owner types
  `SetINI "bBorderRegionsEnabled:General" 0` and then `1` (the command run _f used), and the plugin's log shows the
  byte that changed. Card B sets that offset and `Mode=2`, then the Vault 95 exit and a walk at the west edge.
- The plugin refuses to write unless exactly one candidate setting is found and its byte reads 0 or 1.
- **Check for card B (Planet research T1):** on foot from Red Rocket, due west and then south (not through the Vault
  95 door), `player.getpos x` and `player.getpos y` at each popup, once with the switch off (Mode=0) and once on.
  The off run says where the fence is; the on run says whether the switch removes it.
- **unresolved** (Planet research, inferred, not measured by us): even with the border off, the planet's physics
  edge is reported at about 6-7 km from the landing centre, and our terrain's SW corner is about 7.4 km from merged
  (0,0). Re-centring the core is a core change for the next phase, not part of this switch.
