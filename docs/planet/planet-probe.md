# The planet probe: our own star system and a test world, before the Commonwealth moves (PR 1, 29 Oct 2026)

For: the Install session on the owner's PC, and anyone reading the result. Plan: the "Strip Starfield down and give
the Commonwealth its own planet" plan of 29 Oct (recommended picks A F H K N R; route A, our own star system). This is
step 1 of its order of work. Nothing here runs by itself, and nothing installs until the owner types the line in
section 6 in the Install thread.

Status: **built and checked offline only.** The C# tool and both checks pass on synthetic masters and on a Bethesda
Creation's records (cloud, 29 Oct). Nothing has run in game. Every Starfield fact below says how it is known:
verified (read from a file or log), supported (a strong hint, not proven) or hypothesis.

## 1. The question

Starfield never plays our worldspace directly. On a planet it plays a runtime copy of the planet's world (for
example MarsPlanetWorld, `FF00C482` on 29 Oct) and merges our overlay world into it. Our persistent references
(Codsworth, doors, markers) stay behind in the base world, so every system of ours needs a script that moves things
(verified from the 29 Oct mission log: the Codsworth keeper moved him at 00:10:21Z; by 00:13:39Z he was back in
`04000803`).

The offset is not the cause: vanilla LC172World also lands off-centre, about (-500, -2300), and its own persistent COC
marker `0010238E` moves with the merge (verified, 11 Oct). Two fixes failed (A, the persistent cell's shape; E, the
OFST / CLSZ tables). Two ideas were never tried:

* the **location links**: an LCPR row on the world's location and an XLCN on the reference. Bethesda's own Creations
  do this, and our records do not (verified: SFBGS00D.esm SFFLDR022World keeps 18 of 18 actors as **temporary**
  ACHRs with XLCN and an LCPR row; our core's location has no LCPR and our markers no XLCN);
* **MergeProbe**: one persistent marker of a plugin of ours inside vanilla LC172World's own persistent cell.

The probe answers one question above all: **which persistent test reference is in the player's world with no script
moving it?** It asks it on our own planet in our own star system, so the same session also shows whether that move
works at all.

## 2. The six test references

All six stand in the spawn cell (0, 0) of the test world, around the arrival, on flat ground:

| Tag | Record | Placed | Location links | Stands for |
|---|---|---|---|---|
| T1 | REFR XMarker | persistent | none | our core's markers today |
| T2 | REFR XMarker | persistent | XLCN + LCPR row | a fix for markers and doors |
| T3 | ACHR citizen | temporary, in the spawn cell | XLCN + LCPR row | Bethesda's Creation pattern |
| T4 | ACHR citizen | persistent | none | our Codsworth today |
| T5 | REFR XMarker | temporary, in the spawn cell | none | the control: plain cell content |
| T6 | ACHR citizen | persistent | XLCN + LCPR row | a fix for Codsworth |

The citizen is Starfield.esm's EncCitizen01Template (`2B211C`), the calm NPC the combined-core probes placed. The
same session also reads two references in LC172World: `MERGE` (FO4SFMergeProbe.esm's marker, persistent, in vanilla's
persistent cell) and `LC172COC` (vanilla's own persistent COC marker `0010238E`, the control that moved on 11 Oct).

## 3. What gets built

Everything is cloned at stage time from the user's own game files. No Bethesda bytes enter the repo or ship.

**FO4SFPlanet.esm** (master Starfield.esm only; adds records, overrides none; `src/fo4sf/planet/records.py`):

* `0x800` STDT, a clone of Sol's star with our name, our own system id `0xF04F1` (checked against every star of
  every plugin in Data: Starfield.esm, the DLC, the built-in Creations and any mod) and a free map position 2 / 2 / 1
  parsecs from Sol;
* `0x801` to `0x804` LCTN, the system, planet, orbit and surface locations, with the DATA of the vanilla locations
  they copy and the keyword of each (checked by EditorID);
* `0x805` PNDT, a clone of Jemison with our name and ids, no master worldspaces (Jemison's register New Atlantis), no
  edited worldspaces, no unique space cell, and no fauna or flora in its biomes. Gravity, day length, atmosphere and
  temperature stay Jemison's.

The master is written with our own raw writer (`src/fo4sf/planet/esm.py`), not Mutagen: Mutagen 0.55's Starfield
schema lacks some star fields (STDT SNAM, HNAM and WED0), so a Mutagen copy would drop them. A clone keeps every
subrecord of its template byte for byte, except the ones listed above.

**FO4SFPlanetProbe.esm** (masters Starfield.esm and FO4SFPlanet.esm; `dotnet/PlanetProbe`, layout in
`src/fo4sf/planet/probe.py`):

* `0x800` to `0x805` the six test references, `0x806` a COCMarkerHeading (`coc FO4SF_PlanetProbeSpawn`);
* `0x807` SFBK, the overlay block: our 3 x 3-cell BTD, Absolute alignment (BTD heights are world z);
* `0x808` LCTN, the probe location: LC172WorldLocation's fields without its references, keyword LocTypeOverlay,
  parent our surface location, one LCPR row per linked reference;
* `0x809` WRLD, a copy of LC172World without its cells, offset tables, large references or parent. Its overlay
  component names **our** system id, planet id and block. Its climate stays LC172's (Mars), so the sky tells whether
  the world record or the planet decides it. Its biome is one of the planet's (`--world-biome planet`, the default:
  New Atlantis's own biome when it is one of Jemison's);
* `0x80A` the persistent cell, `0x80B` to `0x813` the nine exterior cells (-1..1), `0x814` the quest
  FO4SF_PlanetProbe (start game enabled, script FO4SF_PlanetProbeQuest, no properties).

**FO4SFPlanetProbe_Reg.esm**: our planet again, with one master worldspace (the test world at latitude 0,
longitude 0), the separate registration plugin the terrain core also uses.

**FO4SFMergeProbe.esm** (`dotnet/MergeProbe`, unchanged): the marker in LC172World's persistent cell, at vanilla's COC
marker + (3, 0, 0).

**Data files**, packed into "FO4SFPlanet - Main.ba2" at install (loose files are not read on this install, verified
in October): the BTD (flat ground at 10 m and a 30 x 15 m block 25 m high north of the arrival, so a screenshot tells
our ground from the planet's), its overlay mask, the script, and the biome map.

**The biome map** (`src/fo4sf/planet/biom.py`): Jemison's `.biom` copied out of the user's own
"Starfield - PlanetData.ba2" under our planet's name. Which folder the game reads for a plugin's planet is not known
(hypothesis), so the copy goes to both `Data/PlanetData/BiomeMaps/fo4sf probe.biom` and
`Data/PlanetData/BiomeMaps/fo4sfplanet.esm/fo4sf probe.biom`. Verified in the cloud on the real archive: Jemison's map
is there and lists five biomes. Whether they are the planet record's biomes is checked at stage time and recorded in
`offline_check.json` (a difference would be Jemison's own, so the copy is kept).

## 4. The census

`make_planet_probe.py census` (and the first step of `stage`) reads, without writing anything
(`src/fo4sf/planet/census.py`): the template star and planet; every star id in use; the three records the test world
copies and the three bases it places, each checked by EditorID (a missing or renamed one stops the stage);
LC172World's references (how many are persistent, how many carry XLCN / XLRL, and whether `0010238E` is in
LC172WorldLocation's LCPR rows); Mars's master worldspaces; the planet of every overlay world; and the coc cells of
the other arrivals (an exterior cell with an EditorID and a COC marker in TempJemisonWorld and in New Atlantis). It
goes into `census.json` in the stage.

## 5. Reading the run

`make_planet_probe.py log --stage <stage>` reads `FO4SFPlanetProbe.0.log` in `My Games\Starfield\Logs\Script\User`
under `OneDrive\Documents` (where the owner's PC keeps it), else under `Documents`; `--file` names another
(`src/fo4sf/planet/probe_log.py`). The script logs each arrival (another worldspace, another interior cell, or a jump
over 500 m) and reads everything 2, 10, 30 and 60 s later. Each reference gets a verdict at each arrival:

* **with player**: found, in the player's worldspace;
* **left behind**: found, in another worldspace (for ours: the base probe world the game never plays);
* **not loaded**: not found, a temporary reference whose cell is not loaded;
* **not installed**: its plugin is not loaded;
* **unknown**: the line lacks a value the verdict needs (a cut line).

Starfield prints a bool as `true` / `false`, and it can print literal text in another case (both verified: the
bridge log of 14 Oct and the new game log of 28 Oct, which printed `FO4Port.esm` as `fo4port.esm`). The reader
ignores case everywhere, so the verdicts do not depend on how a word comes back.

The offset (position now minus position in the plugin) shows whether a merged reference moved with its world.

What each result means for the move (section 5 of the plan):

| At our planet | Meaning | Next |
|---|---|---|
| T2 and T6 with player, T1 and T4 left behind | the location links carry persistent references into the played world | the re-home patch adds LCPR rows and XLCN to our core's persistent references; the movers can go |
| T3 with player, T2 and T6 left behind | only temporary references with links follow, as in Bethesda's Creations | our actors become temporary references with links |
| all six with player | our planet's world is played as it is, no copy | owning the planet fixes the split by itself |
| T1 to T6 all left behind | no plugin persistent reference follows the merge | the movers stay, or a standalone world (TempJemisonWorld's result) |
| no arrival on our planet, or a crash | our star system or planet record is wrong | read the crash and the census; route B (a planet in Sol) has Bethesda precedent |

| At LC172 | Meaning |
|---|---|
| MERGE with player | a plugin's persistent reference merges in a vanilla world: the cause is in our own WRLD / LCTN records |
| MERGE left behind, LC172COC with player | only Starfield.esm's own persistent references merge |

The planet line at our planet gives the gravity, day length and temperature the game uses there: Jemison's values
mean our cloned record is read. TempJemisonWorld shows whether a standalone world (no overlay component) is played
directly. New Atlantis is the vanilla baseline on the planet ours copies. The sky in the screenshots shows which
record decides the climate (ours keeps Mars's on purpose).

## 6. Stage, install, run, take out

The owner's line, typed in the Install thread (the PC's guard needs the owner's own words for builds, installs and
holds):

> Stage the planet probe (build its tools, compile its script), install it for one test session, run its four
> arrivals and read the log, then take it out.

Steps for the Install session (PowerShell, repo at main after this PR merges):

```powershell
$sf = 'D:\SteamLibrary\steamapps\common\Starfield'
$stage = "D:\Modding\staging\planet_probe_$(Get-Date -Format yyyyMMdd)"
python scripts\planet\make_planet_probe.py precheck
python scripts\planet\make_planet_probe.py stage --data "$sf\Data" --out $stage
python scripts\planet\make_planet_probe.py check --stage $stage --data "$sf\Data"
# game closed:
python scripts\planet\planet_probe_install.py install --dir $stage --starfield $sf
```

Then in game, from the session's dedicated test save (never the owner's own, and never saved over one), in the
order `plan.json` and the stage's README give: `coc LC172Ext01`, `coc FO4SF_PlanetProbeSpawn`, then the census's
TempJemisonWorld and New Atlantis cells. Stay 75 s at each, with one screenshot after 10 s and one after 60 s. The
LC172 control goes first, so its readings are in the log before the new star system is tried.

```powershell
python scripts\planet\make_planet_probe.py log --stage $stage --out "$stage\run_summary.json"
# game closed:
python scripts\planet\planet_probe_install.py uninstall --starfield $sf
```

Rules:

1. **Game closed** for install and uninstall: Starfield rewrites Plugins.txt on launch.
2. **It rides along.** `planet_probe_install.py` runs exp_install.py's code against its own record
   (`Data\FO4SFPlanetProbe.install.json`); the installed experiment (the core set) is not read or changed. The four
   plugins go to the end of Plugins.txt; `order` and `active` work as for exp_install.py.
3. **No holds needed.** Our core keeps LC172World registered on Mars (verified: the installed FO4TerrainCore_Mars.esm
   lists 02DF8C first, then the core world). A plugin_toggle.py hold makes install and uninstall refuse; install
   first, hold after, and put the holds back before the uninstall.
4. **A failed launch is a result.** If the game does not reach the main menu, uninstall (game closed), launch once
   clean, and send the crash dump's name.
5. **Send back**: the log summary (`run_summary.json` and the printed table), the screenshots, `census.json` and
   `offline_check.json`. Nothing from the PC is committed.

## 7. Assumptions and gaps

* The game accepts a star system and planet that only a plugin adds: hypothesis, with community precedent
  (SFStarEditor's systems; read as a layout reference only, its code is CC BY-NC-SA and none is copied). Bethesda's
  Creations add planets to existing systems but no star (verified: no STDT in the built-in Creations).
* The coc into our planet's world builds the planet from our records like a vanilla landing: hypothesis.
* The biome map's folder for a plugin's planet: hypothesis (both are staged).
* A user log stays open only in the game session that opened it (Skyrim and Fallout 4); the script reopens it when a
  write fails.
* Mutagen 0.55 writes the LCPR grid as Y then X (verified on a written plugin with a nonzero grid, 29 Oct).
* Form ids in the log are signed decimal; the reader converts them, and names the probe's from the init line.
