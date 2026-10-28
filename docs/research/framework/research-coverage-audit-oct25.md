# Research coverage audit: what is known and what is still missing

Codex, owner-requested follow-up, 25 October 2026 Mountain / 26 October UTC. **Coverage and provenance audit, not a complete primary-source verification of Fallout lore or a whole-repository code review.** Existing implementation, native evidence and owner decisions retain their own acceptance gates.

## Verdict

There is substantial research breadth, but it is not defensible to say all Fallout lore or all project requirements have been researched and verified. The framework has a wide question inventory and useful precedents. Much of it remains a source summary, hypothesis or proposed experiment. The lore ledger explicitly records hundreds of partial and unread sources. Grok's submitted task was a second read of one geographical batch, not an exhaustive lore survey.

Codex's earlier review of all 170 submitted entries was an intake/consistency review, including marker parity. It expressly did not reread all primary sources. Do not shorten that result to “all lore reviewed.” Similarly, finding an API or compiling a fixture does not close a gameplay requirement. This audit does not infer how long another agent worked, accuse it of fabrication, or certify unobserved reading.

## What was actually inspected

- Repository main `5fa5c20575519f87e75f497bdf1507e7a7947e97`; owned research draft #553 at `37691a9e147015dd62c96e549ce184d28687cbd8` before this addition. Indexed 18 top-level framework Markdown documents and 65 including supporting notes. Read the framework/dependency indexes and selected relevant summaries, uncertainty tables and behavior/persistence sections. These counts describe files, not completed research.
- Grok's [#544](https://github.com/fo4sf/fo4-to-starfield/pull/544) at `92186e198da2919ffaad16dcbb5a023a16b62e31`: full submitted 170-entry batch, second-read notes and prior scoped review. PR body still describes an earlier partial slice; notes describe the completed batch.
- Read-only local lore mirror: source ledger, queue, schema/readme, handoff, the `gwe` batch and relevant query code. The mirror contains **only one entry batch**. The handoff reports 3,844 total entries; those other entry files are not present here, so that total and their primary-source accuracy were not independently verified.
- Three fresh wiki page opens returned HTTP 403. No factual verification credit is assigned to those attempts. Existing ledger revisions and preserved records, not a claim of fresh page reading, support the coverage findings below.
- No agents awakened, store edited, game accessed, source implementation changed or current native tests rerun. Private evidence remains outside Git.

## Lore findings supported by the available evidence

### 1. The ledger itself establishes unfinished coverage

The 24 October mirror has **1,176 unique source rows: 206 full, 371 partial, 599 todo**. The separate queue has the same 599 entries. These are statuses in a selected source inventory, not a percentage of the Fallout universe. The ledger consists of 1,174 fallout.wiki URLs and two archived Fandom URLs; it is primarily a discovery/extraction ledger. A wiki can contain transcribed primary material, but being listed there does not prove the original game record was inspected.

The handoff reports 2,438 entries second-read and 1,406 single-read. Its eight enumerated pending batch counts sum to 1,322, an 84-entry discrepancy. Reconcile those counts against the authoritative store before reporting progress. This is not evidence that 84 entries were deleted: the handoff may have omitted a batch or mixed snapshots. Its tier totals also need an explicitly dated recount after the documented policy migration rather than reusing historical totals.

### 2. Grok's 170-entry batch is mainly geography, not behavior coverage

The submitted batch contains 99 places, 38 features, 23 events, five drivers, four policies and one culture entry. It contains no entries whose `kind` is creature or faction. Every entry remains **as-reported**; 151 have `check=checked`, and 19 have `check=corrected` for added marker positions. These two fields answer different questions.

Its sources collectively reference 101 unique URLs. Ninety-four entries have some quoted text; none has an eight-digit hexadecimal record ID in its source `locator`. That narrow mechanical check is not a universal provenance test: some source kinds do not use record IDs, and a valid locator can take another form. Nevertheless, neither a quotation nor a game-themed source title establishes that the primary text was checked. Grok explicitly says the primary in-game text was not opened in CK.

The notes enumerate 17 raw wiki pages opened for the second read. They do not provide a per-entry primary-record verification log covering the 101 cited URLs. Do not infer that every referenced page or every underlying quest/dialogue branch was reread. Coordinates already checked against a named FO4 marker remain coordinate evidence, not proof of a guide zone's bounds or native Starfield arrival.

### 3. “Full” currently has inconsistent boundaries

The schema defines `full` as every lore claim on a page represented. Some full rows explicitly defer material: the Enclave (Fallout 76) row says mutation-serum/X-01 research lines were not entered separately; the Skyline Valley region row excludes named locations and topics for another batch. These may be deliberate topic splits rather than bad facts, but consumers need explicit exclusion and cross-reference information.

A source read once does not mean every subject in it is covered forever. Preserve completed sections, page revisions and excluded/transcluded material; revisit only missing sections or a changed claim. A targeted primary-source check is also different from repeating a broad wiki extraction. Never use a “read once” efficiency rule to prevent correction, independent verification or examination of missing content.

### 4. Held material can appear accepted in the query presentation

In the submitted records, `GW-0014` and `GW-0058` have `status=adopted` but `ruling.decision=hold`. Calling the existing read-only `show_rows` formatter on these exact records prints “adopted” and omits the ruling. This was reproduced without building or modifying the store.

This is a **presentation/consumption risk**, not proof that a world generator has already used them. Before production consumers rely on query output, the lore owner should define effective eligibility from status, ruling, accuracy, canon tier, era and intended use, and display holds/rejections clearly. A `--tier 1` filter alone is not a primary-verification filter. Do not silently rewrite historical claims or resolve owner choices through code.

### 5. The source queue contains directly relevant gaps

Examples from the available ledger—not statements that no other source covers them:

- Brotherhood of Steel overview partial; FO3, FO4 and FO76 chapter pages todo. Chapter, era and mission differences matter to our behavior design.
- Institute and Railroad partial; Railroad HQ terminal entries todo. Their organizational constraints cannot be reduced to one universal aggression setting.
- Fallout 4 raider groups todo; raider overviews partial. Distinct gangs, intimidation, warnings and local relationships matter to neutral/disguise play.
- Ghoul partial; Anti-Ghoul Decree of 2282 todo. Ghoul identity affects settlement/faction reactions and is not just a visual option.
- Intelligent deathclaw material todo; Super Mutant partial. A broad species label is insufficient to prescribe every individual's behavior.
- NCR history holodisk and NCR–Legion War todo. Later regional plans need chapter/era/quest-outcome context rather than one timeless faction profile.

Videos can be valuable discovery and interpretation sources. Their length is not itself a completeness or accuracy measure. For a useful video, record creator, title, date, timestamp and precise claim; follow the cited game/terminal/dialogue evidence and preserve uncertainty when no primary support is available. Do not label a video's interpretation as game canon, or claim to have watched material from its title or summary.

## Project-wide coverage map

This maps existing work to the next missing evidence. “Unresolved” means the reviewed material does not close it; it does not erase valid source/native results elsewhere.

| Area | Existing useful research | What needs deeper work or reconciliation |
|---|---|---|
| Lore and canon | Separate tiers, accuracy labels, conflicts, rulings and source ledger | Authoritative full-store snapshot; section-level coverage; primary-source checks for behavior-critical claims; clear effective eligibility |
| Mode rules | Owner direction in [decision brief](claude-reuse-decision-brief-oct25.md) | Trace each settled rule to design, implementation and acceptance evidence; do not reopen settled preferences |
| Factions/reputation/disguise | [AI/faction questions](engine-mechanics-notes/companions-ai-factions-combat.md), [precedents](combined-core-notes/settlements-factions-precedents.md) | Chapter/era-specific doctrine; individual exceptions; warnings, proximity, crime, disguise discovery and faction reactions across modes |
| Creatures and encounters | Combat-style, race/animation and hostility questions already listed | Separate lore expectation from actual FO4 behavior and intended Starfield behavior; controlled interaction cases with context, not a single enemy/friend table |
| Actor residency and simulation | [Combined core](combined-core.md), prototype, event/behavior shortlist | Authority handoff when actors load/unload, duplicate events, interrupted actions, dead/missing actors, time jumps and scheduler budgets |
| Save/load and Warfare succession | Identity/recovery work and owner’s another-faction-member rule | Save association, backward loads, death transitions, new/existing replacement identity and transferred progression. External state must not silently advance an old save |
| Story coexistence | [People/story research](people-and-story.md), quest/alias questions | Exact protected roles/locations and conditions; temporary protection and release; interaction between territory capture, missing NPCs, radiant jobs and story quests |
| Settlement economy | Supply lines, growth and actor-budget precedents | Resource sources/sinks, feedback loops, faction collapse/recovery, player exploitation, capture consequences and loaded/offscreen consistency |
| Travel and generation | [Bounded travel note](travel-and-runtime-risks-oct25.md), [world notes](world-and-planet.md) | One-time area identity/version/content, persistent edits, landing validity, companions and regional simulation time. Full continuous walking stays deferred |
| UI, Pip-Boy, suits and player systems | [Tool workflow](modding-tool-workflows-oct25.md), engine mechanics and asset notes | Input focus, camera/equipment/animation transitions, accessibility/controller behavior and rollback. Menu/mesh support is not an end-to-end capability |
| Assets/navigation/animation | [Asset pipeline](asset-pipeline.md), [interiors](interiors.md), [doors](door-animations.md) | Per-asset-class coverage and unsupported cases; representative animated/skinned/physics/navmesh evidence rather than generalizing a static-asset success |
| Tool/runtime compatibility | [Tooling](tooling-and-testing.md), [versions](versions-and-maintenance.md) | Exact supported combinations and lifecycle tests. Reconcile obsolete summaries with current code and pinned findings; Caprica guard correction is one example |
| Performance and build cost | Existing timing/recovery framework and budget questions | Representative build peak disk/RAM, frame/tick latency, population and save-growth measurements. Source claims and standalone benchmarks are not project measurements |
| Multi-game and FO76 | [Multi-game research](multi-game-future.md), owner single-player/ghoul direction | Era/ending compatibility, selected FO76 mechanics, original-script and content mappings; do not extrapolate FO4 coverage to every game/DLC/update |
| Distribution/maintenance | [Release research](release-community-legal.md), launcher and reusable-support policy | Component-specific packaging/version/license decisions; keep community precedent distinct from permission and technical feasibility |

The reviewed AI tables already propose useful tests for furniture use, stairs, alias/package precedence, schedules, faction hostility and detection. The problem is not that every area was ignored. The missing step is closing each relevant requirement with the right evidence and propagating that result to summaries. Large question counts, a source link or a “verified as reported” label are not closure.

Two documentation examples need reconciliation: the asset summary calls static assets “solved,” which is broader than class/build-specific proof; the combined-core adapter paragraph still mentions an SFSE co-save although the same document records its absence. These are scope/staleness findings, not new engine-limit claims. Preserve history and link the current answer instead of multiplying contradictory summaries.

## Recommended next research packets, in order

1. **Reconcile coverage and consumers.** Lore owner supplies a dated asset-free export/manifest of the authoritative store and section ledger. Recount batches, reconcile the 84-entry handoff discrepancy and full-row exclusions, and specify effective eligibility/display behavior. Preserve record IDs and original evidence. Deliverable: a trustworthy coverage statement, not another claim that all lore is finished.
2. **Boston faction behavior dossiers.** Start with the factions actually present in the first playable area; include specific Brotherhood chapter, Institute, Railroad, Minutemen and distinct hostile/neutral groups as applicable. For each required behavior: primary locator, time/quest conditions, exceptions, vanilla evidence, proposed mode policy and owner choice. A faction’s ideology does not determine every member’s reaction.
3. **Creature interaction specification.** Inventory available creatures first as the owner requested. Choose a small representative set and cover neutral proximity, territory warning, predation, ally assistance, flight, injury, protected young, disguise and player interference only where relevant. Mark unsupported ecological assumptions as design choices. Later native tests require their own release.
4. **Persistence and story-protection contract.** Review save identity/backward load, actor residency and Warfare succession together with protected quests/NPCs. Distinguish lore deaths, scripted quest conditions and sandbox simulation outcomes. This is more urgent than increasing abstract population size.
5. **One vertical capability investigation.** Choose one settlement-to-encounter-to-travel-and-return scenario. Identify available API/record support, remaining hook and measurable resource budget. Use existing tests and synthetic fixtures; avoid another isolated helper that never reaches the real caller.
6. **Expand regional/lore coverage by dependency.** After Boston-critical claims, deepen relevant DLC, DC and other regional packets, including dates and contradictory outcomes. FO76 and ghoul rules follow the owner’s selected single-player experience. Weather probability detail remains low priority. Full walking remains a later optional experiment.

For any packet, the completion record should name: question and scope; exact source/version/section or record; claim and conditions; omitted material; independent verification method; result and counterexample; affected owner requirement; remaining uncertainty; implementation/test evidence if applicable. Separate **catalogued**, **read**, **primary-checked**, **design-decided**, **implemented** and **native-tested** states. An unanswered question is useful research output when accurately labelled.

The owner has authorized this audit, not a new implementation campaign. Claude and the owner decide phase changes on return. Do not wake Grok, resume scheduled work, merge research into implementation, or treat queued reading as already performed. The next useful work is targeted evidence closure, with a visible record of what remains unknown.
