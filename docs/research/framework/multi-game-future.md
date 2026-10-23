# The multi-game future: Fallout 3, New Vegas and others on the same core

Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/multi-game-scope.md (cited as MS),
findings/precedents.md (cited as PR; its TTW, Capital Wasteland, F4NV and FNV to FO4 parts only).

## In short

- Tale of Two Wastelands (TTW) proves a merged FO3 + NV playthrough works when the installer builds from the player's own
  files, one game's rules win everywhere, travel between worlds is a scripted chokepoint, and content is rebalanced (MS 1).
- The direct converter precedent, fnv-to-fo4, gets the world across (cells, landscape, placed objects, models) but no
  NPCs, creatures, quests or scripts, and it dropped navmesh (MS 2, PR 6). So a FO3/NV reader feeding our world pipeline is
  realistic; behaviour (ObScript, CREA, karma, reputation, skills, hardcore) must be rebuilt on our core.
- Most uncertain: whether locally converted FO3/NV voice audio is acceptable. Capital Wasteland (FO3 in FO4) was cancelled
  over exactly this in 2018 (PR 5). Also unknown: whether the shipped masters keep ObScript source text (SCTX).
- Geography forces separate landings: DC to Las Vegas is about 3,350 km, DC to Boston about 630 km (computed, MS 5).
- The 3 decisions that unlock the most: (1) whose rule set wins (MG-07); (2) the voice policy for converted games
  (MG-03); (3) whether to run a 1-week multi-game spike now to avoid design lock-in (MG-01).
- Cheap now: game-neutral names and a per-game prefix and provenance key on the core (section "What the core should
  reserve now").

## What is settled

- **Forward priority (owner, 2026-10-19 23:19Z and 23:24Z):** the GAMMA-style combined core comes first; stories continue but second for now. Where this file overlaps it (MG-01, MG-05, MG-07, MG-09, MG-10, MG-14), [combined-core.md](combined-core.md) is the working file.

| Item | Source | Label |
|---|---|---|
| Build 2, "All games, one playthrough", is a planned later build on the core. Each game needs its own converter and the player's own copy. FO3/NV are a second reader feeding the same pipeline. | docs/ROADMAP.md C3 | owner decision |
| Fallout 1, 2 and Tactics would be hand-built recreations outside the deterministic pipeline. FO76 is in or out at the owner's call after research. | docs/ROADMAP.md C3 | owner decision |
| Players own every game a build reads; nothing of Bethesda's is redistributed; the launcher never changes an executable or removes anything. | docs/ROADMAP.md, Phase C constraints | owner decision |
| FO4 comes first; breadth before polish; silent player; SFSE and the Starfield CK MAY be required. | findings/BRIEF.md | owner decision |
| Each world gets its own overlay landing on one host planet, joined by scripted travel. | MS 5, citing engine-mechanics/vehicles-and-travel.md | project layout (settled there) |
| The current FO4 core prefix is `FO4SF_` (474 uses in the repo, e.g. FO4SF_AnimatedLoadDoor). | repo grep, 2026-10-19 | verified |
| FO3/NV record set differs: FO3 has 89 record types in xEdit, FNV 106 (17 NV-only types such as REPU, CHAL, IMOD, RCPE, CSNO, CCRD, DEHY, HUNG, SLPD). FO4 has no CREA, SCPT, REPU or CHAL. | MS 3 (xEdit dev-4.1.6; docs/measurements/fo4_esm.json) | verified |
| FO3/NV actor values are a hardcoded 77-entry enum (Karma 23, skills 32-45, NV adds Dehydration 73 to Damage Threshold 76). FO4/SF use AVIF forms. | MS 3 (xEdit) | verified |
| Anchorage is a VR simulation and Zeta is in orbit; the Pitt and Point Lookout are real places. Only the latter two need map positions. | MS 4 (Wikipedia FO3 DLC) | verified (answers part of MG-14) |
| TTW's current level cap is 60 (older forum answers of 50 are out of date). | MS 1, Corrections (ModPub; TTW FAQ) | verified |
| Mutagen has a `Mutagen.Bethesda.Fallout3` project; New Vegas is not named. | MS 3 (GitHub Mutagen) | verified (maturity unresolved) |
| TTW will not move engines: "would require an entire rebuild". Nobody has moved a merged FO3+NV to a newer engine. | MS 1 (fallout.wiki; Insider Gaming) | verified quote; "we would be first" is inference |

## Possibilities

### Unified rules and progression

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| FO4 rules everywhere (SPECIAL and perks, no skills, no karma); FO3/NV skill checks remapped | One system, matches build 1 | Every FO3/NV condition on skill AVs 32-45 needs a remap; loses flavour | TTW did the same with NV's rules as the winner (MS 1) | supported hypothesis |
| Superset core (FO4 rules plus skills, karma, reputation, DT as data) | Keeps legacy systems | Long build; rebalancing per content | F4NV restores skills, DT, weapon condition (MS 2) | supported hypothesis |
| Per-world rule swap | Each game plays like itself | No precedent; likely confusing | none | supported hypothesis |
| TTW-style cap (60, one perk per level, half rate in Hardcore) | Known balance | Clashes with FO4's uncapped curve | TTW (MS 1) | verified (TTW facts) |
| Bobbleheads as mini perks | Avoids easy maxing | Design work | TTW (MS 1) | verified |

### ObScript to Papyrus

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Transpiler from SCTX source to Papyrus with a shim library | Scale over thousands of scripts | Depends on SCTX being filled in shipped masters (unchecked); untested | none; fnv-to-fo4 converts no scripts (MS 2) | supported hypothesis |
| Hand rewrite of quest logic on SF records (QUST stages, dialogue) | Correct, idiomatic | Very high effort | F4NV remakes every quest (MS 2) | verified (F4NV approach) |
| Hybrid: transpile simple object scripts, hand-port quests | Balances both | Two toolchains | none | supported hypothesis |

Embedded scripts also live inside INFO, PACK, TERM and PERK entries (MS 3, verified), so any route must cover them too.

### Creatures and actors

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Convert CREA to NPC_ plus race | Keeps FO3/NV creature data | Skeletons, animations, behaviour all new | none (fnv-to-fo4 skips creatures) | supported hypothesis |
| Substitute FO4/SF creatures (deathclaw, radroach, ghoul exist in FO4) | Reuses build-1 work | FO3/NV-only creatures need a fallback | none | supported hypothesis |
| Rebalance per world | Avoids NV-strength enemies in FO3 areas | Ongoing tuning | TTW had to (super mutants too hard) (MS 1) | verified |

### World placement and travel

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Real relative geography for the east-coast cluster (DC, Pitt, Point Lookout, Boston, Far Harbor, Appalachia), Mojave as a far landing | Lore-faithful map | Distances are inference only | none | supported hypothesis |
| Abstract "regions" map | Simple | Less immersive | none | supported hypothesis |
| Separate planets | Fits SF travel | Breaks the "one Earth" premise | none | supported hypothesis |
| Travel by train scene at each end, quest-gated | Sets world-state at one chokepoint | Console or test teleports bypass it | TTW Union Station (MS 1) | verified |
| Vertibird scene, travel-menu activator, or SF ship (fenced out) | Options for our setting | Cross-landing surface fast travel unresolved | engine-mechanics/vehicles-and-travel.md | unresolved |
| Anchorage and Zeta as sealed worldspaces; Zeta could use SF's space engine | No map position needed | Design work | none | supported hypothesis |

### Readers, formats and libraries

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Mutagen Fallout 3 project | Typed reader, same stack | Maturity and NV coverage unknown | Mutagen repo (MS 3) | verified (exists) |
| Own reader from xEdit definitions, or xEdit script export | Full control | Effort | fnv-to-fo4 credits xEdit (MS 2) | supported hypothesis |
| Extend NIF converter to bsver 34 (NiTriShape plus BSShaderPPLightingProperty, no BGSM) | Reuses mesh pipeline | Long tail of old mesh, havok and skin bugs | nif.xml defines all versions (MS 3) | verified (versions); supported hypothesis (shape types) |
| Read fnv-to-fo4 (GPL-3) and BSA# (MIT) as reference | Known fixes (materials, terrain holes) | Targets FO4, not SF | PR 6, PR 1 | verified (licences) |

### Legal and release

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Convert FO3/NV voice locally (TTW model) | Full story audio | Capital Wasteland's same-shape plan was flagged by Bethesda staff and a lawyer | TTW converts audio locally (MS 1); CW cancelled (PR 5) | verified (both facts); outcome for us unresolved |
| Subtitles only | No audio risk | Weak story experience (about 45,000 FO3 lines) | none | supported hypothesis |
| Re-voice | Legally clean | Huge volunteer effort | CW v2, F4NV (PR 5, PR 6) | verified |
| Separate optional FO3/NV module | FO4 build survives a takedown | Two release tracks | TTW hosting friction (MS 1) | supported hypothesis |

## Questions

### Scope and timing

**MG-01. When is the multi-game go/no-go: after FO4 is complete, or as an early 1-week spike to avoid design lock-in?**
- Why it matters: core choices (rules, names, readers) are cheap now and costly later.
- Options: after FO4 (ROADMAP order); a spike covering MG-07, MG-10, MG-21, MG-22 without building content (MS Q39).
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page MU-1): "1-week research spike after phase 1" (as recommended). Before: open.

**MG-02. Fallout 1, 2, Tactics and FO76: in or out?**
- Why it matters: 1/2/Tactics are 2D and need hand-built recreations; FO76 is online-only under its own terms.
- Options: record FO76 "out" unless research finds an offline data path; 1/2/Tactics deferred (MS Q33; ROADMAP C3).
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game. Status: **Owner answer, 2026-10-19:** [Terms read 2026-10-19: Fallout 76's ToS bars reverse engineering, derivative works and copying content that is not a Game Mod, and Bethesda says 76 supports no mods; see REL-60 and findings/fo76-terms.md; 76 work waits on Bethesda's answer.] decided by owner in the talk-through, 2026-10-19 (page MU-2): Fallout 76's story and places only (no online parts) for the combined core, best version of repeated places; Fallout 1, 2 and Tactics stay open; 76's terms go into the Bethesda letter. Owner's note: "For Fallout 76 we will not recreate the online parts, only the gameplay and story people might want. That is mostly so the other core has the location: we take Appalachia and its missions and add them, for the core that combines all the locations into one travel area. Where a location exists more than once, like the Pitt in Fallout 3 and Fallout 76, we will likely add the best version.". Before: open.

### Legal and release

**MG-03. Is local conversion of FO3/NV voice audio acceptable, and how does it differ from what Capital Wasteland tried?**
- Why it matters: voice is the bulk of story content (about 45,000 FO3 lines, DSOGaming). CW was cancelled in 2018 after
  Bethesda staff "heavily hinted at our methods being illegal" and a lawyer called it "sketchy"; voice is licensed, not
  owned (PR 5, verified). Yet TTW converts audio locally and still ships (MS 1, verified). PC Gamer's "same audio format"
  explanation is a journalist's gloss; "same engine family" is the likelier difference (PR 5, supported hypothesis).
- Options: local conversion (TTW model); subtitles only; re-voice (CW v2, F4NV).
- Answer by: written question to Bethesda or ZeniMax community staff, legal opinion, a talk with the TTW team. Who:
  owner, Bethesda contact, community contact.
- Blocks: Multi-game, People and story, Release. Status: **Owner position, 2026-10-19 22:38Z:** reusing voice lines is a known no for Fallout 3 (the Capital Wasteland precedent) and, by the owner's word at 22:54Z, for New Vegas; for Fallout 4 and Fallout 76 it is open until Bethesda answers the letter's voice question (sent 22:30Z). **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page RE-1): "No: subtitles only, for now" (as recommended). Owner's note: "Did you guys ask? You have access to my email to send any.". Before: open. (also: MS Q9, PR Q31)

**MG-04. Should the TTW team be contacted before any FO3/NV work, and could they be partners?**
- Why it matters: they hold the know-how and the history with Bethesda (MS 1).
- Options: no contact; informal; partnership.
- Answer by: owner approves a contact. Who: owner, community contact.
- Blocks: Multi-game. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page RE-4): "Yes, all the named authors" (as recommended). Before: open. (also: MS Q30)

**MG-05. Does FO3/NV ship as a separate optional launcher module, so the FO4 build survives if it is taken down?**
- Why it matters: Bethesda reportedly asked sites not to host TTW, even with no assets (MS 1, verified as reported).
- Options: separate module; one bundle.
- Answer by: owner decision. Who: owner.
- Blocks: Launcher, Release. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page MU-3): two cores: a pick-your-games core with each game as its own module, and a combined core that needs every game plus Starfield. Owner's note: "There will be two options: one lets you pick whichever games you own and play them as a Creation Engine 2 experience; the other core requires all of the games plus Starfield. That locks out a lot of players, but I don't care.". Before: open. (also: MS Q31)

**MG-06. Is fnv-to-fo4 (GPL-3) reusable code or only a reference, and does its licence fit ours?**
- Why it matters: it solved materials, terrain "black holes" and TTW issues (MS 2). It targets FO4, not SF (PR Q29).
  Note: GitHub names terry-haire, the Nexus page names bololo11 as uploader (MS 2, PR 6).
- Options: reference only; reuse parts with GPL-3 notice; ignore.
- Answer by: read its source and licence. Who: offline research, owner.
- Blocks: Multi-game. Status: open. (also: MS Q10, PR Q29)

### Unified rules and progression

**MG-07. Whose rule set wins: FO4 SPECIAL and perks only, or a superset with skills, karma, reputation and DT?**
- Why it matters: every dialogue condition (GetActorValue Speech >= 50), lock level and perk depends on it (MS Q21).
- Options: (a) FO4 rules everywhere; (b) superset core (F4NV); (c) per-world swap (no precedent). TTW chose one winner.
- Answer by: owner decision, informed by MG-08 counts. Who: owner.
- Blocks: Multi-game, Fallout systems. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page MU-4): each game keeps its own rules in the pick-your-games core; the combined core uses a superset of systems from all games. Owner's note: "In one core each game has its own systems; the larger core combines systems from the earlier games, since, for example, the faction system did not exist in Fallout 4 the way it did in New Vegas. So it depends.". Before: open.

**MG-08. If skills are dropped, how are FO3/NV skill checks (Speech, Lockpick, Science, Repair) remapped?**
- Why it matters: conditions reference AVs 32-45 (MS 3, verified).
- Options: SPECIAL thresholds; perk ownership (FO4 style); hidden skill AVs.
- Answer by: xEdit script counting conditions per skill AV in Fallout3.esm and FalloutNV.esm. Who: offline research.
- Blocks: Multi-game. Status: open. (also: MS Q22)

**MG-09. Karma (FO3), reputation (NV) and affinity (FO4): one alignment system or three?**
- Why it matters: karma gates FO3 companions and spawns hit squads (fandom Karma, verified); NV reputation is per-faction
  REPU; NPCs carry a "Karma (Alignment)" float (MS 4). How TTW reconciles karma and reputation is unresolved (MS 1).
  NV fame/infamy thresholds are unresolved (MS 4).
- Options: keep karma as an AV plus REPU as factions plus affinity; derive karma from affinity events.
- Answer by: owner decision; wave-2 research on TTW and NV reputation. Who: owner, offline research.
- Blocks: Multi-game, People and story. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page MU-4): each game keeps its own rules in the pick-your-games core; the combined core uses a superset of systems from all games. Owner's note: "In one core each game has its own systems; the larger core combines systems from the earlier games, since, for example, the faction system did not exist in Fallout 4 the way it did in New Vegas. So it depends.". Before: open. (also: MS Q23)

**MG-10. What is the unified level cap and XP curve?**
- Why it matters: FO3 20 then 30 (Broken Steel, verified); NV 30 to 50 (supported hypothesis); TTW 60 with one perk per
  level and one per two in Hardcore (verified); FO4 uncapped.
- Options: uncapped FO4 curve with per-world XP rebalance; TTW-style cap.
- Answer by: XP totals of a full FO3+NV run (TTW community); owner decision. Who: owner, offline research.
- Blocks: Multi-game, Fallout systems. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page MU-4): each game keeps its own rules in the pick-your-games core; the combined core uses a superset of systems from all games. Owner's note: "In one core each game has its own systems; the larger core combines systems from the earlier games, since, for example, the faction system did not exist in Fallout 4 the way it did in New Vegas. So it depends.". Before: open. (also: MS Q24)

**MG-11. How are FO3/NV bobbleheads, skill books and NV challenges (CHAL) handled?**
- Why it matters: TTW turned FO3 bobbleheads into mini perks (verified). CHAL has 14 types; SF activity trackers are the
  closest match (MS 3).
- Options: mini perks; map CHAL to SF activity trackers; cut.
- Answer by: offline mapping. Who: offline research.
- Blocks: Multi-game. Status: open. (also: MS Q25)

**MG-12. Is NV hardcore (dehydration, hunger, sleep) merged with FO4 Survival, and is it one mode for all worlds?**
- Why it matters: DEHY/HUNG/SLPD records exist (verified); FO4 Survival is a different design. TTW Hardcore also restores
  FO3's death ending (verified).
- Options: one survival mode for all worlds; per-world.
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game, Fallout systems. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page MU-4): each game keeps its own rules in the pick-your-games core; the combined core uses a superset of systems from all games. Owner's note: "In one core each game has its own systems; the larger core combines systems from the earlier games, since, for example, the faction system did not exist in Fallout 4 the way it did in New Vegas. So it depends.". Before: open. (also: MS Q26)

**MG-13. What happens to NV-only systems: weapon mods (IMOD), recipes (RCPE), ammo effects (AMEF), currencies (CMNY),
casinos and Caravan (CSNO, CCRD, CDCK, CHIP)? And how do VATS-modifying FO3/NV perks map onto one VATS?**
- Why it matters: these record types are NV-only (verified); FO4/SF entry points lack Damage Threshold (verified).
- Options: IMOD to OMOD, RCPE to COBJ, AMEF to OMOD/MGEF; casinos and Caravan rebuilt or cut; caps, NCR dollars and
  denarii unified or kept.
- Answer by: offline mapping; owner on cuts. Who: offline research, owner.
- Blocks: Multi-game, Fallout systems. Status: open. (also: MS Q27, Q28, Q29)

### World placement and travel

**MG-14. Where do the Capital Wasteland and the Mojave sit on our planet?**
- Why it matters: no continuous terrain can join worlds about 3,350 km apart (computed, MS 5).
- Options: real-geography landings (east-coast cluster close; Mojave far); abstract regions; separate planets. Anchorage
  (VR) and Zeta (orbit) need no position (verified).
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game, World. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page MU-5): "Same planet, real relative positions" (as recommended). Owner's note: "Pay attention to my other comment about placing the locations on the planet (WO-4).". Before: open (partly answered for Anchorage and Zeta: MS 4). (also: MS Q11, Q13)

**MG-15. How does the player travel between FO4, FO3 and NV worlds, and does every route run the same arrival handler?**
- Why it matters: TTW sets quest variables on the train; the FAQ warns console moves "bypass" them (verified, MS 1).
- Options: train scene; vertibird; travel-menu activator; SF ship (fenced out).
- Answer by: the vehicles-and-travel.md probe on cross-landing surface fast travel; owner choice. Who: PC probe, owner.
- Blocks: Multi-game, World. Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page NG-9): no usable ship, scripted travel; the vertibird-ship idea is kept for the combined core. Owner's note: "Go with your recommendation for now, but don't drop the idea of using the ship as a vertibird, maybe for the second core that combines the games.". Before: open. (also: MS Q12)

**MG-16. What weather and climate do the DC and Mojave landings use?**
- Why it matters: FO3's green tint and NV's desert are part of each game's identity.
- Options: map FO3/NV CLMT/WTHR into SF biomes and weather; reuse FO4's.
- Answer by: offline mapping. Who: offline research.
- Blocks: Multi-game, World. Status: open. (also: MS Q14)

**MG-17. How many landings, plugins and loaded worlds can one save carry?**
- Why it matters: FO4 + FO3 + NV + 11 DLC is about 15 source masters; TTW pins FO3 and DLC at fixed indices (verified);
  Starfield plugin limits and save size with many landings are untested.
- Options: one plugin set per game; merged plugins per game.
- Answer by: PC stress test with terrain-only landings. Who: PC probe.
- Blocks: Multi-game, World. Status: open. (also: MS Q15)

### People and story across worlds

**MG-18. Which game does a multi-game playthrough start in, and who is the player character?**
- Why it matters: chargen happens once; later arrivals must skip it (TTW skips NV creation, verified as a 2014 report;
  current TTW offers a wasteland selection, verified). NV quests call you "Courier".
- Options: always Vault 111; chronological (FO3 2277, NV 2281, FO4 2287); player choice. One person with lore glue, one
  person with no lore claims, or a frame outside canon.
- Answer by: owner decision plus a prototype arrival quest. Who: owner.
- Blocks: Multi-game, New game. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page NG-8): "Vault 111, start-world hook built in" (as recommended). Before: open. (also: MS Q1, Q2)

**MG-19. Do companions travel between worlds, and how do faction relations and story state carry over?**
- Why it matters: Brotherhood exists in DC and Boston; NCR only in the West. TTW did not carry faction relations in 2014
  (player report; current state unresolved).
- Options: sandboxed games; light flags (dialogue variants); deep links. Shared or per-game factions.
- Answer by: owner decision; a probe for cross-world followers. Who: owner, PC probe.
- Blocks: Multi-game, People and story. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page MU-6): "Light flags only (dialogue variants)" (as recommended). Before: open. (also: MS Q18, Q19, Q20)

### ObScript to Papyrus

**MG-20. How are FO3/NV ObScript scripts turned into Papyrus: transpiler, hand port, or hybrid?**
- Why it matters: no precedent converted scripts (fnv-to-fo4 does not). ObScript is SCPT with SCDA bytecode and an SCTX
  source field, plus embedded scripts in INFO, PACK, TERM, PERK (verified layout). Whether shipped masters keep SCTX
  filled is a supported hypothesis.
- Options: see Possibilities.
- Answer by: confirm SCTX is filled in Fallout3.esm and FalloutNV.esm; transpile ten varied scripts. Who: offline
  research, PC probe (needs the owner's game files).
- Blocks: Multi-game, People and story. Status: open. (also: MS Q16)

### Creatures

**MG-21. What happens to FO3/NV creatures (CREA, ACRE), their skeletons, animations and behaviour?**
- Why it matters: FO4 has no CREA; creatures are NPC_ with a race (verified).
- Options: convert CREA to NPC_ plus race; substitute FO4/SF creatures; rebalance per world (TTW).
- Answer by: a map of FO3/NV creature types to FO4 races. Who: offline research.
- Blocks: Multi-game, People and story. Status: open. (also: MS Q17)

### Readers and formats

**MG-22. Does Mutagen read Fallout3.esm (and FalloutNV.esm) well enough, or do we need our own reader?**
- Why it matters: the reader is the entry point for everything else. FO3/NV plugin form version is unresolved.
- Options: Mutagen FO3; own reader from xEdit definitions; xEdit script export.
- Answer by: load both masters with Mutagen and count unread subrecords. Who: offline research, PC probe.
- Blocks: Multi-game. Status: open. (also: MS Q34)

**MG-23. Does our NIF converter extend to bsver 34 cheaply, and how are FO3/NV materials (no BGSM) mapped to SF .mat?**
- Why it matters: FO3/NV are NIF 20.2.0.7 user 11 bsver 34 (verified); fnv-to-fo4 had to add material files (MS Q6).
- Options: extend our converter via nifly/pynifly; read fnv-to-fo4's material handling.
- Answer by: convert three FO3 meshes (static, skinned, havok) to SF. Who: offline research, PC probe.
- Blocks: Multi-game, All interiors. Status: open. (also: MS Q6, Q35)

**MG-24. Can the interior pipeline take FO3/NV cells (no precombines, older lighting) with only a new reader, and what
about navmesh and doors?**
- Why it matters: fnv-to-fo4 dropped navmesh because it crashed (verified). FO3/NV DOOR/XTEL layout is unresolved; FO4
  to SF XTEL is identical (engine-mechanics notes).
- Options: regenerate navmesh in the SF CK; convert NAVM; ship without. Diff DOOR/XTEL in xEdit.
- Answer by: convert one small FO3 interior (Vault 101 entrance) end to end. Who: PC probe, offline research.
- Blocks: Multi-game, All interiors, Door animations. Status: open. (also: MS Q4, Q5)

### Launcher

**MG-25. Does the launcher require each game with all DLC, English, and detect FO3 GOTY / NV Ultimate store variants?**
- Why it matters: TTW requires English FO3 and FNV with all DLC, Steam/GOG/Epic mixable, no Microsoft Store, each run once,
  about 40 GB free; German No Gore exe is a problem (verified, MS 1, PR 1). One rule set is easier with all DLC.
- Options: all DLC required; base-only build; per-DLC optional. Hash tables per variant.
- Answer by: owner decision; hash table from TTW docs if public, or owner PCs. Who: owner, offline research, PC probe.
- Blocks: Launcher, Multi-game, Release. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page LA-5): "Steam, then GOG; refuse others" (as recommended); decided by owner, 2026-10-19 (page LA-7): "Require all DLC" (not the recommended option). Before: open. (also: MS Q7, Q8, Q32)

### Data model (reserve now)

**MG-26. Should the core reserve namespaces now (editor ID prefixes, script names, FormID ranges, plugin names) per game?**
- Why it matters: name clashes are real (engine-mechanics notes); TTW pins load indices (verified).
- Options: see "What the core should reserve now".
- Answer by: owner decision, recorded in docs/ai/decisions.md. Who: owner, offline research.
- Blocks: Multi-game (cheap now, costly later). Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page FS-2): "Yes: FO4SF_, FO3SF_, FNVSF_, shared FOSF_" (as recommended). Before: open. (also: MS Q37)

**MG-27. Should actor values, factions and keywords on the core be named game-neutrally (e.g. `FO_Karma`,
`FO_Skill_Speech`) even if FO4 does not use them?**
- Why it matters: later games plug in without a migration (MS Q38).
- Options: neutral names now; rename later.
- Answer by: owner decision. Who: owner.
- Blocks: Multi-game, Fallout systems. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page FS-1): "FO4 names, rename later" (not the recommended option). Before: open.

**MG-28. Does phase 1's new-game flow need a "start world" hook now so a FO3/NV start can plug in?**
- Why it matters: cheap now, costly to retrofit (MS Q3).
- Options: add a parameter now; retrofit later.
- Answer by: offline review of the new-game design. Who: offline research.
- Blocks: New game, Multi-game. Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page NG-8): "Vault 111, start-world hook built in" (as recommended). Before: open.

### Testing

**MG-29. What is the acceptance test for "one playthrough"?**
- Why it matters: a route that starts in one world, travels, and keeps inventory, level and quest flags proves build 2.
- Options: a scripted route-run like the existing ones.
- Answer by: tooling design. Who: offline research.
- Blocks: Multi-game, Release. Status: open. (also: MS Q36)

## What the core should reserve now

All items below are **recommendations** (inference from the findings, not owner decisions). They cost little during
FO4 work and avoid a migration later.

| # | Recommendation | Why (source) | Closes |
|---|---|---|---|
| R1 | Keep `FO4SF_` for FO4-derived content; reserve `FO3SF_` and `FNVSF_` for later games; use one game-neutral prefix (for example `FOSF_`) for shared core systems (rules, travel, arrival handler). | `FO4SF_` is the current prefix (repo, verified); clashes are real (MS Q37) | MG-26 |
| R2 | Name shared actor values, factions and keywords game-neutrally (`FO_Karma`, `FO_Skill_Speech` style), even if unused by FO4. | MS Q38 | MG-27 |
| R3 | Key the converter's provenance map by (source game, source plugin, source FormID), not by plugin and FormID alone, so identical editor IDs and FormIDs from two games never collide. | Several games share one load order (MS Risks) | MG-26 |
| R4 | One output plugin set per source game, with plugin names carrying the game tag. | TTW pins per-game load indices (MS 1); plugin limits unresolved (MG-17) | MG-17, MG-26 |
| R5 | Give the new-game flow a "start world" parameter, defaulting to Vault 111. | MS Q3 | MG-28, part of MG-18 |
| R6 | Route every world entry (travel scene, COC, test teleports) through one arrival handler that sets world state. | TTW's console-bypass warning (MS 1) | part of MG-15 |
| R7 | Keep rule remaps (skill check to SPECIAL/perk, karma, reputation) as data tables keyed by source game, not code. | MG-07 is open; tables survive whichever answer (inference) | eases MG-07, MG-08 |
| R8 | Make the launcher's game list and edition checks a per-game manifest rather than FO4-only code. | TTW per-game requirements (MS 1) | eases MG-25 |
| R9 | Gate any audio conversion path per source game, off by default for games without a decision. | CW precedent (PR 5) | eases MG-03 |
| R10 | Place landings in one shared planet coordinate frame with room for the east-coast cluster and a far Mojave slot. | Computed distances (MS 5) | eases MG-14 |

## Owner decisions in this area

Each default is a **recommendation**, not a decision.
- MG-01 timing: recommend a 1-week offline spike after phase 1 ships, not content work; it exposes lock-in cheaply.
- MG-02 FO76: recommend recording "out"; FO1/2/Tactics deferred. Online-only data, own terms (ROADMAP).
- MG-03 voice: recommend no FO3/NV audio conversion until a written answer from Bethesda staff or legal advice; CW precedent.
- MG-04 TTW contact: recommend an informal contact before any FO3/NV work; they hold the know-how.
- MG-05 module: recommend a separate optional module, so the FO4 build is not exposed to FO3/NV hosting friction.
- MG-07 rule set: recommend FO4 rules as the winner with remap tables (R7), following TTW's one-winner model; superset
  only if MG-08 counts show remaps lose too much.
- MG-09 alignment: recommend keeping karma and reputation as data on the neutral names (R2) until MG-07 is settled.
- MG-10 level cap: recommend the FO4 uncapped curve with per-world XP rebalance; matches build 1.
- MG-12 survival: recommend one survival mode for all worlds; fits the one-rule-set lesson.
- MG-14 geography: recommend real relative positions for the east-coast cluster and a far Mojave landing.
- MG-15 travel: recommend a train or vertibird scene through one arrival handler (TTW model).
- MG-18 start and identity: recommend Vault 111 by default with a start-world option, one silent person, no lore claims.
- MG-19 cross-world state: recommend light flags only at first.
- MG-25 DLC: recommend all DLC required, as TTW; one rule set and less support.
- MG-26, MG-27, MG-28: recommend adopting R1 to R5 now.

## Cheapest experiments

Nothing here runs now.

| # | Experiment | Kind | Closes |
|---|---|---|---|
| E1 | Read xEdit FO3/FNV definitions for DOOR/XTEL, CLMT/WTHR, CREA vs NPC_ and perk entry points; write mapping tables. | offline | MG-11, MG-13, MG-16, MG-21, part of MG-24 |
| E2 | Read fnv-to-fo4's GPL-3 source: licence, material handling, terrain holes, why navmesh crashed. | offline | MG-06, part of MG-23, part of MG-24 |
| E3 | Load Fallout3.esm and FalloutNV.esm with Mutagen (and xEdit): count unread subrecords, check SCTX is filled, count conditions per skill AV. | PC read-only probe (owner's files) | MG-20 (first half), MG-22, MG-08, informs MG-07 |
| E4 | Transpile ten varied SCTX scripts (object, quest, effect, embedded INFO) by hand into Papyrus sketches. | offline after E3 | MG-20 |
| E5 | Convert three FO3 meshes (static, skinned, havok) and one small interior (Vault 101 entrance) to SF. | PC probe | MG-23, MG-24 |
| E6 | Terrain-only landing stress test: several extra landings and plugin sets in one save. | PC probe | MG-17, part of MG-15 |
| E7 | Review the new-game design for a start-world parameter. | offline | MG-28 |

Top 3 by questions closed per cost: E3, E1, E2.

## Gaps for wave 2

- NV reputation fame/infamy split and thresholds (primary source).
- How TTW reconciles FO3 karma with NV reputation; whether faction relations now carry between worlds.
- NV level-cap steps (30 to 50) from a primary source.
- FO3/NV plugin form version and BSA version number.
- Current status of F4NV and Capital Wasteland; whether the PCGamesN NV-in-FO4 sandbox is F4NV.
- Mutagen Fallout 3 maturity and any New Vegas coverage.
- Whether TTW publishes variant hash tables or a legal stance.
- Beyond Skyrim structure (Bethesda staff pointed CW to it; PR 5); not read.
- Starfield plugin limits and save behaviour with many landings.

## Handed to phase files

These stay in this file because they are multi-game, but the phase owner should know.

| Question | Target file |
|---|---|
| MG-28 start-world hook; MG-18 start game and identity | newgame.md |
| MG-24 FO3/NV DOOR/XTEL compatibility | door-animations.md |
| MG-23, MG-24 FO3/NV cells, materials, navmesh | interiors.md |
| MG-25 per-game edition checks; MG-05 optional module; R8 manifest | launcher.md |
| MG-13 VATS perks and NV systems; MG-12 survival | engine-mechanics.md |

## Sources

- docs/ROADMAP.md C3 and Phase C constraints (repo); repo grep for `FO4SF_`
- docs/measurements/fo4_esm.json, sf_esm.json (repo, via MS)
- /mnt/project-files/research/engine-mechanics/special-perks-leveling.md, vehicles-and-travel.md (via MS)
- https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands
- https://mod.pub/ttw/133-tale-of-two-wastelands
- https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions
- https://thebestoftimes.moddinglinked.com/
- https://thebestoftimes.moddinglinked.com/faq.html
- https://thebestoftimes.moddinglinked.com/intro.html
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://www.taleoftwowastelands.com/
- https://taleoftwowastelands.com/viewtopic.php@t=6908
- https://taleoftwowastelands.com/viewtopic.php@t=1935
- https://taleoftwowastelands.com/viewtopic.php@t=1031
- https://taleoftwowastelands.com/viewtopic.php@t=2111
- https://steamcommunity.com/app/22380/discussions/0/522728813700378577
- https://tropedia.fandom.com/wiki/Tale_of_Two_Wastelands
- https://bloody-disgusting.com/video-games/3536003/fallout-new-vegas-mod-tale-two-wastelands-updated-total-rebuild/
- https://insider-gaming.com/?p=170979
- https://github.com/jzebedee/bsasharp/
- https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281
- https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- https://www.pcgamer.com/uk/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development/
- https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development
- https://www.dsogaming.com/?p=121487
- https://www.gamerevolution.com/news/478241-fallout-4-capital-wasteland-mod-returns
- https://www.gamerevolution.com/news/433019-fan-project-fallout-4-new-vegas-shows-progress
- https://www.nexusmods.com/dispatch/news/13916
- https://www.pcgamesn.com/fallout-4/new-vegas-mod
- https://nexusmods.com/fallout4/mods/75425
- https://github.com/terry-haire/fnv-to-fo4
- https://github.com/Mutagen-Modding/Mutagen
- https://raw.githubusercontent.com/niftools/nifxml/develop/nif.xml
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFNV.pas
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFO3.pas
- https://en.wikipedia.org/wiki/Fallout_3_downloadable_content
- https://fallout.fandom.com/wiki/Karma_(Fallout_3)
