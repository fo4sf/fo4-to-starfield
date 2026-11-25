# Vault 111 Look Verification Card (`gemini/r14-v111-look-anims`)

Paired offline fixes: `src/fo4sf/pipeline.py`, `src/fo4sf/convert_static.py`, `dotnet/PluginSpike/Program.cs`, and [vault111-look-fix.md](../terrain/vault111-look-fix.md).

| Row ID | Tag | Mode | What to Check & Expected Result |
|---|---|---|---|
| **V111-LOOK-1** | `REACHABLE`, `VIDEO` | Player in `FO4Port_Vault111Cryo` after next `FO4Port` rebuild (`convert_batch` + `PluginSpike` with `RESOLVE_ENABLE_PARENTS=1`, `DEDUP_EXACT_REFS=1`, `LIGHT_MERGE_M=2`) | **Restricted-area floor decals & hall sweep:** Walk from Cryo Bay (`1B5EBD..1B5EC0`) through Hall `1A78B1`, Overseer junction `V111Hall01` (`-34.7, 27.4`), and Cog-Door / Pip-Boy restricted stripes (`0556FE`, `001907`, `1B5EC9..1B5ECA`) while panning camera slowly up/down and side-to-side. All yellow/black restricted stripes render with proper alpha blending (no opaque black/grey slabs) and zero Z-fighting / flashing against floor tiles or overlapping hall pieces. |
| **V111-LOOK-2** | `REACHABLE`, `VIDEO` | Same session, `Vault111Cryo` corridor & Cryo Bay -> Gear Room walk | **Vault 111 lighting & disabled Pre-War lights:** Verify the `25` Pre-War `PreWarPlayerHouseLightCool*` (`0x000481D4`) and `3` post-exit klaxon lights (`0x002075E4`) remain initially disabled before cog-door activation, corridor/reactor lighting shows even coverage without washed-out clusters (`LIGHT_MERGE_M=2`), and klaxon lighting only enables upon activating the Vault door console (`V111ExitLightingEnableMarker`). |
