# Codex / Claude / Grok status

Owner: project owner. Goal: Red Rocket -> Sanctuary -> nearby interiors -> wider Commonwealth (#31). Keep interior failures as regressions.

## Acceptance

Walk Red Rocket-Sanctuary and its bridge/cell borders both ways; prove terrain remains loaded. Then enter source-linked interiors normally and return to the same exterior with correct position/facing, stairs and closed/open door collision. Cave triggers and Vault111 lift/sliding doors need explicit tests. Initial COC/ray hops are setup/loading evidence, not walking or door acceptance. Pin code, plan, plugin/archive hashes and persistent IDs; unreached/unreadable results are inconclusive. Preserve FO4 gameplay and native Starfield physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / locks

- Claude: collision/Havok, convert_static.py, pipeline.py, convert_batch.py, PluginSpike, terrain/actors, game scripts/staging/live control. No concurrent edits or other game input.
- Codex: deployment/recovery, identities/checkpoints/cache/output QA, Fo4Export/ReferenceLinks, animation/door bridge modules and tests, this status/archive. Shared sfnif.py changes need a scope claim; Codex owns exp_install compatibility and #89 exit protocol. Claude retains live controls.
- Grok: acceptance oracle, route_eval.judge, terrain_evidence.py/tests. #69 still needs capture-provenance QA correction; identical XYZ may be independent stationary captures. No other game/control files without a new claim.

## Latest evidence / open work

Core64c (#76):648,358 staged refs/1,708 populated cells across6.4km; nearby probes cover510m only. Its audit corrects older300m-hop claims: <=2 cells/axis mostly landed, >=3 sometimes relocated/hung; supported hypothesis, not guarantee. Continuous travel remains unproven. N1c NPC moved; commanded/cross-cell paths remain open.

Open regressions: Fort Hagen shutter/frame collision and load-door prompt, Vault114 cinder-block step and movable physics. Cave/native playback need live proof; interior acceptance remains incomplete.

#34/#35 (main): degraded checkpoint retries and streamed archive SHA; immutable sources. #86 in #66 at85e342f: portable resource lookups,360 Windows tests/Linux CI/independent QA pass; report counts unchanged.

Reviewed #81/#80 are merged into #79 at29f3b83: generated skeleton/Open/Close dependencies remain tracked and small authored bind rotations are preserved.814 Windows tests/Linux CI/independent cache/matrix QA pass. Reviewed #83 is merged into #78 at75598ed: verified BA2 packing, recovery, --needs/order/plugin-only support, and install/order/uninstall guards for interrupted main recovery.883 Windows tests/Linux CI/independent QA pass. Tested child trees match integrations.

#89 budget-resume fix is merged into #78 at02cfa8e: paused work returns4, completed/dry-run returns0;887 Windows tests/Linux CI/independent QA pass. Old batch_full hit12h and exited0 with1109 left; its chain ended. Non-movable work estimates15-18 active hours plus waits. Offline133-test plan retains16 cells/49 failures/old2470f876 pin (~3-4h), independently checked, not run. Adopt runner before resume; preserve full batch; re-plan movable tests.

Parents #66/#78/#79 remain open, not runtime accepted. Moving collision/cave/save need live tests. #84 replace/unlink races remain; one controller required.

Codex #91 prepares pinned smoke/baseline/informational exterior queues and regional coverage candidates. Final unjudged beyond jumps are suppressed; SHA checks guard input/queue drift. [Campaign/run gates](testing/commonwealth-campaign.md). No live scheduling/install/input; walking/connected interiors/distant arrivals remain separate gates.

## Coordination

GitHub #29-32 is the inbox/status source. [History](handoff-archive/2026-10-07-codex-history.md). Keep below4KB; link experiments. Preserve staging/multi. Live controls unchanged.
