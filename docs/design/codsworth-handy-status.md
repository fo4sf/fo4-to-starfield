# Codsworth (Mister Handy) Status & Integration Requirements

Status as of Round 15 Wave B (`#854`, `claude/robot-anim` @ `abfa189c` integrated onto `gemini/r15-wb-854-handy`):

## What `#854` (`claude/robot-anim` @ `abfa189c`) Fixes
Evidence inspected in `<owner-tests>/robot-anim/E2` (proven RA3 offline + anim checks, merged with `#854` chrome & `HandyLens.BGEM` materials):
1. **Locomotion & Animation (58 `.af` clips):** Provides 58 converted Animation Framework clips targeting the 113-bone Mister Handy `.rig` (`112` FO4 `skeleton.hkx` bones + `DirectAt`) so Codsworth translates, hovers, turns, and idles cleanly instead of freezing in bind pose or sliding statically.
2. **Textures & Materials (5 body `.mat` + `HandyLens.BGEM` `.mat` / `.dds`):** `convert_codsworth.py` converts the 5 FO4 `Handy*_s.DDS` specular/gloss maps from `Fallout4 - Textures1.ba2` into real BC4 `_rough.dds` textures (preserving roughness maps alongside brushed-steel Metalness) and generates a glass `.mat` for `HandyLens.BGEM`.
3. **COM-Height `DirectAt` (`z = 0.984447 m`):** Appends `DirectAt` (map key `137`, look-at / aim) directly under rebased `COM` at local `(0, 0, 0)` with identity rotation (`model_position_m = [-0.0, 0.0, 0.984447]`, matching `com_model_position_m`), mirroring Starfield's Mini Bot rig (`DirectAt` under `C_Body` on `COM`). That `0.984447 m` height is Codsworth's `COM` (torso-base) height — not eye-stalk sensor height — which replaced the Mini Bot ground-plane framing in RA3 while leaving eye-level framing and choice-greeting replay as separate checks.

## What `2g-fix7` / Candidate Integration Carries
- In `FO4SFMission.esm`, `dotnet/Mission/Program.cs` supports `--codsworth-handy <template>` (mutually exclusive with `--codsworth-race-framing`; framing-0 MiniBot parity check is off under `--codsworth-handy`), and `make_mission.py` / `make_core_bundle.py` forward `--codsworth-handy` alongside `--codsworth-assets` and `--actor-looks-assets`.
- Existing converted `codsworth.nif`, `FO4SF_CodsworthRace`, `FO4SF_CodsworthVoice`, and `FO4SF_Codsworth01Quest` remain intact in the folded bundle (`02b-mission`).

## Integration Checklist
1. **Live-game verification (`#854` + chrome):** Verify Sanctuary hover locomotion, eye-stalks/arms, brushed-steel/chrome roughness shading, `HandyLens` eye glass, and 4-choice `DialogueMenu` in Sanctuary once deployed by Claude (PC).
2. **Bundle manifest & hash update (`make_mission.py` / `make_core_bundle.py`):** Fold `--codsworth-handy` (58 `.af` clips, 113-bone `.rig`, `handy.nif`, manifests) with `--codsworth-assets` (converted `_s.dds` -> `_rough.dds`, 5 body `.mat`s, `HandyLens` `.mat`).
3. **Clean-core fold check (`<= 4.000 GiB`):** Verify the added `.af`/`.rig`/`.dds` count and byte total stay within Starfield BA2 archive bounds when folded into `FO4ActorRaider - Main.ba2`.
