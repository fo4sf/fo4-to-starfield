# Reuse and phase decisions for Claude and the owner

Codex, 25 October 2026. **Discussion brief, not an architecture decision, optimization result or implementation assignment.** Requested by the owner for Claude's return. Related: [travel/risk research](travel-and-runtime-risks-oct25.md), [Claude's combined core](combined-core.md), [engine feasibility](combined-core-notes/engine-feasibility.md), and the existing [Python prototype](combined-core-notes/prototype/README.md).

## What the owner wants decided

Evaluate processes and independently useful components from other engines and game reimplementations that could improve this project without replacing Starfield or dismantling existing work. Rust is a candidate language, not the requested outcome. Borrowing a design and implementing it in the existing language is a valid result. No particular remake has been identified, so there is no audited donor project or selected dependency yet.

Staying on Starfield is a firm owner constraint. This brief makes no independent legal claim about what Bethesda permits. Reuse must separately consider the selected project's license, provenance and dependencies before code is incorporated.

The owner and Claude make the final decisions together. Claude should bring a recommendation, alternatives, evidence and phase consequences; do not turn this note into an automatic rewrite or library adoption.

## Current scope to preserve

- Boston/Commonwealth first, then additional Fallout regions after working mechanics. Preserve baseline geography/missions unless the selected mode changes them. Warfare and Survival choices remain as recorded in the travel note.
- Modest outskirts expansion and limited generation. Use corridor transitions or map-selected eligible destinations within a distance cap; longer travel needs vertibirds or other transport. Settlement-based vertibird range and distance-priced hired travel are desired; numerical rules remain undecided.
- Generate an intermediate area once and preserve it. Approximate real-world layout plus Fallout styling can support custom settlements, such as the owner's Thompson Falls example. This is not exact building reconstruction or a continent-generation commitment. Generation timing and map-data source remain open.
- Continuous walking across all regions is **out of the current delivery scope**. Only consider an optional build/test after all planned locations are added. The concern includes NPC behavior and simulation at scale, not just traversable ground. Whether a particular behavior would require engine source access remains unproved.
- Keep the coupled overall framework together. Independently useful support modules may be considered separately, including living-world, UI or powered-suit support; neither dependency-free operation nor standalone release is required now.

## Compare these options before adding a language

| Option | Potential benefit to investigate | Cost or limitation to establish |
|---|---|---|
| Keep the current implementation; borrow patterns only | Least disruption; improve data layout, tick scheduling, caching or test structure where measurements justify it | Whether the actual bottleneck remains after focused changes |
| Extend existing Python prototype as a reference model; use existing native stack for proven runtime needs | Preserve current rules/tests and reduce extra toolchains | Native implementation effort; equivalence and engine integration still required |
| Reuse a small Rust library behind a narrow adapter | Candidate efficient entity storage/scheduling or reusable simulation component | Extra build/distribution/debugging burden, C-compatible boundary, threading and save integration |
| Run a separate simulation process | Isolation and independent testing are possible benefits | Process lifecycle, synchronization, crash recovery and save association; not inherently simpler or faster |

No option is selected. An entity-component system (ECS) organizes data and updates; it is not a ready-made NPC brain, A-life implementation or engine-access workaround. Do not add another simulator alongside the existing one without a clear replacement/ownership plan.

### Concrete references, not promised capabilities

- [Bevy ECS](https://docs.rs/bevy_ecs/latest/bevy_ecs/) explicitly supports use as a standalone library without adopting the Bevy engine. It is worth inspecting for entity storage and scheduling.
- [hecs](https://docs.rs/hecs/latest/hecs/) is a smaller ECS library that leaves application organization to its caller. Compare dependency and scheduling needs rather than assuming either is best.
- [Rust's interoperability guide](https://doc.rust-lang.org/nomicon/ffi.html) explains C-compatible boundaries and their safety requirements. A Rust module could communicate through a native adapter, but this does not supply Starfield hooks or make arbitrary game calls thread-safe.

These official references were checked on 25 October. Pin versions if a later experiment selects them. Generation, behavior rules, persistence and game adapters are separate responsibilities; none is supplied merely by choosing ECS or Rust.

## What Claude should analyze first

1. **Inventory existing work.** Identify current prototype, schemas, seeds, tests, runtime adapters and ownership by observed commit/file. Separate implemented behavior from planning. Keep the offline build orchestrator separate from game-runtime simulation. Do not replace the prototype based on generic benchmark claims.
2. **Find the actual bottleneck or missing capability.** Distinguish simulation computation, engine API access, navigation, actor residency, serialization and content production. A faster abstract simulation cannot fix an unavailable engine hook or missing navmesh.
3. **Define a narrow boundary on paper.** Stable entity IDs, game-time ticks, ordered input events, output intents and authoritative state ownership. Define which thread can apply engine actions, how spawn/despawn acknowledgements work, and how retries avoid duplicates. Specify determinism explicitly: ECS, parallel execution and a random seed alone do not guarantee identical replay.
4. **Resolve persistence risks before increasing scope.** Match simulation state to character/save generation/content set; define backward-load, overwritten quicksave, interrupted save and missing-state behavior. Save messages are not an atomic external-state transaction. Engine actors and external entities must not independently become competing authorities.
5. **Specify one-time generation.** Record area ID, seed, generator/content versions, generated result and player changes. A seed alone may produce a different layout after an update. Keep a frozen result or an explicit versioned regeneration/migration policy; do not reroll a settlement on revisit.
6. **Estimate adoption cost.** Include Windows/runtime compatibility, dependency maintenance, debugging, packaging, save migration and loss of test coverage. Preserve a fallback to the existing implementation. No unmeasured speedup claim.

## Candidate phase adjustment for discussion

These are proposed gates to map into the existing phase plan, not replacement phase numbers.

| Gate | Result to bring to the owner | Effect on later work |
|---|---|---|
| A: bounded architecture review | Existing-work inventory; missing capabilities versus performance issues; recommended option and alternatives | Decide whether any implementation experiment is worthwhile |
| B: contracts and baseline | Save/entity/version contracts plus a small reproducible workload using existing prototype | Establish compatible foundations before more content depends on them |
| C: one comparative experiment, only if approved | Same inputs/rules/outputs against baseline, runtime/memory/tick latency and bridge overhead; failures retained | Adopt only if benefit meets agreed criteria and correctness is preserved; otherwise keep baseline |
| D: smallest native integration, separately authorized | One bounded encounter and save/leave/return case; authoritative IDs and no duplicate actors/state | Prove the adapter before larger populations or multiple regions |
| E: regional expansion | Persistent generated area, bounded travel and settlement changes survive revisits/reloads | Reuse established contracts for additional locations |

Finish current delivery/acceptance gates first unless owner and Claude explicitly reprioritize them. Do not block completed conversion work on a hypothetical Rust optimization. UI and powered-suit support may need their own capability probes; do not make them depend on an ECS choice unnecessarily. Full-world walking stays outside these gates until the owner's later prerequisite is met.

### Evidence for a comparative experiment

Use a small synthetic workload derived from the existing prototype: factions, places, squads, supplies and reproducible events. Agree representative workload sizes and a tick budget before testing. Compare identical scenarios, output hashes/invariants, memory and timing under the same conditions. Cover save/reload/backward load, duplicate events and interrupted updates. Report bridge overhead separately; a fast standalone loop is not proof of an improved Starfield session. Do not run a broad benchmark suite or native test merely because this brief lists one.

## Requested response when Claude returns

**Claude on the Windows PC:** read the workspace ENVIRONMENT-HANDOFF and live checkpoint first; use your actual shell/tools and an owned checkout. Record branch/commit and current phase evidence. This request authorizes analysis and discussion, not a game test, deployment, merge, source rewrite or another agent launch.

**Claude-cloud, if the owner assigns the analysis there:** use the repository documents and observed GitHub heads. Do not assume access to the PC, local checkpoints, private native evidence or Windows tools. Identify missing evidence and ask for an authorized handoff rather than inventing observations.

Return one short decision table: **keep / adapt / investigate / defer**, with evidence and exact affected components. Include one recommended path, a fallback, proposed changes to existing phase dependencies, and what remains unknown. Ask the owner to choose the desired simulation scale, acceptable integration/maintenance cost and which small experiment (if any) to authorize. Do not reopen settled engine, travel, mode or one-time-generation choices.

After discussion, record accepted decisions in the normal architecture decision log and amend the phase plan with owner approval. Until then, this remains a proposal. Codex's scheduled follow-up stays paused; no dormant agent is awakened by publication of this brief.
