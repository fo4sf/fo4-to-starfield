# Tool research and practical workflows for FO4SF

Codex, 25 October 2026 (Mountain time; source checks continued into 26 October UTC). Owner-requested research for Claude's return. **Verified upstream capabilities and local source inspection; proposed uses, not installed or native-tested integrations.** Read with the [decision brief](claude-reuse-decision-brief-oct25.md) and [travel risks](travel-and-runtime-risks-oct25.md).

## Recommendation and corrections

Keep the existing converter, official compiler and Archive2 baseline. Prioritize independent output inspection and a capability inventory before writing more engine hooks. Existing [engine notes](engine-mechanics.md), [interior tooling notes](interiors.md) and [launcher decisions](launcher.md) already identify many of these tools; this follow-up updates evidence and turns candidates into bounded workflows rather than claiming them as new discoveries.

Two corrections matter:

- The older engine note says Caprica lacks Starfield guards. At upstream `e4dee0860914d75e770d3f9ab374f7aba474b701`, it has Guard/TryGuard semantic processing and PEX generation. However, its TryGuard implementation explicitly retains a correctness TODO and nested-guard semantics have verification TODOs. **Implemented support is not established parity.** Preserve the owner's official-compiler decision; replace the categorical absence claim when Claude reconciles his notes. See [Guard generation](https://github.com/Orvid/Caprica/blob/e4dee0860914d75e770d3f9ab374f7aba474b701/Caprica/papyrus/statements/PapyrusGuardStatement.h), [TryGuard generation](https://github.com/Orvid/Caprica/blob/e4dee0860914d75e770d3f9ab374f7aba474b701/Caprica/papyrus/statements/PapyrusTryGuardStatement.h) and [semantic checks](https://github.com/Orvid/Caprica/blob/e4dee0860914d75e770d3f9ab374f7aba474b701/Caprica/papyrus/statements/PapyrusTryGuardStatement.cpp).
- CommonLibSF's active location is [libxse/commonlibsf](https://github.com/libxse/commonlibsf); the older Starfield-Reverse-Engineering repository is historical. Its published license includes GPL and linking/modding exceptions: do not categorize every community library as MIT or assume packaging rights from availability. The current README requires XMake 3+ and a C++23 compiler and still requires SFSE at runtime.

No benchmark, native compatibility or universal legal clearance follows from this research. Bethesda explicitly provides the [free Starfield Creation Kit](https://help.bethesda.net/app/answers/detail/a_id/65849/~/where-do-i-get-the-creation-kit-for-starfield). Community tools demonstrate workable analysis/modding techniques; their existence does not establish permission for every use or redistribution. Use the player's own game/CK where required, keep extracted/decompiled proprietary material private, and review the selected component's actual license before shipping it. No proprietary source or piracy tooling is needed for the proposed investigations.

## The original seven tools: what each contributes

| Tool | Concrete project use | Boundary and evidence |
|---|---|---|
| **B.A.E.** | Locate and selectively extract the scripts, menus or reference assets needed for one investigation. Record archive/member identity and hashes. | Extraction is separate from packing or script decompilation. Its Starfield release history includes texture-archive fixes; select a compatible version, not a legacy Fallout build. Do not assume all scripts occupy one named archive. [Author page](https://www.nexusmods.com/starfield/mods/165). |
| **Champollion** | Read event flow, native calls and property requirements of a relevant PEX; obtain assembly alongside reconstructed Papyrus. Useful for door/quest glue, equipment transitions and learning which part is delegated to native code. | Its stated aim is functionally equivalent output, not original comments/source. Current `bc961a0bdfb4831f8240e6dacee0818b4bf81e00` contains guard/try-guard nodes; their presence is not a correctness test. Prefer supplied PSC when available. [README](https://github.com/Orvid/Champollion), [guard node](https://github.com/Orvid/Champollion/blob/bc961a0bdfb4831f8240e6dacee0818b4bf81e00/Decompiler/Node/GuardStatement.hpp). |
| **Caprica** | Optional second compiler for small original scripts and a differential check of our script assumptions. | Do not compile all converted scripts with it by default. Compare against the CK compiler for our actual syntax, imports, properties and control flow, especially guards. Speed claims do not resolve semantic differences. See pinned source above and [project documentation](https://github.com/Orvid/Caprica). |
| **SF1Edit/xEdit** | Inspect winning overrides, masters, persistent references, CELL/WRLD placement, VMAD and linked records. A second reader helps distinguish a wrong writer from a wrong checker. | Use the Starfield mode and inspect exact-build support/restrictions. A readable record does not prove correct native behavior; avoid automatic cleaning or FormID changes on a live save stack. [Repository](https://github.com/TES5Edit/TES5Edit), [release notes](https://github.com/TES5Edit/TES5Edit/releases). |
| **SFSE** | Load small native adapters where ordinary scripting cannot expose a required observation or action. Its interfaces provide messaging, tasks, menus and trampolines. | Official page currently lists 0.2.21 for Steam runtime 1.16.244, not Game Pass. The inspected PluginAPI does not expose a serialization interface: do not import an SKSE save design by assumption. [Official compatibility](https://sfse.silverlock.org/), [API](https://github.com/ianpatt/sfse/blob/master/sfse/PluginAPI.h). |
| **CommonLibSF** | Reuse known C++ types and relocation abstractions when implementing a narrowly specified SFSE hook instead of reconstructing everything. | Community reverse-engineered definitions are incomplete and runtime-dependent. Community-generated PDB/type resources are not Bethesda's original source or complete debug symbols. Pin the actual definitions and validate relevant calls. [Current repository](https://github.com/libxse/commonlibsf), [historical repository](https://github.com/Starfield-Reverse-Engineering/CommonLibSF). |
| **JPEXS** | Inspect/edit SWF resources and ActionScript for a Pip-Boy-style interface, faction panels or travel menus. Separate display logic from the game-side data/actions it calls. | Supports Scaleform-related formats and ActionScript editing; it does not provide equipment, camera or simulation hooks. A new visual menu alone is not a working wearable Pip-Boy. [Feature documentation](https://github.com/jindrapetrik/jpexs-decompiler/wiki/Features). |

### Script investigation workflow

For one mechanic, trace **record/VMAD property → script event → Papyrus function → native boundary**. First inspect existing source and the relevant records. If source is unavailable, extract only the required PEX and compare reconstructed PSC with its assembly. Keep the game/version/input identity and the analysis private. Write a small original reproduction instead of copying a whole proprietary script into the repository.

Compile that reproduction with the official compiler and inspect the result. An optional Caprica comparison should cover success, failure, early return and cancellation paths, including guard behavior if used. Byte equality alone is not the acceptance rule: metadata can differ, while superficially similar outputs can still behave differently. Native behavior is a separately authorized test. A function declared `native` marks where Papyrus decompilation stops explaining the implementation.

## Additional tools worth using or evaluating

### First inspect existing APIs: Cassiopeia

[Cassiopeia Papyrus Extender](https://www.nexusmods.com/starfield/mods/10896) is an SFSE plugin; the author page lists version 10.0. Relevant documented additions include `GetCurrentPackageTargetRef`, `GetAITargetRef`, `GetAIFollowTargetRef`, inventory-instance queries and actor cell-change events. Its changelog records fixes to event parameters and target-related crashes, so pin the DLL and PSC/PEX interface together. The page restricts redistribution/modification; dependency use does not imply permission to bundle or fork it.

**Proposed use:** audit a short list of observations/actions for our creature encounters and faction adapter against vanilla Papyrus, Cassiopeia and existing project code before authoring hooks. Verify event ordering, unloaded-reference behavior and save/load lifetime in a later controlled test. These APIs do not establish autonomous offscreen simulation or a full faction-member succession system.

### Independent asset inspection: NifSkope and DirectXTex

The [fo76utils NifSkope fork](https://github.com/fo76utils/nifskope) documents Starfield handling and headless operations for internal/external geometry, bounds, tangents and LOD generation. This is a concrete way to revisit the existing T12–T14 tooling proposals. Several operations overwrite inputs; duplicate-vertex removal explicitly warns about morph breakage. Run operations only on disposable copies with original hashes retained. Its parser/rendering is a second implementation, not native acceptance.

**Proposed use:** compare our small synthetic mesh outputs with this reader, including negative scales, malformed indices, bounds and material references. Separate parse/display checks from repair operations. An operation that silently fixes a file can conceal our writer defect; save before/after differences and diagnose the disagreement. Do not batch-sanitize real content merely because a tool exits successfully.

We already use `texconv` in [textures.py](../../../src/fo4sf/textures.py). Add investigation of its sibling [texdiag](https://github.com/microsoft/DirectXTex/wiki/Texdiag), which reports texture metadata/statistics and compares images with error metrics or difference images. **Proposed use:** detect missing mipmaps, format/alpha mistakes or unexpected channel changes in a small conversion fixture. Compare equivalent color spaces/channels; a good PSNR score does not prove a material looks correct in Starfield. Keep the current texture pipeline and record exact tool versions/options.

### Authoring unusual geometry: Blender plus Starfield Geometry Bridge

[Starfield Geometry Bridge](https://starfieldgeometrybridge.github.io/) documents Blender export of geometry, morph and physics data. Its [mesh guide](https://starfieldgeometrybridge.github.io/docs/tips/mesh/) distinguishes the NIF reference from external mesh geometry. This is worth evaluating for custom suit parts, wearable UI housings, vehicles and original creatures where straight conversion is insufficient.

**Proposed use:** round-trip one original static part, then one weighted/morphed part, checking transforms, weights, materials and preserved blocks. Export capability does not prove an animation graph, creature AI, usable power armor or mech locomotion. Unsupported data loss and Blender/plugin version compatibility must be checked. Keep art authoring separate from the runtime support mod decision.

### Readable plugin review: Spriggit with existing Mutagen

[Spriggit](https://github.com/Mutagen-Modding/Spriggit) serializes Bethesda plugins into text; its current tree contains Starfield JSON/YAML translation packages and Starfield VMAD/quest/cell tests. Our writers already use Mutagen, so this is a candidate for review visibility rather than a reason to replace them. See the [Starfield package](https://github.com/Mutagen-Modding/Spriggit/tree/main/Translation%20Packages/Spriggit.Yaml.Starfield).

**Proposed use:** serialize a synthetic authored plugin before/after a writer change and inspect changed fields. Check FormIDs, masters, reference links and VMAD in the binary too. Translation packages have sorting/omission customizations; text equality is not automatically full binary preservation. Because it shares Mutagen, Spriggit is not an independent oracle for Mutagen parsing bugs: combine with xEdit/raw checks. Proprietary record dumps remain private.

### Creation Kit reliability: CKPE

[Creation Kit Platform Extended](https://github.com/Perchik71/Creation-Kit-Platform-Extended) provides editor fixes and explicitly lists Starfield support; its current README names CK 1.15.222.0 and later. Treat that as the project's compatibility statement, not confirmation of our installed combination.

**Proposed use:** when an authorized CK task is blocked by editor behavior, inspect whether a specific documented patch addresses it, pin it and compare a small fixture with unmodified CK. Avoid enabling an entire patch collection as an unexplained fix for a game crash. CKPE affects the editor; it is not a runtime boundary-wall or AI solution. No editor installation/change was made for this research.

### Native questions: Ghidra, a debugger and profiling

[Ghidra](https://github.com/NationalSecurityAgency/ghidra) supplies disassembly, decompilation, graphs and scripting. **Proposed use:** for a precisely named missing capability, analyze a private copy of the exact runtime and existing public type/relocation information, recording evidence and uncertainty. This can help locate where a known event is dispatched or a condition checked. Decompiled pseudocode is an inference; it does not restore original source, types or a rebuildable engine.

[x64dbg](https://github.com/x64dbg/x64dbg) is a Windows debugger that can test runtime hypotheses. Breakpoints and process attachment affect execution, so they belong to a separately released native investigation, not this research pass. Start with an owned plugin or existing crash evidence; no attachment to the running game is implied. Keep private binaries/dumps out of Git.

[Tracy](https://github.com/wolfpld/tracy), already in the reuse shortlist, can profile instrumented owned code. Use it only when existing timing identifies a useful question: simulation tick cost, bridge latency, allocations or locking. It does not automatically expose every Starfield subsystem. These tools supply evidence for a small hook or optimization; none proves we can override every engine limitation safely.

## Map tools to the owner's intended systems

| System | Reuse first | Work that still belongs to this project |
|---|---|---|
| Persistent doors and bounded regional travel | xEdit/raw record inspection; script event trace; existing paired-stage/identity code; cell-change observation | Winning world/cell proof, actual round trip, save association, partial-state recovery and eligible-destination policy. No tool here guarantees seamless world streaming. |
| Living-world factions and creature encounters | Existing simulation prototype; native AI packages; API inventory and controlled observations | Shared mode policies, residency handoff, event ordering, cancellation, faction consequences and deterministic save behavior. **No runtime language model or AI server.** |
| Warfare faction-member succession | Inspect death/new-character/player-related script and record paths, then identify missing native hooks | Another faction member, not revival of the same character; identity, inventory/progression transfer and persistent-world consequences remain decisions. No listed tool establishes feasibility by itself. |
| Pip-Boy-style UI | JPEXS for menu structure; game-facing data API and event bindings; original geometry authoring | Wearable interaction, input focus, camera/equipment transitions and save lifecycle. Start with a small panel plus one real action, not a complete UI replacement. |
| Power armor or reusable mech support | Original model/rig fixtures; known equipment/animation hooks; precise native investigation if needed | Entry/exit, camera, collision, animation/controller transitions and failure recovery. A Blender export is not a playable vehicle. A reusable support module remains a candidate, not a selected deliverable. |
| Ghoul and FO76-derived content | Existing single-player rules, character/record tools, small original fixtures | FO4-style baseline, selectively retained FO76 mechanics and owner-written policy. Ghoul play desired for Warfare/story-off Survival; broad story-dialogue rewriting is deferred. |

## Small investigations to propose when work resumes

These are suggested decisions for Claude and the owner, not queued automatic work. Preserve existing delivery gates and ownership.

1. **Capability table before a new native plugin.** For one creature encounter, list required observations/actions and the vanilla/Cassiopeia/project API that supplies each. Record exact versions and unresolved semantics. Success: identify the actual missing capability instead of designing a whole replacement AI stack.
2. **Independent mesh/texture fixture audit.** A handful of original synthetic assets through our writer, NifSkope and texdiag. Preserve originals and repairs separately. Success: explain disagreements and catch deliberately malformed cases without silently fixing them.
3. **Papyrus compiler/decompiler parity sample.** Original scripts covering properties, events, guards, early return and cancellation; compare official compile, decompile/recompile and optional Caprica. Success: a documented supported subset, not a blanket compiler endorsement. Native semantics remain a later gate.
4. **One interface capability slice.** Original UI panel, one observation and one reversible action; specify UI/native boundary and failure behavior on paper first. Success: distinguish menu work from unavailable game hooks before large Pip-Boy/suit art investment.
5. **Save/identity design review before faction succession.** Determine authoritative state, character association and backward-load behavior using existing project contracts. Success: explicit failure/recovery rules; SFSE messages or external JSON alone are not assumed to make saves transactional.

For every adopted tool record release/commit, binary hash, runtime/editor compatibility, invocation, inputs, output checks and redistribution status. Select the smallest useful experiment. The owner and Claude choose architecture and phase changes together; no engine migration, implementation, installation, game test, agent wake or automation resume occurred here.
