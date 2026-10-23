# Community, policy and licensing research: FO4 to Starfield launcher

Research date: 2026-10-19. Author: Claude (research subagent "community").
Scope: Bethesda/Microsoft policy, Nexus Mods policy, licensing, community operations of big projects,
AI reception, versioning. The launcher being researched is free, open source (MIT core, GPL-3 C# helpers that link
Mutagen), converts the player's own Fallout 4 install into a Starfield total conversion on their PC, and ships no assets.

## Labels and method

- **verified**: I read the page at the URL given, and the claim is what that page says. A verified claim is only as
  good as its source. Where the source is secondary (press, Wikipedia, a forum moderator), I say so.
- **supported hypothesis**: several sources point the same way, or one source says it indirectly, but no primary
  text says it outright.
- **unresolved**: I could not find or read a source.

Things that limited the reading:
- WebFetch was rate-limited (HTTP 429) partway through. I read the remaining pages through TinyFish fetch, and the
  Wabbajack and Mutagen licence files through raw.githubusercontent.com. Direct curl to most hosts was refused by
  the egress proxy.
- **Not readable:** `https://documents.bethesda.net/terms-of-service` (ZeniMax ToS: WebFetch 429, TinyFish
  `empty_content`). `https://app.swaggerhub.com/apis-docs/NexusMods/...` (official Nexus API docs) renders with
  JavaScript, so only the page shell came back. I could not search inside the private GitHub repos either (the
  session has no access).
- "Supported hypothesis" claims about the ZeniMax ToS rest on the Skyrim Creation Kit EULA (UESP copy) and
  Bethesda's Community Standards page, not on the current ToS text.

---

## 1. Bethesda / Microsoft policy

### 1.1 EULA and Creation Kit terms on mods

- **verified (secondary copy of the EULA)**: The Skyrim Creation Kit EULA, as transcribed on UESP
  (https://en.uesp.net/wiki/Tes5Mod:EULA), says:
  - Mods must be free: "You agree that You will not charge or require, directly or indirectly, a fee"
    (Section 1.D, "No Fees for Use").
  - Mods may go only to owners of the game: you are "only permitted to distribute the Game Mods to users who have
    purchased the Product".
  - Mods are "for non-commercial use solely in connection with the Product". Editor use is "for Your personal
    non-commercial use".
  - The author owns their mod ("As between You and ZeniMax, You are the owner of Your Game Mods"). ZeniMax gets an
    "irrevocable, perpetual, royalty-free … worldwide, non-exclusive right and license", including use "in other
    Games and Services".
  - **Why this matters for us:** our output is a Starfield mod built from Fallout 4 data. The phrase
    "solely in connection with the Product" is the exact clause a cross-game converter strains. The Fallout 4 and
    Starfield EULA text is **unresolved**: I did not read it, and it may differ from Skyrim's.
- **verified**: Bethesda's Community Standards page
  (https://bethesda.net/en-US/news/bethesda-softworks-community-standards) says, under MODS:
  - "No Crowdfunding or Monetization mod projects is allowed. – This is outlined in Section 1 of the EULA that
    states 'No Fees of Use'."
  - "Only upload your creations."
  - "We also do not allow uploading or linking of … mods relating to copyrighted or trademarked content."
  - "Do not promote or share anything that is a violation of copyright infringement or the illegal distribution of
    copyrighted material."
  - "Use caution when creating content from external IP – Our standards cover ZeniMax/Bethesda-owned brands."
  - The page does **not** mention moving assets between Bethesda's own games.
  - **Why this matters for us:** the crowdfunding/monetization ban affects any Patreon, Ko-fi or GitHub Sponsors
    link on the project.
- **verified (secondary)**: Under Bethesda's paid Creations / Verified Creator rules, PCGamesN
  (https://www.pcgamesn.com/skyrim/mods-creations-ai) quotes: "Creations cannot contain anything produced through
  generative AI." The same rules say a Creation "cannot depend on other community releases, free or paid", and that
  other authors' work is excluded "unless contracted".
  - So a converter-dependent output can never be a paid Creation, which is fine because we don't want one.
  - **Supported hypothesis:** an AI-assisted code base is also a reputational mismatch with Bethesda's own channel.
- **verified**: Microsoft's Game Content Usage Rules (https://www.xbox.com/en-US/developers/Rules) apply to "all
  games and Game Content published and owned by Microsoft Studios".
  - They cover "machinima, videos, and other cool things". If your Item "is an app or website, it can't include any
    malware".
  - They forbid earning compensation except through YouTube/Twitch programs and optional donations.
  - They do **not** mention mods, Bethesda or ZeniMax.
  - **unresolved:** whether Microsoft treats Bethesda IP as covered by these rules.
- **unresolved**: the current ZeniMax Terms of Service text on "Game Mods" and "Editor Tools" (page unreadable, see
  above). A search snippet shows it contains "non-commercial, non-transferable, and limited use … Game Mods (each
  such tool is an 'Editor Tool')", but I could not read the clauses.

### 1.2 Public statements and enforcement history on cross-game ports

| Case | What happened | Label / source |
|---|---|---|
| **Tale of Two Wastelands (FO3 to FNV)** | TTW forum staff member Risewild (2019): "Bethesda personally asked Nexus to not host TTW in the past, and we're still not allowed to host it there in the present date." He also said Nexus did not want direct links to the TTW site "because Bethesda might get angry at the Nexus". Fallout Wiki: Bethesda "regularly checked to make sure Tale of Two Wastelands wasn't distributing Fallout 3's assets which is the reason for the special installer". Another TTW dev (Sesom) said Nexus hosting "could've encouraged modmakers to actually distribute Fallout 3 assets". | **verified** as what the TTW team says (https://taleoftwowastelands.com/viewtopic.php@t=7850, https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands). I found no Bethesda-side statement, so Bethesda's actual request is **supported hypothesis**. |
| **Capital Wasteland (FO3 remade in FO4)** | Shut down by the team itself after legal advice, not by a Bethesda takedown. Lead: "Bethesda didn't technically shut us down. But a few members of staff heavily hinted at our methods being illegal". A lawyer called the approach "sketchy as all hell". The core problem was reusing Fallout 3 voice files. | **verified (secondary)**: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod (the March 13 update; year not on the page, contemporaneous reports date it to 2018) |
| **Skyblivion (Oblivion in Skyrim)** | Wikipedia: "To release Skyblivion, Bethesda required the project to fully replace 100% of all assets from the original to not redistribute their own proprietary content." In April 2025 the team said "Bethesda made it clear that they have no intention of shutting down our project" and Bethesda gave the team Oblivion Remastered keys. Release slipped to 2026 (December 2025). | **verified (secondary)**: https://en.wikipedia.org/wiki/Skyblivion, https://www.neowin.net/news/bethesda-confirms-it-has-no-intention-of-shutting-down-skyblivion-modding-project/. I found no formal licence. |
| **Skywind (Morrowind in Skyrim)** | Wikipedia says it "has been officially approved by the publisher Bethesda Softworks" (citing VG247, 2024) and needs ownership of Morrowind and Skyrim SE. In 2012 the team switched from porting Morrowind assets to "remaking or replacing everything". | **verified (secondary)**: https://en.wikipedia.org/wiki/Skywind. "Officially approved" rests on one press citation, so the form of approval is **unresolved**. |
| **Fallout London (FO4 total conversion)** | Original assets, distributed through GOG (partly because "its size would overwhelm sites like Nexus"). Bethesda later hired two FOLON members (VGC). Todd Howard, January 2026: "Only some videos that I've seen online; I have not played it"; "It seems a lot of fans love it." No formal Bethesda endorsement found. | **verified**: https://pcper.com/2024/07/fallout-londons-coming-youll-need-to-downgrade-though/, https://videogameschronicle.com/news/a-fallout-london-modder-has-joined-bethesda-while-the-projects-lead-has-rejected-a-fallout-job-offer, https://insider-gaming.com/todd-howard-no-interest-fallout-4-mod-london/ |
| **Fallout: New California (FNV)** | Original-asset mod. Wikipedia: "received an official release on GOG in July 2026, requiring the original game". No Bethesda dispute found. | **verified (secondary)**: https://en.wikipedia.org/wiki/Fallout:_New_California |
| **"Fallout 4 assets in Starfield" mods** | I found no Nexus takedown record or Bethesda statement specific to this. The general Nexus rule (Section 2) forbids it without permission. | **unresolved** |
| **Bethesda DMCA history against ports** | I found no DMCA notice in any of the cases above. The pattern is informal pressure (TTW, Capital Wasteland) or conditions (Skyblivion), not litigation. | **supported hypothesis** (absence of evidence in the sources I read) |

**The pattern (supported hypothesis):**
- Bethesda tolerates cross-game projects that (a) redistribute none of its assets, (b) require the player to own
  both games, and (c) are free.
- It pushes back on projects that redistribute assets (Capital Wasteland's voice files), and, through Nexus, on
  hosting a "converter" that could normalise asset redistribution (TTW).
- Our design (no assets, local conversion) matches TTW's model. TTW's model was **tolerated but kept off Nexus**.

### 1.3 Bethesda and game updates (relevant to breakage communication)

- **verified**: Todd Howard (TweakTown, 2026-03-17,
  https://www.tweaktown.com/news/110512/...): "We try to give them an early look to sort of prepare for it". He was
  talking about script extender authors.
- **verified**: Nexus (2025-11-06, https://www.nexusmods.com/news/15400) said that for the FO4 Anniversary update
  "the Fallout 4 Script Extender Team has not been given early access". Nexus added a "Works with Anniversary
  Upgrade" tag and published rollback steps.
- **verified**: The Fallout 4 update of August 18, 2026 raised the BA2 archive limit from 256 to 1024
  (https://fallout.bethesda.net/tr-TR/news/fallout-4-update-august-18th). FinalBoss reports Bethesda warned players
  to back up load orders.
- **verified**: Starfield runtime history from the SFSE sticky (https://www.nexusmods.com/starfield/mods/106?tab=posts):
  - 1.15.216 (May 2025): "has broken most if not all plugins, as well as the Address Library".
  - 1.16.236 (2026-04-07), 1.16.242 (2026-05-14), 1.16.244 (2026-06-11).
  - "As usual, beta updates are not supported."
  - 1.14.70 made "a major change to the base form type", so "all gameplay plugins will need to be recompiled".
- **verified**: The FO4 Next-Gen update (2024-04-25, 1.10.980) broke F4SE (https://shacknews.com/article/139690/...).
  It delayed Fallout London, which then shipped with a downgrader to the pre-next-gen build (pcper, above). Fallout
  London was "a no go on the Epic Games Store given the version of the base game on there doesn't support update
  rollbacks" (Mirror, 2024-10-18).

---

## 2. Nexus Mods policy (2024–2026)

### 2.1 Cross-game assets, ports and "port your own assets" tools

- **verified**: The File Submission Guidelines (https://help.nexusmods.com/article/28-file-submission-guidelines,
  "Last updated: September 29, 2026") say:
  - "User submissions which include copyrighted content, be it game files or images, are prohibited".
  - Also prohibited: "Providing links to external sources for files that would not be permissible to host on our
    services".
- **verified (moderator forum post, 2021)**: Nexus moderator Zaldir
  (https://forums.nexusmods.com/topic/9720278-questions-about-content-usage-from-other-bethesda-games): "Using assets
  from other Bethesda games is not allowed unless you have permission", and "Bethesda rarely gives permission for
  such things". Mods based on another game's look, without its assets, are fine.
- **unresolved**: whether Nexus allows a **tool** that ships no assets but generates another game's assets on the
  user's PC.
  - **Supported hypothesis that it is risky:** TTW (the closest precedent) is not hosted on Nexus by Bethesda's
    request, per the TTW team.
  - **Precedent that tool output is policed:** Wabbajack forbids uploading VRAMR/ParallaxGen outputs to Nexus
    (2.5 below). Nexus Collections bundle "tool generated files e.g. DynDOLOD output", but only for the same game.
  - Only Nexus staff can answer this (see Questions).

### 2.2 Executables, internet access, virus scanning

- **verified** (File Submission Guidelines, 2026-09-29):
  - "Files (especially executables) that connect to the internet to download or send information and/or files are
    prohibited". Exceptions need contact with staff, and the guidelines ask for "the source code for your tool/app".
  - "Auto update" functionality does not count as a reason to need internet access.
  - Nexus reserves the right to "moderate and/or remove any files/tools/utilities/mods that communicate with the
    internet".
  - "Submitted files will be subject to virus scanning and may be moderated as a result."
  - **Why this matters for us:** a launcher that self-updates, downloads SFSE/Mutagen/xEdit, or phones home for
    telemetry or crash upload is prohibited on Nexus by default.
- **verified (2014 post)**: Nexus scans uploads with VirusTotal (https://www.nexusmods.com/trinitytrigger/news/12378).
  "more than four" engines flagging a file sends it to quarantine for a moderator decision.
  - **unresolved:** whether that threshold still holds in 2026.
- **verified**: A Nexus Community Manager sticky on SFSE says reports of malware are "a false positive and … you
  should add an exception … You should also report this false positive to your virus scan provider".
- **verified**: SFSE's author bought a code-signing certificate on 2024-10-19 "to hopefully reduce virus scanner
  false positives". He wrote it costs "$657 every three years". He also moved to "a single loader executable that
  doesn't need to change with each version" to reduce false positives (Shacknews, F4SE, April 2024).

### 2.3 AI-generated content

- **verified**: On 2026-07-29 Nexus posted new categories
  (https://forums.nexusmods.com/topic/13542525-an-update-on-generative-ai-categorisation-tagging/), now in the File
  Submission Guidelines:
  - **AI-Generated Content**: "AI-Generated code, user interface elements, voices, dialogue, translations, music,
    in-game AI-generated assets".
  - **AI Media**: promotional art and descriptions.
  - **AI Assisted**: "Developer-led code, content, or mod assets, with limited AI involvement". This tag "requires
    significant evidence of development and proven knowledge", for example version control history and the
    developer's understanding of the code.
  - "Failure to correctly tag mods, including undisclosed generative AI usage, may be subject to moderation action."
  - **Why this matters for us:** our repo is built mostly by AI agents. "AI-Generated Content" covers "AI-Generated
    code", so the honest tag may be AI-Generated rather than AI Assisted. Our public git history and evidence logs
    are exactly the "evidence of development" the AI Assisted tag asks for.
- **verified**: The 2023 policy (https://www.nexusmods.com/hyperlightdrifter/news/14850) said AI content "is not
  against our rules". It encouraged creators to avoid AI tools "unless you have explicit permission to use all the
  assets", "particularly true for AI-generated voice acting". Removal happens on a valid complaint from the rights
  holder.

### 2.4 Ownership change

- **verified (secondary)**: Nexus Mods was sold to Chosen; the sale was announced 2025-06-17
  (https://aftermath.site/nexus-mods-new-owners-chosen-monetization.md). The new leadership said:
  - mods stay free;
  - "We're not changing the core model";
  - no paid mods;
  - more monetization was not ruled out.

  A spokesperson said: "Our focus is on continuity, not disruption."

### 2.5 Collections, Wabbajack-style tool outputs

- **verified**: The Collections guidelines (https://help.nexusmods.com/article/115-guidelines-for-collections, still
  marked "preliminary") say:
  - A collection is a meta file; "No actual mods or mod files may be included".
  - Bundled assets "are strictly reserved for tool generated files e.g. DynDOLOD output".
  - External resources may not link to "A mod including copyrighted material from a third party without their
    express permission".
  - The list and its metadata are "released to the public domain".

### 2.6 API terms for third-party launchers

- **verified**: The API Acceptable Use Policy (https://help.nexusmods.com/article/114-api-acceptable-use-policy,
  "Last updated on December 1, 2020") says:
  - Public apps must contact support with "a testing build of your application which can be used with a personal
    API key". Registered apps get a "slug" for SSO, and SSO is optional.
  - Registration "does not imply an endorsement".
  - Prohibited: scraping to rehost; "Storing user API keys on your own server"; "Using personal API keys for a
    public-facing application"; blank or impersonated request metadata.
  - The policy is non-exhaustive, "at our sole discretion".
- **supported hypothesis (strong)**: Free users cannot get download links through the API without first visiting
  the website. The API's `download_link` endpoint takes `key` and `expires` values from an nxm:// link generated on
  the site; premium users can request links directly.
  - Sources: moddingforge's client docs (https://moddingforge.com/docs/nexus-mods-api/reference/rest-v1) describe
    `key` as a "Premium download key from a Nexus Mods URL" with paired `expires`; the official swaggerhub page was
    unreadable.
  - User-visible behaviour **verified** on a Wabbajack list page (https://www.nexusmods.com/newvegas/mods/79547):
    "If you have Nexus Premium, you can lean back … Otherwise, you will have to click through the mod pages and
    download manually (Wabbajack will guide you)."
- **verified (third-party, 2024-12-18)**: The Genesis modlist FAQ (https://genesismodlist.com/wabbajack-issues/)
  states the Nexus API limit is "10,000 requests per 24h, and then an additional 500 per hour".
  - **unresolved:** I did not find this in an official Nexus document.

---

## 3. Licensing

- **verified**: Mutagen is GPL-3.0
  (https://raw.githubusercontent.com/Mutagen-Modding/Mutagen/dev/LICENSE.txt is the GPLv3 text).
  - Our C# helpers that link it must be GPL-3 when distributed. The MIT core may stay MIT if it is a separate
    program.
- **verified**: GPLv3 §5 (in https://raw.githubusercontent.com/wabbajack-tools/wabbajack/main/LICENSE.txt) says a
  compilation with "separate and independent works … is called an 'aggregate'". "Inclusion of a covered work in an
  aggregate does not cause this License to apply to the other parts of the aggregate."
- **verified**: The GPL FAQ (https://www.gnu.org/licenses/gpl-faq.html#MereAggregation) says:
  - "pipes, sockets and command-line arguments are communication mechanisms normally used between two separate
    programs".
  - But "if the semantics of the communication are intimate enough, exchanging complex internal data structures,
    that too could be a basis to consider the two parts as combined".
  - **Why this matters for us:** an MIT Python launcher calling GPL C# executables over the command line or JSON is
    normally an aggregate. Exchanging rich record structures over JSON is the grey zone the FAQ names.
- **verified**: On source obligations, the GPL FAQ (#AnonFTPAndSendSources) says: "If you make object code
  available on a network server, you have to provide the Corresponding Source on a network server as well … the
  source should be just as easy to access as the object code … The sources you provide must correspond exactly to
  the binaries." This is GPLv3 §6(d).
  - Practical consequence: every GitHub/Nexus release asset needs a matching source tag or archive, and the
    installer must carry the GPL text and notices.
- **verified**: Wabbajack's LICENSE.txt says "The Wabbajack Codebase is under the GPLv3 license. Modlists produced
  by Wabbajack under the CC BY-NC-SA 4.0 … Wabbajack modlists may *not* be paywalled … Any quid-pro-quo payment
  structure in connection with Wabbajack lists is strictly prohibited."
  - This is the community norm we can copy: an OSS tool licence, plus a separate non-commercial licence for content
    or recipes built on it.
- **verified**: Wabbajack's pre-compilation docs
  (https://wiki.wabbajack.org/modlist_author_documentation/Pre-Compilation.html) say Wabbajack is safe because "we do
  not distribute any copyrighted material". It ships "instructions on how to modify the copyrighted material"
  (binary patches). Utility outputs "are strictly forbidden from being uploaded on both Nexus and the Wabbajack CDN".
- **supported hypothesis**: Our output (converted Starfield files generated from the user's FO4 data) is a
  derivative of Bethesda's FO4 assets. The legal shelter is the same as Wabbajack's or TTW's: the user makes it from
  their own copy. Users must never re-upload the output, and third-party add-ons must not ship converted assets.
  Add-on licensing terms are for us to design; no source sets them.

---

## 4. Community operations of large projects

| Project | Support channels | What they ask for | Antivirus | Game-update stance | Source / label |
|---|---|---|---|---|---|
| **TTW / The Best of Times guide** | Forum now read-only; "For community discussion and questions, head over to our Discord". Guide says to ask in ModdingLinked or TTW Discords. | Strict requirements: English copies on Steam/GOG/Epic, "Microsoft Store versions are not supported". Modified/LTSC Windows: "We can refuse to provide help in such cases." | Advises antivirus exclusions for the MO2 folder. | Verifying game files reverts patches, so re-run the patcher. | **verified**: https://thebestoftimes.moddinglinked.com/intro.html, https://thebestoftimes.moddinglinked.com/faq.html, TTW forum |
| **Wabbajack** | Discord plus wiki; site says "Requires Windows 10/11 Home or Pro. LTSC, IoT Enterprise, and modified Windows versions are not supported." Linux: community guides. | Logs live in the versioned folder's `logs`; the list of failed downloads is at the end of the log. Game Pass: "Short answer - NO." | List authors tell users to add exclusions or disable third-party antivirus (Genesis, Begin Again). | Script extenders support only the latest Steam version. | **verified**: https://www.wabbajack.org/, https://wiki.wabbajack.org/user_documentation/Troubleshooting FAQ.html, https://genesismodlist.com/wabbajack-issues/ |
| **Begin Again (Wabbajack list for TTW)** | Separate Discord; "DO NOT spam the TTW discord server". "Please don't spam the comments with entire crash logs." Modifying the list will "void all support". Includes a "debug mode" profile. | Clean vanilla reinstall, no UAC-protected folders, English language. | "add the folders you will be working in as an exemption". | "The list is up to date with the latest version of TTW (3.4) It is incompatible with older versions." | **verified**: https://www.nexusmods.com/newvegas/mods/79547 |
| **Fallout London** | Discord-first. At launch the team ran "dedicated 1-on-1 troubleshooting sessions" and folded Buffout 4 (crash logger) into the hotfix. Per-quest bug channel. Full change log in a public spreadsheet. Twitch dev streams. | Quest name + stage for quest bugs. | not found | Ships a downgrader. Not on Epic (no rollback). Patch 1.02 warns Papyrus properties in saves may make updated quests "act in unexpected ways". Rabbit & Pork (Sep 2025) recommends a new save and adds an Overwolf-powered launcher next to GOG. | **verified**: PC Gamer (https://pcgamer.com/games/rpg/fallout-london-devs-are-working-on-a-huge-patch-...), Mirror (https://www.mirror.co.uk/gaming/fallout-london-patch-102-makes-33923964), GamingOnLinux (https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/) |
| **STALKER GAMMA** | Discord (community). As of 2025-12-01 it is also available as a free one-click GOG package; a reader quotes the listing as requiring ownership of STALKER 2 or Call of Pripyat EE. | not found | not found | Linux users report the GOG version doesn't work. | **verified** (article), ownership requirement **supported hypothesis** (reader comment): https://gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install |
| **SFSE / F4SE (core dependency)** | Status log in a pinned Nexus comment; "Do not email with questions." "Game Pass discussion is off topic." Users must paste `sfse_loader.txt` "inside spoiler tags". | The log file | Code-signing certificate; Nexus CM sticky about false positives. | Rebuilds within hours or days of each Starfield patch; beta branches unsupported. | **verified**: https://www.nexusmods.com/starfield/mods/106?tab=posts |

- **unresolved**: reported support *load* in numbers (tickets per day, Discord size, volunteer hours) for any of
  these projects. I found no source with numbers.
- **unresolved**: GAMMA's own FAQ, bug-template and log-uploader practice. The GAMMA site and Discord weren't
  reachable through search.
- **supported hypothesis**: The common pattern:
  - Discord is the primary support desk, and the forum or Nexus comments are secondary.
  - Supported configurations are spelled out strictly (store, language, Windows edition, clean install), and anyone
    who strays loses support.
  - A crash logger is part of the package.
  - A rollback or downgrade path is published when the base game updates.
  - Antivirus exclusions are normal instructions.
  - Tools signed with a code-signing certificate get fewer false positives.

---

## 5. AI reception risk

- **verified**: PC Gamer, 2026-07-31
  (https://www.pcgamer.com/gaming-industry/nexus-mods-finally-tightens-the-screws-on-ai-...):
  - The tone is hostile: "the tide of slop".
  - It cites cloned voices in NSFW mods, "vibe coded" mods, AI promo art, and undisclosed AI use.
- **verified**: A Nexus forum thread (2025-11-02,
  https://forums.nexusmods.com/topic/13525267-...) reports mod pages "flooded with attacks" on authors who used AI
  (Fallout 4 music, posters).
  - The only replies came from community members, not staff. One said: "Nexus doesn't particularly protect or love
    AI-generated content mods".
- **verified (secondary)**: TechRadar, Kotaku and Yahoo (2023) covered voice actors objecting to AI clones of their
  voices in Skyrim mods. Nexus removes such content on the rights holder's request (2023 policy above).
- **verified**: Bethesda bans generative AI in paid Creations (PCGamesN, above).
- **supported hypothesis**:
  - The main risks for an AI-built *tool* are (1) a mandatory "AI-Generated Content" tag on Nexus and (2) brigading
    of the comments.
  - What reduces the risk is content-policy, not code: no AI voices or AI art in our outputs or promo, plus a
    public, evidence-heavy git history.
  - I found no case of a pure conversion tool being attacked for AI-written code. That part is **unresolved**.

---

## 6. Versioning and save-compatibility conventions

- **verified**: SemVer 2.0.0 (https://semver.org/):
  - "Major version zero (0.y.z) is for initial development. Anything MAY change at any time."
  - The project must "declare a public API".
  - Released versions "MUST NOT be modified".
- **verified**: Practice in big mod projects. Most state save compatibility per release in plain words rather than
  through the version number:
  - Fallout London 1.02: saves "may act in unexpected ways"; "The be all and end all fix is to try a new game".
  - Rabbit & Pork: start a new save.
  - TTW 3.4: Begin Again calls it "incompatible with older versions".
  - Nexus collection Immersive Survival: per-revision changelogs keyed to the game build ("works with Fallout 4
    Anniversary Edition August Update, the version 1.11.240.0").
  - SFSE: names each build after the runtime it supports (`sfse_1_16_244.dll`).
- **supported hypothesis**: For us, the "public API" in SemVer terms is the generated plugin's FormIDs, editor IDs
  and record layout that a save game references. A change that renumbers FormIDs breaks saves and should be a major
  version, even for a tool. The launcher should also record which game runtimes each release supports (FO4 source
  build, Starfield runtime, SFSE version), the way SFSE and collections do.

---

## Questions this raises for our launcher

Each question gives why it matters (**Why**) and what would answer it (**Answer**).

1. **Will Nexus host a tool that generates Fallout 4-derived Starfield content locally from the user's files?**
   - **Why:** File Submission Guidelines ban copyrighted game files and links to impermissible files. TTW, our
     closest precedent, was kept off Nexus at Bethesda's request per the TTW team. A takedown after launch would
     strand users.
   - **Answer:** a written reply from Nexus staff (support ticket or moderator) describing our exact architecture,
     before any upload.
2. **Should we ask Bethesda directly, and through which channel?**
   - **Why:** Skyblivion got conditions ("replace 100% of all assets") and Skywind is reported "officially
     approved". Both had contact with Bethesda; TTW got informal pressure. A no-asset converter is a new case.
   - **Answer:** a decision by the owner on whether to contact Bethesda community or legal staff. If yes, their
     reply in writing, logged in docs/ai/decisions.md.
3. **Does the Fallout 4 / Starfield EULA "solely in connection with the Product" clause make a FO4-to-Starfield
   output a breach by the user?**
   - **Why:** it is the clause our core idea strains. I only read the Skyrim CK EULA and could not read the current
     ZeniMax ToS.
   - **Answer:** read the current ZeniMax ToS (https://documents.bethesda.net/terms-of-service) and the FO4 and
     Starfield CK EULA text in a browser. If still ambiguous, a lawyer's reading.
4. **Does the launcher need internet access at all (updates, SFSE/xEdit download, Nexus API, crash upload)?**
   - **Why:** Nexus prohibits internet-connecting executables by default and wants source code for exceptions; "auto
     update" doesn't count. Any network feature changes our Nexus path and our antivirus profile.
   - **Answer:** an inventory of every network call in the launcher design, then a yes/no from Nexus staff for each
     one we keep.
5. **If we download dependencies from Nexus, do we register an app slug and support free users through the nxm
   "Slow download" flow?**
   - **Why:** the API policy bans personal keys in public apps and requires registration with a test build. Free
     users cannot get direct links without visiting the site.
   - **Answer:** the official swaggerhub endpoint docs, read in a browser, plus a registration request to Nexus
     support with a test build.
6. **Are the MIT launcher and the GPL-3 Mutagen helpers a "mere aggregation" in our real interface?**
   - **Why:** the GPL FAQ says command-line or pipe communication is normally separate programs, unless it exchanges
     "complex internal data structures". If they count as one program, the whole installer must be GPL-3.
   - **Answer:** document the actual IPC contract (CLI args plus JSON files, their schema size and semantics). Ask an
     open-source licensing reviewer, or simply relicense the launcher GPL-3 if in doubt.
7. **What exactly goes in each release for GPL compliance?**
   - **Why:** GPLv3 §6(d) needs Corresponding Source "just as easy to access", matching the exact binary version,
     plus licence texts and notices.
   - **Answer:** a release checklist: tag, source archive, LICENSE files for MIT and GPL-3, a third-party notices
     file (Mutagen and its dependencies, with licences). Verify it against the GitHub release assets.
8. **What licence and rules govern third-party add-ons built on our core?**
   - **Why:** Wabbajack uses GPL for code and CC BY-NC-SA for lists, "may not be paywalled". Bethesda bans
     monetised mod projects. Add-on authors need to know they may not ship converted FO4 assets or charge for
     access.
   - **Answer:** a short ADD-ONS policy decided by the owner: content licence, no-asset rule, no paywall. Check it
     against Bethesda's Community Standards and Nexus rules.
9. **Can the project take donations (GitHub Sponsors, Ko-fi) at all?**
   - **Why:** Bethesda: "No Crowdfunding or Monetization mod projects is allowed". Nexus allows "tactful discussion
     of donations" but bans soliciting. Microsoft rules allow optional donations only in narrow cases.
   - **Answer:** an owner decision. If yes, a reading of whether a donation link on a tool repo, as opposed to a mod,
     falls under Bethesda's rule.
10. **Which Nexus AI tag applies to us, and what evidence do we show?**
    - **Why:** "AI-Generated code" falls under AI-Generated Content. AI Assisted "requires significant evidence of
      development and proven knowledge". Mistagging is moderated.
    - **Answer:** compare our git history, research log and the owner's role against the 2026-07-29 definitions, then
      a pre-upload query to Nexus moderation. Also decide a public AI-disclosure paragraph.
11. **Do we promise "no AI voices, no AI art" in outputs and promotion?**
    - **Why:** the hostile reactions and removals cluster on AI voices and art, not tooling (PC Gamer 2026, voice
      actor complaints). A clear promise lowers brigading risk.
    - **Answer:** an owner decision, recorded in docs/ai/decisions.md and on the release page.
12. **Which game builds do we support, and how do we announce breakage?**
    - **Why:** Starfield shipped runtime updates 1.16.236, .242 and .244 in roughly two months of 2026. SFSE notes
      breaking changes (1.14.70 form type, 1.15.216 broke "most if not all plugins"). FO4 Next-Gen and Anniversary
      updates broke F4SE, and Fallout London needed a downgrader.
    - **Answer:** a support matrix (FO4 source builds, Starfield runtime, SFSE version, stores: Steam/GOG/Game Pass),
      a launcher check that refuses unknown runtimes, and a pinned status post like SFSE's.
13. **Do we support Game Pass / Microsoft Store and Epic copies?**
    - **Why:** Wabbajack says no to Game Pass; TTW excludes Microsoft Store; SFSE "only works through Steam
      installations" (per a community reply). Fallout London couldn't support Epic because there is no rollback.
    - **Answer:** test whether our FO4 reader and Starfield output work on each store's files, and publish the result.
14. **What is our support channel and minimum bug report?**
    - **Why:** every comparable project is Discord-first, with strict supported configurations. They ask for logs (a
      crash logger in the package, `sfse_loader.txt` in spoiler tags), and ban full crash logs pasted in comments.
    - **Answer:** an owner decision on Discord vs GitHub Discussions, and a bug template that gets launcher version,
      game builds, store and log bundle. Do we need a one-click "collect logs" button that writes a zip locally
      (no upload)?
15. **How do we handle "my antivirus flagged it"?**
    - **Why:** VirusTotal quarantine on Nexus (more than four engines, as of 2014). SFSE paid $657 per three years
      for code signing to cut false positives. Unsigned PyInstaller and .NET single-file binaries often trigger
      heuristics (**supported hypothesis**, not tested).
    - **Answer:** run our release binaries through VirusTotal before release and record the engine count. Decide on
      code signing (cost, who holds the certificate), and write a FAQ entry modelled on the Nexus CM sticky.
16. **What is our versioning promise for saves?**
    - **Why:** the save "API" is the generated plugin's FormIDs and records. Fallout London and TTW broke saves
      between versions and told users in plain words.
    - **Answer:** an ADR defining what counts as a breaking change (FormID or EditorID renumbering, removed records).
      SemVer major for breaking changes, 0.y.z until the first public in-game acceptance. A "save compatible: yes/no"
      line in every changelog.
17. **Is GOG (as with Fallout London, FNC and GAMMA) a better distribution partner than Nexus?**
    - **Why:** GOG now distributes free total conversions and modpacks that require the base game. That avoids Nexus
      upload rules, but GOG would want a vetted, asset-free installer.
    - **Answer:** read GOG's mod/total-conversion partnership terms (not researched here) and decide once the GitHub
      release is stable.
18. **Do we need a "no re-upload of generated output" rule, and how do we make it visible?**
    - **Why:** Wabbajack forbids uploading tool outputs to Nexus or its CDN. Converted FO4 assets re-uploaded by
      users would be exactly the redistribution Bethesda objected to with TTW and Capital Wasteland.
    - **Answer:** an owner decision. Then a line in the README, a first-run screen, and a marker in generated files
      (e.g. a header comment in the plugin) that identifies them as locally generated.
