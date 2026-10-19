# Conversations: dialogue, scenes and voice (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: **verified** /
**supported hypothesis** / **unresolved**.

Main sources: xEdit `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas` (DIAL, INFO, SCEN, DLBR, SPCH, VTYP; read
2026-10-19), the Fallout 4 CK dialogue tutorial, the project's B4 spike and Codsworth voice work (#361).

## In short

- Same building blocks in both engines: a **DIAL** topic holds **INFO** responses (text, conditions, voice), topics
  sit in **DLBR** branches or are used by **SCEN** scenes, and every line plays from a file named after its INFO under
  `Sound\Voice\<plugin>\<VoiceType>\`. **verified** (xEdit; project voice work)
- FO4's conversations are **scenes** with a fixed **four-slot player wheel** (Positive, Negative, Neutral, Question),
  each slot pointing at a player topic and a matching NPC response topic. Starfield's scene "Player Dialogue" action
  holds a **variable list of choices**, each with a player topic, an NPC response topic and an optional scene to start.
  FO4's four slots become four entries in that list. **verified** (xEdit SCEN action layouts)
- Topic **subtype numbers were renumbered** (FO4 Hello = 88, Starfield Hello = 125; Starfield inserted ship, vehicle,
  smuggling and other subtypes). Both keep the 4-character subtype name (SNAM), so a converter maps by name, never by
  number. **verified** (xEdit enums)
- Starfield INFO **dropped** FO4's per-line camera path (SRAF), speaker and listener idles, "Previous INFO" ordering,
  audio output override and greet distance; it **added** affinity event, speech challenge, skill/perk link, a WEM file
  id per response, an animation block and head tracking. **verified** (xEdit)
- Persuasion is different machinery: FO4 has a Charisma check per INFO (Challenge enum Easy to Repeatable, color
  coded); Starfield has a **Speech Challenge** record (SPCH, a points minigame over a list of scenes) plus the same
  INFO challenge field. FO4's checks carry over as the INFO field; SPCH is not needed. **verified** (xEdit, both)
- Verdict: **translate as data** for topics, infos, branches and scenes (the biggest single converter in the area,
  3,568 FO4 scenes); **rebuild** the voice (`.fuz` to `.wem`) and lip sync (FaceFX `.ffxanim`, Creation Kit route);
  drop player voice (the player is silent; settled).

## How Fallout 4 does it

**DIAL (35,443).** EDID, FULL (topic text, used as the player prompt when no INFO prompt is set), PNAM priority,
BNAM branch, QNAM quest (every topic belongs to a quest), KNAM keyword, DATA (flags; **Category** Player / Command /
Scene / Combat / Favor / Detection / Service / Miscellaneous; **Subtype** enum of 125 values: Custom, ForceGreet,
Rumors, Call, Follow, ... Hello, Goodbye, SharedInfo, SceneChoice ...), SNAM 4-char subtype name (HELO, GREE, IDAT,
HIT_, CUST ...), TIFC info count. **verified** (xEdit)

**INFO (78,089).** Lives in its topic's group. Key fields (xEdit):

| field | meaning |
|---|---|
| VMAD (fragmented) | begin and end fragments (Papyrus) that run when the line starts or ends |
| ENAM | response flags (Goodbye, Random, Say Once, Random End, Force Subtitle, Can Move While Greeting, Has Capture, Requires Player Activation, Player Address ...); reset hours |
| TPIC / PNAM | previous topic / **previous INFO** (the editor order the game walks top to bottom) |
| DNAM | **shared INFO** (reuse another line's audio and text: one voice file, many uses) |
| GNAM | INFO group |
| responses (1..n) | TRDA: emotion keyword, response number, sound file (SNDR), interrupt %, camera target and location alias; NAM1 text; NAM2 script notes; NAM3 edits; NAM4 alternate lip text; SNAM/LNAM speaker and listener **idle animations**; SRAF **camera path** (CPTH) |
| CTDA | conditions (who may say it: GetIsID, GetIsVoiceType, GetStage, faction rank ...) |
| RNAM | player **prompt** (the short text on the wheel) |
| ANAM | speaker (NPC_) |
| TSCE / NAM0 | start a scene / phase when the line plays |
| TIQS | set the parent quest's stage on begin / on end |
| INCC | **speech challenge**: None, Easy, Medium, Hard, Always Succeeds, Easy Repeatable, Medium Repeatable, Hard Repeatable |
| GREE | greet distance (Hellos) |

**SCEN (3,568).** A scene is a quest-owned script of **phases**; each phase holds **actions** for alias actors. Action
types (xEdit, FO4): 0 Dialogue (one topic, looping times, player camera FOV, emotion type/value, head tracking,
subtype keyword, audio override), 1 Package, 2 Timer (can set a quest stage), **3 Player Dialogue** (PTOP / NTOP /
NETO / QTOP player topics for Positive / Negative / Neutral / Question, matching subtype keywords, then NPOT / NNGT /
NNUT / NQUT NPC response topics and subtypes, dialogue target actor), 4 Start Scene, 5 NPC Response Dialogue, 6
Radio. Flags per action include Face Target, Headtrack Player, Looping, Camera Speaker Target. Scenes carry fragments
on begin, end and each phase. B4: 243 of the 255 topics in `DialogueConcordArea` are scene topics, so FO4's story talk
is almost all scenes. **verified**

**The wheel.** The four slots are fixed directions on the controller: Positive (Y/top), Negative, Neutral, Question;
the prompt text (RNAM) is what the player sees; the full line is the voiced player response. A slot can be left
empty. Topics with the "SceneChoice" subtype show as choices. The 150-character response limit is a CK rule. **verified**
(CK tutorial; xEdit)

**Camera.** FO4's dialogue camera is the cinematic two-shot (CAMS camera shots, CPTH camera paths, chosen per line or
by default rules); first-person dialogue is an option in settings. **supported hypothesis** for the default-rule
details; the records are verified (CPTH 447, CAMS 772 in Fallout4.esm).

**Voice files.** One `.fuz` per INFO response: `Sound\Voice\Fallout4.esm\<VoiceTypeEditorID>\<INFO FormID>_<n>.fuz`.
A `.fuz` is "FUZE", version, lip size, the `.lip` data, then an xWMA RIFF (UESP; checked file by file by
`scripts/actors/codsworth_voice.py`). 122,857 `.fuz` in the base game. **verified**

**Voice types (VTYP, 531).** Each NPC (or its template) names a voice type; conditions such as GetIsVoiceType and
alias forced voices (ALFV) decide who can say generic lines. Generic NPCs share large pools (`MaleEvenToned`,
`RaiderMale01` ...); named NPCs have their own (`NPCMPrestonGarvey`). **verified** (B4)

**Lip sync.** FO4's `.lip` is FaceFX data generated by the CK from the WAV plus the text (or NAM4 alternate lip text).
**verified** (format container); the inner lip format is **unresolved** (not public).

## How Starfield does it

**DIAL (68,154).** Same as FO4 plus ANAM **Affinity Event** (AFFE) and TIFL, an explicit list of its INFOs. Category
enum unchanged; **Subtype** enum grew to 183 values and was renumbered (ship crew, ship combat, vehicle passenger,
smuggling, piracy, Max Carbon Dioxide, Blocking Hellos ...). SNAM subtype name kept. **verified** (xEdit)

**INFO (126,347).** Kept: fragments, response flags, previous topic, shared INFO, group, responses (emotion keyword,
text, notes, edits, alternate lip text), conditions, prompt, speaker, start scene and phase, set parent quest stage,
challenge, subtitle priority. Changed (xEdit):
- each response's TRDA is now emotion keyword, **WEM file id** (u32, the voice file's name), emotion out; TROT per
  voice type overrides; TROI original INFO; BNAM **animation** block; HNAM **head tracking** (aliases, force rotate).
- **gone**: previous INFO (PNAM ordering), speaker/listener idles, camera path, audio output override, greet
  distance (WED0 sound reference in its place).
- **new**: NAM8 affinity event, SCSP speech challenge, PERK skill/perk link (lines gated on a skill).

**SCEN (7,613).** Action types: 0 Dialogue, 1 Package, 2 Timer, 3 Player Dialogue, 4 Start Scene, 5 Radio, **6 Move,
7 Camera, 8 FX, 9 Animation, 10 Timeline** (new). FO4's "NPC Response Dialogue" (5) is gone and Radio moved from 6 to
5. Player Dialogue holds `Dialogue Topics`, a repeated **Choice** struct: ESCE player choice topic, PPST player
subtype, PNST NPC subtype, PASP start scene, PAPI/PAPN phase index/name, ESCS NPC response topic; plus an optional
NPC Reaction and head tracking. Action flags keep FO4's bits (7-11 and 27-30 still name the Positive/Negative/Neutral/
Question subtype flags), "Camera Speaker Target" became "Disable Camera Speaker Target". **verified** (xEdit)

**The choice list.** Starfield shows up to four (sometimes more) choices as a vertical list, with tags such as
[Persuade] and skill or background tags. **supported hypothesis** for "more than four" (player-facing; the record
allows a list). Starfield's camera in dialogue is a close first-person framing on the speaker. **verified** (game
behaviour, widely documented).

**Speech challenge (SPCH, new).** Quest, win and loss stages, a list of scenes (rounds), keywords, difficulty Easy /
Medium / Hard; the player spends persuasion points against a meter. **verified** (xEdit); rules from the Starfield wiki
Persuasion page.

**Voice files.** Wwise `.wem` named by the response's WEM file id under the voice type's folder (the mission's
Codsworth lines use `sound\voice\starfield.esm\robotminibota\`), plus a FaceFX `.ffxanim` per line for lips.
325,246 `.wem` and about 278k `.ffxanim` in Starfield. **verified** (project measurements; Codsworth work)

**Lip sync.** The Starfield CK generates `.ffxanim` from WAV in `Data\Sound\Voice\<plugin>\<VoiceType>\` (Audio > Run
FaceFX compiler). **supported hypothesis** (Starfield modding wiki; not run here).
Command line (verified, PC string scan of both CKs, job 18): Starfield's CK has `-CompileFaceFXAnims` but no
`-GenerateLips` (FO4's CK has `-GenerateLips` and `-GenerateSingleLip`); it runs `Tools\LipGenerator\LipGenerator.exe`
as a command-line tool (setting `sLipGeneratorPath`). FO4's CK calls LipGenerator with the WAV, the text,
`-Language:` and `-GestureExaggeration:`. So a headless route likely exists: call LipGenerator.exe directly, or the CK
with `-CompileFaceFXAnims` (**unresolved** until one PC run writes an `.ffxanim`).
Usage printed by Starfield's `Tools\LipGenerator\LipGenerator.exe` (verified, PC job 19):
`LipGenerator wav text actor.facefx actoranalysis.facefx [-Language:] [-OutputFileName:] [-AnimationGroupName:]`,
example `LipGenerator Test.wav test.txt -OutputFileName:foo.ffxanim`; languages USEnglish, UKEnglish, French, German,
Spanish, Italian, Korean, Japanese. It ships with FonixData.cdf (speech analysis data) and runs without a window, so
**lip generation can run unattended from the launcher** (supported hypothesis until one line is generated and plays).
It needs an actor `.facefx` and an actor analysis `.facefx` per face rig: where Starfield keeps them and which one fits
each converted voice type is **unresolved**. Starfield's archives ship **no** `.facefx` files, only 278,582 per-line
`.ffxanim` files named by WEM id under `sound/voice/(plugin)/(voicetype)/` (verified, PC job 21: FaceAnimation01 to 04,
FaceAnimationPatch and the DLC main archives). The actor files would come from the CK's tools or source data, if
anywhere. Found (verified, PC job 22): `Starfield\Tools\FaceFX\` holds four actor files, `StarfieldHumanMale.facefx`,
`StarfieldHumanFemale.facefx`, `GenesisDefault.facefx` and `GenesisDeadHead.facefx`; none in ContentResources.zip or
the FO4 folder. No file is named as an analysis actor, so which one goes in which LipGenerator slot is **unresolved**
until a trial run.
**Trial (verified, PC job 24):** a Windows text-to-speech WAV plus its text through LipGenerator with
`StarfieldHumanMale.facefx` and `GenesisDefault.facefx` wrote an `.ffxanim` (18,170 bytes) in seconds, no window, no
error; using the male actor twice (17,762 bytes) and passing the text inline instead of a file (17,052 bytes) also
worked. Header `FACE`, then "ZeniMax Media" and an `EFG` block. So **unattended lip generation works with the files the
free CK installs**. Still open: that the output matches a vanilla `.ffxanim` header and plays on a face in game, which
analysis actor is right, and which actor fits robots and creatures (Codsworth).

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| DIAL fields | DIAL | translate | subtype by **SNAM name**, not number |
| DLBR (132) | DLBR | data copy | Starfield adds a Dialog View link; leave empty |
| DLVW (1) | none in Starfield.esm (record defined but empty) | drop | CK layout only |
| INFO text, prompt, flags, conditions | INFO | translate | conditions by function **name** (see [records-and-plugins.md](records-and-plugins.md)) |
| INFO previous-INFO order | none | translate to **order in TIFL** | FO4 picks the first INFO whose conditions pass in editor order; keep that order in the topic's info list (**supported hypothesis** that TIFL order is the evaluation order; one test) |
| shared INFO (DNAM) | DNAM | data copy | keep, it saves voice files |
| response sound file (SNDR) | WEM file id | rebuild | a new id per converted line; our own voice folders |
| speaker/listener idles, camera path | Animation block / scene Camera action | rebuild later | first pass drops them (breadth first) |
| INCC Charisma checks | INCC (same field) | data copy | the check rolls on Charisma in FO4; in Starfield the field exists, the stat behind it does not (our SPECIAL lives in our own actor values); a script condition or perk entry point rebuilds the odds (**unresolved**) |
| scene phases and actions 0-4 | same types | translate | |
| Player Dialogue 4 slots | Choice list | translate | one Choice per non-empty slot; NPC response topic per slot into ESCS |
| NPC Response Dialogue action (5) | none | translate | fold into the Choice's ESCS |
| Radio action (6) | Radio (5) | translate | see [radio-music-sound.md](radio-music-sound.md) |
| scene fragments | Papyrus | rebuild | recompile |
| `.fuz` voice | `.wem` (+ `.ffxanim`) | rebuild | ffmpeg decodes xWMA; Wwise console encodes; 123k files plus DLC |
| `.lip` | `.ffxanim` | rebuild | CK FaceFX compiler (route a) or a converter (route b, unresolved) |
| player voice | none | drop | silent player (settled) |
| VTYP (531) | VTYP | translate to **our own** voice types | never place converted lines in a Starfield voice folder |

## What must be rebuilt, and what needs SFSE or the Creation Kit

- **Rebuild:** voice audio (Wwise), lip files, all INFO and scene fragments, dialogue cameras and idles (later),
  Charisma odds.
- **Creation Kit:** the practical route for `.ffxanim` lip files (run on the player's PC by the launcher; settled that
  the CK may be required). Not needed for the records.
- **SFSE:** not needed for dialogue. Possibly for a faithful four-direction wheel UI (Scaleform menu swap), which is
  polish, not breadth.

## Port status and links

- In game: the mission's Preston and Codsworth topics; Codsworth's 20 converted lines (Wwise 2026.1.3; whether they
  play is still an open check after v6e). docs/mission/when-freedom-calls.md, #361.
- Plans and scale: [../next-phase/npcs-ai-factions-dialogue-quests.md](../next-phase/npcs-ai-factions-dialogue-quests.md)
  section 5 and [../next-phase/voice-lipsync-companions.md](../next-phase/voice-lipsync-companions.md).

## Open questions and cheap checks

- Does Starfield evaluate a topic's INFOs in TIFL order (FO4's previous-INFO chain)? One test topic with two
  conditioned INFOs.
- How the Choice list renders four FO4 slots plus "empty" slots, and whether the Positive/Negative flags change
  anything in Starfield's UI: one converted FO4 scene (Preston's scene 006 is the candidate).
- `.wem` from Wwise 2026 decoding in the game: Codsworth's line check.
- Whether the Starfield CK's FaceFX compiler runs headless (launcher route a): **unresolved**; a look at the CK's
  command-line switches.
- A vanilla Starfield SCEN dump (Player Dialogue with four choices) to confirm the xEdit layout end to end.

## Sources

- xEdit: https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas (DIAL, INFO, SCEN, DLBR,
  DLVW), .../wbDefinitionsSF1.pas (DIAL, INFO, SCEN, DLBR, SPCH, AFFE).
- FO4 CK dialogue tutorial: https://ck.uesp.net/wiki/Fallout_4_Simple_Fetch_Quest_Tutorial_Chapter_6:_Creating_Dialog
- Starfield persuasion: https://starfieldwiki.net/wiki/Starfield:Persuasion
- UESP FUZ file format (cited in scripts/actors/codsworth_voice.py).
- Repo: docs/spikes/B4-mission-anatomy.md 1.5, scripts/actors/codsworth_voice.py, docs/FORMAT-GAP.md.
