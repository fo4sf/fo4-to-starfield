# In-game test sheet: what exists today, and the console lines that show it

For the owner, by Claude (2026-10-16). Every line below is a console command (open the console with the key left of 1,
the grave key `` ` ``; close it the same way). Copy a line, paste it into the console, Enter. Nothing here changes your
saves on disk unless you save; the test save `fo4sf_test_2470f876` is the runner's and can be overwritten.

**What was installed on 16 Oct (history; section A names today's build):** `terrain_core64k` = the whole playable Commonwealth exterior (64 x 64 cells,
648,358 placed objects) + its navmesh (12,104 NAVM) + 5,156 containers and 12,438 loose items as real Starfield containers and items, 2,246 activators, 140 terminals, 6,249 exterior lights, 29 workshops (build stations) and 269 crafting benches; interiors = `integ_1018` (vault door rigs, posed skeletons and scanners, the shooting-crash collision fix #274; the exterior carries the same fix) + the converted
raider (`FO4ActorRaider.esm`), on top of the pinned interior build `FO4Port.esm` and the observation bridge
`FO4SFBridge.esm`. Section 8 says what is known not to work yet. If Starfield shows a "load order changed" dialog at
start, choose **Current**.

**Form ids in sections 1 to 8** are the 16 Oct load order: `03` was the load index of `FO4TerrainCore.esm` and `02`
FO4Port.esm (the runner's own sessions loaded it at `02`, so its logs show `02...` for the same objects). They are
not the v6i indexes, which moved on 22 Oct (section A), so read the current Plugins.txt before any `prid` from those
sections, or use the cell and object names instead.

## A. Next session on v6i (22 Oct 2026): the checks that close phase 0

Added 22 Oct. The installed build is now v6i_plainshader (FO4Port 9AF962D2, core DC751664, mission 03C2A7A8) plus
the map markers plugin; sections 1 to 8 below are the 16 Oct sheet for core64k and are kept for reference. The same
section A is on the owner's live test sheet (https://claude.ai/artifact/N5ZhYy7zgoxnJ2Fuzhws6b), with copy buttons
and tick boxes. Verified on v6i so far: both Red Rocket walks, Codsworth rendering, the four map markers. Console ids
moved on 22 Oct (Codsworth went from 06000811 to 05000811 because Plugins.txt was rewritten 25 s after start; the
game is the inferred writer, not a traced one), so this section uses cell names and object names only. Results go to [playtest-issues.md](playtest-issues.md).

**Save to use:** the dedicated test save `fo4sf_test_1d4591b6_s100`. It predates the mission plugin, so the mission
starts fresh; the 19 Oct save already completed it and cannot replay it.

### A1. Start

Through the launcher window (the desktop shortcut). The crash watcher starts with the game. Pick **Current** at the
plugin warning if it shows. At the main menu choose Load and pick `fo4sf_test_1d4591b6_s100`. Once in control, open
the console and go to Red Rocket: `coc FO4Core_RedRocketSpawn` (on 19 Oct this crashed v6; the cause was Codsworth's
model, fixed on 22 Oct, and the automated Red Rocket walks passed after the fix). Take a Ctrl+Alt+L screenshot of
anything odd, all the way through.

### A2. Mission: When Freedom Calls (NPC thread's asks)

Walk the road from Red Rocket to the Museum of Freedom in Concord. Expected: the Missions tab shows When Freedom Calls
with Find the Last Minutemen; the raiders fight you near the museum; Preston never shoots you, even after he is downed;
after the raiders die, walk up to Preston: +100 credits and the mission reads complete.
Report: `Mission: tab YES/NO | raiders fought YES/NO | Preston shot me YES/NO | credits YES/NO | complete YES/NO`.

### A3. Codsworth (NPC and Bugs)

Then walk to Sanctuary. Expected: a small hovering robot named Codsworth near his house, with his own Fallout 4 look
(size and textures). Stand near him: his greeting is heard, subtitle only, or neither.
Report: `Codsworth: at his house YES/NO | look OK/OFF (what) | greeting HEARD/SUBTITLE/NEITHER`. If he is not there on
this save either, say so; that is the fix Bugs is working on.

### A4. Map extent (Map thread's ask)

Back at Red Rocket: `player.getpos x`, `player.getpos y`, `player.getpos z`. Open the surface map, zoom out until the
whole merged area shows, and take a Ctrl+Alt+L screenshot of it. (The 3D-view spots, Cydonia and the landing
coordinates, are dropped: that was the border question, now answered.)
Report: `Map: getpos X Y Z | screenshot taken YES`.

### A5. Doors and prompts (Bugs and Interiors)

For each: the prompt text (or "none"), and where you end up.

- (a) Outside Fort Hagen (near -2470, -2772): walk up to the elevator entrance. Is there a prompt, what does it say,
  does it take you inside?
- (b) Outside Vault 95 (near -1916, -3985): the same at its elevator entrance.
- (c) Inside the Museum of Witchcraft (`coc FO4Port_MuseumOfWitchcraft01`): climb to the roof hatch. Prompt? Does it
  put you on the roof?
- (d) Inside Fort Hagen (`coc FO4Port_FortHagen01`): the roof hatch, the same.
- (e) Inside Vault 114 (`coc FO4Port_Vault114`, then walk to the manhole): at the exit manhole and ladder, prompt? Does
  it put you outside on the street?
- (f) Red Rocket's side door: does it slide open?

Report per door: `(a) prompt "..." / none | ended up: ...`.

### A6. Extras

Any time: cans and books still pick up; press Ctrl+Alt+K once and the describe box opens in front (fixed on 22 Oct).
No wall to check north of Vault 111: that report was a misreading and is withdrawn (the owner walked past the spot
without the popup, 22 Oct). The border fix the owner picked (B, our world only) is being tested on the PC at the
Vault 95 exit.

## 1. Get there

| Line | What happens |
|---|---|
| `coc FO4Core_RedRocketSpawn` | The Red Rocket forecourt, under the fuel canopy (the arrival marker). First load takes a while. |
| `tgm` | God mode (no damage, infinite O2). |
| `SetLocalTime 12` | Noon. `SetLocalTime 21` for dusk. (A planet-only command: it works here.) |
| `tcl` | Toggle collision: fly through things; `tcl` again to land. Useful when a roof or wall traps you. |
| `tm` | Toggle the HUD (for screenshots); `tm` again to get it back. |

Coordinates: the world is Fallout 4's, in metres, shifted by (−1200, −2700). A FO4 position (x, y) becomes
(x − 1200, y − 2700) here; heights are unchanged. The arrival is at (−2189.26, −1553.49, 105.26).

## 2. Look around (what the walk gate proved)

The runner's walk went Red Rocket → Sanctuary and back: 254 m, 29 legs, every leg on the converted statics within
0.14 m of FO4's heights. On foot: from the forecourt go north-west, down the road, over the bridge
(`FO4Core_northbridge`, the 44 m deck), up into Sanctuary Hills. Or jump:

| Line | Where |
|---|---|
| `player.setpos x -2185` then `player.setpos y -1561` then `player.setpos z 145` | 8 m south of the arrival, on open ground (the runner's `zref_ground` probe, lands at 105.0). Three lines, one axis each. |
| `player.setpos x -2289.8` / `player.setpos y -1573.5` / `player.setpos z 145` | The first road waypoint (`wp_01`, lands at 109.5). |
| `player.setpos x -2390.4` / `player.setpos y -1553.5` / `player.setpos z 145` | 200 m west (`w_200m`, lands at 102.4). |

Rule learnt the hard way: `setpos z` is an absolute height, so 145 is 40 m above this ground; and a single teleport of
more than ~2 cells (200 m) can throw "Boundary Reached" — go in hops.

## 3. The first-aid kit (R05 slice 1: a converted container that opens)

The kit is inside the station, on the wall. The runner opened it from the console nine times; you can do both:

| Line | What happens |
|---|---|
| walk in, look at the kit, press **E** | The container menu: FIRST AID KIT, Credits 25, Digipick 1 (the vanilla inventory the build gives it). This is the one thing the runner cannot do: a real activation by the player. |
| `prid 03069420` then `GetIsID 030A2A9D` | Selects the kit's reference; the reply `GetIsID >> 1.00` proves the selection (the runner's rule before it activates anything). |
| `prid 030116FA` then `activate player` | Picks up the Stimpak 7 m from the arrival (a converted loose item); the one thing the runner could not confirm is that it lands in your inventory. |
| `activate player` | Opens the kit's menu from the console (after the two lines above), wherever you stand. Hold **Tab** to leave the menu (a tap only goes back one level). |

## 4. NPCs walk here (the exterior navmesh gate, passed 2026-10-16)

| Line | What happens |
|---|---|
| `player.placeatme 002B211C 1` | A vanilla citizen appears at your feet. |
| `PickLastRef` | Prints its runtime id, `FFxxxxxx`. |
| `prid FFxxxxxx` | Select it (use the id just printed). |
| `GetIsID 002B211C` | `>> 1.00`: the selection is the citizen. |
| `PathToRef player` | It walks to you. On the exterior navmesh this is what never worked before this build (the runner's first test: 19 m away, walked 7.2 m towards the player in 30 s). Step back 20 m first (`player.setpos` a few metres, or walk) to see it. |
| `player.placeatme 02F04800 1` then `PickLastRef`, `prid FFxxxxxx`, `StartCombat player` | The converted FO4 raider; it fights you (two runner passes). `tgm` first. |
| `prid FFxxxxxx` then `disable` | Removes a spawned actor when you are done. |

## 5. What the runner reads (if you want to see its instruments)

| Line | What happens |
|---|---|
| `cgf "FO4SF_Probe.Pos" 50762784` | The bridge script logs the kit reference's position and whether it is loaded to `Documents\My Games\Starfield\Logs\Script\User\fo4sf.0.log` (`FO4SF ref=... pos=... loaded=true`). Claude reads that log. |
| `cgf "FO4SF_Probe.Player"` | The same for you. |
| `player.getpos x` (`y`, `z`) | Your position on the console (what the runner's OCR used to read). |
| `GetInCell FO4Core_RedRocketSpawn` | `>> 1.00` in the arrival cell. |

## 6. Interiors (the pinned interior build, independent of the exterior)

The 16 converted interiors are reached by `coc` (they are not linked to the exterior yet: section 8):

`coc FO4Port_RedRocket01` · `coc FO4Port_Vault111Cryo` · `coc FO4Port_SuperDuperMart01` · `coc FO4Port_Vault114` ·
`coc FO4Port_Vault75` · `coc FO4Port_Vault81` · `coc FO4Port_Vault95` · `coc FO4Port_FortHagen01` ·
`coc FO4Port_FortHagen02` · `coc FO4Port_BostonPublicLibrary02` · `coc FO4Port_CambridgePolymerLabs01` ·
`coc FO4Port_MuseumOfWitchcraft01` · `coc FO4Port_ParsonsState01` · `coc FO4Port_PrydwenHull01` ·
`coc FO4Port_GoodneighborHotelRexford` · `coc FO4Port_DmndValentines01`

`coc FO4Core_RedRocketSpawn` brings you back outside.

## 7. When something looks wrong: press the look button (or say "look")

**The button:** press **F13** (map a spare key to F13 in the Womier software: a macro / key-remap to F13) or
**Ctrl+Alt+L**. A short beep = the snapshot is taken; Claude's session sees it within seconds and answers. Both keys
are listened for by `C:\Modding\tools\look\look_hotkey.ps1`, started at every logon from the Startup folder
(`fo4sf-look-hotkey.cmd`; delete it to stop). It types nothing into the game.

**Or say "look"**

Tell Claude **"look"** and what you see (one sentence). Claude runs `scripts/game/snapshot.ps1`, which takes a
screenshot of your screen, reads your position and cell from the bridge log and the game's script log, sends nothing to
the game, and files it under `C:\Modding\snapshots\<time>\`. Claude then reads the picture and the numbers and
documents the issue with them. Keep the game in the foreground when you say it.

## 8. Known not to work yet (do not spend time on these)

- **Doors from the exterior into interiors**: the cave door at the station (local (−994.95, 1109.49)) and every other
  exterior door do nothing. Three builds tried; the last hypothesis fell on 2026-10-15. Next design: the door inside the
  core plugin itself. Use `coc` for interiors.
- **Lights, idle markers, sound markers, splines** are not placed (6,275 lights exported, 0 placed); nights are dark.
- **Containers other than the kit, loose items, terminals, activators** are statics for now: visible, not usable
  (5,185 containers and 12,438 items are listed for the next builds).
- **Far terrain** beyond the 64-cell core is Mars.
- **NPCs**: only the ones you spawn; no encounters, no schedules, no quests.
- The exterior cells are big (100 m): a teleport over 200 m in one go can misbehave; hop.

## 8. Stations, lights and terminals (core64k, 16 Oct night)

Form ids below use your load index `03` for FO4TerrainCore.esm. The benches use Starfield's own station records, so
pressing E on them should open the vanilla crafting menu.

| Command | What it does |
|---|---|
| walk into the Red Rocket garage, look at the workbench, press E | The workshop is a build station now: expect Starfield's build mode (the outpost build HUD). It is 19 m from the arrival. |
| `prid 0300D271` then `activate player` | The same workshop from the console, if E gives no prompt. |
| Sanctuary: `prid 03005C50` then `activate player` | Sanctuary's workshop (by the player's house). |
| Sanctuary benches: `prid 0306BC16` (weapon), `prid 03069B4B` (spacesuit), `prid 0306BBF1` (pharmaceutical), `prid 0305CA9A` (cooking), each followed by `activate player` | The four crafting stations nearest the Sanctuary centre; each should open its vanilla crafting menu. Walking up and pressing E is the same test. |
| `set gamehour to 22` | Night: 6,249 exterior lights are placed; look at Red Rocket and Sanctuary (a flickering fire, the station's lamps). `set gamehour to 12` brings the day back. |
| dim lights variant | If the night lights look too bright, the dim variant is `terrain_core64l_l125` (every light's lumens x0.375, nothing else changed): `set gamehour to 22` at the Red Rocket garage and at the Diamond City gate, and say which looks right. |
| any terminal: press E | 140 terminals are native TERM records with one menu line; the open question is whether terminal mode starts. |
