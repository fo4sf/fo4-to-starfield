# Release, community and legal

Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/legal-policy.md, findings/distribution-community.md, findings/precedents.md.

Not legal advice. Every open legal point is a question for the owner, for Nexus staff or for a Bethesda/ZeniMax
contact. Labels: **verified** (read in a linked source or a repo file), **supported hypothesis**, **unresolved**.

## In short
- Our position rests on tolerance, not permission. Read literally, Bethesda's ToS forbids any tool "derived from or created for" its games without written authorisation, and the Starfield CK EULA allows cross-game mods only when "approved by Bethesda" (**verified**, legal-policy findings 1 and 4).
- Tolerance is real: FNV to FO4, a player-side cross-game converter, has been on Nexus since 2023, and a Nexus moderator said a mod needing both games installed "would be different" from porting (**verified**, distribution-community 3, legal-policy 10).
- The sharpest precedent is a warning: Capital Wasteland built a tool to convert FO3 audio from the player's copy and cancelled it after Bethesda staff and a lawyer flagged it, because voice acting is licensed, not owned (**verified**, precedents 5). Our `scripts/actors/codsworth_voice.py` has the same shape (FO4 `.fuz` to `.wem`).
- Four rules carry the most weight: ship no Bethesda byte or derived output; never charge or crowdfund; never bundle Bethesda tools, SFSE or Wwise; ask Bethesda and Nexus in writing before the Nexus release.
- Most uncertain: whether Bethesda would object to a cross-game converter at all (no takedown precedent verified), the voice policy, and the expectation gap ("a free FO4 remaster").
- The 3 decisions that unlock the most: (1) the voice and audio policy, including what happens to codsworth_voice.py (REL-26, REL-27); (2) whether and how we contact Bethesda and Nexus before the Nexus release (REL-30, REL-31); (3) the licence split, GPL-3 launcher or MIT launcher plus GPL-3 tools (REL-01).

## What is settled

| Item | Basis |
|---|---|
| GitHub release first, then Nexus, with a GPL-3 notice for the Mutagen-linked binaries | Owner decision (findings/BRIEF.md) |
| Silent player by default | Owner decision (BRIEF.md) |
| SFSE and the free Starfield Creation Kit MAY be required | Owner decision (BRIEF.md) |
| No game assets in Git; outreach is owner-only; only the owner triages `needs-triage` community reports | AGENTS.md (repo) |
| Repo `LICENSE` is MIT. README "Legal and license" already says: unofficial, not affiliated, MIT covers only original code and docs, do not share game-derived outputs, screenshots excluded. Missing: a GPL-3 notice for C# binaries and a third-party notices file | **verified**, repo files (legal-policy 17) |
| Mutagen, Spriggit and Synthesis are GPL-3.0; our `dotnet/*.csproj` reference Mutagen 0.55.0-alpha.67 | **verified** ([Mutagen](https://github.com/Mutagen-Modding/Mutagen), [Spriggit](https://github.com/Mutagen-Modding/Spriggit), [Synthesis](https://github.com/Mutagen-Modding/Synthesis); repo) |
| Bethesda ToS Section 9 tools clause; Section 3 "personal, private and non-commercial use only" and no derivative works; Section 2(A) derivative works need ZeniMax written consent | **verified** ([ToS](https://bethesda.net/data/tos/en.html)) |
| Starfield CK EULA: use limited to personal use with the one Product, or mods "approved by Bethesda, in connection with one or more BGS Games"; no fees; distribute only to buyers of the Product; no reproduction of the Editor | **verified** ([Steam EULA 2722710](https://store.steampowered.com//eula/2722710_eula_0)) |
| FO4 CK EULA: same structure without the cross-game clause | **verified** ([Steam EULA 1946160](https://store.steampowered.com//eula/1946160_eula_1)) |
| Bethesda Community Standards: "No Crowdfunding or Monetization mod projects is allowed."; no copyrighted or trademarked content | **verified** ([page](https://bethesda.net/en-US/news/bethesda-softworks-community-standards), 2022-02-07) |
| Nexus: copyrighted content prohibited; submissions must follow the title's licences; internet-connecting executables prohibited "unless where it is crucial"; tactful mention of donations only; no links to impermissible files | **verified** ([Nexus help 28](https://help.nexusmods.com/article/28-file-submission-guidelines)) |
| Nexus moderators: no ported assets between Bethesda games; re-creating audio from captures counts as the original asset; a mod needing both games installed "would be different" | **verified** forum posts, not policy ([7312551](https://forums.nexusmods.com/topic/7312551-fallout-4-assets-modded-into-skyrim), [9720278](https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games)) |
| SFSE may not be re-uploaded, modified or converted; so we link it, never bundle it | **verified** ([Nexus SFSE](https://www.nexusmods.com/starfield/mods/106)) |
| Cross-game converters are hosted on Nexus today: FNV to FO4 (2023 to 2024, GPL-3, needs FO4 CK, no NPCs, quests or audio) and Outfit Porter (Starfield, Oct 2026, flagged "Some suspicious files" by the scanner) | **verified** ([FNV to FO4](https://nexusmods.com/fallout4/mods/75425), [GitHub](https://github.com/terry-haire/fnv-to-fo4), [Outfit Porter](https://www.nexusmods.com/starfield/mods/18458)). No takedown found is a **supported hypothesis**, not proof of permission |
| Capital Wasteland v1 cancelled (March 2018) over audio extraction from the player's copy; restarted 2019 as a full re-voice | **verified** ([Kotaku](https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281), [PCGamesN](https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod), [PC Gamer](https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development)) |
| The repo already converts FO4 voice: `codsworth_voice.py` docstring "Codsworth's FO4 voice files -> .wav (ffmpeg) -> Starfield .wem (Wwise 2021.1.10 WwiseConsole). PC only." | **verified**, repo file |
| Our repo is already publicly discoverable via general web search | **verified by observation** (distribution-community 5) |

## Possibilities

### Licences

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Whole repo GPL-3 | One licence, no split to explain | Relicensing MIT code; contributors' consent | gamma-launcher, FNV to FO4 are GPL-3 | supported hypothesis |
| MIT repo, GPL-3 for Mutagen-linked binaries, called as separate processes | Keeps MIT for the Python pipeline | Must document the split; "mere aggregation" reading not re-read in GPL FAQ | Starfield Community Patch is MIT | supported hypothesis |
| Launcher links Mutagen in-process | Simpler code | Launcher becomes GPL-3 | none verified | supported hypothesis |
| Bundle third-party tools (texconv, BSArch) | Less install friction | Licences unread; Bethesda tools, SFSE and Wwise must never be bundled | SFSE permissions forbid it | unresolved per tool |

### Hosting

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| GitHub Releases only | Full control; source next to binary | Small audience; no virus-scan badge | settled first step | verified (owner) |
| Nexus (Starfield page) | Main audience | Cross-game rules, internet-executable rule, scanner flags | FNV to FO4, Outfit Porter | verified precedents |
| ModPub plus Discord | Fallback host | Smaller reach | TTW moved there ([ModPub](https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions)) | verified |
| Bethesda Creations | Official channel | CK EULA bars ZeniMax-owned content there; useless without the local build | none | supported hypothesis: not a channel |
| GOG-style store listing | Mainstream reach, ownership gate | Needs a publisher deal | GAMMA on GOG since Dec 2025 ([GamingOnLinux](https://www.gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install/page=1)); Fallout London on GOG | verified |

### Money

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| No donations | Lowest legal exposure | No hosting money | Skywind: "We will never charge" ([FAQ](https://tesrskywind.com/faq/)) | verified |
| Nexus Donation Points only | Tactful, platform-managed | Must follow DP rules (unread) | Nexus help 28 | verified rule, unread detail |
| Optional hosting-cost link | Small income | Nexus bans active soliciting | Microsoft rules allow optional donation pages for Microsoft Studios content | verified, scope unresolved |
| Patreon or crowdfunding | Income | Bethesda bans it; most likely takedown trigger | Fallout London Kickstarter (physical goods) is the edge case | verified rule |

### Voice and audio (legal side)

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Silent player (settled) plus subtitles-only NPCs | No audio exposure | Weak immersion | none | owner decision |
| Convert the player's own FO4 voice locally | Full original voices, no shipping | The exact Capital Wasteland pattern; voice is licensed, not owned | CW v1 cancelled | verified precedent |
| Volunteer re-voice | Clean rights | Huge effort (CW about 45,000 lines; Skywind about 300 actors) | Skywind, CW v2, F4NV | verified |
| Synthetic (AI) voice | Cheap lines | Personality rights, unions; Creations AI ban reported in press only | none | unresolved |

### Community home and support

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| GitHub Issues and Discussions only | Fits the owner-only triage rule | Players expect Discord | none | supported hypothesis |
| Own Discord with #how-to-install and #known-issues | Fast install support | Needs human moderators | GAMMA, TTW | verified |
| A channel on an existing server (Starfield Modding, Collective Modding) | No server to run | Their rules (unread) | Community Patch uses Starfield Modding Discord | verified (patch), unresolved (rules) |
| Launcher diagnostic bundle plus one support form | Cuts install support | Implementation work | Fallout London's week one was install problems | supported hypothesis |

### Dates and communication

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| No dates, only "what works now" | No missed dates | Less hype | Skywind, Cascadia | verified |
| Windows with a slip policy | Some planning signal | Slips cost trust; crunch claims | Skyblivion 2025 to 2026, Fallout London 2023 to Jul 2024 | verified |
| Public feature matrix (not yet / partial / works) | Closes the expectation gap | Upkeep | none verified | supported hypothesis |

## Questions

### Licences and code

**REL-01. Is the launcher GPL-3 (Mutagen in-process) or MIT (calls the GPL-3 tools as separate processes)?**
- Why it matters: decides the licence of the most visible binary and the wording of every release note.
- Options: relicense the whole repo GPL-3; keep MIT plus a GPL-3 tools bundle (legal-policy 12). A GPL binary can carry no "non-commercial" or "no redistribution" terms of ours.
- Answer by: GPL FAQ "mere aggregation" read; a docs/ai/decisions.md entry. Who: offline research, then owner decision.
- Blocks: Launcher, Release. Status: open. (also: legal-policy Q8)

**REL-02. How do we deliver "corresponding source" for each binary release?**
- Why it matters: GPL-3 section 6 (supported hypothesis; text not re-read).
- Options: tag plus source zip on the same GitHub release; written offer.
- Answer by: release checklist. Who: owner decision. Blocks: Release. Status: open. (also: legal-policy Q9)

**REL-03. What must the player install themselves, and how is each one checked?**
- Why it matters: Bethesda CK tools (Archive2, Papyrus compiler, ContentResources.zip), SFSE, Address Library and Wwise may not be bundled (legal-policy 11, 13, 15); texconv's licence is unread.
- Options: per-tool detection with an instructions screen; refuse to build if missing.
- Answer by: per-tool licence reads. Who: offline research. Blocks: Launcher, Release. Status: open. (also: legal-policy Q10)

**REL-04. Does Wwise's licence allow a free public tool to drive `WwiseConsole` on the player's PC, and which version must the player install?**
- Why it matters: any audio conversion depends on it; the repo uses 2021.1.10 and notes 2026.1.3 (`codsworth_voice.py`).
- Answer by: read the Wwise licence; ask Audiokinetic if unclear. Who: offline research. Blocks: People and story. Status: open. (also: legal-policy Q29)

**REL-05. Can we depend on CALUMI.Animation (LGPLv3) from MIT and GPL-3 code, and how must it ship?**
- Why it matters: LGPL needs notices and replaceable linking.
- Answer by: read its LICENSE and our linking method. Who: offline research. Blocks: Door animations, Release. Status: open. (also: legal-policy Q4)

**REL-06. Which open code from precedents can we reuse?**
- Options: BSA# (MIT, made for TTW, [bsasharp](https://github.com/jzebedee/bsasharp/)); fnv-to-fo4 (GPL-3, targets FO4, reference only) (precedents Q29).
- Answer by: licence and code read. Who: offline research. Blocks: Launcher. Status: open.

**REL-07. If we write our own SFSE plugins, under which licence do they ship, and what do SFSE's repo licence and Address Library's permissions allow?**
- Answer by: read SFSE GitHub licence (rate-limited in wave 1) and Address Library's Nexus permissions. Who: offline research. Blocks: Fallout systems. Status: open. (also: legal-policy Q19)

**REL-08. What does our Nexus permissions block say?**
- Why it matters: we may restrict re-upload of outputs, but not redistribution of GPL-3 code.
- Options: "code: MIT/GPL-3 as stated; outputs: never upload". Who: owner decision. Blocks: Release. Status: open. (also: legal-policy Q25)

### Bethesda terms and exposure

**REL-09. Does the Bethesda ToS bind Steam-only players, and does its Section 9 tools clause bind us as developers?**
- Why it matters: the clause covers our tool literally. Steam store pages link only the Steam Subscriber Agreement in our fetch (verified).
- Answer by: screenshot first-run screens of FO4 and Starfield on Steam; read the game EULA (bethesda.net/data/eula/en.html, unread). Who: PC probe, offline research, owner. Blocks: Release. Status: open. (also: legal-policy Q30)

**REL-10. Does a plugin generated on the player's PC count as a "Game Mod" under the Starfield CK EULA when it is packed with the player's Archive2 and compiled with the player's Papyrus compiler?**
- Why it matters: if yes, clause (ii) "approved by Bethesda" applies. Our pipeline calls `PapyrusCompiler.exe` and `Archive2.exe` and reads `ContentResources.zip` (verified, `scripts/mission/make_mission.py:293`, `scripts/deploy_starfield.py:155`, `scripts/convert_asset.py:5`).
- Options: accept and ask Bethesda; avoid CK tools (loose files, BSArch, MO2 2.5.2's BSA Packer which "now supports Starfield archive formats", verified [MO2 releases](https://github.com/Modorganizer2/modorganizer/releases); a third-party compiler such as Caprica, Starfield support unresolved).
- Answer by: Bethesda contact; BSArch licence; loose vs BA2 load-time measurement. Who: Bethesda contact, owner, PC probe. Blocks: All interiors, Launcher, Release. Status: open. (also: legal-policy Q5, Q6)

**REL-11. Which storefronts do we support for legal reasons as well as technical ones?**
- Why it matters: Game Pass runs under the Microsoft Services Agreement (unread); Microsoft's rules say "You can't reverse engineer our games to access the assets" ([Xbox rules](https://www.xbox.com/en-US/developers/rules), scope over Bethesda unresolved). Skyblivion rejects Epic and Game Pass copies as "encrypted and/or different" ([FAQ](https://skyblivion.com/faq)).
- Options: Steam-only v1 and say so; Game Pass later without SFSE features.
- Answer by: read the MSA and Microsoft Store Starfield EULA. Who: offline research, then owner decision. Blocks: Launcher, Release. Status: open. (also: legal-policy Q13, distribution-community Q10, precedents Q8)

**REL-12. Is a total conversion that replaces Starfield's content more exposed than an add-on planet?**
- Why it matters: it looks more like "Fallout 4 on Starfield's engine" as a product.
- Options: keep Starfield intact and add the planet; total conversion. Who: owner decision; maybe Bethesda contact. Blocks: World, Release. Status: open. (also: legal-policy Q14)

**REL-13. Do we ever publish anything on Bethesda Creations?**
- Why it matters: the CK EULA bars ZeniMax-owned content there; a Creation of only our scripts is useless without the local build.
- Who: owner decision. Blocks: Release. Status: open; supported hypothesis says no (legal-policy 8).

**REL-14. Does the launcher check ownership beyond file hashes?**
- Why it matters: CK EULA "distribute ... to users who have purchased the Product"; hashes also accept pirated copies.
- Options: hashes only (TTW-like); refuse known cracked executables. Do not ask for store credentials (Fallout London's downgrader needed a Steam login and broke on Steam Guard, verified [PC Gamer](https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/)).
- Answer by: how TTW and Wabbajack handle it. Who: offline research, owner. Blocks: Launcher. Status: open. (also: legal-policy Q12)

**REL-15. Does the launcher show an acceptance screen?**
- Why it matters: documents that the player owns both games and keeps outputs private.
- Options: one-time screen; README only. Who: owner decision. Blocks: Launcher. Status: open. (also: legal-policy Q11)

**REL-16. Is there any record of a Bethesda takedown or C&D against a local converter, as opposed to an asset port?**
- Why it matters: the single most useful precedent we lack.
- Candidates: TTW history, Morroblivion, Fallout 76 ports on Nexus, FNV to FO4 comments. Who: offline research. Blocks: Release. Status: open. (also: legal-policy Q32)

**REL-17. Should the decision record name a jurisdiction?**
- Why it matters: private-copy and interoperability rules differ (EU vs US). Owner is in the US (supported hypothesis).
- Who: owner, with a lawyer if the project grows. Blocks: Release. Status: open. (also: legal-policy Q33)

**REL-18. Does each future game (FO3, New Vegas) need its own legal check?**
- Why it matters: FO3 into a newer engine is literally Capital Wasteland; GECK EULAs are unread.
- Answer by: read the GECK EULA; restart from the audio question. Who: offline research, owner. Blocks: Multi-game. Status: open. (also: legal-policy Q31, precedents Q31)

### What may be shared

**REL-19. Can derived data (heightmaps, navmeshes, placements, animation timings measured from FO4 clips) ever ship, or is all of it generated locally?**
- Why it matters: Zaldir ruled re-creations from captures count as the original asset (legal-policy 10).
- Options: generate everything at build time (supported hypothesis default); ship only original curves made by eye.
- Answer by: owner rule; Nexus staff written answer. Blocks: Door animations, World, Release. Status: open. (also: legal-policy Q3, Q15)

**REL-20. May our own text (tutorial hints, quest notes, launcher lore) quote or paraphrase FO4?**
- Why it matters: paraphrase can be a derivative work; "Vault-Tec" is a trademark.
- Options: generate FO4-authored strings at build time from the player's files (TTW model); neutral original wording; nominative references only. Who: owner decision; include in the Bethesda letter. Blocks: New game, People and story. Status: open. (also: legal-policy Q1, Q2, Q17)

**REL-21. May users share patches and add-ons built on the generated masters, and what may they contain?**
- Why it matters: a patch that copies FO4 record data redistributes Bethesda content.
- Options: patches as local "recipes" (Synthesis-style patchers, GPL-3); records with FormID references and original data only. Nexus Collections can carry such mods after the launcher has built the base (supported hypothesis, distribution-community 1).
- Answer by: deterministic FormIDs across PCs (plan L4); a Nexus ruling. Who: Nexus contact, owner. Blocks: Release, Multi-game. Status: open. (also: legal-policy Q23)

**REL-22. How do we handle someone uploading a pre-built pack?**
- Why it matters: high likelihood; can drag the tool down with it (legal-policy risk 3).
- Options: pinned "we never host outputs" statement; a report template for Nexus; deterministic outputs so there is no reason to share. Who: owner decision. Blocks: Release. Status: open. (also: legal-policy Q26)

**REL-23. Do screenshots and videos of converted content fall under Bethesda's video policy?**
- Why it matters: they show Bethesda assets; the README already excludes screenshots from the code licence.
- Answer by: read Bethesda's video policy (unread). Who: offline research. Blocks: Release. Status: open. (also: legal-policy Q27)

**REL-24. Do release zips, crash bundles and logs pass the same no-Bethesda-bytes guard as the repo?**
- Options: extend `scripts/guard.py` to release artefacts and diagnostic bundles. Who: QA, owner. Blocks: Release. Status: open. (also: legal-policy Q28)

### Naming and trademarks

**REL-25. Do we use "Fallout", Vault Boy or Pip-Boy art in the project, launcher, UI or Nexus page?**
- Why it matters: trademark complaints are easier than copyright ones; Community Standards forbid trademarked material on Bethesda.net.
- Options: nominative "fo4-to-starfield" style name; a neutral brand; "for Fallout 4" phrasing; original neutral Pip-Boy-like UI, or FO4 UI converted locally. No precedent with "Fallout" in the name was verified as having permission.
- Who: owner decision; Bethesda contact. Blocks: Launcher, Fallout systems, Release. Status: open. (also: legal-policy Q18, Q24)

### Voice and audio policy (legal side)

**REL-26. What is the voice policy for NPCs, companions and the Vault 111 opening?**
- Why it matters: Capital Wasteland's halt was "entirely related to audio"; Bethesda staff said voice acting is licensed, so Bethesda could not grant it; PCGamesN says player-side extraction was "also deemed unworkable" (precedents 5). TTW re-encodes audio and survived, likely because both games share an engine family (supported hypothesis).
- Options: (a) convert the player's own files (CW's red flag); (b) subtitles only; (c) volunteer re-voice; (d) synthetic voice (REL-28).
- Answer by: written question to Bethesda or ZeniMax; legal opinion. Who: owner decision, then Bethesda contact. Blocks: New game, People and story, Multi-game. Status: open. (also: precedents Q1, Q16; legal-policy Q16)

**REL-27. Does `scripts/actors/codsworth_voice.py` stay a private PC test, or is it gated out of release builds until REL-26 is decided?**
- Why it matters: it converts FO4 `.fuz` to Starfield `.wem` via Wwise, which is the Capital Wasteland shape. This is an owner decision only; this file records the precedent, not a verdict.
- Options: keep as private test; gate behind a flag off by default in releases; remove from release packaging. Who: owner decision, now. Blocks: People and story, Release. Status: open. (also: precedents Q17)

**REL-28. Is any synthetic (AI) voice allowed, for gaps or for new lines?**
- Why it matters: personality rights of FO4 actors; Bethesda's Creations reportedly bans generative AI (press search results only, **unresolved**).
- Answer by: read Nexus's AI content policy and the Creations rule. Who: offline research, owner. Blocks: People and story. Status: open. (also: legal-policy Q16, precedents Q16)

**REL-29. Does converting FO4 `.lip` and face data carry the same question as audio?**
- Why it matters: Codsworth has no face; humans do. Who: offline research, owner. Blocks: People and story. Status: open. (also: precedents Q18)

### Contacting Bethesda and Nexus

**REL-30. Do we contact Bethesda/ZeniMax before the Nexus release, and what do we ask?**
- Why it matters: the Starfield CK EULA names an approval route for cross-game mods. Contact killed CW v1; Skyblivion got conditions (100% asset replacement) and later praise; Skywind is described as "officially approved"; Fallout London reported "zero correspondence" (precedents 3, 4, 5, 2).
- Options: no contact (TTW model); an informational letter; an explicit approval request covering REL-10, REL-20, REL-25, REL-26. Who: owner decision; Bethesda contact. Blocks: Release, People and story. Status: open. (also: legal-policy Q20, precedents Q23)

**REL-31. What exactly do we ask Nexus staff, and in what order?**
- Proposed: (a) is a no-assets FO4-to-Starfield converter acceptable as a "modding tool" (cite FNV to FO4); (b) is the launcher's internet use "crucial", or must the Nexus build be offline (REL-32); (c) may add-ons on generated masters be hosted (REL-21); (d) which game page and category.
- Who: owner via Nexus support. Blocks: Release. Status: open. (also: legal-policy Q21, distribution-community Q28)

**REL-32. Will the Nexus build of the launcher connect to the internet (manifests, hash tables, updates, crash reports)?**
- Why it matters: Nexus prohibits internet-connecting executables unless crucial (legal-policy 9).
- Options: offline-only Nexus build; hash table compiled into the release; a separate GitHub-hosted updater on explicit user action. Who: owner decision, then Nexus staff. Blocks: Launcher, Release. Status: open. (also: legal-policy Q7)

**REL-33. Do we contact the FNV to FO4 and Outfit Porter authors?**
- Why it matters: they solve parts of our pipeline and have already dealt with Nexus about cross-game converters. Outreach is owner-only (AGENTS.md).
- Who: owner decision. Blocks: Release. Status: open. (also: distribution-community Q27)

### Hosting and release page

**REL-34. Where do we host after GitHub, and under which Nexus game page?**
- Options: Nexus Starfield page; ModPub plus Discord as fallback (TTW); GitHub only. Who: owner, Nexus contact. Blocks: Release. Status: open. (also: precedents Q24)

**REL-35. How does the release page answer "is this legal?" and avoid reading as a remaster or a "free FO4"?**
- Options: first sentence of every page states "you must own both games; nothing is shipped; free"; a takedown contact. The Lemmy and Steam threads show remaster and takedown framing come first ([Lemmy](https://next.lemm.ee/post/12632388), [Steam](https://steamcommunity.com/app/377160/discussions/0/3059616584924796846/?l=greek)).
- Who: owner wording. Blocks: Release. Status: open. (also: precedents Q22, distribution-community Q31)

**REL-36. How do we pre-empt antivirus and scanner flags on the released executable?**
- Why it matters: Nexus flagged Outfit Porter as "Some suspicious files"; unsigned downloads get SmartScreen and "Unblock" prompts (TTW FAQ).
- Options: code signing (costs money); published hashes and a VirusTotal link; reproducible source builds. Who: owner decision. Blocks: Launcher, Release. Status: open. (also: distribution-community Q15, release part)

### Money

**REL-37. Do we accept donations at all?**
- Options: none; Nexus Donation Points only; a tactful optional hosting link. Never Patreon or crowdfunding (Community Standards).
- Who: owner decision. Blocks: Release. Status: open. (also: legal-policy Q22)

**REL-38. Is a GOG-style store listing ever a goal?**
- Options: not a goal; revisit after 1.0. Who: owner decision. Blocks: Release. Status: open. (also: distribution-community Q32)

### Community home and support

**REL-39. Where is the project's home?**
- Options: GitHub Issues and Discussions only; own Discord with install and known-issues channels; a channel on Starfield Modding or Collective Modding (rules unread).
- Answer by: ask those servers' admins. Who: owner, community contact. Blocks: Release. Status: open. (also: distribution-community Q23)

**REL-40. Who triages community reports when volume grows, given only the owner may remove `needs-triage`?**
- Options: trusted human volunteers with a triage role; AI-drafted summaries the owner approves in bulk; a known-issues auto-reply. Needs an AGENTS.md change. Who: owner decision. Blocks: Release. Status: open. (also: distribution-community Q24)

**REL-41. What is the day-one support model?**
- Why it matters: Fallout London's first week was install problems (INI overwrites, CC files, wrong `Fallout4.esm` size; [GameStar](https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html)); TTW's FAQ is mostly environment errors (quotes in paths, Controlled Folder Access, Unblock, CPU heat).
- Options: launcher writes a diagnostic bundle (hashes, plugin list, INIs, crash log) for one support form; an FAQ seeded from TTW's list. Who: owner, Implementation. Blocks: Launcher, Release. Status: open. (also: precedents Q26)

**REL-42. What must every bug report carry to be reproducible?**
- Options: cell, position and a build hash printed by the launcher; reproducible "on a new save" bar like the Community Patch ([starfieldpatch.dev](https://starfieldpatch.dev)); our report hotkey already records cell and position (docs/community/reporting-tool.md).
- Who: offline design, owner sign-off. Blocks: All interiors, Release. Status: open. (also: distribution-community Q5, Q35)

**REL-43. How do we recruit testers and specialists, and which environments must be tested before a public release?**
- Why it matters: agents cannot test other PCs, languages, Linux or Game Pass; Fallout London had about 20 testers and launched "barely playable".
- Options: tester sign-up issue form; ask in r/starfieldmods; matrix of Steam Windows English, non-English, OneDrive-redirected Documents, Proton, Steam Deck. Who: owner, community. Blocks: Release. Status: open. (also: distribution-community Q26, Q33; precedents Q6)

**REL-44. Is "all interiors" a public milestone or internal?**
- Options: closed tester beta; public GitHub pre-release; nothing public. Answer by: support capacity estimate. Who: owner decision. Blocks: All interiors, Release. Status: open. (also: distribution-community Q4)

### Contributors and succession

**REL-45. Do we accept outside human contributors, and on what terms?**
- Options: no outside PRs before 1.0; PRs with DCO sign-off or a CLA; per-asset provenance manifest (The Frontier had to strip one person's work, [PC Gamer](https://www.pcgamer.com/uk/fallout-mod-the-frontier-returns-after-stripping-out-content-from-disgraced-artist/)); credits page; existing code of conduct. Licence split (REL-01) affects the terms.
- Who: owner decision; decisions.md. Blocks: Release. Status: open. (also: distribution-community Q25, precedents Q25)

**REL-46. How do we plan succession and avoid management failure in an owner-plus-agents team?**
- Why it matters: the Community Patch is "looking for new caretakers" within about 3 years; The Frontier's rework collapsed through "poor management" and competing visions.
- Options: named caretakers and a handover rule; single owner for direction plus decisions.md; public roadmap with previews. Who: owner decision. Blocks: Release. Status: open. (also: precedents Q27)

### Dates and communication

**REL-47. What is our policy on dates?**
- Options: no dates, only "what works now" (Skywind); windows with a slip policy. Every precedent slipped. Who: owner decision. Blocks: Release. Status: open. (also: distribution-community Q29, precedents Q21)

**REL-48. How do we answer "voices, quests, companions, VATS, Far Harbor?" before those phases exist?**
- Options: a public feature matrix (not yet / partial / works); a roadmap page or no promises; a map image explaining one planet. Who: owner wording. Blocks: Release. Status: open. (also: distribution-community Q17, Q20, Q21)

**REL-49. What do we say about FO4 mods working with the port?**
- Options: "no, but mods built on our core will" (plan L2) in the first post; a later FO4-mod converter. Who: owner. Blocks: Release. Status: open. (also: distribution-community Q22)

**REL-50. Which outputs do we show publicly as video, and with what caption?**
- Options: show with "pre-alpha, no quests" caption; nothing until interiors. Legal side is REL-23. Who: owner decision. Blocks: Door animations, Release. Status: open. (also: distribution-community Q3)

**REL-51. What goes in a player changelog, and do we promise save compatibility?**
- Why it matters: GAMMA says saves are "mostly" compatible across a big update; our FormIDs change if the build changes (plan L4).
- Options: player changelog separate from the agent journal, generated from PR labels, with "new save? rebuild?" lines; no save promise before 1.0, or a save-safe flag per release.
- Answer by: determinism test plus a save loaded across two builds. Who: owner after an L4 probe. Blocks: Release, New game. Status: open. (also: distribution-community Q1, Q30)

**REL-52. What can ship first as a public release?**
- Options: a "walkable Commonwealth" release before people and story (FNV to FO4 shipped world and placements only and has an audience). Who: owner decision. Blocks: World, Release. Status: open. (also: precedents Q15)

**REL-53. What is our realistic time scale?**
- Precedents: Enderal 5 years with 14 people; Fallout London 5 years with about 100; Skyblivion and Skywind 13 years or more. Converting rather than remaking is our structural advantage (supported hypothesis).
- Answer by: hours per converted interior cell now, extrapolated. Who: owner, QA. Blocks: Release. Status: open. (also: precedents Q32)

### Localization

**REL-54. Which languages can the port support, and does it inherit them from the player's own FO4?**
- Why it matters: TTW requires English installs of both games; if our record writer keeps localized string references, a German FO4 could give a German port.
- Options: English-only v1 (TTW precedent); pass string tables through; voice per language (tied to REL-26).
- Answer by: list FO4 and Starfield language sets (unresolved in wave 1); a synthetic non-English STRINGS fixture through the converter. Who: offline research, owner. Blocks: People and story, Launcher, Release. Status: open. (also: distribution-community Q18)

**REL-55. What happens when a player's FO4 is not English?**
- Options: one hash table per language; hash language-neutral files and treat STRINGS separately; refuse (TTW). Who: offline research. Blocks: Launcher. Status: open. (also: distribution-community Q19)

## Owner decisions in this area
Recommendations only; the owner decides.
- REL-01 licence split: *recommend* MIT repo plus GPL-3 for Mutagen-linked binaries run as separate processes, pending the GPL FAQ read; least churn.
- REL-08 Nexus permissions: *recommend* "code under its stated licence; outputs must never be uploaded".
- REL-12 total conversion vs add-on: *recommend* add the planet and keep Starfield intact for now; lower exposure.
- REL-13 Creations: *recommend* no; nothing useful can live there.
- REL-15 acceptance screen: *recommend* a one-time screen; cheap evidence of intent.
- REL-20 our own text: *recommend* generate FO4 strings at build time; write only neutral original text.
- REL-22 pre-built packs: *recommend* a pinned "we never host outputs" statement plus a report template.
- REL-25 naming: *recommend* a nominative or neutral name, no Vault Boy or Pip-Boy art; trademark complaints are the easiest kind.
- REL-26 voice policy: *recommend* silent player plus subtitles for NPCs until Bethesda answers in writing; Capital Wasteland is a direct match.
- REL-27 codsworth_voice.py: *recommend* keep as a private PC test, gated out of release packaging until REL-26 is decided.
- REL-30 contact Bethesda: *recommend* a written, informational letter with specific questions before the Nexus release; the CK EULA names an approval route.
- REL-31 and REL-32 Nexus: *recommend* ask in writing, citing FNV to FO4, and plan an offline Nexus build.
- REL-33 precedent authors: *recommend* yes, owner-only outreach.
- REL-36 scanner flags: *recommend* published hashes, a VirusTotal link and source builds first; signing later.
- REL-37 donations: *recommend* none, or Nexus Donation Points only; never crowdfunding.
- REL-38 store listing: *recommend* not a goal before 1.0.
- REL-39 community home: *recommend* GitHub Issues and Discussions first, then a channel on an existing Discord.
- REL-40 triage: *recommend* AI-drafted summaries the owner approves in bulk, then trusted volunteers.
- REL-44 interiors milestone: *recommend* a closed tester beta.
- REL-45 contributors: *recommend* PRs with DCO sign-off and a per-asset provenance manifest.
- REL-46 succession: *recommend* name a second caretaker and a handover rule in decisions.md.
- REL-47 dates: *recommend* no dates; publish "what works now".
- REL-50 videos: *recommend* only with a "pre-alpha, no quests" caption.
- REL-51 saves: *recommend* no save promise before 1.0.
- REL-52 first release: *recommend* a walkable-world release before people and story, after REL-30 and REL-31.
- REL-54 languages: *recommend* English-only v1, but keep string references so other languages can follow.

## Cheapest experiments
Nothing here runs now.
1. **Licence reading pass (offline).** GPL FAQ (aggregation, object code), Wwise, DirectXTex, xEdit/BSArch, SFSE repo, Address Library permissions, CALUMI, Bethesda game EULA, Microsoft Services Agreement, Bethesda video policy, Nexus Donation Points and AI content rules. Closes or narrows REL-01, 02, 03, 04, 05, 07, 09, 11, 23, 28, 37.
2. **Repo audit (offline, read-only).** Which binaries link Mutagen in-process; every call to CK tools; whether `codsworth_voice.py` or Wwise is reachable from any release path; run `scripts/guard.py` logic over a mock release zip. Closes REL-01 (facts), REL-10 (facts), REL-24, REL-27 (facts for the owner).
3. **Precedent read (offline).** FNV to FO4's Nexus page, permissions block, comments and GitHub issues for any moderation or Bethesda contact; TTW's legal stance; any takedown history. Closes or narrows REL-16, REL-31, REL-33, REL-34.
4. **Draft the two contact letters (offline).** One for Bethesda, one for Nexus, listing the exact questions; the owner decides whether to send. Frames REL-10, 19, 20, 21, 25, 26, 30, 31, 32.
5. **Synthetic non-English STRINGS fixture (offline unittest).** Run a fake German STRINGS table through the record writer and check whether references survive. Closes REL-54 (technical part), REL-55.
6. **Determinism check (offline, then PC).** Build the same input twice and diff FormIDs; then load one save across two builds. Closes REL-21 (technical part), REL-51.
7. **PC read-only probe.** Screenshot FO4 and Starfield first-run screens on Steam for ToS or EULA prompts; list installed language files. Narrows REL-09, REL-54.

## Gaps for wave 2
- Any verified Bethesda DMCA or C&D against a local converter or asset port (Fallout 76 ports, Capital Wasteland letters, PS4 external-asset ban 2016).
- Follow-up reads blocked by HTTP 429 or budget: GNU GPL FAQ; xEdit/BSArch, SFSE repo and MO2 repo licences; Nexus collections guidelines (help article 115), Donation Points and permissions articles; TTW site legal stance; Techdirt 2025-01-03; Bethesda game EULA; Microsoft Services Agreement; Bethesda video policy; Wwise and DirectXTex licences; ModDB and GitHub acceptable-use rules.
- Bethesda Creations generative-AI rule and Nexus AI content policy (only press search results seen).
- Fallout London launch history in depth; Overwolf launcher terms (ads, data).
- Skyblivion and Skywind volunteer recruitment pages; Skywind volunteer handbook; Beyond Skyrim structure; F4NV status after 2018; Enderal Steam editions.
- Discord rules for Starfield Modding and Collective Modding; r/FalloutMods and r/starfieldmods self-promotion rules; starfieldwiki.net modding namespace.
- FO4 and Starfield language lists.
- Starfield total conversions on Nexus and Creations.

## Handed to phase files

| Question | Target |
|---|---|
| Must the Vault 111 start be reachable from the main menu without a console? (distribution-community Q2) | newgame.md |
| What does the start do if a Starfield update breaks the start-quest overrides? (precedents Q2) | newgame.md |
| Keep reusing Starfield's own door animations; record in decisions.md (precedents Q3) | door-animations.md |
| Per-file hash table for FO4 masters and BA2s before conversion (precedents Q4) | interiors.md |
| Navmesh for every interior: generated or converted? (precedents Q5) | interiors.md |
| Interior QA budget (precedents Q6; release side in REL-43) | interiors.md |
| Mod-manager output targets; `sTestFile` handling; Starfield.ccc and ContentCatalog.txt; pinning a Starfield build; update transport; CLI-first for Linux and Deck; finding My Games robustly; non-ASCII paths; Controlled Folder Access; disk and time budget (distribution-community Q6 to Q16; release side of Q15 in REL-36) | launcher.md |
| FO4 versions accepted (1.10.163 vs next-gen); deltas vs rebuild; base build vs fix updates; thread and thermal limits; own UI vs MO2 vs Overwolf; Linux and Proton (precedents Q7, Q9 to Q13) | launcher.md |
| Starfield CK required on players' PCs as a launcher check (precedents Q28); CK Papyrus compiler under Proton (distribution-community Q37) | launcher.md |
| Which Fallout systems to rebuild; SFSE lag after Starfield updates; whether any phase needs SFSE (precedents Q19, Q20; distribution-community Q36) | engine-mechanics.md |
| TTW-style worldspace merge as precedent for Far Harbor and Nuka-World (precedents Q14) | world and planet cross-cutting file (not a phase file) |
| Spriggit text plugins for diffs; two-version FO4 regression fixtures (distribution-community Q34, precedents Q30) | tooling and testing cross-cutting file (not a phase file) |

## Sources
- https://bethesda.net/data/tos/en.html
- https://www.zenimax.com/legal_terms
- https://bethesda.net/en-US/news/bethesda-softworks-community-standards
- https://store.steampowered.com//eula/2722710_eula_0
- https://store.steampowered.com/app/2722710/Starfield_Creation_Kit/
- https://store.steampowered.com//eula/1946160_eula_1
- https://store.steampowered.com/app/1946160/
- https://store.steampowered.com/app/377160/
- https://store.steampowered.com/app/1716740/
- https://en.uesp.net/wiki/Tes5Mod:EULA
- https://en.uesp.net/wiki/Skyrim_Mod:Verified_Creations
- https://www.xbox.com/en-US/developers/rules
- https://help.nexusmods.com/article/28-file-submission-guidelines
- https://forums.nexusmods.com/topic/7312551-fallout-4-assets-modded-into-skyrim
- https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games
- https://www.nexusmods.com/starfield/mods/106
- https://github.com/Mutagen-Modding/Mutagen
- https://github.com/Mutagen-Modding/Spriggit
- https://github.com/Mutagen-Modding/Synthesis
- https://github.com/ModOrganizer2/modorganizer/releases/tag/v2.5.0rc2
- https://github.com/Modorganizer2/modorganizer/releases
- https://www.nexusmods.com/site/mods/634
- https://forums.nexusmods.com/topic/13458887-starfield-extension-has-been-updated-to-support-load-ordering-and-pluginstxt
- https://wiki.wabbajack.org/user_documentation/Supported%20Games%20and%20Mod%20Managers.html
- https://www.nexusmods.com/games/starfield/collections
- https://github.com/oleh5230/Stalker_GAMMA
- https://github.com/Mord3rca/gamma-launcher
- https://github.com/Mord3rca/gamma-launcher/issues/185
- https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/lzvuf8f/?context=3
- https://www.gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install/page=1
- https://nexusmods.com/fallout4/mods/75425
- https://github.com/terry-haire/fnv-to-fo4
- https://www.nexusmods.com/starfield/mods/18458
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://thebestoftimes.moddinglinked.com/intro.html
- https://thebestoftimes.moddinglinked.com/faq.html
- https://taleoftwowastelands.com/viewtopic.php@t=1031
- https://taleoftwowastelands.com/viewtopic.php@t=2111
- https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions
- https://github.com/jzebedee/bsasharp/
- https://www.nexusmods.com/codevein/news/14877
- https://starfieldpatch.dev
- https://forums.nexusmods.com/topic/13203033-helpful-links-references-and-news/page/36
- https://redlib.belloworld.it/r/starfieldmods
- https://steamcommunity.com/app/377160/discussions/0/3059616584924796846/?l=greek
- https://next.lemm.ee/post/12632388
- https://en.wikipedia.org/wiki/Fallout:_London
- https://www.techspot.com/community/topics/fallout-london-was-ready-for-launch-until-bethesdas-buggy-next-gen-update-broke-it.285631/
- https://www.pcgamesn.com/fallout-london/epic-games-store
- https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/
- https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html
- https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- https://en.wikipedia.org/wiki/Skyblivion
- https://skyblivion.com/?p=10677
- https://skyblivion.com/faq
- https://hitmarker.net/news/oblivion-in-skyrim-mod-skyblivion-delayed-to-2026-to-provide-additional-development-time-1591206
- https://frvr.com/blog/news/former-skyblivion-dev-accuses-leads-of-rushing-the-long-in-development-mod
- https://en.wikipedia.org/wiki/Skywind
- https://tesrskywind.com/faq/
- https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/
- https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281
- https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development
- https://www.gamerevolution.com/news/478241-fallout-4-capital-wasteland-mod-returns
- https://www.gamerevolution.com/news/433019-fan-project-fallout-4-new-vegas-shows-progress
- https://fallout.wiki/wiki/Mod:Fallout:_The_Frontier
- https://www.pcgamer.com/uk/fallout-mod-the-frontier-returns-after-stripping-out-content-from-disgraced-artist/
- https://www.gfinityesports.com/article/fallout-nuevo-mexico-modder-lessons-learned-from-frontier
- https://www.pcgamesn.com/fallout-cascadia/fan-game-update
- https://en.wikipedia.org/wiki/Enderal
- Search results only, not read (unverified): https://www.pcgamesn.com/skyrim/mods-creations-ai , https://insider-gaming.com/bethesda-skyrim-creation-mods-ai/
- Repo files: LICENSE, README.md, AGENTS.md, dotnet/*.csproj, scripts/actors/codsworth_voice.py, scripts/actors/codsworth_inventory.py, scripts/mission/make_mission.py, scripts/deploy_starfield.py, scripts/convert_asset.py, src/fo4sf/textures.py, docs/community/reporting-tool.md
