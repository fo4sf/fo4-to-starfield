# The landing-area border ("BOUNDARY REACHED") in our world

Owner's decision (Oct 22): fix it for our world only, not with the global INI, because the project will hold more
than one game's world.

## What is known
- **verified** (PC run _f, Oct 22, #444): it is the engine's border-region system. With
  `SetINI "bBorderRegionsEnabled:General" 0` typed in the running game, the Vault 95 exit after a coc PASSes at 0.00 m;
  with it on, the exit FAILs STAYED and the popup shows.
- **verified** (owner, Oct 22 18:55Z): no wall on foot. They walked far north of Vault 111, past where Fallout 4's own
  border would be, without the popup. An earlier note of a wall there was a misreading and is withdrawn.
- **verified** (JOURNAL 2026-10-11/12): single jumps of more than about 450 m raise it; 300 m hops travel freely.
- **supported hypothesis**: so the border is a limit on how far one teleport (MoveTo, coc, setpos) may move the player
  from where the engine last had them outside, not a fence at a position. The Vault 95 exit after a coc from Red
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

If no variant passes, the next per-world route is to toggle `bBorderRegionsEnabled` only while the player is in our
world. That needs SFSE code, since no Papyrus INI setter has been verified in Starfield.
