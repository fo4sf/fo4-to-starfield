# Next-phase preparation — 25 October 2026

Codex, requested by the owner. Documentation and review preparation only; no game, deployment, asset cleanup or main merge. Snapshot: main `5fa5c205`. Refresh linked heads before acting. Claude retains integration and game control.

## Start here

- [#545](https://github.com/fo4sf/fo4-to-starfield/pull/545), `a2756e19`, records the owner's **phase 0 is done** decision and the first-load border fix. It remains an open ledger PR at this snapshot. Preserve its accepted gates; missing source reviews on other proposals do not reopen phase 0.
- Next concrete owner priorities recorded there: map icons/FO4 locations on a Pip-Boy-style map, and adding the owner's newer Steam FO4 build to the launcher's compatibility checks. Detect and pin the actual build before changing its allowlist; do not guess the version.
- The existing [framework](README.md), [combined-core design](combined-core.md) and [prototype](combined-core-notes/prototype/README.md) already cover broad world simulation. Extend that work instead of creating another core.
- GitHub reports this repository public and GitHub Pages disabled. These are repository documents, not a deployed Pages site. The separate lore lookup page is not deployed or updated by this change.

## Reduce the review queue before adding helpers

The owner clarified that cleanup includes branches and commits. The [repository housekeeping proposal](../../maintenance/repository-cleanup-oct25.md) lists 168 exact merged-branch candidates and six optional local refs, with protected exclusions and approval steps. It preserves commit history and awaits independent review plus owner approval; no deletion has happened.

These are overlapping **candidates for consolidation**, not claims that every implementation is equivalent. Preserve branches, tests and review history. Have the author identify unique behavior, then review one combined change; do not merge competing implementations independently.

| Family | Existing work | Next action |
|---|---|---|
| BA2 planning/census | #370, #372–374, #387–389, #480, #540–541, #546 | Start with [#480's family audit](https://github.com/fo4sf/fo4-to-starfield/pull/480); reconcile newer variants against it. Do not create another summary API. |
| Version/status display | #508–511, #516, #527–529, #550 | One CLI/metadata contract; keep help and dependency diagnostics usable without optional packages. |
| Door-leaf floor evidence | #479, #532–534, #538; [#458](https://github.com/fo4sf/fo4-to-starfield/issues/458) | Preserve actual-converter regression and measured table. Avoid duplicate helper-only tests or claims that an offline clamp test proves a crash cause. |
| NIF/BGSM diagnostics | [#547](https://github.com/fo4sf/fo4-to-starfield/pull/547), [#549](https://github.com/fo4sf/fo4-to-starfield/pull/549) | Scoped reviews clear at `b3cfbf64` / `73ad93c4`; keep all sibling command registrations when integrating. No strict format/native acceptance implied. |
| DDS diagnostic | [#548](https://github.com/fo4sf/fo4-to-starfield/pull/548) | Original `c5f99966` held for mandatory NumPy import breaking help/status/validate. Correction `b63f7e30` needs the original subprocess replay and current CI; do not carry the old verdict forward blindly. |
| Paired staging / audits | [#410](https://github.com/fo4sf/fo4-to-starfield/pull/410), [#482](https://github.com/fo4sf/fo4-to-starfield/pull/482), [#413](https://github.com/fo4sf/fo4-to-starfield/pull/413) | Independent QA still pending at `71442c46`, `c87874b4`, `d458a035`. Author tests are not peer review. |

## Grok's lore inbox

Reviewed all 170 submitted `gwe` records in [#544](https://github.com/fo4sf/fo4-to-starfield/pull/544) at `92186e19`, against the read-only source batch and its documented schema/policy. This is intake, consistency and content review, **not another primary-source verification of 170 claims**. The lore thread remains the store writer; this PR is explicitly **not for merge into main**.

- All 170 IDs retained; no entries dropped or claim/source/ruling text changed. Only `check`, 19 `pos` values and their 19 notes differ.
- 151 checked, 19 corrected; all 170 remain **as-reported**, not verified-source. All 33 tier-2 entries have rulings; quotes meet the store's 300-character bound. The supplied validator reports zero problems.
- All 19 added XY positions exactly match the cited FO4 map-marker FormIDs. That verifies source-marker copying, not Starfield positions, geographic projection, zone extents or valid travel arrival.
- Before fold-in, resolve or explicitly carry these flags: `GW-0058` remains tier 3 with `source_kind=cut`, a legacy mismatch with the owner's tier-2/hold rule; `GW-0145` lists weather percentages totalling 103%, so it cannot be consumed as an exclusive probability table without source-context clarification. Do not silently normalize it or rewrite the underlying lore claim.
- `GW-0031/0032` use Lexington/Malden town markers for guide-zone descriptions. Keep them identifiable as representative anchors, not exact boundaries or centres of those zones.
- The PR body still describes the initial partial second read; the committed notes describe all 170 complete. Reconcile the body without erasing the earlier history. Keep the rejected `GW-0081` date conflict rejected.

Preserve game, worldspace and era on every use: FO76's earlier Appalachia and FO4's 2287 Commonwealth are not simultaneous snapshots by default. Adopted guide/developer material remains grey area. Generated settlements and simulation outcomes belong in a separate design/world-state layer, never silently in the canon store.

## Owner ideas: smallest useful next steps

| Idea | First bounded task and acceptance |
|---|---|
| Map/Pip-Boy locations | Reuse source IDs and the marker export; compare source, converted reference and first-load UI visibility/labels separately. Four known locations must appear and resolve consistently before scaling the map. A map skin alone is not evidence of fixing absent references. |
| A living world driven by rules | Extend the existing game-neutral prototype with deterministic seeds, time steps, faction relations and small encounter budgets. Same inputs must replay identically; saving/reloading must retain state. No native AI implementation is authorized by this note. |
| Creature interaction tests | Plan a controlled encounter matrix: hostile, neutral, allied, frightened and provoked pairs. Pin actor records, factions, AI packages, scenario and observation window. Compare the appropriate original game's behavior; forcing actors together must not force the expected hostility. Test combat, flee and ignore outcomes separately from pathfinding. |
| Minimal loading across the Commonwealth | Keep streaming research separate from border/teleport fixes. Measure a fixed cross-cell route, frame times, memory and save/reload continuity before promising seamless travel. A separate launcher/executable wrapper alone does not change engine streaming limits. |

## Reuse tools before building more

Primary project/author pages checked 25 October; advertised capabilities are not tested compatibility with our build. Nothing is installed or downloaded here.

| Tool/mod | Recommendation and boundary |
|---|---|
| [SFSE](https://sfse.silverlock.org/) and existing FO4SF plugins | Keep the existing pinned stack. Upstream currently lists 0.2.21 for Starfield 1.16.244; runtime matching matters. No automatic update during a controlled test. |
| [Spriggit](https://mutagen-modding.github.io/Spriggit/spriggit-file/) | Candidate for private, version-pinned plugin record diffs; Starfield known-master metadata is supported. Use synthetic/public-safe examples in Git, not extracted game records. |
| [PresentMon](https://github.com/GameTechDev/PresentMon) | Reuse for later route/frame-time measurements instead of inventing a profiler. Keep runs pinned and compare the same route/settings. |
| [Bethesda Multitool](https://github.com/slfx77/bethesda-multitool/blob/main/README.md) | Advertises a .NET 10 worldspace viewer and BTD inspection. Keep the existing A6 deferral until a full-map offline visual check is actually needed; capability listings do not validate our converted output. |
| [FallUI Map](https://www.nexusmods.com/fallout4/mods/49920) / [StarUI Inventory](https://www.nexusmods.com/starfield/mods/773) | UI references to investigate, not selected dependencies: FallUI Map targets FO4 and StarUI Inventory targets Starfield inventory. Neither page establishes a compatible Commonwealth map fix. Check current compatibility and reuse permissions before adopting code or assets. |

Likely project-specific work is a source-ID-to-map adapter, a lore-aware encounter fixture format, and a small bridge between the existing simulation and native actors. Reuse current marker, runner, evidence and persistence machinery. No new archive parser, profiler or competing CLI is needed merely to start the phase.
