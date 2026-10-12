# Codex / Claude / Grok status

Owner: project owner. Priority: connected Red Rocket -> Sanctuary -> nearby interiors -> wider Commonwealth ([owner direction in #31](https://github.com/fo4sf/fo4-to-starfield/issues/31#issuecomment-6117671801)). Keep existing interior failures as regressions. Actor milestone planning remains available; the connected region is the next shipping goal.

## Acceptance

Walk Red Rocket-Sanctuary and its bridge/cell borders both ways; prove terrain remains loaded. Then enter source-linked interiors normally and return to the same exterior with correct position/facing, stairs and closed/open door collision. Cave triggers and Vault111 lift/sliding doors need explicit tests. Initial COC/ray hops are setup/loading evidence, not walking or door acceptance. Pin code, plan, plugin/archive hashes and persistent IDs; unreached/unreadable results are inconclusive. Preserve FO4 gameplay and native Starfield physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / locks

- Claude: collision/Havok, convert_static.py, pipeline.py, convert_batch.py, PluginSpike, terrain/actors, game scripts/staging/live control. No concurrent edits or game input from others.
- Codex: deployment/recovery, identities/checkpoints/cache/output QA, Fo4Export/ReferenceLinks, animation/door bridge modules and tests, this status/archive. Shared sfnif.py changes need an exact scope claim. Codex owns exp_install.py compatibility with #78; Claude retains cycle/qstep and all live tests.
- Grok: acceptance oracle, route_eval.judge, terrain_evidence.py/tests. #69 still needs capture-provenance QA correction; identical XYZ may be independent stationary captures. No other game/control files without a new claim.

## Latest evidence / open work

Claude reports core64b NW short hops through Sanctuary/Vault111 to2km with matching terrain heights (#32, 6118693845). Earlier large-jump Boundary/seam conclusions need hop reruns; full continuous traversal and all directions remain open. Red Rocket objects/ground align in exp2c/exp2d. N1c NPC moved with156 converted NAVM records; N0/commanded arrival and cross-cell navigation remain unproven (#32, 6121240178).

Claude's supervised_1011:10 PASS/5 FAIL/2 inconclusive. Open: multi-part shutter motion, load-door activation, Vault114 cinder-block step and movable item. #78 cave entry/return is staged, not runtime-accepted. #79 multi-part rigs/clips/body fix is offline; native playback/moving-body linkage needs in-game proof. Older eight-interior reports are not complete acceptance. Do not combine different builds into one result.

Codex #34/#35 merged: degraded checkpoints retry; archive sources use streamed SHA; keep them immutable during conversion. #62 recovery/packing is reviewed (399 tests + hosted CI), awaiting integration. Its compatibility follow-up on #78 brings --needs/order and plugin-only --pack into the verified installer, tracks every selected plugin, refuses inactive masters/cycles/incomplete installs, and guards Plugins.txt rewrites. 872 tests pass (37 skips); independent QA pending. No live install changed.

Codex #80 tracks generated skeleton/Open/Close.af/.afx despite omitted files lists/rig tags (7 focused/808 full;28 skips). #81 preserves small authored bind rotations (5 focused/813 full;28 skips + pose-matrix checks). Both independently reviewed; hosted CI blocked by #66's existing Linux game-path lookup. Four-lookup patch prepared for Claude; terrain file untouched. Native playback/collision still need in-game proof.

## Coordination

GitHub #29-32 is the inbox/status source. [Actor proposal](ACTOR-MILESTONE.md); [older history](handoff-archive/2026-10-07-codex-history.md). Keep this file below4KB; link experiments instead of copying transcripts. Preserve staging/multi. No automation/local-team or live-control changes by Codex this run.
