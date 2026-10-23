# Fallout 76 terms

Researched 2026-10-19 by Claude (subagent). Not legal advice. Every claim is labelled **verified** (read in the linked source, quoted), **supported hypothesis**, or **unresolved**.

**Bottom line.** Fallout 76 does not ship with its own game EULA that differs in kind. It falls under the general ZeniMax / Bethesda.net Terms of Service (last updated November 12, 2024), which treat it as a "game as a service". That text is stricter than what applies to the single-player games in practice. It grants a "personal, private and non-commercial" licence and then forbids, without any non-commercial carve-out, (b) modifying, reverse engineering or decompiling the Software, (c) creating "any derivative works based upon any Services", and (e) copying any Software or Content unless it is a Game Mod or DLC. Separately, Bethesda Support states that "Fallout 76 does not support the use of any mods, add-ons, or other third-party programs", and Bethesda has said it will not add script-extender-style mod support because "Being online, we have to protect the integrity of the game." **Verified:** all of this text exists. **Supported hypothesis (inference):** a tool that reads SeventySix.esm and its archives out of the player's own install and rebuilds 76 quests and places inside Starfield would conflict with the literal wording of clauses 3(b), 3(c) and 3(e), even though it is private, offline and non-commercial. The single-player games come with official Creation Kits and mod policies; 76 has neither. Enforcement found so far targets online cheating and exploits, not offline reading of files, but no source settles whether Bethesda would act on an offline converter. **Verified:** 76's quest and world data is in a local master file, SeventySix.esm, which FO76Edit can open from an install.

## What the terms say

All quotes below are **verified**. They come from the ZeniMax Terms of Service at https://bethesda.net/data/tos/en.html ("Last Updated: November 12, 2024"; the page also points to www.zenimax.com/legal_terms). The full page was fetched and searched. The string "Fallout" never appears in it, so it has no Fallout 76 clauses by name. **Verified** (text search of the fetched page).

**Scope: the Game, its Content and its Software are all "Services"** (Section 1):
> "...ZeniMax's computer, mobile, and console entertainment software game(s) (collectively, "Game(s)") ... (iii) software, including, but not limited to, third-party software and small amounts of code that might be necessary to facilitate playing online Games that are provided by ZeniMax as a service offering (collectively, "Software") ... (together with Content, Games and Software collectively referred to as "Services"). For purposes of these Terms of Service, references to a "Game" include, unless the context requires otherwise, Content that is accessible by or used or available in the Game ..."

**Licence grant** (Section 3, Limited License to Use):
> "...for Your personal, private and non-commercial use only, a non-exclusive, revocable, nontransferable license to access, receive, play, and use Services ... In the case of Games and Software made available for download, the foregoing license includes the right to download and install a single copy of the Game or Software on a single computer, console or mobile device owned by You for Your personal, private and non-commercial use."

**Restrictions** (Section 3; this is the key clause):
> "You may not (a) distribute, publicly perform or display, sell, transmit, publish, edit, reproduce, sublicense, rent, lease, loan or otherwise transfer any Game, Software, and/or Content, including without limitation any access keys; (b) modify, adapt, reverse engineer or decompile the Software, or otherwise attempt to derive source code or anti-cheating measures from the Software; (c) create any derivative works based upon any Services; (d) otherwise access, receive, play or use any Services except as expressly provided in these Terms of Service; (e) copy or download any Software or Content unless the Content is a Game Mod available for download from a ZeniMax website or is Downloadable Content (other than Virtual Currency) or You are otherwise expressly authorized to do so in writing by ZeniMax; and/or (f) remove, obscure, or alter copyright, patent, trademark, or other proprietary rights notices affixed to any Services."

**Reserved rights and the "as a service" clause** (Section 3):
> "ZeniMax reserves title to the Services and all rights to any Services not specifically granted under these Terms of Service, including without limitation all rights of reproduction, modification, distribution, display, disassembly and decompilation ..."

> "You acknowledge and agree that in the case of Games that are made available as a service, (i) You might not have a copy of the Game on Your computer, mobile device, or console, as the case may be, (ii) You will access and play the Game via the Internet, and (iii) You must have a persistent Internet connection to access and play the Game."

> "ZeniMax actively enforces its intellectual property rights to the fullest extent of the law."

**Content and derivative works** (Section 2.A):
> "Except as necessary to use the Services in compliance with these Terms of Service, You may not copy, use or download any Content from a Service unless You are expressly authorized to do so by ZeniMax in writing. You acknowledge and agree that You shall not reproduce, prepare derivative works based upon, distribute, publicly perform, or transmit any Content for commercial uses unless You obtained the express written consent ..."

> "...if You or someone else creates a work and it is likely to bring to mind either or both Services (such as a Game) and Content, then it is likely that such work is a derivative work and as such may not be used for commercial purposes."

**Who owns what you make from their Content** (Section 2.B):
> "ZeniMax Owned UGC also includes all Content (other than Game Mods (as defined below)) that You create or develop using Content provided or made available by ZeniMax, including but not limited to Content that You create or develop that is a derivative work of the Content provided or made available by ZeniMax."

**Game Mods are defined only as Editor Tool output** (Section 2.D):
> "The term "Game Mod" means downloadable, user-generated Content developed or created by You or a third party using an Editor Tool (as defined below)."

> "...You will be required to download from a ZeniMax website or otherwise gain access to via a ZeniMax website one or more software tools through which You may create or develop Game Mods (each such tool is an "Editor Tool"). To obtain a copy of or get access to any such Editor Tool, You will be required to agree to the terms of a separate EULA (the "Editor EULA")."

**Third-party tools, emulators, derived tools** (Section 9):
> "You further agree not to access, create, or provide any other means through which the Services, including, but not limited to, any Game(s), may be used or accessed by others, such as through server emulators."

> "You agree not to use any hardware or software or any other method of support that is not authorized by ZeniMax or that may in any way influence or advantage Your playing abilities ... Third-party tools, the use of "bots", "speed hacks", "deep-link", "page-scrape", "robot", "spider", algorithms or other programs that copy or monitor any part of the Services ... are examples of methods not authorized by ZeniMax."

> "You acknowledge that You do not have the right to create, publish, distribute, or create derivative works from or use any software programs, utilities, applications, emulators, or tools derived from or created for certain Content (such as Game(s)), except as authorized in writing by an authorized ZeniMax representative."

**Offline or private use.** The ToS has no clause that permits offline or private use of a game-as-a-service. The only related clause is the "persistent Internet connection" acknowledgment quoted above. **Verified** (absence, from a search of the fetched text). The words "personal, private and non-commercial" describe the scope of the licence. They do not exempt the user from the restrictions in (a) to (f).

**Steam EULA.** The Steam store page (https://store.steampowered.com/app/1151340/Fallout_76/) sits behind an age gate when fetched, and the guessed EULA URL https://store.steampowered.com/eula/1151340_eula_0 returned "There was an error loading the content of this EULA." **Unresolved:** whether Steam links a separate 76 EULA. **Supported hypothesis:** it points to the same ZeniMax ToS, because playing requires a Bethesda.net account. That is not confirmed from Steam.

**Fallout 76 Code of Conduct.** No standalone 76 code of conduct was found. The Bethesda Softworks Community Standards (https://bethesda.net/en-US/news/bethesda-softworks-community-standards) say "Do not use/discuss/share Hacks or Exploits within our games." and "We also do not allow uploading or linking of ... mods relating to copyrighted or trademarked content." **Verified.**

## Bethesda's 76 modding policy

- **Verified.** Bethesda Support, "Can I use mods/add-ons or other third-party programs with Fallout 76?" (https://help.bethesda.net/app/answers/detail/a_id/44429/~/can-i-use-mods-or-other-third-party-programs-with-fallout-76):
  > "Fallout 76 does not support the use of any mods, add-ons, or other third-party programs. Please be aware that the use of such applications may result in Fallout 76 not functioning properly."
  > "Be advised that using any mods, add-ons, or other third-party programs for hacking, cracking, phishing, taking advantage of exploits or cheats and/or distribution of counterfeit software and/or Virtual Currency or virtual items is a violation of our Terms of Service."
  The article does not date itself. **Inference:** "does not support" is a support stance, not an explicit ban. The explicit ToS-violation sentence covers cheating, exploit and counterfeit uses.
- **Verified.** Windows Central interview with the Fallout 76 team, 11 June 2024 (https://www.windowscentral.com/gaming/fallout-76-interview-discussing-crossplay-mods-skyline-valley-nuclear-winter-and-the-future-with-bethesda). The quotes are not attributed to a named speaker: "Being online, we have to protect the integrity of the game"; on "any other mods where you would expect to have like a script extender that you often need for single-player games"; "We try not to break the UI mods, but sometimes it's necessary."; and on offline play: "Always online is not something we've discussed in depth, so there are no plans right now to add that kind of support."
- **Verified (historic promise).** Todd Howard at QuakeCon 2018, reported by Windows Central on 11 Aug 2018 (https://www.windowscentral.com/bethesda-commited-fallout-76-mod-support): "It's not just having a private server, it's being able to mod it." **Verified (outcome).** The official Fallout Worlds announcement of July 20, 2021 (https://bethesda.net/en-US/news/announcing-fallout-worlds) offers settings-based "Custom Worlds" for "active Fallout 1st members". It never mentions the Creation Kit, and no plugin modding was found. **Supported hypothesis:** no Fallout 76 Editor Tool or Editor EULA exists, so no 76 content can count as a "Game Mod" under ToS 2.D.
- **Verified.** Bethesda.net Modding Guidelines, article 51731 (https://help.bethesda.net/app/answers/detail/a_id/51731):
  > "Do not upload mods using third-party content (licensed properties, content from other games, and other trademarked properties). This includes using assets from other Bethesda games."
  It names no game, so it says nothing about Fallout 76 specifically. **Verified.** It governs uploads to Bethesda.net / Creations, not local tools.

## Precedents

- **Verified.** Fallout 4 mods that recreate Appalachia rebuild it from Fallout 4 assets, not 76 files. Kotaku, 21 May 2019, on DeeZire's project (https://kotaku.com/meet-the-modder-painstakingly-rebuilding-fallout-76-in-1834930738): "There are locations in Fallout 76 that I will simply not be able to fully realize, as there's nothing like those assets in Fallout 4." PCGamesN on "Fallout: Appalachia" by UnleashOne (https://www.pcgamesn.com/fallout-4/fallout-mod-appalachia) says the modder builds with Fallout 4's base game and DLCs and hopes to stay within the EULAs. Neither article reports any Bethesda action. **Inference:** the best-known 76-to-FO4 projects deliberately avoided extracting 76 data, which suggests modders saw that as the risky step.
- **Verified.** Client-side 76 mods (texture and UI .ba2 archives) have been made since the 2018 beta. PC Gamer, 3 Nov 2018 (https://www.pcgamer.com/uk/fallout-76-players-are-already-modding-the-beta) reports no Bethesda response. Nexus Mods hosts a Fallout 76 section (for example https://www.nexusmods.com/fallout76/mods/154).
- **Verified (enforcement against online exploit use, not offline reading).** Bethesda's ban email in Dec 2018, per TweakTown (https://www.tweaktown.com/news/64272/fallout-76-cheaters-write-essay-unbanned/index.html): "The account was detected to be running a third-party application, which provides an unfair in-game advantage". In Nov 2019 the creator of Map76 was suspended after testing an exploit with technical tools. Bethesda's statement: "In cases where this has happened, this is a violation of our Terms of Service and in those cases the accounts are actioned." (Reclaim The Net, https://reclaimthenet.org/bethesda-fallout-76-ban-controversy-response; TheGamer, https://www.thegamer.com/fallout-76-data-miner-banned-despite-efforts-to-help-bethesda/). The remedy was account action.
- **Unresolved.** No source was found for any takedown or legal action against a mod or tool that ports actual Fallout 76 assets or data into another game, and none for action against offline data-mining alone. The search was not exhaustive.

## Is the data local

- **Verified.** The FO76Edit page on Nexus (https://www.nexusmods.com/fallout76/mods/30) says: "FO76Edit is the Fallout 76 version of xEdit." and "The primary purpose of this tool right now is to look at SeventySix.esm." It also says: "The game does not support plugins at the moment! You can not use this tool to create mods for Fallout 76!"
- **Verified.** Mappalachia's developer guide (https://github.com/AHeroicLlama/Mappalachia/blob/master/Developer_Guides/EditScripts.md) requires "A copy of Fallout 76 installed on your machine", launches FO76Edit "with the parameter -D:"<Path_to_FO76_Data_folder>"", and says to "Select SeventySix.esm".
- **Verified.** The client Data folder holds "SeventySix - *.ba2" archives such as "SeventySix - 00UpdateMain.ba2", "SeventySix - GeneratedMeshes.ba2" and "SeventySix - StaticMeshes.ba2" (readme of https://www.nexusmods.com/fallout76/mods/154?tab=docs), at a path like "C:\Program Files (x86)\Bethesda.net Launcher\games\Fallout 76\Data".
- **Supported hypothesis.** SeventySix.esm contains the quest, worldspace (Appalachia), cell and dialogue records, since Mappalachia builds its map from it. No source read here lists which quest scripts and logic run server-side. **Unresolved:** how much of 76's quest behaviour (server scripts, event logic, NPC state) can be rebuilt from client files alone. This needs an offline inspection with evidence before any claim, per AGENTS.md.

## What this means for us (inference)

Everything in this section is inference from the quoted text, not a legal conclusion.

1. **The single-player path does not carry over.** For FO4 the project leans on a modding culture Bethesda supports: official Creation Kits, and Editor EULAs that allow private use. 76 has no Editor Tool, so nothing we produce from 76 data fits the ToS definition of a "Game Mod". Without that carve-out, clause 3(e) ("copy ... any Software or Content") and clause 3(c) ("create any derivative works based upon any Services") apply on their face. They apply even to non-commercial use, because the non-commercial wording in 2.A is an extra restriction, not an exemption from Section 3.
2. **Reading files is a weaker problem than converting them.** Opening SeventySix.esm read-only (as FO76Edit and Mappalachia do) is arguably "use" of the installed copy. Writing converted quests and cells into Starfield formats is closer to reproduction plus a derivative work. Section 9's ban on tools "derived from or created for certain Content (such as Game(s))" could be read to cover the converter itself, and so could the ban on means for others to access the Game.
3. **"Combined offline experience" cuts against the "as a service" framing.** The ToS says play needs "a persistent Internet connection". Bethesda says it has "no plans" for offline support. An offline single-player rebuild of 76's story is the very product Bethesda has chosen not to offer, and that makes it more likely to draw attention than a texture mod.
4. **Enforcement found so far is account action against online exploit use.** Nothing found shows Bethesda acting against offline file readers or against Appalachia recreations built from FO4 assets. That is an absence of evidence, not permission.
5. **Interoperability and fair-use defences** (for example DMCA 1201(f), EU Software Directive Art. 6) were not researched here, and they vary by jurisdiction. They are a question for a lawyer, not for agents.
6. **Lowest-risk options, in rough order:** (a) leave 76 out of scope; (b) recreate 76 places and stories from FO4 and Starfield assets with original writing, as the Appalachia mods do (this is still a "brings to mind" derivative under 2.A, but it is non-commercial and copies no 76 files); (c) ask ZeniMax for written permission, which the ToS names as the route ("expressly authorized ... in writing"); (d) build a read-only extractor that runs locally and ships nothing, which conflicts most directly with 3(b), 3(c) and 3(e).

## Questions for the framework

1. **Is Fallout 76 in scope at all?** Options: (a) no, single-player games only; (b) yes, but recreation only (no 76 files read); (c) yes, with local extraction. Who answers: owner (dasscooby), ideally after independent legal advice.
2. **If it is in scope, may the converter read SeventySix.esm and the SeventySix ba2 archives?** Options: (a) never; (b) read-only metadata for reference (names, coordinates), with no output derived from it; (c) full conversion. Who answers: owner; Research labels the risk in docs/ai/research-log.md.
3. **Should we ask ZeniMax/Bethesda for written permission before any 76 work?** Options: (a) yes, before any code; (b) only if (c) in Q1 is chosen; (c) no. Who answers: owner (any outreach is the owner's, not an agent's, under AGENTS.md safety rules).
4. **How much of 76 quest logic is actually in client files?** Options: (a) a research spike with an offline FO76Edit inspection on the owner's install, results labelled verified/unresolved; (b) defer until Q1 is answered. Who answers: owner approves; Research or Claude runs the spike.
5. **Does the Steam build carry a different EULA?** Options: (a) owner checks the Steam store page legal section or the in-launcher agreement and pastes the text; (b) treat the ZeniMax ToS as governing. Who answers: owner (a page behind an age gate or login cannot be read by agents).
6. **How should the project describe 76 support publicly** (README, Nexus page) so it does not imply Bethesda endorsement or encourage ToS breaches? Options: (a) say nothing until decided; (b) add an explicit "not supported, not affiliated" note. Who answers: owner; Claude drafts.

## Sources

- ZeniMax / Bethesda.net Terms of Service, last updated Nov 12, 2024: https://bethesda.net/data/tos/en.html (canonical pointer: www.zenimax.com/legal_terms)
- Bethesda Support, Can I use mods/add-ons or other third-party programs with Fallout 76?: https://help.bethesda.net/app/answers/detail/a_id/44429/~/can-i-use-mods-or-other-third-party-programs-with-fallout-76
- Bethesda Support, Bethesda.net Modding Guidelines (51731): https://help.bethesda.net/app/answers/detail/a_id/51731
- Bethesda Softworks Community Standards: https://bethesda.net/en-US/news/bethesda-softworks-community-standards
- Bethesda, Announcing Fallout Worlds (July 20, 2021): https://bethesda.net/en-US/news/announcing-fallout-worlds
- Windows Central, Fallout 76 interview (11 June 2024): https://www.windowscentral.com/gaming/fallout-76-interview-discussing-crossplay-mods-skyline-valley-nuclear-winter-and-the-future-with-bethesda
- Xataka Mexico on the same interview (26 June 2024): https://www.xataka.com.mx/videojuegos/a-pesar-promesas-bethesda-confirmo-mala-noticia-fallout-76-no-tendra-soporte-oficial-para-mods
- Windows Central, Bethesda committed to Fallout 76 mod support (11 Aug 2018): https://www.windowscentral.com/bethesda-commited-fallout-76-mod-support
- PCGamesN, Fallout 76 private servers mod support: https://www.pcgamesn.com/fallout-76/fallout-76-private-servers-mod-support
- PC Gamer, Fallout 76 players are already modding the beta (3 Nov 2018): https://www.pcgamer.com/uk/fallout-76-players-are-already-modding-the-beta
- Kotaku, modder rebuilding Fallout 76 in Fallout 4 (21 May 2019): https://kotaku.com/meet-the-modder-painstakingly-rebuilding-fallout-76-in-1834930738
- PCGamesN, Fallout: Appalachia mod: https://www.pcgamesn.com/fallout-4/fallout-mod-appalachia
- TweakTown, Fallout 76 ban email (27 Dec 2018): https://www.tweaktown.com/news/64272/fallout-76-cheaters-write-essay-unbanned/index.html
- Reclaim The Net, Map76 ban response (18 Nov 2019): https://reclaimthenet.org/bethesda-fallout-76-ban-controversy-response
- TheGamer, Fallout 76 data miner banned: https://www.thegamer.com/fallout-76-data-miner-banned-despite-efforts-to-help-bethesda/
- Nexus Mods, FO76Edit: https://www.nexusmods.com/fallout76/mods/30
- Nexus Mods, map mod readme listing SeventySix archives: https://www.nexusmods.com/fallout76/mods/154?tab=docs
- Mappalachia developer guide: https://github.com/AHeroicLlama/Mappalachia/blob/master/Developer_Guides/EditScripts.md
- Steam store page (age-gated, EULA unresolved): https://store.steampowered.com/app/1151340/Fallout_76/
- Steam community thread quoting article 44429: https://steamcommunity.com/app/1151340/discussions/0/3033726413397946325
