# Connected travel and runtime risks

Codex, 25 October 2026. **Exploratory research, not an approved implementation plan or native acceptance.** Prepared at the owner's request before a work pause. Base: main `5fa5c20575519f87e75f497bdf1507e7a7947e97`. No game, staging, installation or asset inspection was performed for this note. It supplements Claude's research rather than replacing its decisions or claiming an independent peer review of the whole framework.

## Owner clarification after this research

The owner subsequently narrowed the current scope: modest outskirts expansion, limited one-time persistent generation, and corridor transitions or map-selected eligible landing areas within a distance cap. Longer travel requires vertibirds or other transport; settlement-based range and distance-priced hired transport are desired. Approximate map layout and Fallout styling may support custom settlements, not building-by-building real-world reconstruction. Generated areas persist rather than rerolling.

Continuous inter-region walking is **deferred**, only an optional build/test after all planned locations are added. The alternatives below remain research history, not equally active delivery options. The owner confirmed the Claude descriptions located here were the intended sources. Generation timing, exact ranges/costs and permitted destination rules remain undecided.

See the [decision brief for Claude and the owner](claude-reuse-decision-brief-oct25.md) for evaluating reusable implementation techniques while preserving Starfield and existing work. No Rust/library adoption, rewrite or phase change has been approved.

## Direction and evidence

The project is a GAMMA-style Fallout experience built on Starfield, initially Boston/Commonwealth, with more regions after its mechanics work. It is also an integrated framework others could adapt for an original world. The owner clarified on 25 October:

- Warfare chooses a faction and one of its starting bases at save creation; its missions and world activity emphasize survival and faction combat.
- Survival chooses story participation and faction or solo start. Story-off adds generated missions and progression opportunities. Neutrality is not immunity: aggressive groups, proximity, disguise and earned relationships need separate rules.
- Foundational settings are fixed per save; other settings may change during play. The exact boundary still needs design.
- Keep the Commonwealth area and original missions as the baseline unless the applicable setting changes them. Inspect existing creature behavior before proposing new AI.
- Cut content is considered per game/addition. Exact weather percentages are not a current requirement.
- Independently useful support mods may eventually ship separately, including living-world, Pip-Boy or power-armor support. The tightly coupled overall framework stays together. No dependency is selected or release authorized here.

**Earlier decisions located, not re-asked:** [combined core](combined-core.md) records settlements, factions and a connected wasteland as the pillars; [multi-game MG-14/15](multi-game-future.md#world-placement-and-travel) records one planet at real-relative positions and scripted travel, with ship-as-vertibird retained as a combined-mode candidate. [World and planet](world-and-planet.md#what-is-settled) records procedural world generation as later work, with a limited generated-horizon exception. Today's request explores how far walking can go; it does not silently replace those decisions with a continent-generation project.

Labels below: **recorded result** means project evidence linked here, not a new replay; **primary-source fact** means directly checked documentation/source; **proposal** and **unknown** are not promises. Older pages mix recommendations, historic tests and later corrections; use their latest dated correction, not a crossed-out claim.

## What “one world” can mean

These are separate requirements:

1. One character/save, consistent rules and consequences across every region.
2. Regions placed on the same logical planet, at sensible relative positions.
3. Routes the player must physically reach and use, without arbitrary map teleportation.
4. An uninterrupted walk across all intermediate terrain, with no region-loading transition.

The first three do not require the fourth. **Hardcore travel without map fast travel is a plausible design target; an uninterrupted Boston-to-DC walk is unproved.** A door, ferry, train or route transition can preserve a demanding journey if reaching it, access, time, supplies and consequences matter. It is still a transition and must not be described as seamless streaming.

| Route design | Player experience | Main unknown/cost | Research position |
|---|---|---|---|
| Detailed regions linked by transport gateways | Walk to a station, harbor or faction transport, then enter another region | Correct transfer of player/world state; transport availability and arrival | Closest to the prior approved direction; lowest relative technical uncertainty, not yet proven across our regions |
| Playable corridors between regions, with transitions | Travel through authored roads, tunnels, checkpoints or encounter stretches | New geography/content, route seams and companion/vehicle transfer | Candidate if the owner wants substantial on-foot inter-region travel; not an accepted scope expansion |
| Seamless local regions, explicit long-distance transport | Continuous traversal where measured safe, deliberate long-distance transition elsewhere | Local streaming envelope and a consistent travel service | Proposed baseline for comparison, not a decision |
| Continuous continent-scale terrain | Every kilometer is physically traversable | Physics/residency limits, precision, terrain/LOD/navmesh production, content density and save behavior | Highest-risk research track; do not advertise it or infer impossibility from distance alone |

Real-relative placement does not itself decide terrain scale or travel duration. For illustration only, a 600 km route at 5 km/h takes 120 hours of movement; a 20:1 spatial compression makes it 30 km and six hours at that speed. Those are arithmetic examples, not measured player speed or a Boston–DC route survey. Spatial scale, game-time rate and represented journey time need separate choices.

## The boundary lesson: several limits can look like one wall

[The border investigation](../../terrain/border.md) records why a one-run fix was misleading: early WRLD variants were overwritten later in the load order; controlled repeats did not establish SmallWorld/HNAM as reliable fixes. Door-script coordinates and visible post-transition behavior also disagreed while the boundary popup paused updates. The later world-aware SFSE setting switch has an owner-reported successful west/south walk and Vault 95 exit, plus a subsequent signal-flicker correction. That evidence must be retained; it is not proof of arbitrary-distance traversal or every reload/region combination.

The same document labels a roughly 6–7 km physics edge as **unresolved and unmeasured by the project**. The [Border Regions Unlock author](https://www.nexusmods.com/starfield/mods/14643) instead claims exploration beyond 10 km while acknowledging missing POIs and some objects. Neither establishes a universal safe radius. Avoid copying either number into an acceptance threshold.

Separate these failure classes in future measurements:

- **Policy fence:** popup or forced return despite otherwise usable ground.
- **Streaming readiness:** terrain visible while collision, actors, navigation or interactive objects are not ready.
- **Coordinate/frame error:** source-local, registered overlay and runtime-world coordinates disagree.
- **Physics/precision degradation:** jitter, falling, aiming or vehicle instability with increasing distance.
- **Resource pressure:** repeatable stalls, memory growth or missing content after long routes and returns.
- **Persistent-state error:** arrival succeeds, but a reload duplicates actors, loses cargo or restores the wrong faction state.

The existing [#286 preload investigation](https://github.com/fo4sf/fo4-to-starfield/issues/286#issuecomment-6229586870) found `PreloadExteriorCell` and `PreloadTargetArea` declarations in the installed SDK. This is a bounded experiment candidate, not proof of cross-world preloading, collision readiness or invisible transitions. Keep the preload window small until residency and unloading are measured. A separate launcher executable would not remove engine limits.

## A shared travel service before more routes

**Proposal:** gateways, trains, boats, permitted fast travel and any later corridor transition should call one travel service. Do not build separate ad hoc teleport scripts per DLC. Its steps would be:

1. Resolve the destination region/anchor from stable content identities; verify the installed content and arrival frame. Refuse missing or mismatched destinations before moving anything.
2. Check mode rules, access, faction restrictions, combat restrictions, equipment/capacity and journey cost. A story-off route must not depend exclusively on an original main-quest unlock.
3. Record a pending journey with its unique ID, source/destination, party, cargo/vehicle, world-state generation and intended costs. Define what cancellation and interruption mean.
4. Perform the transition using a proven engine path; wait for actual readiness. Handle companion identity, vehicle placement, arrival safety, regional atmosphere/border policy, quest/radio context and current map region.
5. Apply costs and elapsed simulation time exactly once, then mark completion. A crash/reload must resolve the recorded journey rather than silently create another vehicle or charge the fare twice. Do not claim a save plus external state file is an atomic transaction.

This is a design contract, not a new helper implementation. Reuse the project's persistent identity and recovery principles; do not confuse the offline build orchestrator in `src/fo4sf/core/` with the game-runtime simulation.

The [TTW guide's travel FAQ](https://thebestoftimes.moddinglinked.com/faq.html) describes its train connection and warns that console travel bypasses required quests/variables. That is a useful precedent for centralized arrival bookkeeping, not proof that TTW code or its engine behavior transfers to Starfield.

### Region types and hardcore access

- **Boston and another mainland region:** walk to an actual road/rail/transport gateway. Continuous intermediate terrain is a separate content/engine decision.
- **Far Harbor and other water-separated locations:** a boat/ferry can be legitimate required equipment, with access and journey costs. Open-water travel needs its own vehicle/water/streaming proof; do not promise it from a boat scene.
- **Nuka-World and later DLC:** preserve story-mode route requirements where appropriate, while providing a deliberate sandbox access rule. One setting should not accidentally strand a story-off character.
- **DC and subsequent regions:** retain the same character state and named home region; specify where dismissed companions and parked vehicles go.
- **Exceptional environments:** simulations, orbital areas and other non-overland spaces should remain distinct route types rather than being forced onto a walkable terrain map.

Hardcore mode needs a list of all travel entry points: world/surface/Pip-Boy maps, scanner shortcuts, ship/landing menus, quest teleports, recall, death/recovery and scripted gateways. Blocking a menu button is not sufficient. Whitelist intended transport and essential transitions. Paid or equipment-based travel must still work after story shutdown, faction hostility, poverty or vehicle loss; choose whether recovery means a rescue debt, a dangerous foot route or an explicit exceptional recovery action. Do not secretly grant unlimited free recall.

## Likely support work and its smallest useful proof

These are integration risks and research candidates, not an instruction to build twelve new frameworks.

| Area | Where we can get surprised | Reuse first / possible work | Small proof before expanding |
|---|---|---|---|
| World registration and arrival | A second overlay or DLC uses a different runtime offset, winning WRLD or location parent | Existing world/door/frame work; explicit destination metadata | Two regions, both directions, walk-in and reload; correct arrival and later movement |
| Long walking routes | Removing the fence leaves a streaming/physics edge | Existing border switch and #286 telemetry; bounded preload only if justified | Walk out/back across successive cells; record frame/world IDs, collision and state, not just screenshot position |
| Survival travel policy | Scanner/ship/quest shortcut bypasses the mode, or the player becomes stranded | Existing native controls where verified, with a shared policy adapter | Every entry point tested in each mode, including denied and recovery cases |
| Ground vehicles | Vanilla acquisition/spawn assumes ship infrastructure we may hide | Evaluate native vehicle lifecycle before new physics; possibly a transport support layer | Acquire/park/retrieve, save/load, change region with cargo and companion; no duplicates |
| Living-world persistence | Older save loads newer simulation state; filename collision or interrupted save loses territory | Existing deterministic prototype; save-bound state adapter | Two characters, same-named saves, backward load, overwritten quicksave and missing/corrupt state; no silent reset |
| Off-screen factions | Loading a region spawns a second copy of a squad; actor death never reaches simulation | Keep squads abstract off-screen and materialize near the player | Leave/return/save while a small encounter progresses; survivors and inventories conserved |
| Navigation and territory | Converted navmesh exists but patrols cannot cross seams/doors; missing location hierarchy | Current PACK/navmesh/location work | One caravan across several cells and an interior gateway, including a blocked route |
| Story versus Warfare | A capture kills a required NPC, removes an objective or leaves an alias unfilled | Story protection rules plus separately authored sandbox missions | One location tested with story on/off and multiple owners; terminal quest outcomes recover correctly |
| Reputation and disguise | One friendly faction hides another hostile membership; proximity instantly starts permanent combat | Relationship resolver feeding engine factions/packages | Small faction/creature matrix: neutral, disguised, discovered, trespassing, attacked, disengaged and reload |
| Pip-Boy and maps | A visible custom map lacks discovery, objectives, input, world coordinates or travel restrictions | Evaluate menu frameworks; build a data/input adapter if needed | Correct markers in two regions; keyboard/controller; map denied-travel behavior; safe close/resume |
| Power armor / future mechs | Playing an animation is mistaken for implementing a powered body with collision and persistent equipment | Inspect native mechanics and animation frameworks; support layer only for demonstrated missing capabilities | Enter/exit, interruption, camera/collision, inventory/energy, combat and save/reload in a tiny scene |
| Scale and maintenance | More plugins/assets increase patch conflicts, references, build size and memory; game update invalidates hooks | Existing identity/manifest tooling, pinned runtime compatibility, bounded diagnostics | One extra region at a time with build/load/save/performance comparisons; no arbitrary universal capacity claim |

## Important external checks and cautions

**Vehicles are available, but their lifecycle matters.** Bethesda's [vehicle support page](https://help.bethesda.net/app/answers/detail/a_id/61369/~/are-there-any-vehicles-in-starfield%3F) documents the REV-8/Moon Jumper as ship-installed modules that deploy near the ship on landing. Thus “hide the ship and add a vehicle” has an acquisition/spawn dependency to solve; this does not prove free-standing vehicles are impossible. Bethesda's [Free Lanes description](https://help.bethesda.net/app/answers/detail/a_id/74225/~/free-lanes---update---starfield) is about interplanetary space travel. It is not evidence of uninterrupted planetary-surface streaming or a ready-made atmospheric vertibird.

**A handcrafted planet is a useful precedent, not a continent-scale guarantee.** [Xbox's Shattered Space account](https://news.xbox.com/en-us/2024/08/22/starfield-shattered-space-release-date-preview/) describes a largely single-planet expansion with handcrafted areas. It does not publish a transferable maximum terrain size, navmesh budget or cross-region seam implementation.

**Save integration is an early architecture gate.** The currently checked [SFSE changelog](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt) records disabled preliminary serialization in 0.2.12; the current [PluginAPI header](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse/PluginAPI.h) exposes save/load messages but no serialization interface. A custom sidecar remains a proposal requiring explicit synchronization and recovery. A save filename alone is not a sufficient identity. Test character/profile ID, save generation, content-set identity and backwards loading. Lossy rebuilding from a small Papyrus state mirror is a degraded recovery choice to disclose, not proof of a faithful restoration. Claude's [engine-feasibility note](combined-core-notes/engine-feasibility.md) already identifies this issue; reuse that investigation.

**Native extensions require maintenance.** [SFSE's support page](https://sfse.silverlock.org/) currently lists 0.2.21 for Steam runtime 1.16.244 and excludes the Windows Store/Game Pass version. Its changelog records changes that invalidated existing plugins/Address Library assumptions. Use the maintained [CommonLibSF project](https://github.com/libxse/commonlibsf) as a candidate implementation resource, not a guarantee that a required hook exists. Keep unsupported-runtime refusal and recovery visible.

**Existing UI and animation tools are candidates, not solved mechanics.** [SFSE Menu Framework](https://raw.githubusercontent.com/QTR-Modding/SFSE-Menu-Framework/main/README.md) provides an ImGui menu/input layer and declares current runtime dependencies. It could help settings/debugging; it does not establish a working wrist-mounted Pip-Boy or map backend. [NAFSF's author page](https://www.nexusmods.com/starfield/mods/7360) says animation playback sits over the normal animation system and is not remembered across game sessions. The page's update history does not establish compatibility with our current runtime. Do not install it blindly or treat a successful clip as a complete power-armor/creature behavior implementation. Claude's [UI](engine-mechanics-notes/ui-pipboy-vats.md), [character](engine-mechanics-notes/character-systems.md) and [animation](engine-mechanics-notes/animation-audio-physics.md) notes contain the broader alternatives.

## Suggested next experiments, after the pause and controller release

1. **Freeze one known build and classify the world edge.** Reuse current border/route evidence. Choose one short terrain route, walk both ways, then extend it gradually. Record world/cell/position, movement, collision, frame times, memory, popup state and reload. Recheck after any recentering because it changes arrival transforms and persistent placement assumptions.
2. **Two small regions, one journey service.** A test gateway is enough; no full DC conversion required. Cross with one companion, a marked inventory item and one stateful object. Interrupt at each transition stage; load an earlier save; confirm no duplicates, double charges or lost state.
3. **Save-bound simulation before larger populations.** Reuse Claude's small deterministic simulation. Prove save association and backward restore with a tiny faction/settlement set before running hundreds of squads.
4. **Hardcore policy and transport lifecycle.** Disable ordinary map shortcuts while preserving the chosen route. Test no-money/hostile-base/vehicle-loss recovery. Add a vanilla vehicle only after the on-foot transfer is stable.
5. **UI and powered-suit capability spikes.** Demonstrate one map/one input path and one complete suit enter/exit/save cycle before choosing dependencies or promising a standalone support mod.

No live experiment, new helper, dependency installation, or queue entry is created by this research. Claude retains controller/deployment ownership. Separate source review, native acceptance, publication permission and packaging decisions remain distinct.

## Remaining design choices

The earlier route-choice and source-identification questions were answered by the owner clarification above; do not re-ask them. Remaining choices include outskirts extent, travel range/cost/access rules, generation timing and content-version persistence, acceptable stranded-player recovery, and whether optional regions can be added mid-save. Owner and Claude will decide the architecture/phase questions in the linked brief. These open details do not reopen the narrowed travel scope or settled Warfare/Survival choices.

## Research limits and handoff

Read current repository notes and primary developer/author sources on 25 October; main was unchanged during this pass. No new native evidence. The old planet-size/physics numbers, Papyrus API applicability, live navmesh coverage, vehicle independence, every-map fast-travel block and power-armor runtime remain unproved until tested. Existing Phase 0 owner acceptance is not revoked by these future-region questions. Weather probability cleanup and content-rights research were not expanded here; existing content/release restrictions remain in force.

For Codex desktop on the Windows PC or another authorized environment: identify your actual checkout, shell/tools and permissions; read the workspace ENVIRONMENT-HANDOFF where accessible and the latest checkpoint. Review this note alongside Claude's sources. Do not interpret it as a task to start the game, reactivate agents, merge code, delete cleanup candidates or implement every proposed support layer. Owner answers and later measured evidence should revise the plan before construction.
