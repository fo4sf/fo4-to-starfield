# Quests, dialogue and voice: research findings and question framework

Area notes for the next-phase framework. Author: Claude (research agent, cloud), 2026-10-19. Builds on
`/mnt/project-files/research/engine-mechanics/quests.md`, `dialogue.md`, `papyrus-and-script-extenders.md` and
`/mnt/project-files/research/next-phase/voice-lipsync-companions.md` and `npcs-ai-factions-dialogue-quests.md`. It does
not repeat their record layouts; it adds what the community and tools offer, precedents, limits, and the questions.

Labels: **verified** (read on the source page or in a project file), **supported hypothesis** (evidence, not
confirmed), **unresolved**. Research caveat: partway through, the web proxy rate-limited page reads (HTTP 429). These
pages could not be read and are cited only as search hits, never as evidence: the Tale of Two Wastelands FAQ
(thebestoftimes.moddinglinked.com/faq.html), the Skyblivion FAQ and about page, the Starfield silent-player article on
TechRaptor, the GameSkinny article on FO4's line count, and a WEPC page on Starfield's languages.

## What the community and tools offer today

**Lip sync**
- The Starfield Creation Kit's **Audio > Run FaceFX Compiler** is the community's only documented route to `.ffxanim`.
  You load the masters and your plugin, put WAVs at `Data\Sound\Voice\<plugin>.esm\<VoiceType>\<number>.wav`, pick
  the master and compile. It writes `.animset` and then `.ffxanim`, and logs to `ffxc_00.log`. **verified**
  (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion; the same steps are in the Nexus guide
  "Complete Guide - Creating Lip Sync for Voice Files in Starfield" by Tbonex28b, https://nexusmods.com/starfield/mods/12576)
- Known traps from those guides **verified**:
  - no spaces anywhere in file names or folder paths;
  - the character's **body type must match the voice type** (the voice's gender does not matter);
  - the compiler looks frozen at some percentage while it is still working;
  - "Could not find audio file" means the path or number doesn't match;
  - a muted line in game means a missing master, a misplaced `.wem`, or a name mismatch.

  FaceFX's own forum adds that the embedded FaceFX is case sensitive for plugins with spaces, and that FaceFX staff
  send support to Bethesda (https://facefx.com/node/4600). **verified**
- **Bulk precedent.** The Nexus mod "Lip Sync Japanese" (Momidi, v1.20250531, updated 22 June 2025) regenerated
  Starfield's lip files for the Japanese voice set:
  1. decode the `Voices_ja` `.wem` to WAV with vgmstream;
  2. run the CK's FaceFX compiler against `Starfield.esm` and `ShatteredSpace.esm`;
  3. ship the `.ffxanim`.

  It says Starfield's lip generation does not support Japanese, so the match is approximate.
  https://www.nexusmods.com/starfield/mods/12842 **verified** (page). That a whole game's voice set went through the
  CK compiler is the closest precedent to our ~123k lines: **supported hypothesis**. The page gives no run time and no
  file count.
- **No headless route is documented for Starfield.** No command-line switch for the Starfield CK or for `ffxc.exe` was
  found on the Starfield wikis or Nexus. **unresolved**. Earlier engines did have one:
  - Skyrim's CK has `-GenerateLips:<plugin>` (https://ck.uesp.net/wiki/How_to_generate_voice_files_by_batch).
    **verified**
  - For FO4 the forum recipe is `CreationKit32.exe -GenerateLips:<plugin>.esp`, with crashes on newer master versions
    and a patch for them (https://forums.nexusmods.com/topic/8900503-generating-lip-files-any-new-and-improved-method).
    **verified** (forum)
  - So trying `-GenerateLips:` on the Starfield CK is the obvious first probe. **supported hypothesis**
- **CK-free FO4 tools exist.**
  - Runalip, and the "Revoice Tool" CLI (GoblinHours69, v0.2.0), use **FaceFXWrapper** plus FO4's own `LipFuzer.exe`
    and `xwmaencode.exe` to make `.lip`/`.fuz` for FO4 (https://www.nexusmods.com/fallout4/mods/107759;
    https://forums.nexusmods.com/topic/13466827-error-facefxwrapperexe-does-not-fit-when-generating-lip-files-with-runalip).
    **verified** (pages)
  - These make CE1 `.lip`, not CE2 `.ffxanim`. No Starfield equivalent was found. **unresolved**

**Voice audio**
- Community guides use these tools **verified**:
  - **vgmstream** to decode `.wem`;
  - **Wwise 2021.1.14.8108** to encode, with a "Sound Voice" import, and the "XboxCreation" profile for Xbox. The guide
    says the method also works for Windows.
  - an Audiokinetic project with a "modding-approval" label, or a newly registered project ID as the licence key.

  Sources: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox;
  https://www.nexusmods.com/starfield/articles/641
- **Starfield Silent Voice** (shadeMe, SFSE plugin, v1.5, needs the Address Library) gives unvoiced dialogue added by
  mods one shared set of silent voice files and turns subtitles on for them, so authors don't bundle their own.
  https://www.nexusmods.com/starfield/mods/3153 **verified** (page). It implies that an unvoiced line without a file
  misbehaves in vanilla Starfield. **supported hypothesis** (the page doesn't describe the vanilla failure). This
  matters for our breadth-first "text before voice" plan.
- **AI voice tools in this community:**
  - xVASynth v3 "SFVA Synth" (DanRuta, v3.0.4, Sept 2023) ships voice models trained on Starfield characters
    (Andreja, Barrett, Sarah Morgan, Vasco and others). Its permissions forbid use in sold mods and conversion to other
    games, and it asks users to say plainly that the voices are generated.
    https://www.nexusmods.com/starfield/mods/53 **verified**
  - "Adoring Fangirl" uses an ElevenLabs voice and added lip files later. https://www.nexusmods.com/starfield/mods/9957
    **verified**

**Strings and localisation**
- **xTranslator** reads and writes Starfield strings (a 2023 Nexus tutorial merges `Starfield_en.strings` edits with
  it). https://nexusmods.com/starfield/articles/245 **verified**
- "Bethesda Strings Editor" (0xra, v0.2.5) reads and writes `.strings`, `.dlstrings`, `.ilstrings`, BA2 and ESM, and
  translates with local Ollama models or Claude. https://www.nexusmods.com/starfield/mods/17158 **verified** (page)
- The project's archive census shows strings in all three kinds and voice archives per language in Starfield:
  `Voices_de`, `_en`, `_es`, `_fr`, `_ja`. FO4's base game has `Fallout4 - Voices.ba2` and DLC `_en` voice archives.
  **verified** (`docs/measurements/sf_ba2.json`, `fo4_ba2.json`)

**Quest debugging**
- Story Manager logs go to `Documents\My Games\Starfield\Logs\StoryManager` once `bEnableStoryManagerLogging=1` is set.
  Also available: `bEnableConditionLogging`, `bEnableSpeechChallengeLogging`, `bEnablePlanetContentManagerLogging`
  (`[General]` in `StarfieldCustom.ini`).
- An alias that fails to fill can stop a quest from starting with **no log line**. The suggested workaround: make every
  alias optional during development and trace each one in `OnQuestInit`.

  Source: https://forums.nexusmods.com/topic/13500091-how-to-detect-alias-errors-with-log-files **verified** (forum
  advice by LarannKiar and SKKmods)
- The same thread says Starfield cannot load ESPs properly and plugins must be ESM. **supported hypothesis**
  (experienced modders on a forum; consistent with the project's `.esm` plugins).
- SKKMods' "CK Papyrus Compiler command files" drive `PapyrusCompiler.exe` from batch files.
  https://www.nexusmods.com/starfield/mods/10320 **verified**

**Dialogue camera**
- Community camera mods are INI changes. "Camera and Dialogue Tweaks and INI QOL" changes dialogue FOV and behaviour
  through `StarfieldCustom.ini`, with no SFSE. https://www.nexusmods.com/starfield/mods/4687 **verified**
- Press reports of a mod that disables the zoom-in dialogue camera:
  https://www.gfinityesports.com/article/starfield-mod-rips-out-bethesdas-scary-convo-camera **unresolved** (not read)

## Precedents and lessons

- **Voice rights are the hardest precedent for this project.**
  - Capital Wasteland (Fallout 3 in FO4) stopped after talking with Bethesda. It used Fallout 3's voice files. "a
    proposed solution that would allow players to rip from their own copies of Fallout 3 was similarly untenable", and
    "Bethesda can't grant the rights to use the game's voice acting, since it's licensed rather than owned by the
    company." https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod **verified** (quoted; the
    article gives no year).
  - Fallout 4: New Vegas recast every voice (Kotaku, 18 Sept 2018). Its stated reasons: ripping needs decompiling,
    which the EULA forbids, and the voice contracts would need renegotiating.
    https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325 **verified**
  - On the other side, Tale of Two Wastelands converts the player's own Fallout 3 install. Its installer needs both
    games, has a CPU-heavy audio encoding step (about 40 minutes on a Ryzen 5 5600X) and writes about 17 GB.
    https://thebestoftimes.moddinglinked.com/ttw.html **verified**
  - Skyblivion's installer refuses to run without Oblivion and its DLC.
    https://content1.uesp.net/wiki/Skyrim_Mod:Skyblivion **verified**; whether Skyblivion reuses Oblivion's voices is
    **unresolved** (its FAQ could not be read).
  - Lesson (**supported hypothesis**): the "convert on the user's PC" model has living precedents (TTW for 10+ years),
    but Bethesda has told at least one team that this does not settle voice rights for a *cross-game* port inside a
    Bethesda engine. Our launcher reuses FO4's voices in Starfield, which is the Capital Wasteland situation. The owner
    should treat this as a release-phase legal question, not a technical one.
- **Volunteer voice casts are feasible but slow and uneven.**
  - Fallout: London had over 100 mostly volunteer actors; a reviewer criticised uneven recordings.
    https://en.wikipedia.org/wiki/Fallout:_London **verified**
  - Skywind cast about 3,000 NPCs with nearly 300 volunteer actors and is about 92% recorded, years in.
    https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/ **verified**
  - For us a recast is the fallback if the rights question goes badly, and it is a multi-year job at FO4's scale.
    **supported hypothesis**
- **Pin the game version.** Fallout: London had to stay on the pre-next-gen FO4 build, and Steam users had to downgrade
  by hand (Wikipedia, above). **verified**. The project already pins Starfield 1.16.244 and SFSE 0.2.21. Starfield
  Silent Voice's changelog shows plugins break and come back per runtime (v1.5 for 1.14.70). **verified**
- **AI voice draws pushback.**
  - Voice actors objected to AI clones of their voices in Skyrim mods (press, 2023; not read in full).
  - Take-Two had an AI-dialogue GTA V mod removed by DMCA (18 Aug 2023).
    https://gamedeveloper.com/business/take-two-removes-i-gta-v-i-mod-that-featured-ai-dialogue **verified**
  - Nexus (27 Apr 2023): AI content is allowed, but "may be removed if we receive a credible complaint from an affected
    creator/rights holder". It advises against AI voice without explicit permission.
    https://www.nexusmods.com/dispatch/news/14850 **verified**
  - Nexus later replaced its single AI tag with tiers (AI-generated, AI-assisted, AI promotional media), and undisclosed
    AI use "may be subject to moderation action". Voices are named as covered.
    https://pcgamer.com/gaming-industry/nexus-mods-finally-tightens-the-screws-on-ai-though-its-still-playing-softball-with-the-tide-of-slop
    **verified** (PC Gamer, 31 July 2026)
  - Bethesda's Creations rules, as reported: "Creations cannot contain anything produced through generative AI."
    https://www.pcgamesn.com/skyrim/mods-creations-ai **verified** as quoted by PCGamesN; the date and the official
    page were not read.
- **The scale of FO4's talk.** Press widely reported "more dialogue than Fallout 3 and Skyrim combined", about 111,000
  lines with about 13,000 for the player (owner's brief; KitGuru and GameSkinny search hits, not read). **unresolved**
  as a number. The project's own counts win: 78,089 INFO and 122,857 `.fuz` in the base game (verified,
  `dialogue.md`).

## Possibilities and hard limits in CE2

- **Possible as data, no CK needed:** quests, aliases, stages, objectives, topics, infos, scenes, branches and
  conditions (quests.md, dialogue.md). **verified** (record layouts)
- **Possible with the CK on the player's PC:** lip files through the FaceFX compiler. **verified** (community
  practice). Whether it can run unattended is **unresolved**, and that is the biggest launcher risk in this area.
- **Possible, needs Wwise or a self-written `.wem`:** voice audio. Wwise 2021.1.x is the family the community uses.
  **verified**. A `.wem` we write ourselves (PCM or ADPCM) is still **unresolved** (voice-lipsync-companions.md
  test 2).
- **Hard limit, not technical:** redistributing FO4 voice is out (settled: no assets ship). Converting it on the
  player's PC is technically the TTW model, but see the Capital Wasteland lesson above. **supported hypothesis**
- **Hard limit:** the player has no voice. A player-voice playback path would be custom (a scene Sound action or a
  script `Say` on the player), and the choice list does not wait for a line. **unresolved** (not tested). Settled for
  now: silent.
- **Hard limit for Creations (not Nexus):** no generative-AI content (as reported). An AI voice route rules out a
  Bethesda Creations release. **supported hypothesis** (official page not read)
- **Limit:** the FO4 per-line camera paths and speaker and listener idles have no INFO slot in Starfield (dialogue.md).
  Scene Camera and Animation actions are the only native place for them. **verified** (layout)
- **Limit:** lip quality for converted lines depends on FaceFX's English analysis of WAV plus text. Non-English FO4
  voice sets would get approximate lips, as Lip Sync Japanese shows. **verified** for Japanese; other languages
  **unresolved**

## Question framework

Phases: **NG** new game, **INT** interiors, **QP** quests and people, **FS** Fallout systems, **REL** release.
"Key" marks the 3 to 5 questions per mechanism that most shape the design.

### 1. Quest records and conversion (QUST, aliases, stages, objectives)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| Q1 | Does a converter-built quest with **external aliases** (Min00 takes 20 of 26 aliases from MQ102 and DN092) fill reliably when the source quest starts later or is stopped? | FO4's alias graph spans quests; one broken fill silently stops a quest from starting | external aliases exist in both layouts (quests.md); a failed fill can leave no log line (Nexus forum) | build two linked quests in the quest probe plugin and trace each alias in `OnQuestInit` with Story Manager logging on | deterministic FormID map; blocks every multi-quest mission | QP | **key** |
| Q2 | How many FO4 quests use each alias fill type, and especially "Find Matching Reference" with conditions that Starfield evaluates differently? | sizes the alias translator and finds the risky fills | Starfield inserted "Create Matching Ref" and reordered the match sub-types (quests.md) | offline scan of all 1,336 QUST plus DLC with Mutagen; count by fill type and condition function | records walker; informs Q1 | QP | |
| Q3 | Does our own **QTYP keyword** get its own heading in the Missions menu, or does it fall into a default group? | decides whether Minutemen, Brotherhood, Railroad and Institute missions can be grouped as in the Pip-Boy | only quests with a QTYP show (mission, verified in game); the heading rule is unknown | the quest probe (PR #393 branch) answers it in one load | blocks the quest-type mapping table | QP | **key** |
| Q4 | Do Starfield's per-stage reward blocks (XP, currency, items, affinity) carry FO4's XP and caps rewards with no script? | cheaper than porting reward script calls; ties into SPECIAL and caps decisions | Starfield moved rewards into stage data (quests.md) | one probe stage with a reward block; read the XP and item change in game | caps-vs-credits decision (economy page) | QP | |
| Q5 | How do Starfield's mission log and HUD handle FO4's **QTGL text globals** (counts in log text such as `MQ102FirstRaiderCount`)? | many FO4 objectives show live counts | QTGL exists in both (quests.md) | one objective with a global in the probe | none | QP | |
| Q6 | What does the **FTYP quest faction keyword** do in Starfield's menu and systems, and should our factions get one? | owner asked for ties to Starfield's faction mechanics; FTYP may drive a faction tab or faction-standing UI we can reuse | FTYP exists (quests.md); its effects are not read | read where FTYP is referenced in Starfield's UI files and scripts (ContentResources.zip); set one in the probe | factions page (factions-crime-relationships.md); blocks faction UI design | QP | **key** |
| Q7 | Do "Keep Instance", "Want Dormant" and "Run Once" behave as in FO4? | radiant repeatables and dialogue quests depend on them | flag bits keep their meaning (quests.md); behaviour **unresolved** | probe quest restarted twice | low risk | QP | |
| Q8 | Do Starfield's **pronoun choice** conditions or FO4's player-sex conditions (`GetIsSex` on the player) decide NPC lines addressed to the player? | FO4 has gendered lines (sir or ma'am, Nate or Nora); our new game makes a FO4-style character | Starfield lets players pick pronouns and changes dialogue (press, not read); FO4 uses conditions | condition-function scan of FO4 INFOs addressing the player; look at one Starfield pronoun-gated INFO in xEdit | character creation (saves-and-new-game.md) | NG | |

### 2. Quest scripts and fragments

The full Papyrus route is in papyrus-and-script-extenders.md. These are only the quest-facing questions.

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| S1 | Why did `OnStageSet` never fire on our mission quest, and do generated stage fragments (`QF_*`) fire? | fragments hold most of FO4's story logic | unresolved since the mission; the quest probe tests it | the quest probe in game | blocks the whole fragment route | QP | **key** |
| S2 | Do FO4 quest fragments compile unchanged against Starfield sources plus the `FO4SF:` shim? How many errors per 100 fragments? | sizes the shim and the converter's rename pass | about 77 FO4-only names on core scripts (papyrus page) | compile `QF_MQ102_0001CC2A` and 20 random fragments on the PC; log each error | Starfield compiler (CK) on the PC | QP | **key** |
| S3 | Can fragment script names keep FO4's `QF_<EDID>_<FormID>` pattern when FormIDs are remapped, or must the converter rename them and patch VMAD? | save safety and determinism | Papyrus saves script names; renaming later drops data (papyrus page) | decide the naming rule in decisions.md; one synthetic test | FormID map; must be frozen before public saves | QP | |
| S4 | Which FO4 quest scripts call Story Manager or event natives Starfield lacks (`OnStoryClearLocation`, `ResetSpeechChallenges`)? | small, but these break the compile | named in the native-gap table | call-site count over the 7,854 base sources | S2 | QP | |

### 3. Story Manager and radiant quests

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| R1 | Can our plugin add its own Story Manager branch so that Starfield's radiant nodes never pick our refs, and ours never pick theirs? | the fence between Starfield's procedural content and our world | SMBN/SMQN/SMEN exist; probe plugin built (quests.md) | quest probe: own branch under the Script Event node with "Shares Event" set | blocks every radiant quest | QP | **key** |
| R2 | Which FO4 SMQN nodes use events Starfield dropped (Kill Actor, Trespass, Craft Item, Arrest ...)? How many radiant quests need a script-sent event instead? | sizes the "rebuild the trigger" work | the dropped list is verified (quests.md); the usage count is not | offline SMEN/SMQN ENAM scan over Fallout4.esm and DLC | records walker | QP | **key** |
| R3 | Does Starfield's **Planet Content Manager** or any Starfield radiant system try to run in our planet's worldspace (bounty boards, POI quests, random encounters)? | unvetted systems already crashed us (Red Rocket outpost activator) | PCM logging switch exists (`bEnablePlanetContentManagerLogging`, Nexus forum) | turn on PCM and Story Manager logging; walk for 30 in-game minutes; read the logs | fence list (npcs-ai page section 8) | NG | **key** |
| R4 | Could FO4's Minutemen settlement requests and faction repeatables ride on Starfield's **Mission Board** block (QMTY, summary, detail lines) with our own board? | a ready-made radiant UI; owner wants Starfield mechanics reused on purpose | the Mission Board block is in QUST (quests.md); its scripts are not read | read one vanilla mission-board quest and its board script in ContentResources.zip; list what it assumes (ships, planets, credits) | economy (caps), factions | FS | |
| R5 | Do random encounters (FO4 `RE_*` quests via Change Location) fire on our worldspace's location records? | breadth: the Commonwealth feels alive | Change Location is kept in Starfield (quests.md) | one converted RE quest under our SM branch; walk into its location | world location records (world-cells-navigation.md) | QP | |

### 4. Quest markers, compass and map

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| M1 | Does an objective target on a forced-ref alias show a HUD marker and a local-map marker in our worldspace? | quests are unplayable without markers | unresolved; in the quest probe | quest probe in game | navmesh and the world-identity merge fix | QP | **key** |
| M2 | Do markers path across our cell boundaries and through doors with Starfield's pathing (Straight Line Pathing, Compass Ignores Locks flags)? | long FO4 missions cross many cells | flags exist in both (quests.md) | a probe objective in an interior behind a door | interiors and doors | INT | |
| M3 | Does editing our worldspace's cells break the surface map or POI markers the way overriding SFBGS008 cells did for others? | our world sits in its own plugin; a cell clash could kill the map | a forum report fixed missing maps by carrying SFBGS008 cell sub-blocks into a patch (https://forums.nexusmods.com/topic/13497605-info-mods-changing-world-spaces-may-break-surface-maps-poi-markers) | xEdit conflict view of our plugin against all Starfield masters | world plugin | NG | |

### 5. Dialogue records and the choice list

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| D1 | Does Starfield pick a topic's INFOs in TIFL order (replacing FO4's previous-INFO chain)? | every conditioned greeting and branch depends on it | **supported hypothesis** (dialogue.md) | one test topic with two conditioned INFOs | blocks the INFO converter's ordering rule | QP | **key** |
| D2 | How does the choice list show four FO4 slots, empty slots, and slot order? Do the Positive and Negative flags change anything? **Decided by owner, 2026-10-19 (page NG-16):** as recommended, full line, no own menu file. Owner's note: "Only have fo4 have that option for later phases." | UX of every FO4 conversation | the record allows a list (dialogue.md) | convert Preston's scene 006; screenshot in game | D1 | QP | **key** |
| D3 | Do we show FO4's short **prompt** (RNAM) or the full player line as the choice text? **Decided by owner, 2026-10-19 (page NG-16):** as recommended, full line, no own menu file. Owner's note: "Only have fo4 have that option for later phases." | FO4's prompts were often vague paraphrases that players disliked; with a silent player the full line may read better | FO4 stores both (dialogue.md) | owner decision plus a 10-line A/B mock in game | the silent-player policy (section 7) | QP | **key** |
| D4 | How are FO4 Charisma checks (INCC Easy, Medium, Hard) rolled in Starfield: a condition on our SPECIAL actor value, a perk entry point, or Starfield's SPCH minigame? | persuasion is central to FO4 talk | the INCC field exists in both; the stat behind it does not (dialogue.md) | one INFO with INCC and our Charisma AV; see what the UI shows and whether success rolls | SPECIAL design (special-perks-leveling.md) | QP | |
| D5 | Can Starfield's skill-gated INFO (PERK link) display FO4's perk-gated lines (Lady Killer, Black Widow, Intimidation) with tags in the list? | keeps FO4's perk dialogue visible | the Starfield INFO PERK field exists (dialogue.md) | one INFO gated on our converted perk | perk converter | FS | |
| D6 | Does INFO **subtitle priority** or "Force Subtitle" make unvoiced lines readable at the right pace? | the breadth-first plan ships text before voice | Silent Voice exists because unvoiced mod lines need help (Nexus page) | one unvoiced INFO with and without a silent `.wem`; with and without Silent Voice | V5 | QP | |
| D7 | How many FO4 topics are "SharedInfo" reuses, and does Starfield's DNAM shared INFO play the shared audio from **our** voice folder? | saves files and work; FO4 shares many lines | DNAM kept (dialogue.md) | one shared INFO across two topics in a probe | voice path rule (V2) | QP | |

### 6. Scenes and the dialogue camera

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | Does a converted FO4 scene (phases, Dialogue and Player Dialogue actions, NPC response folded into the choice) run start to end with the right speakers? | 3,568 scenes carry most of FO4's story talk | action layouts verified; no converted scene run yet | convert one short scene (Preston 006) with the general converter, not by hand | D1, D2, S1 | QP | **key** |
| C2 | What does the dialogue camera do with FO4 framing: Starfield's close first-person zoom, or a scene Camera action to recreate FO4's two-shot? | look and feel; FO4's 772 CAMS and 447 CPTH have no INFO slot | Starfield added Camera and Timeline scene actions (dialogue.md); community camera changes are INI tweaks (Nexus 4687) | one scene with a Camera action; compare with the INI-only zoom setting | animations | QP | |
| C3 | Do FO4's **NPC-to-NPC scenes** (overheard talk, scenes with "Headtrack Player") keep their timing without the per-line idle animations? | ambient life in Diamond City and Goodneighbor | idles dropped in Starfield INFO (dialogue.md) | one converted ambient scene | animation phase for later polish | QP | |
| C4 | Does scene audio in **radio** actions (FO4 action 6, Starfield 5) play our converted radio lines? | Diamond City Radio and Travis's scenes | type renumbered (dialogue.md) | one radio scene | radio page | FS | |

### 7. The silent player

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| P1 | Settled silent. Do we drop all ~13k (press figure, **unresolved**) FO4 player lines, or keep them as an opt-in later? | drives converter design and launcher time | settled: silent player (brief) | owner confirms "drop now, revisit after release" | D3 | QP | **key** |
| P2 | Do NPC lines that answer a voiced player line still make sense when the player's line was only a short prompt? | FO4 NPC replies often echo the player's spoken words | known design problem with FO4's paraphrase wheel (Game Developer article, search hit only) | read 50 random Player Dialogue choices with prompt, full line and NPC reply; score them | D3 | QP | |
| P3 | If a voiced player is ever tried: does a scene action or `Say` on the player play FO4's line before the NPC replies, and does the choice list wait? | keeps the option open | unresolved (voice-lipsync-companions.md) | later experiment, one scene | after release | REL | |

### 8. Voice audio pipeline and voice types

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| V1 | Do Codsworth's 20 Wwise-2026 `.wem` play in game, or do we need Wwise 2021.1.x as the community uses? | fixes the encoder version the launcher asks for | community guides use 2021.1.14.8108 (starfieldwiki) | the Codsworth greeting check after v6e | blocks the launcher's Wwise step | QP | **key** |
| V2 | What is the voice path rule for a non-Starfield master (`sound\voice\<our>.esm\<voicetype>\<id>.wem`), and does the file name follow the WEM file id or the INFO FormID? | every converted line depends on it | the community path is `Data\Sound\Voice\<plugin>.esm\<VoiceType>\` with numbered files (starfieldwiki) | the same Codsworth check; one human line | V1 | QP | **key** |
| V3 | Does a self-written PCM or ADPCM `.wem` play, so the launcher can skip Wwise? | removes a large third-party install from the player's setup | unresolved; no open Vorbis encoder exists (voice-lipsync-companions.md) | the no-Wwise test (cloud builds, PC plays) | V2 | REL | **key** |
| V4 | Wwise licensing: may the launcher drive a Wwise the player installed under their own Audiokinetic account? Does the "modding-approval" project label cover a free mod? | the launcher must not break Audiokinetic's terms | Wwise free for non-commercial use; project ID licence key step (starfieldwiki Xbox guide) | read Audiokinetic's current licence page; ask on the Starfield modding Discord or forum | release | REL | |
| V5 | What happens to a converted line whose `.wem` is missing (not yet converted)? Does it skip, flash, or hold for the subtitle? Do we need Silent Voice or our own silent files? | breadth-first ships text before voice | Silent Voice (SFSE) exists for this case (Nexus 3153) | one INFO with no file; then with a silent `.wem` | D6 | QP | |
| V6 | How many of FO4's 531 voice types are generic pools versus unique NPCs? Which human ones need a body-type match for lips? | lip generation needs voice type and body type to match (starfieldwiki) | 531 VTYP (dialogue.md) | offline VTYP plus NPC_ scan: voice type to race and sex | actors converter | QP | |
| V7 | Does Starfield's dialogue system treat our VTYPs like its own (GetIsVoiceType conditions, alias forced voice ALFV), with no fallback to vanilla lines? | the fence: no Starfield line from our NPCs | Starfield always-on dialogue quests (DialogueMiniBot) may also fire (voice-lipsync-companions.md) | Codsworth check: listen for vanilla mini-bot lines | fence list | QP | |

### 9. Lip sync

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| L1 | Can the Starfield CK generate lips **without the GUI** (a `-GenerateLips:` style switch like Skyrim's and FO4's), or can `ffxc.exe` run alone from the command line? | decides whether the launcher can make ~120k lip files unattended | no Starfield switch documented; Skyrim and FO4 CK have `-GenerateLips:` (ck.uesp, Nexus forum) | read-only PC job: `CreationKit.exe -GenerateLips:<plugin>.esm` on a 5-line test plugin; `ffxc.exe -h` | blocks the launcher's lip stage | REL | **key** |
| L2 | How long does the CK's FaceFX compiler take per 1,000 lines, and does it hold up over tens of thousands (Lip Sync Japanese suggests a whole game is possible)? | launcher time budget; the TTW precedent is 40 minutes for the whole install | no timing published | time 1,000 converted Codsworth or Preston lines on the PC | L1 | REL | **key** |
| L3 | Does the CK compiler need the WAV next to the `.wem`, and can WAVs be deleted after? Does it need the plugin loaded with every master? | disk use (WAV for 123k lines is large) and the launcher's step order | guides say keep WAV and WEM until lips work, then delete WAVs (Lip Sync Japanese, starfieldwiki) | same 1,000-line run; measure disk | L2 | REL | |
| L4 | Do the `StarfieldHumanMale` and `StarfieldHumanFemale` FaceFX actors give acceptable lips on converted FO4 faces (our NPCs use Starfield's head rig)? | quality of every human conversation | the actors exist in Tools (voice-lipsync-companions.md) | one Preston line on a Starfield-rig Preston, recorded side by side | actors and face conversion | QP | |
| L5 | Is converting FO4's own `.lip` (inside each `.fuz`) to `.ffxanim` worth a spike, given the CK route works? | a CK-free fallback | both FaceFX; the formats are not public (dialogue.md) | park until L1 fails | L1 | REL | |
| L6 | Does the CK's lip generation give usable results for FO4's non-English voice sets (German, French and others, if players own them)? | localisation of voice | Starfield's lip generation doesn't support Japanese (Lip Sync Japanese page) | one German line, if the owner's install has one | localisation | REL | |

### 10. AI voice and voice rights

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| A1 | Is converting FO4's licensed voice acting on the player's PC for use in another Bethesda game acceptable to Bethesda? Do we ask them before the Nexus release? **Decided by owner, 2026-10-19 (page RE-1):** as recommended, no voice reuse for now, subtitles only. Owner's note: "Did you guys ask? You have access to my email to send any" Whether to write to Bethesda is part of the RE-8 talk-through; nothing sent. | Capital Wasteland stopped on exactly this; voice is licensed, not owned | Capital Wasteland quotes (PCGamesN); TTW and Skyblivion use the player's own installs within or into Bethesda games | owner decision; optionally a polite written question to Bethesda's mod or community contact; read Bethesda's mod EULA wording on voice | blocks the release of any converted voice | REL | **key** |
| A2 | Policy: does the project use **no AI voice at all**, AI only for gap-filling with consent and labels, or AI never for real actors' voices? **Decided by owner, 2026-10-19 (page RE-2):** as recommended, no new voice in early releases. | Creations bans generative AI (reported); Nexus allows it with tags and removes it on complaint; voice actors object | sources in Precedents | owner decision, written in decisions.md | A1; decides whether Creations is ever an option | REL | **key** |
| A3 | If new lines are ever needed (patching gaps, our own connective quests), do we use volunteer actors (Fallout: London, Skywind model), the silent route, or text-only? | our own glue content will need lines | volunteer casts work but take years | owner decision; count the glue lines once quests are mapped | A2 | QP | |
| A4 | Which Nexus AI tag applies if any tool in the pipeline is AI (for example AI translation with Bethesda Strings Editor or machine-made lip curves)? | undisclosed AI use is moderated on Nexus | tiered tags since 2026 (PC Gamer) | read Nexus's tag definitions at release time | A2 | REL | |

### 11. Subtitles, strings and localisation

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| T1 | Do we write our master as **localized** (lstring ids into our own `.strings`, `.dlstrings`, `.ilstrings`) or with inline text? | FO4's text is in the player's string files; the converter must place ~78k INFO texts and every quest log | both games use the three-file scheme (records-and-plugins.md, supported hypothesis); xTranslator reads Starfield strings | build a 10-string localized test master with Mutagen; load in game; also open it in xTranslator | blocks the text converter | QP | **key** |
| T2 | Which FO4 languages can the launcher convert (strings `_en`, `_de`, `_es`, `_cn` ... on the player's PC), and do Starfield's fonts show them (Chinese especially)? | non-English players | FO4 strings seen for cn, de, en, es in the census; Starfield voice in de, en, es, fr, ja (sf_ba2.json) | list `Strings\` in the owner's FO4 install; load one Chinese string in game | T1 | REL | |
| T3 | Does Starfield cap subtitle or choice text length lower than FO4's 150-character response rule? | long FO4 lines may clip | FO4 150-character CK rule (dialogue.md) | in-game test with a 150-character line and a long prompt | D3 | QP | |
| T4 | Do NAM4 alternate lip text and NAM2 script notes survive to strings, and does the CK FaceFX compiler use alternate lip text? | better lips for lines with odd spellings | fields exist in both (dialogue.md) | read the CK lip run with one alternate-lip INFO | L1 | REL | |

### 12. Scale and the launcher pipeline

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| X1 | What are the real totals with all DLC (QUST, DIAL, INFO, SCEN, `.fuz` count and bytes per voice type)? | sizes every stage; Far Harbor and Nuka-World add a lot | base game only measured (npcs-ai page section 2) | recon.py over DLC esm and Voices ba2 (read-only PC job) | launcher budget | QP | **key** |
| X2 | Per-stage throughput on the owner's PC: decode, encode, lips, strings, records. What is the total first-run time, and can each stage resume? | TTW takes about 40 minutes and Fallout: London users complained about installs; ours could be many hours | Codsworth 20-line run only | time 1,000 lines through each stage | V1, L1 | REL | **key** |
| X3 | Final disk size: `.wem` (Vorbis about 4 GB estimated), `.ffxanim`, temporary WAV | player requirements page | estimate only (voice-lipsync-companions.md) | measure on the 1,000-line batch and scale | X2 | REL | |
| X4 | Which quests ship in the first breadth release (new game, then main quest, then factions), and is text-only dialogue acceptable for the rest at first? | breadth before polish (settled) | settled order: new game first | owner decision with a quest list from the census | X1 | QP | **key** |
| X5 | Can the converter generate every quest, scene and dialogue record **deterministically**, so the launcher can patch or resume with stable FormIDs across versions? | saves survive updates; voice file names derive from ids | deterministic FormID map exists for the mission | unit tests with synthetic fixtures (repo rule) | S3, V2 | QP | |

### 13. Ties to Starfield mechanics worth reusing (owner's request)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | Can FO4 faction standing (Minutemen, Brotherhood, Railroad, Institute, and the "faction enemy" outcomes) be driven from quest stages through Starfield's faction records and the FTYP quest faction keyword, with no Starfield faction content? | owner wants faction and relationship mechanics reused | factions page; FTYP and per-stage rewards exist (quests.md) | probe: a stage that changes our faction's relation and rank; read the result in game and in conditions | Q6, factions-crime-relationships.md | QP | **key** |
| F2 | Can FO4's companion affinity reactions in dialogue (Piper likes, Danse dislikes) use Starfield's INFO and DIAL **affinity event** fields (NAM8, ANAM AFFE) instead of FO4's scripts? | removes a big script port | AFFE is native in Starfield, 1,360 records (voice-lipsync-companions.md) | one INFO with our own AFFE on Codsworth; check the affinity change | companions.md | QP | **key** |
| F3 | Can Starfield's **SPCH speech challenge** host FO4's big persuasion moments (or should it stay unused)? | richer persuasion UI is available for free | SPCH layout verified (dialogue.md); FO4 checks map to INCC | design note only after D4 | D4 | FS | |
| F4 | Can Starfield's quest-level **time limit** (QTLM) and stage timer flags replace FO4 timer scripts (for example settlement attack windows)? | fewer scripts | QTLM and timer stage flags exist (quests.md) | probe stage with a timer | R4 | FS | |

## Sources

Project files (read 2026-10-19): `/mnt/project-files/research/engine-mechanics/quests.md`, `dialogue.md`,
`papyrus-and-script-extenders.md`, `README.md`; `/mnt/project-files/research/next-phase/voice-lipsync-companions.md`,
`npcs-ai-factions-dialogue-quests.md`; repo `docs/measurements/sf_ba2.json`, `fo4_ba2.json`,
`docs/research/engine-mechanics/records-and-plugins.md`.

Web (read unless marked "not read"):
- Starfield audio and lip sync guide: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion
- Porting custom audio to Xbox (Wwise 2021.1.14.8108): https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox
- Starfield sound files guide: https://www.nexusmods.com/starfield/articles/641
- Lip sync guide (Tbonex28b): https://nexusmods.com/starfield/mods/12576
- Lip Sync Japanese (Momidi): https://www.nexusmods.com/starfield/mods/12842
- FaceFX forum on the Starfield CK: https://facefx.com/node/4600
- Skyrim CK batch lips (`-GenerateLips:`): https://ck.uesp.net/wiki/How_to_generate_voice_files_by_batch
- FO4 lip generation thread: https://forums.nexusmods.com/topic/8900503-generating-lip-files-any-new-and-improved-method
- FO4 Revoice Tool: https://www.nexusmods.com/fallout4/mods/107759 ; Runalip thread: https://forums.nexusmods.com/topic/13466827-error-facefxwrapperexe-does-not-fit-when-generating-lip-files-with-runalip
- Starfield Silent Voice (shadeMe): https://www.nexusmods.com/starfield/mods/3153
- xVASynth SFVA Synth: https://www.nexusmods.com/starfield/mods/53 ; Adoring Fangirl: https://www.nexusmods.com/starfield/mods/9957
- Bethesda Strings Editor: https://www.nexusmods.com/starfield/mods/17158 ; xTranslator strings merge: https://nexusmods.com/starfield/articles/245
- Starfield Creation Kit overview: https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit
- Alias errors and logging: https://forums.nexusmods.com/topic/13500091-how-to-detect-alias-errors-with-log-files
- Worldspace overrides breaking maps: https://forums.nexusmods.com/topic/13497605-info-mods-changing-world-spaces-may-break-surface-maps-poi-markers
- CK Papyrus compiler command files: https://www.nexusmods.com/starfield/mods/10320
- Camera and Dialogue Tweaks: https://www.nexusmods.com/starfield/mods/4687
- Nexus AI policy 2023: https://www.nexusmods.com/dispatch/news/14850 ; tiers 2026: https://pcgamer.com/gaming-industry/nexus-mods-finally-tightens-the-screws-on-ai-though-its-still-playing-softball-with-the-tide-of-slop
- Creations and generative AI: https://www.pcgamesn.com/skyrim/mods-creations-ai
- GTA V AI mod takedown: https://gamedeveloper.com/business/take-two-removes-i-gta-v-i-mod-that-featured-ai-dialogue
- Capital Wasteland: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- Fallout 4: New Vegas recast: https://kotaku.com/fallout-4-modders-cant-use-new-vegas-voice-acting-so-t-1829149325
- Tale of Two Wastelands install: https://thebestoftimes.moddinglinked.com/ttw.html
- Skyblivion: https://content1.uesp.net/wiki/Skyrim_Mod:Skyblivion
- Fallout: London: https://en.wikipedia.org/wiki/Fallout:_London
- Skywind 2026: https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/
- Not read (rate-limited or search hit only): https://thebestoftimes.moddinglinked.com/faq.html ,
  https://techraptor.net/gaming/news/your-starfield-character-does-not-have-voice-bethesda-says ,
  https://www.gameskinny.com/h3gox/fallout-4-will-have-more-dialogue-than-fallout-3-and-skyrim-combined ,
  https://www.gamedeveloper.com/design/fallout-4-the-problem-with-voiced-protagonists ,
  https://www.gfinityesports.com/article/starfield-mod-rips-out-bethesdas-scary-convo-camera ,
  https://www.windowscentral.com/todd-howard-starfield-players-choose-pronouns
