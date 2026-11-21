# Documentation index

Where to find things, current information first. The project's front page is [the repository README](../README.md).

## Current

- [ROADMAP.md](ROADMAP.md): the current stage, the order of work and the dated ledgers behind them. Start at the top.
- [JOURNAL.md](JOURNAL.md): the dated evidence log, newest last (append-only). It is thin after 1 November: later results
  are recorded in the per-area pages below and in the roadmap.
- [owner/playtest-issues.md](owner/playtest-issues.md): what the owner sees in play tests.
- [known-issues.md](known-issues.md): active in-game crashes, stalls, and safe defaults enforced before merging into `main`.
- [merge-plan-20261120.md](merge-plan-20261120.md): open-PR inventory (Classes A–D), file-overlap flags, and ordered merge train.
- [core/port-requirements.md](core/port-requirements.md): Track 2 multi-title core design (`FO3`, `FNV`, `FO1 & FO2`), New Vegas console-cut restorations, Pip-Boy style hooks, and `W7` Survival/Hardcore Open Mode fallback contract.
- [testing/quest-test-plan.md](testing/quest-test-plan.md): four-tier quest testing strategy (offline fragility checker, Tier 2 console break-it batches, Tier 3 known-bug regressions, Tier 4 owner play).
- [testing/reachability-fixes.md](testing/reachability-fixes.md): multi-route fixes for fragile/missable content (starting with New Vegas's Pimp-Boy 3 Billion).
- By area:
  - the map: [terrain/map-markers.md](terrain/map-markers.md), [terrain/border.md](terrain/border.md)
  - the first mission: [mission/when-freedom-calls.md](mission/when-freedom-calls.md)
  - the new game: [newgame/vault111-start.md](newgame/vault111-start.md)
  - the Pip-Boy & UI: [ui/pipboy-arm-visibility-study.md](ui/pipboy-arm-visibility-study.md), [ui/pipboy-map-s1-s4.md](ui/pipboy-map-s1-s4.md)
  - the gunplay study (`HOLD`): [design/gunplay-study.md](design/gunplay-study.md)
  - the multi-title quest/script census & known-bug ledgers: [research/all-games-quests-scripts.md](research/all-games-quests-scripts.md), [research/core-fit-by-title.md](research/core-fit-by-title.md), [quests/fo3-fnv-conversion-readiness.md](quests/fo3-fnv-conversion-readiness.md), [quests/known-bugs/README.md](quests/known-bugs/README.md)
  - the current Candidate 2e card (`Round 8` `X1`–`X3`): [testing/candidate-2e-card.md](testing/candidate-2e-card.md) (prior `Round 7` card: [testing/candidate-2d-card.md](testing/candidate-2d-card.md))
  - our own planet: [planet/planet-probe.md](planet/planet-probe.md)
  - the launcher: [ai/launcher-backbone.md](ai/launcher-backbone.md), [ai/launcher-recovery.md](ai/launcher-recovery.md)
  - the combined core (living world): [combined-core.md](combined-core.md), the in-game probes
    [spikes/combined-core-probes.md](spikes/combined-core-probes.md)
  - the agents' standing decisions: [ai/decisions.md](ai/decisions.md)

## Reference

- [SETUP.md](SETUP.md): pinned game and tool versions.
- [PLAN.md](PLAN.md): the method and its phases (written 6 to 10 October 2026).
- [FORMAT-GAP.md](FORMAT-GAP.md) and [measurements/](measurements/): measured format differences.
- [RISKS.md](RISKS.md) and [spikes/](spikes/): the early risks and the experiments that answered them.
- [combined-core-cpp-port.md](combined-core-cpp-port.md), [combined-core-gateways.md](combined-core-gateways.md): the
  combined core's C++ port plan and gateway data contract.
- [CELL-EXPORT.md](CELL-EXPORT.md), [REFERENCE-LINKS.md](REFERENCE-LINKS.md), [RESUMING-BUILDS.md](RESUMING-BUILDS.md),
  [INTERIOR-ACCEPTANCE.md](INTERIOR-ACCEPTANCE.md): tool and format manuals.
- [actors/](actors/), [terrain/](terrain/), [testing/](testing/), [questprobe/](questprobe/): per-area notes; older
  run records sit beside the current ones and carry their dates.
- [research/](research/): research notes per system (October to early November 2026); reference, not current status.
- [ai/for-ai-reviewers.md](ai/for-ai-reviewers.md): how to review the repository with an AI assistant.

## History

Kept as a record; do not use these as a task list.

- [history/](history/): status sections that once stood on the front page
  ([3 November 2026](history/readme-status-2026-11-03.md), [October 2026](history/readme-progress-2026-10.md))
  and superseded pre-bundle PC working cards ([core-candidate-pc-card.md](history/core-candidate-pc-card.md),
  [hold-group5-pc-card.md](history/hold-group5-pc-card.md), [vault111-exit-pc-card.md](history/vault111-exit-pc-card.md),
  [pipboy-stack-candidate.md](history/pipboy-stack-candidate.md)).
- [CODEX-HANDOFF.md](CODEX-HANDOFF.md): the agents' handoff of 3 November 2026 (its file-ownership rules still apply).
- [WORK-PACKAGES.md](WORK-PACKAGES.md), [ACTOR-MILESTONE.md](ACTOR-MILESTONE.md),
  [CHATGPT-BRIEF.md](CHATGPT-BRIEF.md), [REVIEWS.md](REVIEWS.md): plans and briefs from early October 2026.
- [PLAY-AND-TEST.md](PLAY-AND-TEST.md): a play guide, withdrawn by the owner on 19 October 2026.
- [slice/](slice/), [handoff-archive/](handoff-archive/): mid-October slice notes and an old agent handoff.
