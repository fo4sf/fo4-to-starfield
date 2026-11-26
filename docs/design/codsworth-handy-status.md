# Codsworth (Mister Handy) Status & Integration Requirements

Status as of `2g-fix6` (`2026-11-25`):

## What `#854` (`claude/robot-anim` @ `abfa189c`) Fixes
Evidence inspected in `<owner-tests>/robot-anim/E2` (proven RA3 offline + anim checks; not yet merged to `main`):
1. **Locomotion & Animation (58 `.af` clips):** Provides 58 converted Animation Framework clips targeting the 112-bone Mister Handy `.rig` so Codsworth translates, hovers, turns, and idles cleanly instead of freezing in bind pose or sliding statically.
2. **Textures & Materials (5 `.mat` / `.dds`):** Supplies the converted Mister Handy brushed-steel/paint material and DDS texture chain matching the `codsworth.nif` plain-shader geometry slots.
3. **Eye-Level `DirectAt` (`z = 0.984447 m`):** Fixes the Mister Handy eye-stalk focus height at `0.984447 m` so player-to-Codsworth conversation camera framing (`DirectAt`) targets his optical sensor instead of the ground plane or belly thrusters.

## What `2g-fix6` Carries Today
- In `FO4SFMission.esm`, `dotnet/Mission/Program.cs` includes `--codsworth-race-framing 1` (configured for `ModelARace` standing dialogue camera height until `#854` lands).
- Existing converted `codsworth.nif`, `FO4SF_CodsworthRace`, `FO4SF_CodsworthVoice`, and `FO4SF_Codsworth01Quest` remain intact in the folded bundle (`02b-mission`).

## What `#854` Needs Before Joining the Candidate Bundle
1. **Host/CI review & merge to `main` (or explicit bundle override):** Merge `#854` (`claude/robot-anim` @ `abfa189c`) into `main` once Claude clears live-game E2 dialogue + hover locomotion in Sanctuary.
2. **Bundle manifest & hash update (`make_mission.py` / `make_core_bundle.py`):** Point `make_core_bundle.py` / `convert_codsworth.py` asset copy and expected SHA-256 verification tables at the 58 `.af` clips, 112-bone `.rig`, and 5 `.mat`/`.dds` files shipped by `#854`.
3. **Clean-core fold check (`<= 4.000 GiB`):** Verify the added `.af`/`.rig`/`.dds` count and byte total stay within Starfield BA2 archive bounds when folded into `FO4SFMission - Main.ba2`.
