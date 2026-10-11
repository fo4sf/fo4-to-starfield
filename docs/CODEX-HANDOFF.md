# Codex / Claude / Grok status

Owner: repository owner. Current joint focus: prove converted Commonwealth terrain loads in Starfield. Interior acceptance remains open; actor implementation follows verified terrain/navigation probes.

## Goal and acceptance

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library, Parsons: walkable floors/stairs, clear doorways, correct door swing/body ownership/frame collision, acceptable materials and recoverable deployment. Require in-game evidence tied to exact revision/artifact hashes. Unreadable results are inconclusive. Preserve Fallout 4 gameplay and Starfield native physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

Next: [actor milestone proposal](ACTOR-MILESTONE.md), #31. Planning only until interiors pass; assignments not yet acknowledged.

## Owners / locks

- Claude: collision/Havok (`sfcollision`, `fo4collision`, `hkpackfile`, `hktagfile`, `meshcollision`), `convert_static.py`, `pipeline.py`, `scripts/convert_batch.py`, `dotnet/PluginSpike`, game scripts/staging/live control. Do not overwrite active edits.
- Codex: deployment/recovery, persistent IDs/checkpoints/cache/output verification, Fo4Export/ReferenceLinks; animation/door bridge modules (`animation_curves`, `door_motion`, `door_clips`, `door_rig`, `native_door`, `door_model`, `door_prototype`, `door_collision`, `fo4_compounds`) and tests. Owns this status/archive. Shared `sfnif.py`: announce exact function before edits.
- Grok: acceptance oracle and `route_eval.judge` plausibility. No other game scripts/collision/doors/live control without a new claim.

## Current evidence / remaining work

Claude's pinned build1d3d5bf: Vault11112/12 routes PASS, Parsons11 doors OPEN-verified from both sides. Full eight-cell acceptance remains open. New integration2470f876:2 stairs/2 falls PASS,2 door failures from route aim; movable/teleport checks pending. Keep builds separate.

Terrain: custom experiments loaded procedural Mars ground. Claude's vanilla LC172World control matches BTD heights within0.02m in the authored centre; mask borders blend. #64 stages corrected FNAM/Location/mask/alignment/registration. Converted terrain still unverified in game. Claude owns probes; Codex verifies deployment/output. #61 NPC/navigation is research.

Claude b166d6c reports Parsons load door solid; teleport absent,9 models rebuilt with stable IDs. Codex:2 synthetic policy tests cover static collision routing/reporting and normal hinged control; historical swing reproduced. Runtime evidence belongs to Claude; reconcile later load failures against exact artifact hashes.

Door prototype:30 rigs/60 clips read back,42 selected source bodies/62 leaves; offline only, not installed, native moving linkage/activation still unverified. Collision ownership contract:14-byte target/flags/data/BodyID; shared systems select the body's node index, never every body per attachment.

`.af` samples: Open/Close sizes vary. Claude confirmed the second u16 at 0x28 matches named rig-bone counts in four families; frame rate and track mapping remain unknown. Details: research note and #32.

Codex #62 keeps --pack, pins inputs/files/activation and journals rollback/uninstall. Typed config conflicts, pre-publication SHA and inventory checks close review findings.34 regressions;344 total OK (1 skipped), guard/QA PASS. Two Opus5.5 max reviews completed; main Claude asked on #32 to confirm effort/quota. #65 CI dependency merged. No live install changed.

## Coordination / housekeeping

Check #29-32 each session; publish concise evidence and blockers there. Keep this file <4KB. [History](handoff-archive/2026-10-07-codex-history.md).

Delete reviewed scratch/recordings; never commit recordings. Keep staging\multi. Inspect before cleaning Codex's staging\codex-resume-smoke and research\codex-reflect.
