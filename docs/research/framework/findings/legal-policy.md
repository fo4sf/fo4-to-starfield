# Legal and policy ground for a no-assets cross-game conversion tool

Written 2026-10-19 by legal-policy (Claude-cloud research agent) for the framework. Not legal advice: every open point is
framed as a question for the owner, for Nexus staff or for a Bethesda/ZeniMax contact. Builds on
`/mnt/project-files/research/next-phase/launcher-gamma-model-and-community-tools.md` section 2 and does not repeat it.
Labels: **verified** (read in the linked source or a repo file), **supported hypothesis**, **unresolved**.

**Research limits this session (say so up front):** the shared web-search budget ran out after a few searches, and the
fetch proxy rate-limited (HTTP 429) the pages for xEdit/BSArch, the SFSE GitHub repo, MO2's repo, the GNU GPL FAQ,
Nexus's collections guidelines, the TTW site and the Techdirt article. Those items are marked **unresolved** and listed
in "Follow-up reads" at the end. No DMCA precedent could be verified this session.

**Bottom line.** The binding texts are stricter than community practice. Read literally, Bethesda's Terms of Service
forbid creating or distributing *any* tool "derived from or created for" its games without written authorisation, and
both Creation Kit EULAs limit mods to the one game they ship with, with cross-game mods ("one or more BGS Games") only
when "approved by Bethesda". At the same time, the entire modding ecosystem (xEdit, F4SE/SFSE, Mutagen, MO2, TTW) lives
outside those literal terms and is tolerated, and a Nexus moderator has said a mod that requires the player to own both
games "would be different" from porting assets. So our position rests on tolerance, not on a permission, exactly like
TTW. That makes four things load-bearing: (1) never ship any Bethesda byte or any output derived from one, (2) never
charge or crowdfund, (3) do not bundle Bethesda's own tools (Archive2, Papyrus compiler, ContentResources.zip) or SFSE,
make the player install them, and (4) ask Bethesda and Nexus in writing before the Nexus release, because the
Starfield CK EULA explicitly names a Bethesda-approval route for cross-game mods. The GPL-3 obligation from Mutagen is
real but easy: ship the C# binary as GPL-3 with its source; the MIT repo can stay MIT. A new Nexus rule matters for the
launcher design: executables that connect to the internet are prohibited on Nexus "unless where it is crucial for the
functioning of the mod/utility", so a GAMMA-style auto-downloader must justify that or ship without it on Nexus.

## Findings

### A. Bethesda / ZeniMax terms

1. **ToS, tools clause (verified).** Bethesda's Terms of Service, Section 9 ("Your Use of the Services"), read in four
   consecutive pieces: "You acknowledge that You do not have the right to create, publish, distribute, or create
   derivative" / "works from or use any software programs, utilities, applications, emulators, or tools" / "derived from
   or created for certain Content (such as Game(s)), except as authorized in writing" / "by an authorized ZeniMax
   representative." ([ToS](https://bethesda.net/data/tos/en.html)). "Services" is defined to include Games: "(together
   with Content, Games and Software collectively referred to as "Services")" (verified, same). Read literally this
   covers our converter, the launcher, and also xEdit, SFSE, Mutagen and MO2. **Supported hypothesis:** ZeniMax does not
   enforce it against free, non-commercial, no-asset modding tools; the evidence is the long public life of those tools
   (SFSE has its own Nexus page with hundreds of dependent mods, verified below), not any written waiver. **Unresolved:**
   whether a player who bought Fallout 4 or Starfield on Steam, and never accepted the Bethesda.net ToS, is bound by it
   (the Steam store pages for both games link only the Steam Subscriber Agreement in our fetch, verified:
   [FO4 store](https://store.steampowered.com/app/377160/), [Starfield store](https://store.steampowered.com/app/1716740/)).
2. **ToS, licence and derivative works (verified).** Section 3 grants a licence "for Your personal, private and
   non-commercial use only" and bars users to "(c) create any derivative works based upon any Services"; Section 2(A)
   bars reproducing or preparing "derivative works" of Content "unless You obtained the express written consent of an
   authorized representative of ZeniMax" ([ToS](https://bethesda.net/data/tos/en.html)). A converted Commonwealth is a
   derivative work of Fallout 4 by any ordinary reading (supported hypothesis); our defence is that it is made by the
   owner of the copy, for private use, and never distributed. Whether private, on-PC derivation is permitted under the
   game EULA is **unresolved** (the per-game EULA at `bethesda.net/data/eula/en.html`, cited in our README, was not read
   this session).
3. **ToS, mods (verified).** Section 2(D) defines a Game Mod as "downloadable, user-generated Content developed or
   created by You or a third party using an Editor Tool", says mods need the separate Editor EULA, and says "ZeniMax does
   not endorse, sponsor, guarantee or approve any Game Mods" ([ZeniMax legal terms](https://www.zenimax.com/legal_terms)).
   Section 2(B): users may not submit UGC "that is copyrighted, protected by trademark or trade secret law" without rights
   or written permission (verified, [ToS](https://bethesda.net/data/tos/en.html)).
4. **Starfield Creation Kit EULA (verified,** [Steam EULA 2722710](https://store.steampowered.com//eula/2722710_eula_0)**):**
   - Scope: "All uses of the Editor are limited to:" "(i) Your personal non-commercial use solely in connection with the
     Product" or "(ii) The creation of Game Mods, approved by Bethesda, in connection with one or more BGS Games". The
     Product is "the ZeniMax computer game with which the Editor is intended for use".
   - No fees: "You will not charge or require, directly or indirectly, a fee or other consideration for others to
     download," (exception: Creations Paid Content under Bethesda's provider agreement).
   - Distribution: "You further agree that You are only permitted to distribute the Game Mods to users who have
     purchased the Product", through "authorized and legitimate distribution channels."
   - Third parties: "Your Game Mods must not infringe or misappropriate any intellectual property or personal right of
     any third party." and "You may not distribute anything owned by ZeniMax or made available by a third party on the
     Bethesda Creations unless ZeniMax specifically agree to it."
   - Redistribution of the Editor: "Any use or reproduction of the Editor not expressly authorized by the terms of this
     Agreement prohibited." The Editor is "THIS CREATION KIT™ SOFTWARE EDITOR TOOL AND RELATED DOCUMENTATION"; the EULA
     does not name Archive2, the Papyrus compiler or ContentResources.zip (verified absence in the fetched text).
   - Mod ownership: "You are the owner of Your Game Mods" with a perpetual, royalty-free, non-exclusive licence granted to
     ZeniMax. Termination: ZeniMax "may terminate this Agreement at any time for any reason or no reason". No date given.
   - **Reading for us (supported hypothesis):** clause (ii) is the only text we found that contemplates a mod spanning
     more than one Bethesda game, and it requires Bethesda's approval. Clause (i) ties personal use to the single
     Product. Whether our build counts as "use of the Editor" at all is **unresolved**: we write plugins with Mutagen,
     not the CK, but the pipeline calls the CK-shipped `PapyrusCompiler.exe` and `Archive2.exe` and reads
     `Tools\ContentResources.zip` (verified in repo: `scripts/mission/make_mission.py:293`,
     `scripts/deploy_starfield.py:155`, `scripts/convert_asset.py:5`).
5. **Fallout 4 Creation Kit EULA (verified,** [Steam EULA 1946160](https://store.steampowered.com//eula/1946160_eula_1)**):**
   same structure without the cross-game clause: mods "for non-commercial use solely in connection with the Product";
   "You agree that You will not charge or require, directly or indirectly, a fee"; "only permitted to distribute the Game
   Mods to users who have purchased the Product"; "Its component parts may not be separated for use on more than one
   computer." The Skyrim SE CK EULA as transcribed by UESP has the same clauses (verified,
   [UESP Tes5Mod:EULA](https://en.uesp.net/wiki/Tes5Mod:EULA)). We do not require the FO4 CK, so this binds us only if a
   future step does (for example `xWMAEncode.exe` from FO4's `Tools\Audio`, probed in
   `scripts/actors/codsworth_inventory.py:122`, which ships with the FO4 CK install; supported hypothesis on its origin).
6. **Bethesda Community Standards (verified,** [page](https://bethesda.net/en-US/news/bethesda-softworks-community-standards)**,
   published 2022-02-07):** "No Crowdfunding or Monetization mod projects is allowed.", tied to the EULA's "No Fees of
   Use"; mods using copyrighted or trademarked content are not allowed; ports of other authors' mods after 2023-03-12 need
   public proof of permission; "Our standards cover ZeniMax/Bethesda-owned brands." This governs Bethesda.net/Creations
   uploads, but it is also the clearest public statement of Bethesda's stance on crowdfunding (Patreon-style) mod
   projects.
7. **Microsoft Game Content Usage Rules (verified,** [Xbox rules](https://www.xbox.com/en-US/developers/rules)**, "Last
   Updated: January 2015"):** "You can't reverse engineer our games to access the assets"; "you can't sell or otherwise
   earn any compensation from your Item"; "You may use the Item on a page where you ask for optional donation requests."
   They cover games "published and owned by Microsoft Studios" and do not mention Bethesda or mods. Whether they apply to
   Bethesda titles after the 2023 acquisition is **unresolved**; Bethesda's own ToS and EULAs are the closer text. The
   Microsoft Services Agreement (relevant to Game Pass / Xbox-app Starfield players) was **not read** this session.

### B. Bethesda Creations
8. **Creations are not a channel for us (supported hypothesis, from finding 4).** The CK EULA bars distributing
   "anything owned by ZeniMax ... on the Bethesda Creations unless ZeniMax specifically agree to it", and the Community
   Standards ban copyrighted content and monetisation. A free Creation containing only our original Starfield-side
   scripts would technically be possible, but it would be useless without the locally generated build and would invite
   the question "where does the content come from" on Bethesda's own platform. Verified Creations (paid, since
   2023-12-05) pay royalties and are vetted by Bethesda (verified,
   [UESP Verified Creations](https://en.uesp.net/wiki/Skyrim_Mod:Verified_Creations)); the page has no rule on
   other-game assets (verified absence).

### C. Nexus Mods
9. **File Submission Guidelines (verified,** [Nexus help 28](https://help.nexusmods.com/article/28-file-submission-guidelines)**):**
   - "User submissions which include copyrighted content, be it game files or images, are prohibited".
   - "Submissions must adhere to the licences and agreements associated with the modified or featured title(s)." (So the
     CK EULA and ToS questions above are also Nexus questions.)
   - **New and important for the launcher:** "Files (especially executables) that connect to the internet to download or
     send information and/or files are prohibited" "unless where it is crucial for the functioning of the mod/utility."
     A GAMMA-style launcher that fetches add-ons, update manifests or hash tables, or sends crash reports, needs that
     exception or an offline mode for its Nexus build.
   - Donations: "We allow for a tactful discussion of donations and endorsements"; "Actively soliciting either donations
     or endorsements, however, is prohibited"; content must conform to the Donation Point System rules.
   - "Providing links to external sources for files that would not be permissible to host" is listed as not allowed. A
     Nexus page must therefore never link to a place where converted output can be downloaded.
   - "Public mod pages should contain only functional mod files, modding tools or modding guides." (A converter is a
     modding tool.)
   - The article has no rule on installers that build from the user's own game files and none on cross-game porting
     (verified absence in this article).
10. **Moderator rulings on cross-game content (verified, forum posts):**
    - Jannifer (Moderator, 2019-01-14): "Bethesda does not allow their assets to be ported between games, even if they're
      both Bethesda games." and "Now, if your mod required the user to have both SSE and FO4 installed" "so that the items
      can be cross referenced, that would be different." ([forum 7312551](https://forums.nexusmods.com/topic/7312551-fallout-4-assets-modded-into-skyrim)).
      This is the closest public Nexus statement to our model; it is a moderator's forum post, not policy.
    - Zaldir (Moderator, 2021-03-03): "Using assets from other Bethesda games is not allowed unless you have permission."
      "That means you can't use direct assets." "And Bethesda rarely gives permission for such things." Re-creating
      audio from video captures "is essentially the same as just using the original audio assets."
      ([forum 9720278](https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games)).
      This also rules out "recorded from the game" workarounds for voice or music.
11. **SFSE's own permissions (verified,** [Nexus SFSE page](https://www.nexusmods.com/starfield/mods/106)**):** "You are not
    allowed to upload this file to other sites under any circumstances", not allowed to modify, not allowed "to convert
    this file to work on other games", and not allowed to earn Donation Points "if they use my assets". So the launcher
    must never bundle or mirror SFSE; it can detect it and link to its page. (SFSE GitHub licence not read, rate-limited.)

### D. Licences of code we link or might bundle
12. **GPL-3 from Mutagen (verified licence, supported hypothesis on scope).** Mutagen, Spriggit and Synthesis are GPL-3.0
    (verified, GitHub "About" panels: [Mutagen](https://github.com/Mutagen-Modding/Mutagen),
    [Spriggit](https://github.com/Mutagen-Modding/Spriggit), [Synthesis](https://github.com/Mutagen-Modding/Synthesis));
    the NuGet package is GPL-3.0-only (verified in the prior note). Our `dotnet/*.csproj` reference
    `Mutagen.Bethesda.Fallout4` and `Mutagen.Bethesda.Starfield` 0.55.0-alpha.67 (verified, repo). Consequences when we
    ship the compiled C# tools (supported hypothesis from the GPL-3 text, which we could not re-read this session):
    - The shipped .NET assemblies that reference Mutagen are a covered work and go out under GPL-3 with the licence text,
      the complete corresponding source of that exact build (including the build scripts), and no added restrictions.
    - MIT code may be included in them; the MIT repo can stay MIT, but the release notes must say the binary is GPL-3.
    - The Python pipeline calls the C# tools as separate processes; that is commonly treated as aggregation, not one
      combined program (supported hypothesis; check the GPL FAQ "mere aggregation" entry).
    - **A trap:** "no further restrictions" means the GPL binary cannot carry our own "non-commercial only" or "no
      redistribution" terms. The non-commercial obligation must live in Bethesda's terms, not in our licence.
    - If the launcher itself (C#?) links Mutagen in-process, the launcher becomes GPL-3 too.
13. **Bethesda tools must be the player's own (verified clause, supported hypothesis on scope).** Archive2, the Papyrus
    compiler and ContentResources.zip come with the Starfield CK; the CK EULA forbids any "reproduction of the Editor not
    expressly authorized". The launcher must locate them in the player's own CK install and refuse with instructions if
    absent. The Steam CK page confirms the CK is a separate free download with its own third-party EULA (verified,
    [Steam CK](https://store.steampowered.com/app/2722710/Starfield_Creation_Kit/), released 2024-06-09).
14. **Compiled Papyrus (supported hypothesis).** `.pex` compiled by the player's compiler from *our original* `.psc`
    source are our work and can ship; `.pex` derived from Fallout 4's scripts (decompiled or translated) are derived from
    Bethesda content and must be generated on the player's PC only. Shipping our own `.psc` that `import` or extend
    Starfield base scripts is ordinary mod practice; shipping Bethesda's `.psc` sources is not.
15. **Audio encoder (unresolved, new).** The repo already uses Audiokinetic's `WwiseConsole` to make `.wem`
    (`scripts/actors/codsworth_voice.py:1`, "Wwise 2021.1.10 WwiseConsole"; line 101 notes Wwise 2026.1.3). Wwise is
    proprietary third-party software; its licence (free tiers, redistribution of the console, use in a public tool) was
    not read. Treat it like the CK: the player installs it, we never ship it. `texconv` (DirectXTex) is used for textures
    (`src/fo4sf/textures.py:210`); its licence was not re-read (supported hypothesis: MIT, but verify before bundling).
16. **Other tools (status of evidence).** MO2 GPLv3 (verified in the prior note). xEdit/BSArch, SFSE repo, Wabbajack
    (prior note: GPLv3 code, CC BY-NC-SA 4.0 modlists), NifSkope fork, PyNifly, CALUMI.Animation (LGPLv3 per
    `docs/handoff-archive/2026-10-07-codex-history.md:366`), fo76utils (MIT per `docs/terrain/source-patch.md:10`):
    licences other than these were **unresolved** this session.

### E. Repo's own position (verified, repo files)
17. `LICENSE` is MIT, "Copyright (c) 2026 fo4-to-starfield contributors". `README.md` ("Legal and license") already
    says the project is unofficial, not affiliated with Bethesda or ZeniMax, that MIT covers only original code and docs,
    "not ... Bethesda software, game assets, trademarks, screenshots, or user-generated outputs", and tells users not to
    share game-derived outputs. It also states in-game screenshots depict Bethesda visuals and are excluded from the
    code licence. Missing: any GPL-3 notice for C# binaries, and a third-party notices file.

## Precedents and what they teach us

| Precedent | What we could verify | Lesson |
|---|---|---|
| Nexus moderator, 2019 | "if your mod required the user to have both SSE and FO4 installed ... that would be different" (verified, finding 10) | Our model (player owns both, builds locally) is the case Nexus staff treat differently from porting. Get it in writing for *our* page before uploading |
| SFSE on Nexus | Strict no-reupload, no-modify, no-convert permissions (verified, finding 11) | Dependencies are linked, never bundled. Mirror this in our own permissions: we can set "no re-upload of the converter" if we want, but must not add restrictions on the GPL binary |
| TTW, Wabbajack, GAMMA | Prior note (section 1): build from player's own files, ship no content | The model works in practice; no published Bethesda permission. TTW's own site is the fallback host (not re-read this session) |
| Bethesda Community Standards 2022 | "No Crowdfunding or Monetization mod projects is allowed." (verified) | A Patreon for the project is the single most likely trigger for a takedown; keep any donation link tactful and for hosting only, or have none |
| Bethesda CK EULA (Starfield) | Cross-game mods only "approved by Bethesda" (verified) | There is a named approval path. Asking is cheap; a "no" changes little since tolerance is already the basis, but a "yes" removes the main risk |
| DMCA / takedowns of Bethesda ports | **Unresolved**: no case verified this session (search budget exhausted). Candidates to check: Fallout 76 asset ports removed from Nexus, the "Capital Wasteland" FO3-in-FO4 project's switch to remade assets, Skyblivion/Skywind's remake-only policy, PS4 external-asset ban (2016) | Every remake that survived shipped remade assets; we instead ship none and convert locally. Need at least one verified example of how Bethesda treated a *local converter* |

## Risks

1. **Bethesda objects to a cross-game converter (low-to-medium likelihood, high impact).** The ToS tools clause and CK
   EULA clause (ii) give ZeniMax a contractual basis at any time. Likelihood is reduced by no assets, no money, no
   "Fallout" branding and a polite advance contact; it rises with publicity (a viral "Fallout 4 in Starfield" video) and
   with anything that looks like it competes with a Bethesda product (a Fallout 4 remaster or a Fallout Starfield-engine
   release would raise it sharply; supported hypothesis).
2. **Nexus refuses or removes the page (medium).** Grounds available to them: cross-game content policy, the "must adhere
   to the licences ... of the title" rule, and the internet-connecting executable rule. GitHub-first (already settled)
   limits the damage.
3. **Users share outputs (high likelihood, medium impact).** Someone will upload a converted build or a "pre-built
   pack". That is exactly what Nexus and Bethesda prohibit and it can drag the tool down with it. Mitigations: deterministic
   outputs so there is no reason to share, clear text, quick reporting to Nexus, a "we never host outputs" statement.
4. **GPL non-compliance (low likelihood, easy to fix).** Shipping the C# binary without source/licence text, or adding
   our own restrictions to it.
5. **Accidental asset leak in our own repo or release (low, high impact).** Screenshots, test fixtures, crash dumps,
   logs with FO4 strings, or a generated `.esm` committed by mistake. `scripts/guard.py` exists for this; release
   artefacts need the same guard.
6. **Trademark complaint about naming (low-to-medium).** A launcher called "Fallout ..." with Vault Boy art invites a
   trademark complaint more easily than a copyright one; the Community Standards already forbid trademarked material on
   Bethesda.net.
7. **Third-party licence surprises (medium).** Wwise and the CK tools cannot be bundled; if the build depends on them, the
   player install friction rises and must be designed for.

## Questions for the framework

### New game (Vault 111 start)
1. **Can the new-game start reuse FO4 intro text, holotapes and dialogue lines if they are generated on the player's PC?**
   Why: the start is mostly FO4-authored strings and voice. Options: generate all at build time (TTW model); write
   original placeholder text in the repo. Evidence: ToS Section 3/2(A) bar derivative works (finding 2), but nothing is
   distributed. Who: owner decision; ask Bethesda in the contact letter (question 30).
2. **Are any original texts we write for the start (tutorial hints, launcher-side lore) allowed to quote FO4 names?**
   Why: names like "Vault-Tec" are trademarks. Options: neutral wording; nominative references only. Who: owner.

### Door animations
3. **May we ship hand-made animation data that is measured from FO4 clips (timings, curves) rather than the clips?**
   Why: Zaldir's ruling treats re-creations from captures as the original asset (finding 10). Options: derive at build
   time from the player's files; ship only original curves made by eye. Evidence: a written answer from Nexus staff.
   Who: Nexus contact.
4. **Can we depend on CALUMI.Animation (LGPLv3) from MIT and GPL-3 code, and how must it ship?** Why: LGPL needs
   replaceable linking and notices. Evidence: read its LICENSE and our linking method. Who: offline research.

### All interiors
5. **Does a generated interior plugin, made on the player's PC, count as a "Game Mod" under the Starfield CK EULA when
   it is archived with the player's Archive2 and uses scripts compiled with the player's Papyrus compiler?** Why: if yes,
   clause (i) "solely in connection with the Product" and clause (ii) "approved by Bethesda ... one or more BGS Games"
   apply (finding 4). Options: avoid CK tools entirely (loose files, BSArch, a third-party Papyrus compiler such as
   Caprica: unresolved whether it supports Starfield); accept and ask Bethesda. Who: Bethesda contact; owner.
6. **Do we need loose files instead of BA2 to keep Archive2 out of the pipeline?** Why: performance vs. licence clarity.
   Evidence: measured load times with loose vs. BA2 (tooling), BSArch's licence (offline). Who: PC probe plus research.

### Launcher
7. **Will the launcher download anything (add-on manifests, hash tables, updates, crash reports)?** Why: Nexus prohibits
   internet-connecting executables unless crucial (finding 9). Options: offline-only Nexus build; hash table compiled
   into the release; downloads only via explicit user action in a separate updater hosted on GitHub. Evidence: a
   written Nexus ruling. Who: owner decision, then Nexus staff.
8. **Is the launcher's code GPL-3 (links Mutagen in-process) or MIT (calls the GPL tools as a separate process)?** Why:
   decides the licence of the most visible binary (finding 12). Options: relicense the whole repo GPL-3 for simplicity;
   keep MIT plus a GPL-3 `tools/` bundle. Evidence: GPL FAQ on aggregation; a decision record. Who: owner;
   docs/ai/decisions.md entry.
9. **How do we deliver "corresponding source" for each binary release?** Why: GPL-3 section 6. Options: tag + source zip
   attached to the same GitHub release; written offer. Who: owner; release checklist.
10. **What does the launcher require the player to install themselves, and how is each checked?** List: both games,
    all FO4 DLC, Starfield CK (Archive2, compiler, ContentResources.zip), Wwise (if audio conversion stays), texconv,
    SFSE and Address Library (if used). Why: none of these may be bundled (findings 11, 13, 15). Evidence: per-tool
    licence reads. Who: offline research.
11. **Should the launcher show an acceptance screen?** Why: the player, not us, accepts Bethesda's terms; a screen saying
    "you own both games, output is for your personal use, do not share it" documents intent. Options: one-time screen;
    README only. Who: owner.
12. **Does the launcher verify ownership beyond file hashes (e.g., Steam/Xbox licence)?** Why: the CK EULA's
    "distribute ... to users who have purchased the Product" and anti-piracy optics; hash checks also accept pirated
    copies. Options: hashes only (TTW-like); refuse known cracked executables. Evidence: how TTW and Wabbajack handle it.
    Who: offline research; owner.
13. **Which Starfield storefronts do we support (Steam, Xbox app / Game Pass)?** Why: Game Pass copies run under the
    Microsoft Services Agreement and a different file layout; Microsoft's Game Content Usage Rules ban reverse
    engineering games to access assets (finding 7). Evidence: read the MSA and the Microsoft Store Starfield EULA.
    Who: offline research.

### World and planet
14. **Is a single-planet world that replaces Starfield's content, rather than adding to it, more exposed than an
    add-on?** Why: it looks like "Fallout 4 on Starfield's engine" as a product. Options: keep Starfield's game intact
    and add the planet; total conversion. Who: owner; possibly Bethesda contact.
15. **Can heightmaps, navmeshes and object placements be shipped as data if they are re-derived (not copied)?** Why: they
    are the FO4 world layout, so they are derived content. Supported hypothesis: no, they stay local. Who: owner rule;
    Nexus staff.

### People and story
16. **Voice: are converted FO4 voice files acceptable locally, and is any AI voice extension allowed?** Why: Bethesda's
    Creations programme bans generative AI per press reports (search result only, **unresolved**: PCGamesN, Insider
    Gaming), and AI voice of FO4 actors raises personality-rights issues beyond copyright. Options: silent player
    (settled), only original-actor lines converted locally, no AI voices. Who: owner decision; read Nexus's AI content
    policy.
17. **Can we ship English-only original text (quest notes, objective text) that paraphrases FO4 quests?** Why:
    paraphrase can still be a derivative work. Options: generate quest text at build time from the player's strings.
    Who: owner.

### Fallout systems
18. **Can we ship original UI art for a Pip-Boy-like interface without Vault Boy or Pip-Boy trademarks?** Why: these are
    the most recognisable Bethesda trademarks. Options: convert FO4's UI locally; original neutral UI. Who: owner;
    Bethesda contact.
19. **If SFSE plugins are needed for VATS or the workshop, do we ship our own DLLs, and under which licence?** Why: our
    own SFSE plugin is our code; SFSE itself and Address Library must be linked, not bundled (finding 11). Evidence:
    read SFSE's GitHub licence and Address Library's Nexus permissions. Who: offline research.

### Release and community
20. **Do we contact Bethesda/ZeniMax before release, and what do we ask?** Why: Starfield CK EULA clause (ii) names a
    Bethesda approval route for cross-game mods (finding 4). Options: no contact (TTW model); an informational letter;
    an explicit request for approval. Evidence: any answer. Who: owner; ZeniMax legal / Bethesda community team.
21. **What exactly do we ask Nexus staff, and in what order?** Proposed: (a) is a no-assets FO4-to-Starfield converter
    that runs on the player's PC acceptable as a "modding tool"; (b) is the launcher's internet use "crucial" or must
    the Nexus build be offline; (c) can user-made add-ons that depend on generated masters be hosted, and what may they
    contain; (d) under which game page (Starfield) and category. Who: owner via Nexus support.
22. **Do we accept donations at all?** Why: Bethesda bans crowdfunded or monetised mod projects; Nexus allows tactful
    mention only; Microsoft allows optional donations for Microsoft Studios content (findings 6, 7, 9). Options: none;
    Nexus Donation Points only; a hosting-cost link. Who: owner.
23. **May users share load-order patches and add-ons built on the generated masters, and what may they contain?** Why:
    a healthy community needs patches; a patch that copies FO4 record data (names, text, values) redistributes
    Bethesda content, unlike same-game patches whose masters every user owns from the publisher. Options: patches as
    "recipes" applied locally (Synthesis-style patchers, GPL-3, finding 12); records with FormID references and
    original data only. Evidence: deterministic FormIDs across PCs (plan L4); a Nexus ruling. Who: Nexus staff; owner.
24. **Do we use "Fallout" in the project, launcher or Nexus page name?** Why: trademark. Precedents with "Fallout" in
    the name exist as mods (Fallout London is cited in the prior note) but none verified this session as having
    permission. Options: "fo4-to-starfield" style nominative name; a new neutral brand; "for Fallout 4" phrasing.
    Who: owner; Bethesda contact.
25. **What does our own permissions block on Nexus say?** Why: Nexus lets authors set re-upload/modify/convert
    permissions (see SFSE, finding 11), but for the GPL-3 binary we cannot forbid redistribution of the code. Options:
    "code: MIT/GPL-3 as stated; outputs: never upload". Who: owner.
26. **How do we handle someone uploading a pre-built pack?** Why: risk 3. Options: report template to Nexus; a pinned
    statement; launcher refuses to load builds whose hashes it did not produce (unclear value). Who: owner.

### Tooling and testing
27. **Do screenshots and videos of converted content in the README, issues and Nexus page fall under Bethesda's video
    policy?** Why: they show Bethesda assets; Bethesda's Community Standards encourage videos and point to a video
    policy (not read). Evidence: read the video policy. Who: offline research.
28. **Are test fixtures, golden files and logs free of Bethesda bytes?** Why: risk 5; release zips too. Options: extend
    `scripts/guard.py` to release artefacts and crash-report bundles. Who: owner/QA.
29. **Does Wwise's licence permit a free public tool to drive `WwiseConsole` on the player's machine, and which Wwise
    version must the player install?** Why: audio conversion depends on it (finding 15). Who: offline research, then
    Audiokinetic if unclear.

### Cross-cutting
30. **Does the Bethesda ToS bind Steam-only players, and does its Section 9 tools clause bind us as developers?** Why: the
    clause covers our tool literally (finding 1). Evidence: whether Starfield/FO4 on Steam require accepting the
    Bethesda.net ToS or a game EULA at first launch (PC probe: screenshot the first-run screens). Who: PC probe; owner.
31. **Does adding FO3/New Vegas later change anything?** Why: FO3/FNV CK (GECK) EULAs and their Steam/GOG versions;
    TTW already converts FO3 into FNV. Evidence: read the GECK EULA. Who: offline research.
32. **Is there a record of a Bethesda takedown or C&D against a local converter (not an asset port)?** Why: the single
    most useful precedent we lack. Candidates: TTW history, Morroblivion, Fallout 76 asset ports on Nexus, Capital
    Wasteland. Who: offline research next session (search budget ran out).
33. **Should the decision record cover jurisdiction?** Why: interoperability and private-copy exceptions differ (EU
    software directive vs. US fair use); the owner is in the US (Mountain time per README, supported hypothesis). Who:
    owner, with a lawyer if the project grows.

## Corrections to project notes
- The prior note says Nexus forbids other-Bethesda-game assets "unless you have permission" (correct), but it treats
  Nexus's stance on our tool as entirely unresolved. A Nexus moderator did address the both-games-installed case in 2019
  and called it "different" (finding 10). Still not policy, but it is evidence.
- The prior note recommends "Donations for hosting only". Bethesda's Community Standards say "No Crowdfunding or
  Monetization mod projects is allowed." and Nexus prohibits "actively soliciting" donations (findings 6, 9). The safer
  wording is: no crowdfunding or Patreon, at most a tactful, optional link.
- The prior note lists Archive2 as "the player must have it installed rather than us shipping it" as a supported
  hypothesis. The Starfield CK EULA's "Any use or reproduction of the Editor not expressly authorized ... prohibited"
  supports it, though the EULA does not name Archive2 (finding 4).
- The prior note does not mention the Nexus rule on internet-connecting executables, which bears directly on its
  "add-ons by manifest, fetched from their hosts" recommendation (finding 9).

## Follow-up reads (blocked this session)
GNU GPL FAQ (aggregation, conveying object code); xEdit/BSArch licence (github.com/TES5Edit/TES5Edit); SFSE repo licence
(github.com/ianpatt/sfse); MO2 repo; Nexus collections guidelines (help.nexusmods.com/article/115); Nexus Donation Points
rules and permissions articles; TTW site; Techdirt 2025-01-03 article; Bethesda game EULA (bethesda.net/data/eula/en.html);
Microsoft Services Agreement; Bethesda video policy; Wwise licence; DirectXTex licence; ModDB and GitHub acceptable-use
rules; any Bethesda DMCA precedent.

## Sources
- Bethesda Terms of Service: https://bethesda.net/data/tos/en.html
- ZeniMax legal terms: https://www.zenimax.com/legal_terms
- Bethesda Softworks Community Standards: https://bethesda.net/en-US/news/bethesda-softworks-community-standards
- Starfield Creation Kit EULA (Steam): https://store.steampowered.com//eula/2722710_eula_0
- Starfield Creation Kit store page: https://store.steampowered.com/app/2722710/Starfield_Creation_Kit/
- Fallout 4 Creation Kit EULA (Steam): https://store.steampowered.com//eula/1946160_eula_1
- Fallout 4 Creation Kit store page: https://store.steampowered.com/app/1946160/
- Fallout 4 store page: https://store.steampowered.com/app/377160/
- Starfield store page: https://store.steampowered.com/app/1716740/
- UESP, Skyrim CK EULA: https://en.uesp.net/wiki/Tes5Mod:EULA
- UESP, Verified Creations: https://en.uesp.net/wiki/Skyrim_Mod:Verified_Creations
- Xbox Game Content Usage Rules: https://www.xbox.com/en-US/developers/rules
- Nexus File Submission Guidelines: https://help.nexusmods.com/article/28-file-submission-guidelines
- Nexus forum, FO4 assets into Skyrim (Jannifer, 2019): https://forums.nexusmods.com/topic/7312551-fallout-4-assets-modded-into-skyrim
- Nexus forum, content from other Bethesda games (Zaldir, 2021): https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games
- SFSE on Nexus: https://www.nexusmods.com/starfield/mods/106
- Mutagen: https://github.com/Mutagen-Modding/Mutagen
- Spriggit: https://github.com/Mutagen-Modding/Spriggit
- Synthesis: https://github.com/Mutagen-Modding/Synthesis
- Search results only (not read, unverified): https://www.pcgamesn.com/skyrim/mods-creations-ai ,
  https://insider-gaming.com/bethesda-skyrim-creation-mods-ai/
- Repo files: LICENSE, README.md, dotnet/*.csproj, scripts/mission/make_mission.py,
  scripts/deploy_starfield.py, scripts/convert_asset.py, scripts/actors/codsworth_voice.py,
  scripts/actors/codsworth_inventory.py, src/fo4sf/textures.py
