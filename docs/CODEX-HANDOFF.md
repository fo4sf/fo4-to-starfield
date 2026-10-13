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

#34/#35 (main): degraded checkpoint retries and streamed archive SHA; immutable sources. #86 in #66 at85e342f: portable resource lookups,360 Windows tests/Linux CI/independent QA pass; report counts unchanged.

Reviewed #80/#81 -> #79 at29f3b83: tracked rig/clips and small bind rotations;814 tests/CI/QA pass. #83/#89 -> #78 at02cfa8e: verified BA2/recovery/order/exit protocol;887 tests/CI/QA pass. Parent runtime acceptance remains open.

#89: unfinished work returns4, complete/dry-run0. Preserve old batch_full:1109 pending after12h/old exit0; non-movable estimate15-18 active hours. Offline133-test plan retains16 cells/49 failures/2470f876 (~3-4h), not run. Adopt reviewed runner; re-plan movable tests.

Parents #66/#78/#79 remain open, not runtime accepted. Moving collision/cave/save need live tests. #84 replace/unlink races remain; one controller required.

Codex #91 prepares pinned exterior queues/regional candidates. Live October13: smoke7/7, baseline29/30 matching heights; six repeated roofs match, northeast+1.8939m remains flagged. Sources/installed identities verified; original stage/batch/save preserved. Final unscored jump was NOT suppressed: qstep omits the merge offset. All four entries' post-probes are excluded; boundary dialogue cannot measure map limits. Further launches held for Claude's reviewed fix/fresh pins. Codex owns the scoped controller until23:35:17Z; game closed. #93 adds read-only [evidence audit](testing/commonwealth-evidence.md); walking/connections remain open. [Public handoff](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6136825108).

## Coordination

GitHub #29-32 is the inbox/status source. [History](handoff-archive/2026-10-07-codex-history.md). Keep below4KB; link experiments. Preserve staging/multi. Live controls unchanged.
