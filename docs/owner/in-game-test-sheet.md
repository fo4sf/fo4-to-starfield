# In-game test sheet: what exists today, and the console lines that show it

For the owner, by Claude (2026-10-16). Every line below is a console command (open the console with the key left of 1,
the grave key `` ` ``; close it the same way). Copy a line, paste it into the console, Enter. Nothing here changes your
saves on disk unless you save; the test save `fo4sf_test_2470f876` is the runner's and can be overwritten.

**What is installed for you right now:** `terrain_core64f` = the whole playable Commonwealth exterior (64 x 64 cells,
648,358 placed objects) + its navmesh (12,104 NAVM) + the Red Rocket first-aid kit as a real container + the converted
raider (`FO4ActorRaider.esm`), on top of the pinned interior build `FO4Port.esm` and the observation bridge
`FO4SFBridge.esm`. Section 8 says what is known not to work yet. If Starfield shows a "load order changed" dialog at
start, choose **Current**.

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
| `prid 02069435` then `GetIsID 020A2AA5` | Selects the kit's reference; the reply `GetIsID >> 1.00` proves the selection (the runner's rule before it activates anything). |
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
| `cgf "FO4SF_Probe.Pos" 33985589` | The bridge script logs the kit reference's position and whether it is loaded to `Documents\My Games\Starfield\Logs\Script\User\fo4sf.0.log` (`FO4SF ref=... pos=... loaded=true`). Claude reads that log. |
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

## 7. When something looks wrong: say "look"

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
