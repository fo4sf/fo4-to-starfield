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

Terrain: Claude now reports Red Rocket native Commonwealth heights,13/14 probes within0.08m; one142m miss was unmeasured. Exp2c adds8,069 references/1,385 models, roof/road/shop-floor collision within0.01m. Ground still Mars dirt. #67 tile seams and #68 NPC control are queued; #70 textures/#71 navmesh underway. LC172 control within0.02m. Claude owns runtime evidence; full region/interior acceptance remains open.

Claude b166d6c: Parsons load door solid, teleport absent. Static/hinged routing has synthetic coverage; reconcile runtime failures against exact hashes.

Door prototype:30 rigs/60 clips read back,42 selected source bodies/62 leaves; offline only, not installed, native moving linkage/activation still unverified. Collision ownership contract:14-byte target/flags/data/BodyID; shared systems select the body's node index, never every body per attachment.

`.af`: second u16 at0x28 matches rig-bone counts in four families; frame rate/track mapping unresolved (research note/#32).

Codex #62: stored General pack outside staging, hashes/activation/rollback retained. Output verifier rejects omitted/changed/compressed resources, invalid name lengths and reader-mismatched identities; policy v2 requires uninstall of older records.52 focused/381 full OK (1 skipped), guard/diff/final QA PASS. #59 base4a29506 integrated. Grok #58 at74f0319 QA PASS; #69 has offset/NaN-control false PASS findings to fix. #65 merged. Two Opus max reviews done; main Claude effort acknowledgment pending. No live install changed.

## Coordination / housekeeping

Check #29-32 each session; publish concise evidence and blockers there. Keep this file <4KB. [History](handoff-archive/2026-10-07-codex-history.md).

Delete reviewed scratch/recordings; never commit recordings. Keep staging\multi. Inspect before cleaning Codex's staging\codex-resume-smoke and research\codex-reflect.
