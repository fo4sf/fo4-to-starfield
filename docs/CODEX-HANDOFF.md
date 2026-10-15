# Codex / Claude / Grok status

Owner: project owner. Goal: Red Rocket -> Sanctuary -> nearby interiors -> wider Commonwealth (#31). Keep interior failures as regressions.

## Acceptance

Walk Red Rocket-Sanctuary and its bridge/cell borders both ways; prove terrain remains loaded. Then enter source-linked interiors normally and return to the same exterior with correct position/facing, stairs and closed/open door collision. Cave triggers and Vault111 lift/sliding doors need explicit tests. Initial COC/ray hops are setup/loading evidence, not walking or door acceptance. Pin code, plan, plugin/archive hashes and persistent IDs; unreached/unreadable results are inconclusive. Preserve FO4 gameplay and native Starfield physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / locks

- Claude: collision/Havok, convert_static.py, pipeline.py, convert_batch.py, PluginSpike, terrain/actors, game scripts/staging/live control. No concurrent edits or other game input.
- Codex: deployment/recovery, identities/checkpoints/cache/output QA, Fo4Export/ReferenceLinks, animation/door bridge modules and tests, this status/archive. Shared sfnif.py changes need a scope claim; Codex owns exp_install compatibility and #89 exit protocol. Live controller claim: #32.
- Grok: acceptance oracle, route_eval.judge, terrain_evidence.py/tests. #69 still needs capture-provenance QA correction; identical XYZ may be independent stationary captures. No other game/control files without a new claim.

## Latest evidence / open work

Core64c (#76):648,358 staged refs/1,708 populated cells across6.4km; nearby probes cover510m only. Its audit corrects older300m-hop claims: <=2 cells/axis mostly landed, >=3 sometimes relocated/hung; supported hypothesis, not guarantee. Continuous travel remains unproven. N1c NPC moved; commanded/cross-cell paths remain open.

Open regressions: Fort Hagen shutter/frame collision and load-door prompt, Vault114 cinder-block step and movable physics. Cave/native playback need live proof; interior acceptance remains incomplete.

#117/PR120: Windows fingerprints deny writers/mappings/renames during hashing;14 focused/341 suite (3 skips), guard/CI pass. Independent QA caught a descriptor-ownership bug; fix/re-review pass. Sources stay immutable after return. [Limits](testing/archive-fingerprints.md).

Reviewed #80/#81 -> #79 at29f3b83: tracked rig/clips and small bind rotations;814 tests/CI/QA pass. #83/#89 -> #78 at02cfa8e: verified BA2/recovery/order/exit protocol;887 tests/CI/QA pass. Parent runtime acceptance remains open.

#89: unfinished work returns4, complete/dry-run0. Preserve old batch_full:1109 pending after12h/old exit0; non-movable estimate15-18 active hours. Offline133-test plan retains16 cells/49 failures/2470f876 (~3-4h), not run. Adopt reviewed runner; re-plan movable tests.

Parents #66/#78/#79 remain open, not runtime accepted. Moving collision/cave/save need live tests. #84 replace/unlink races remain; one controller required.

October13: smoke7/7, baseline29/30; six roofs match, northeast+1.8939m remains. #100/e27f6de repairs the final jump; fresh informational15/15, inputs/native captures verified. Four old jumps excluded from map-size claims; walking/connections open. Original campaigns/save preserved. Codex released control and paused its completed monitor; Claude owns live control. #94/#97 [evidence audit](testing/commonwealth-evidence.md). [Results](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6154661951).

## Coordination

GitHub #29-32 is the inbox/status source. [History](handoff-archive/2026-10-07-codex-history.md). Keep below4KB. Preserve staging/multi. #105: [verified private archives before cleanup](testing/progress-storage.md). Live controls unchanged.
