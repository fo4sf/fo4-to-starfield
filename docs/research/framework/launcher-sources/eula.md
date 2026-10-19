# EULA / ToS review: a launcher that converts the player's own Fallout 4 data into Starfield

Research date: 2026-10-19. Author: Claude (research subagent). Reading only.

> **This is not legal advice.** It is a reading of contract text by a non-lawyer AI, done to work out what the
> project should ask a lawyer and what it should design around. Nothing here says the launcher is permitted.
> Labels follow docs/ai/research-log.md: **verified** = the quoted text says it; **supported hypothesis** =
> a reasonable reading of quoted text that a lawyer could dispute; **unresolved** = the text does not settle it.

## 0. Sources and how they were read

Direct `curl` to steampowered.com / bethesda.net was refused by the session's egress proxy, so every document
was fetched through the TinyFish fetch tool on 2026-10-19 and saved under
`/tmp/claude-0/-home-claude-fo4-to-starfield/981f8bb8-d11c-56b1-a518-2b9ee32bceac/scratchpad/research/raw/`.

| # | Document | URL fetched | Raw file | Read |
|---|---|---|---|---|
| 1 | ZeniMax Media Terms of Service, "Last Updated: November 12, 2024" | https://bethesda.net/data/tos/en.html and https://www.zenimax.com/en/legal/terms-of-service (redirect target of zenimax.com/legal_terms) | `raw/doc2.md`, `raw/g4.md` | All of it. The two copies are the same text (word-level diff ratio 0.97; the only differences are headings and bullet lists that one render dropped). No 2025 or 2026 version was found: zenimax.com, the canonical location named in the ToS, still says Nov 12, 2024. `https://documents.bethesda.net/terms-of-service` came back empty (`empty_content`). |
| 2 | Starfield: Creation Kit EULA (Steam app 2722710) | https://store.steampowered.com//eula/2722710_eula_0 | `raw/doc0.md` | All of it. The page holds the same EULA twice. Undated; store page says "© 2012-2024". |
| 3 | Fallout 4: Creation Kit EULA (Steam app 1946160) | https://store.steampowered.com//eula/1946160_eula_1 | `raw/doc1.md` | All of it (also on the page twice). Undated; store page says "© 2012-2022". |
| 4a | Fallout 4 game EULA (Steam app 377160) | https://store.steampowered.com//eula/377160_eula_0 (`_eula_1` returns "There was an error loading the content of this EULA") | `raw/g0.md` | North America/Latin America and UK texts read in full. The France/Italy/Germany/Spain/other regional texts were **not** read clause by clause (they are local-language versions). This is the old boxed-retail "Limited Software Warranty and License Agreement" from Bethesda Softworks LLC. |
| 4b | Starfield game EULA (Steam app 1716740) | https://store.steampowered.com//eula/1716740_eula_0 (`_eula_1` errors the same way) | `raw/g2.md` | All of it (also on the page twice). Modern ZeniMax EULA (mentions "Creation Credits"). |
| 5a | Bethesda Softworks Community Standards | https://bethesda.net/en-US/news/bethesda-softworks-community-standards | not saved (inline fetch result) | All of it. |
| 5b | Bethesda.net Modding Guidelines - Mods/Creations (help article 51731) | https://help.bethesda.net/app/answers/detail/a_id/51731 | not saved (inline fetch result) | All of it. |

The Steam store pages for Fallout 4 and Starfield redirect to an age gate, so the EULA links were taken from
Steam's `/eula/<appid>_eula_N` pattern (the same pattern the CK store pages use, verified on the 2722710 and
1946160 store pages). Not reviewed: the Bethesda.net launcher EULA (https://bethesda.net/data/eula/en.html,
linked in our README; it rendered only its title), the ZeniMax Code of Conduct (incorporated into both CK EULAs
by reference), the Bethesda Creations Online Durables Provider Agreement, and the Microsoft Services Agreement /
Xbox PC terms that may apply to Game Pass copies.

---

## 1. ZeniMax Media Terms of Service (Last Updated November 12, 2024)

**What it is.** The umbrella contract. Both CK EULAs and the Starfield EULA incorporate it by reference; the
Starfield EULA calls itself "Supplemental Terms" under it.

**Editor / Editor Tool definition** (Section 2.D "Game Mods") **verified:**
> "The term "Game Mod" means downloadable, user-generated Content developed or created by You or a third party
> using an Editor Tool (as defined below)."

> "If You desire to develop or create one or more Game Mods, then You will be required to download from a
> ZeniMax website or otherwise gain access to via a ZeniMax website one or more software tools through which
> You may create or develop Game Mods (each such tool is an "Editor Tool"). To obtain a copy of or get access to
> any such Editor Tool, You will be required to agree to the terms of a separate EULA (the "Editor EULA"). If
> there is a conflict between the terms and conditions in any such Editor EULA and the terms and conditions in
> these Terms of Service, the terms in the Editor EULA will control over the conflicting terms in these Terms of
> Service but solely for the purpose of the specific Editor Tool and not for any other purpose."

Note: the definition is "one or more software tools through which You may create or develop Game Mods". That is
plural and functional; it does not limit "Editor Tool" to CreationKit.exe.

**Content, copying, derivative works** (Section 2.A) **verified:**
> "Except as necessary to use the Services in compliance with these Terms of Service, You may not copy, use or
> download any Content from a Service unless You are expressly authorized to do so by ZeniMax in writing. You
> acknowledge and agree that You shall not reproduce, prepare derivative works based upon, distribute, publicly
> perform, or transmit any Content for commercial uses unless You obtained the express written consent of an
> authorized representative of ZeniMax. For clarification purposes, "derivative works based upon" Services
> and/or Content are works that are substantially similar, both in ideas and expression, to Services and/or
> Content. Therefore, if You or someone else creates a work and it is likely to bring to mind either or both
> Services (such as a Game) and Content, then it is likely that such work is a derivative work and as such may
> not be used for commercial purposes."

**Licence grant and restrictions** (Section 3 "Limited License to Use") **verified:**
> "ZeniMax grants to You, for Your personal, private and non-commercial use only, a non-exclusive, revocable,
> nontransferable license to access, receive, play, and use Services (including any Content which is made
> available by ZeniMax (including but not limited to Game Mods that You download from a ZeniMax website) as a
> part of a Service and then solely in connection with such Service) as set forth in these Terms of Service."

> "You may not (a) distribute, publicly perform or display, sell, transmit, publish, edit, reproduce,
> sublicense, rent, lease, loan or otherwise transfer any Game, Software, and/or Content, including without
> limitation any access keys; (b) modify, adapt, reverse engineer or decompile the Software, or otherwise attempt
> to derive source code or anti-cheating measures from the Software; (c) create any derivative works based upon
> any Services; (d) otherwise access, receive, play or use any Services except as expressly provided in these
> Terms of Service; (e) copy or download any Software or Content unless the Content is a Game Mod available for
> download from a ZeniMax website or is Downloadable Content (other than Virtual Currency) or You are otherwise
> expressly authorized to do so in writing by ZeniMax; [...] Any commercial use or play of a Service [...] is
> prohibited absent written permission by an authorized representative of ZeniMax."

The phrase "solely in connection with such Service" is the ToS-level hook for the cross-game question: Fallout 4
Content is licensed for use in connection with Fallout 4.

**Third-party tools / automation** (Section 9 "Your Use of the Services") **verified:**
> "You agree not to use any hardware or software or any other method of support that is not authorized by
> ZeniMax or that may in any way influence or advantage Your playing abilities or influence or disadvantage the
> playing ability of others, or influence or advantage Your access to or receipt, play or use of the Services or
> influence or disadvantage the access of others. Third-party tools, the use of "bots", "speed hacks",
> "deep-link", "page-scrape", "robot", "spider", algorithms or other programs that copy or monitor any part of
> the Services [...], software that transmits, manipulates, or distributes (including, but not limited to,
> "mirroring") the data stream or any aspect of the Services to another computer, server websites or other
> publication or distribution media, or software that permits You to access, receive, play or use Services
> without human input are examples of methods not authorized by ZeniMax."

> "You acknowledge that You do not have the right to create, publish, distribute, or create derivative works
> from or use any software programs, utilities, applications, emulators, or tools derived from or created for
> certain Content (such as Game(s)), except as authorized in writing by an authorized ZeniMax representative.
> You may use the Software to the extent expressly permitted by these Terms of Service and any applicable EULA."

This second paragraph is the one most directly aimed at a project like ours: a converter is plausibly a "tool
[...] created for certain Content (such as Game(s))". It would, on its face, also catch xEdit, BAE, Nifskope,
F4SE and SFSE, all of which have existed for years without enforcement; that is a fact about practice, not
about the text (see §8).

**Termination** (Sections 6, 14) **verified:**
> "ZeniMax may terminate Your access to and/or receipt, play or use of the Services (i) for violating these
> Terms of Service; [...] (iii) if Your access to or receipt, play or use of such Services infringes, or is
> suspected of infringing, another's rights or any intellectual property [...]. Any and all Content [...] will be
> considered forfeit immediately in the event of any cancellation, closure, or termination of Your Account by
> ZeniMax."

> "ZeniMax reserves the right to restrict, suspend or terminate these Terms of Service and Your Account
> immediately and without notice to You (i) if You breach these Terms of Service, [...] or (iv) [...] for any
> other activity whatsoever that is, in ZeniMax's sole discretion, unlawful, inappropriate, and/or in violation
> of the spirit of these Terms of Service or a Service".

**Charging money:** commercial use of Content, derivative works and Services needs ZeniMax's written consent
(quotes above). **Redistribution:** clause 3(a) bars distributing any Game, Software or Content.

---

## 2. Starfield Creation Kit EULA (Steam 2722710)

**What is "the Editor"** (preamble) **verified:**
> "THIS CREATION KIT™ SOFTWARE EDITOR TOOL AND RELATED DOCUMENTATION (THE "EDITOR") IS LICENSED, NOT SOLD, TO
> YOU."

> "The Editor is provided solely to You for installation by You according to the terms of this Agreement. Any
> use or reproduction of the Editor not expressly authorized by the terms of this Agreement prohibited. Any rights
> not granted to You in this Agreement are reserved by ZeniMax."

**Scope of use** (Section 1) **verified:**
> "The Editor enables You, the end user ("You"), to create new downloadable user generated content ("Game
> Mods"), including, without limitation, customized levels and other ways to adjust the experience of using and
> playing the ZeniMax computer game with which the Editor is intended for use (the "Product")."

> "All uses of the Editor are limited to:
> (i) Your personal non-commercial use solely in connection with the Product; or
> (ii) The creation of Game Mods, approved by Bethesda, in connection with one or more BGS Games,
> to be distributed through Bethesda Creations (hereinafter, "Creations Paid Content"). "Bethesda
> Creations" means any marketplace, ZeniMax store, app store or portal that ZeniMax, its affiliates,
> or its or their designees host and makes generally available for customers to procure Creations Paid
> Content through use of the Bethesda.net wallet or otherwise."

> "A. License. [...] a limited, personal, non-exclusive, non-transferable, and terminable license and right,
> during the term of this Agreement, to (i) install a copy of the Editor on computers that You own and (ii) use
> the Editor solely for the purpose of creating and developing Game Mods."

Note the full text of clause (ii): it is not a general "approved mods" path, it ends with "to be distributed
through Bethesda Creations (hereinafter, "Creations Paid Content")". Clause (ii) is the paid-Creations channel.

**Component parts, modification of the Editor** (1.C) **verified:**
> "You may not, in whole or in part: rent, lease, sell, sublicense, copy, photocopy, reproduce, translate,
> reverse engineer, derive source code from, modify, disassemble, decompile, or create derivative works based on
> the Editor; [...] The Editor is licensed to You as a single product. Its component parts may not be separated
> for use on more than one computer."

**Charging money** (1.D.a) **verified:**
> "You agree that, except for the Creations Paid Content, You will not charge or require, directly or
> indirectly, a fee or other consideration for others to download, install or use Your Game Mods [...] This
> includes distributing a Game Mods as part of any compilation You and/or other users may create. You further
> agree not to charge, accept or solicit, directly or indirectly, fees or non-monetary contributions for
> developing or creating Game Mods, including without limitation fees collected through "crowd funding." [...]
> You further agree that You are only permitted to distribute the Game Mods to users who have purchased the
> Product through authorized and legitimate distribution channels, solely for use with such users' own
> authorized copies of such Product".

**Ownership and third-party rights** (2.A, 2.D.c, 3) **verified:**
> "You will not permit any third party to download, distribute or use Game Mods developed or created by You for
> any commercial purpose."

> "Your Game Mods must not infringe or misappropriate any intellectual property or personal right of any third
> party."

> "You own or have sufficient legal rights in all Game Mods to grant to ZeniMax the licenses described in this
> Agreement. [...] each Game Mod is originally created by You [...]"

**Redistribution** (2.D.d) **verified:**
> "You may not distribute anything owned by ZeniMax or made available by a third party on the Bethesda
> Creations unless ZeniMax specifically agree to it. By "distribute" we mean (1) give copies of the Game Mods to
> anyone else; [...]"

**Required notice** (2.B) **verified:** every Game Mod must say "THIS MOD IS NOT MADE, GUARANTEED OR SUPPORTED BY
ZENIMAX OR ITS AFFILIATES."

**Licence back to ZeniMax** (2.D.a) **verified:** personal-use mods grant ZeniMax "an irrevocable, perpetual,
royalty-free, fully paid, worldwide, non-exclusive right and license [...] including [...] Your Game Mods [...] in
other Games and Services", "whether or not You provide a copy [...] to ZeniMax". Relevance: anything the player's
CK produces is, on paper, licensed back to ZeniMax; that is the player's grant, but the player cannot grant
rights in Fallout 4 content they do not own (Section 3 warranty).

**Termination** (Section 7) **verified:**
> "This Agreement shall automatically terminate if You violate or breach any term or condition in this
> Agreement. ZeniMax may terminate this Agreement at any time for any reason or no reason [...]. Upon termination
> of this Agreement for any reason, all licenses granted in this Agreement shall immediately terminate and You
> must immediately do (i) and (ii) above [destroy and remove the Editor]."

Also 1.A: "the licenses granted to You will terminate upon the earlier of the termination of this Agreement or the
termination of Your Account with ZeniMax", so a ToS account termination also ends the CK licence.
Section 10: ZeniMax may seek "injunctive relief, specific performance and equitable remedies with respect to
breaches of Section 1 or Section 2", outside arbitration.

**Third-party program invoking the tools:** no clause addresses it either way (**verified by absence** in a full
read). See §6.

**Cross-game content:** no clause names other games. Clause (i) ties use to "the Product" (Starfield); clause
(ii) allows "one or more BGS Games" only for Bethesda-approved paid Creations.

---

## 3. Fallout 4 Creation Kit EULA (Steam 1946160)

Same template, older; the differences that matter, all **verified**:

> "All uses of the Editor are for Your personal non-commercial use.
> All Game Mods developed or created by You using the Editor are for non-commercial use solely in connection
> with the Product, in each case subject to the terms and conditions of this Agreement."

- No clause (ii) and no "Creations Paid Content" carve-out; 1.D is "No Fees for Use" with the same text as the
  Starfield 1.D.a (fees, compilations, crowd funding, "only permitted to distribute the Game Mods to users who
  have purchased the Product [...] solely for use with such users' own authorized copies of such Product").
- Same "single product / component parts" sentence, same 1.C restrictions, same termination (Section 7), same
  licence back to ZeniMax including "in other Games and Services".
- The required notice reads "THIS MATERIAL IS NOT MADE, GUARANTEED OR SUPPORTED BY ZENIMAX OR ITS AFFILIATES."

Here "the Product" is Fallout 4. If the launcher ever used the Fallout 4 CK's own Archive2 (to unpack Fallout 4
BA2s), that use would fall under this EULA, whose only use is "personal non-commercial use", and its mods are
"solely in connection with the Product" (Fallout 4). **Supported hypothesis:** unpacking Fallout 4 archives with the
Fallout 4 CK's Archive2 so the data ends up in a Starfield mod is not "in connection with" Fallout 4. Reading
BA2s with our own code avoids this EULA entirely but not the ToS or the game EULA (§1, §4a).

---

## 4a. Fallout 4 game EULA on Steam (377160_eula_0)

The Steam-linked Fallout 4 EULA is the old Bethesda Softworks LLC "LIMITED SOFTWARE WARRANTY AND LICENSE
AGREEMENT", per region. North America / Latin America text, **verified**:

> "LICENSOR hereby grants you the non-exclusive, non-transferable, limited right and license to use one copy of
> the Software for your personal, non-commercial use on a single home or portable computer."

> "The Software may not be copied, reproduced or distributed in any manner or medium, in whole or in part,
> without the express prior written consent from LICENSOR."

> "You agree not to: (a) Commercially exploit the Software; (b) Distribute, lease, license, sell, rent or
> otherwise transfer or assign this Software, or any copies of this Software, without the express prior written
> consent of LICENSOR; (c) Make copies of the Software or any part thereof, except for back up or archival
> purposes; [...] (g) Reverse engineer, decompile, disassemble or otherwise modify the Software, in whole or in
> part;"

"THE SOFTWARE UTILITIES" (this is the mod clause, and the most direct cross-game text found) **verified**:
> "If the Software makes available, as a separate downloadable installer, a level editor or other similar type
> tools, assets and other materials (the "Software Utilities") that permit you to construct or customize new
> game levels and other related game materials for personal use in connection with the Software ("Customized
> Game Materials"), then [...]:
> (a) All Customized Game Materials created by you are exclusively owned by LICENSOR [...];
> (b) You will not use or permit third parties to use the Software Utilities and the Customized Game Materials
> created by you for any commercial purposes [...];
> (c) Customized Game Materials must be distributed solely for free;
> (d) Customized Game Materials shall not contain modifications to any other executable files;
> (e) Customized Game Materials must be used alone and can be created if the Customized Game Materials will be
> used exclusively in combination with the commercially released retail version of the Software.
> (f) Customized Game Materials cannot [...] contain any trademarks, copyright-protected work or other property
> of third parties (without a valid license); and
> (g) All Customized Game Materials must contain the proper credits [...] "THIS MATERIAL IS NOT MADE, GUARANTEED
> OR SUPPORTED BY THE PUBLISHER OF THE SOFTWARE OR ITS AFFILIATES.""

Clause (e) says material made with the Fallout 4 tools is "used exclusively in combination with the commercially
released retail version of the Software" (Fallout 4). **Supported hypothesis:** this is the clearest contract
text against Fallout 4-derived material running in Starfield, if the conversion counts as "Customized Game
Materials" (made with the Fallout 4 Software Utilities). If the launcher uses no Fallout 4 tool, it is arguable
that 4a's Software Utilities clause does not apply and the general licence and copying clauses do.

Termination, **verified**: "They shall terminate automatically without notice if you fail to comply with any
provision of this Agreement. Upon termination you shall immediately cease using the Software, and destroy the
Software".

UK text, **verified**: "You are not permitted to copy or otherwise reproduce the SOFTWARE or ACCOMPANYING
MATERIALS; modify or prepare derivative copies based on the SOFTWARE [...] You are expressly prohibited from
selling or using any characters or other components of the game for any purpose." Modifications "must require a
full, registered copy of the Software to run" and "must be distributed solely for free". "Using any characters or
other components of the game for any purpose" is broad; under English law (the UK text's governing law) it is
**unresolved** how far that reaches into a player's private, non-distributed use.

**Which Fallout 4 EULA governs a given player** is **unresolved**: the old Steam text above, the ZeniMax ToS
(which every Bethesda.net account accepted), and possibly a newer in-game EULA after the 2024 "next-gen" update
(not checked) may all apply.

## 4b. Starfield game EULA on Steam (1716740_eula_0)

**verified**:
> "Any use, reproduction, modification, or distribution of the Game not expressly authorized by the terms of
> this Agreement is expressly prohibited."

> "ZeniMax hereby grants [...] a limited, non-transferable, non-exclusive license (a) to install the Game Client
> on one or more computers owned by you or under your legitimate control, and (b) to use the Game Client solely
> as part of the Service for your non-commercial entertainment purposes only."

Section 3 "LIMITATIONS AND RESTRICTIONS": "Any use of the Game in violation of the License Limitations will be
regarded as an infringement of ZeniMax's copyrights in and to the Game and will be a breach of this Agreement.
You agree that you will not and will not assist any other person, under any circumstances, to:"
> "B. in whole or in part, modify, adapt, translate, reverse engineer, attempt to derive source code from,
> modify, disassemble, decompile, or create derivative works based on the Game; [...]
> D. use cheats, automation software (bots), hacks, mods or any other unauthorized third-party software designed
> to modify the Game or adversely impact any other persons playing of the Game or his/her experience of playing
> the Game;
> E. exploit the Game or any of its parts [...] for any commercial purpose [...];
> G. modify or cause to be modified any files that are a part of the Game Client in any way not expressly
> authorized by ZeniMax;
> [...]
> K. take any action or upload, post, transmit, promote, or distribute any content that infringes or violates any
> third-party rights;"

"will not assist any other person" matters for us: a launcher author who is also a Starfield licensee is
promising not to assist breaches by others. Clause D lists "mods" among "unauthorized third-party software
designed to modify the Game"; **supported hypothesis:** read with the CK EULA, this means mods not made in an
authorized way, since ZeniMax itself ships the CK to make mods. Writing a converted plugin and archives to
`Data\` does not touch Game Client files (G) the way an exe patch would, but SFSE-dependent features would.

Termination (Section 7) **verified**: "ZeniMax may terminate this End User License Agreement at any time for any
reason or no reason [...]. Upon termination by ZeniMax for any reason, all licenses granted in this Agreement
(including in the ZeniMax Terms of Service) with respect to the Game [...] shall immediately terminate".

---

## 5. Bethesda Community Standards and Modding Guidelines (for Creations / Bethesda.net)

These govern uploads to Bethesda.net / Creations. Our launcher uploads nothing, but they show how Bethesda reads
cross-game content. **verified**:

Bethesda.net Modding Guidelines (help article 51731), "Examples of why Mods are removed":
> "Do not upload mods using third-party content (licensed properties, content from other games, and other
> trademarked properties). This includes using assets from other Bethesda games."

> "Do not create mods that allow users to circumvent the need to purchase add-on content."

Community Standards, MODS:
> "No Crowdfunding or Monetization mod projects is allowed. – This is outlined in Section 1 of the EULA that
> states "No Fees of Use"."

> "We also do not allow uploading or linking of child killing mods or mods relating to copyrighted or
> trademarked content."

> "Only upload your creations. – Do not upload content from third party websites unless you have permission from
> the original creator."

**Supported hypothesis:** Bethesda's stated policy treats Fallout 4 assets inside a Starfield mod as "content from
other games" not allowed on its platform. This is a platform rule, not a licence term, but it is evidence of how
ZeniMax reads "in connection with the Product". The "circumvent the need to purchase add-on content" line means
the launcher must only convert DLC the player owns (it reads the player's own files, so this is a design check).

---

## 6. Answers

### Q1. Is driving the player's own Archive2.exe / PapyrusCompiler.exe from a launcher "use of the Editor"?

- **Are Archive2 and PapyrusCompiler part of "the Editor"?** **Supported hypothesis: yes.** The EULA defines the
  Editor as "THIS CREATION KIT™ SOFTWARE EDITOR TOOL AND RELATED DOCUMENTATION", says "The Editor is licensed to
  You as a single product. Its component parts may not be separated for use on more than one computer", and the
  ToS defines Editor Tool as "one or more software tools through which You may create or develop Game Mods".
  Both tools are installed by the Creation Kit download (per our docs/PLAY-AND-TEST.md and SETUP.md, not
  re-verified here) and exist to make Game Mods. `Tools\ContentResources.zip` ships the same way and is most
  likely also "the Editor" (it is part of the download and used to build mods); **unresolved** whether it counts
  as "Editor", "related documentation", or Starfield game Content.
- **Is a launcher invoking them "use"?** **Supported hypothesis: yes, by the player.** Nothing in either CK EULA
  mentions automation, scripting, command lines or third-party callers (**verified by absence**). The command-line
  interfaces exist and the CK itself calls them. The natural reading is that when the player runs a program that
  runs the player's own copy, the player is using the Editor, and the use must fit clause (i) or (ii). The
  launcher does not copy, modify, decompile or redistribute the Editor, so the 1.C restrictions are not engaged
  as long as the launcher only calls the installed files.
- **Is a third-party caller forbidden?** **Unresolved.** The CK EULA is silent. The ToS §9 paragraph against
  "tools derived from or created for certain Content (such as Game(s)), except as authorized in writing" and the
  "software that permits You to access, receive, play or use Services without human input" line could be argued
  to reach an unattended pipeline. The first applies to any modding tool; the second is written for online play
  and bots. A lawyer would have to say whether either reaches an offline converter.

### Q2. Is output that mixes Fallout 4 content into Starfield inside clause (i), (ii), or neither?

- **Clause (ii): no. Verified on the text.** Clause (ii) is "The creation of Game Mods, approved by Bethesda, in
  connection with one or more BGS Games, to be distributed through Bethesda Creations (hereinafter, "Creations
  Paid Content")". A local conversion is not approved by Bethesda and is not distributed through Bethesda
  Creations. Clause (ii) is also the only place in either CK EULA where more than one BGS game is mentioned, and
  it is reserved for Bethesda-approved Creations; that silence elsewhere supports reading clause (i) narrowly.
- **Clause (i): unresolved, leaning no. Supported hypothesis.** Clause (i) is "Your personal non-commercial use
  solely in connection with the Product", the Product being Starfield. The player's use is personal and
  non-commercial, and the output runs only in Starfield, so it is arguably "in connection with" Starfield. Against
  that:
  1. the Editor licence is to make "Game Mods", and the player warrants each one "is originally created by You"
     and does not infringe anyone's IP (Section 3); converted Fallout 4 content is not originally created by the
     player, and its owner is ZeniMax itself;
  2. Fallout 4 content is licensed to the player "solely in connection with such Service" (ToS §3) and, for
     Fallout 4 tools, "used exclusively in combination with the commercially released retail version of the
     Software" (Fallout 4 EULA, Software Utilities (e));
  3. Bethesda's own guidelines bar "assets from other Bethesda games" in uploaded mods.
  So the Starfield CK EULA, on its own, may not be what blocks this; the **Fallout 4 licences and the ToS** are
  the stronger obstacle, because they limit what the player may do with Fallout 4 content regardless of which
  tool is used.
- **Neither?** If clause (i) is read narrowly, the use is outside both clauses and therefore unlicensed ("Any use
  or reproduction of the Editor not expressly authorized by the terms of this Agreement prohibited"), which
  triggers automatic termination of the CK EULA (Section 7). **Unresolved** pending legal reading.

### Q3. Does the launcher itself (as distinct from the player) take on these terms?

**Supported hypothesis:** the project's developers are not parties to the player's licences by shipping code, but
(a) every developer who tests it is a licensee who promised not to "assist any other person" to breach the
Starfield EULA (Section 3); (b) the ToS forbids creating or distributing "tools [...] created for certain Content
(such as Game(s)), except as authorized in writing"; (c) secondary/contributory liability for a tool whose main
use might breach a licence or infringe copyright is a question of law (US/UK/EU), not of these texts.
**Unresolved.**

### Q4. Money, redistribution, termination: the practical lines (all **verified**)

- No charging, donations tied to development, crowdfunding or "non-monetary contributions for developing or
  creating Game Mods" (both CK EULAs 1.D). Whether a donation button for the *launcher* (not the mod) counts is
  **unresolved**; the safe reading is no money at all.
- No distributing the output: Fallout 4 game EULA (b), (c); ToS §3(a); CK EULA 2.D.d; and the CK EULA's
  "only permitted to distribute the Game Mods to users who have purchased the Product" would require at minimum
  that every recipient owns Starfield, but the Fallout 4 content inside is not the player's to give.
- Termination is automatic on breach (both CK EULAs §7, Fallout 4 EULA "TERMINATION") and at ZeniMax's discretion
  for any reason (CK EULAs §7, Starfield EULA §7, ToS §§6, 14). Account termination ends the CK licence (CK 1.A)
  and can forfeit purchased Content (ToS §6). The ToS adds that ZeniMax "may terminate other Accounts that share
  the same characteristics".

---

## 7. What a lawyer would need to settle

1. Whether Archive2.exe, PapyrusCompiler.exe and `Tools\ContentResources.zip` are "the Editor" (and whether
   ContentResources is instead Starfield game Content).
2. Whether a player running the CK's command-line tools through a third-party launcher is a use the CK EULA
   permits, and whether the ToS §9 "tools created for certain Content" and "without human input" lines apply to
   an offline converter.
3. The meaning of "solely in connection with the Product" in clause (i) when the input is another Bethesda
   game's content that the player owns.
4. Which Fallout 4 licence governs a current Steam / GOG / Game Pass / disc player (old Steam EULA, ZeniMax ToS,
   any newer in-game EULA), and whether Software Utilities clause (e) or the UK "using any characters or other
   components of the game for any purpose" text forbids private cross-game use.
5. Whether private, non-distributed format conversion of lawfully owned files is permitted by statute regardless
   of contract (US fair use / 17 U.S.C. §117 adaptation, EU Software Directive art. 5-6 interoperability, UK
   CDPA s.50A-50C and s.296A which voids contract terms against certain interoperability acts), and whether those
   rights cover game *assets* (art, audio, text) or only *programs*.
6. Developer exposure: contributory/inducement liability for publishing a converter, and the "will not assist any
   other person" promise in the Starfield EULA for developers who are Starfield licensees.
7. Whether ToS §2.A's "derivative works [...] substantially similar [...] likely to bring to mind" definition (used
   there for commercial use) changes anything for non-commercial private use.
8. Governing law and forum per player (Maryland for North America, England elsewhere, local mandatory law in the
   EEA/UK/Australia etc.; arbitration and class waiver in the ToS).
9. Trademark: whether the launcher's name, README or UI using "Fallout", "Starfield", "Bethesda", "Creation Kit"
   is nominative use or implies endorsement (CK EULA 2.C: "You may not state or imply" ZeniMax endorsement).
10. Whether written permission from ZeniMax is obtainable, and in what form (the texts repeatedly allow
    "express prior written consent of an authorized representative of ZeniMax").

---

## 8. What this review did not check

- Enforcement practice: decades of xEdit/BAE/Nifskope/F4SE/SFSE and cross-game ports (e.g. Skyrim→FO4 asset
  ports removed from Nexus/Bethesda.net, or ZeniMax DMCA history). Practice is not permission, but it shapes
  risk. Owned by the `precedents` agent.
- The ZeniMax Code of Conduct and the Bethesda.net launcher EULA (incorporated / linked, not read).
- Non-English regional versions of the Fallout 4 EULA.
- Any in-game EULA that the 2024 Fallout 4 update or Starfield patches show on first launch.
- That Archive2 and PapyrusCompiler are installed by the Starfield CK depot (taken from our own docs, not
  re-verified against a depot manifest).

---

## Questions this raises for our launcher

1. **Default stance.** Do we treat "personal, non-commercial, never distributed, only on a machine that owns both
   games" as the only supported mode, and say so on first run, in the README and in the output folder?
2. **Ownership checks.** Should the launcher check that the player has a legitimate Fallout 4 install (and each
   DLC it converts) and a Starfield install, and refuse to convert DLC not present, to match "circumvent the need
   to purchase add-on content"?
3. **Do we need the Fallout 4 CK at all?** If our own BA2 reader handles Fallout 4 archives, we avoid the Fallout
   4 CK EULA and its Software Utilities clause (e). Is that a design rule we write into decisions.md?
4. **Do we need the Starfield CK tools?** Could we write Starfield BA2s and compile Papyrus without Archive2 /
   PapyrusCompiler (our own packer, an open-source compiler such as Caprica), so the Starfield CK EULA's
   clause (i)/(ii) question disappears? What do we lose in correctness and what new risk (ToS §9 "tools created
   for certain Content") stays?
5. **ContentResources.zip.** Do we read it at all? If yes, only from the player's install, never copied into
   our repo, caches we publish, test fixtures or bug reports?
6. **Human in the loop.** Should the pipeline require an explicit player action (click "Convert", accept a
   notice) rather than run unattended, given the ToS line on software that runs "without human input"?
7. **Notices.** Should every generated plugin carry the CK EULA 2.B text ("THIS MOD IS NOT MADE, GUARANTEED OR
   SUPPORTED BY ZENIMAX OR ITS AFFILIATES") and the Fallout 4 EULA (g) text, and a "do not share this output"
   notice?
8. **Sharing prevention.** Should outputs be bound to the machine or install (e.g. refuse to load a conversion
   whose source hash doesn't match the local Fallout 4 files), so "just upload the output" is harder?
9. **Money.** Do we refuse all donations, sponsorships and paid support for the project, given 1.D's ban on
   "fees or non-monetary contributions for developing or creating Game Mods"? Does that extend to the launcher?
10. **Naming and branding.** Do we rename anything that uses "Fallout", "Starfield", "Bethesda" or "Creation Kit"
    in a way that could imply endorsement, and add a non-affiliation line?
11. **Permission.** Is it worth writing to ZeniMax legal for written permission (the texts' own exception) before a
    public release, and who would send it (the owner, not an agent: outreach is out of scope for agents)?
12. **Bug reports and logs.** How do we stop community reports, CI artifacts and test logs from carrying Fallout 4
    or Starfield content (strings, meshes, scripts), which would be redistribution?
13. **Account risk to the player.** Do we tell players plainly that ZeniMax can terminate the CK licence and their
    account for "any reason or no reason", and that this is their decision?
14. **Jurisdiction.** Do statutory interoperability rights (EU/UK) change what we can tell EU/UK players versus US
    players, and do we want a lawyer's view per region before release?
15. **Developers' own exposure.** Do contributors who test with their own copies need guidance, given the
    Starfield EULA's "will not assist any other person" promise?
16. **What would make us stop?** Which answers from a lawyer (Q2 "neither", or ToS §9 applying) would end the
    public-release plan and leave the project as private research only?
