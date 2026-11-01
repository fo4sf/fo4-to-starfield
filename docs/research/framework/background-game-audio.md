# Background-game audio: the original games play their own voices and music while we play in Starfield

The owner, 1 November 2026: "a mod for fallout 4, nv, 3, 2, 1 to have the games run in a state where our starfield
can call to it to have the game run voice lines when they should and music (they will run in the background while we
play i just need the audio so lets think about the idea)".

Status: **an idea under design.** Nothing here is built or tested. It ends in a staged plan whose first stage is a PC
check with no code. Written by Claude-cloud-2; review on #32 before any code. Labels as in AGENTS.md: **verified**,
**supported hypothesis**, **unresolved**.

## 1. Why this idea matters more than it looks

The hard part of audio in this port is not the format; it is the right to use the voices.
`engine-mechanics-notes/quests-dialogue-voice.md` ("Precedents and lessons") has the record:
- Capital Wasteland (Fallout 3 in Fallout 4) stopped after talking with Bethesda. Letting players rip from their own
  copies of Fallout 3 was "similarly untenable", because the voice acting is licensed, not owned. **verified**
  (press, quoted there)
- Fallout 4: New Vegas recast every voice for the same reasons. **verified** (press)

Every route the asset pipeline lists for audio copies or converts the original files (`asset-pipeline.md`, "Sound
and music", "Voice and lip sync"):
- `.fuz` or `.xwm` to `.wem` through Wwise on the player's PC;
- loose `.wem` files for radio music.

That is exactly what Capital Wasteland was told no about.

The owner's idea is different in kind. **Nothing is ripped, converted or copied.** The original game, installed and
licensed on the player's PC, runs and plays its own lines and its own music. Starfield only tells it what to play and
when. Whether that difference settles the rights question is not a technical question and is **unresolved**: it is
the owner's call, ideally with Bethesda, before release. As architecture, it is the only route we know of in which
the voice files never leave the game they were licensed for. That alone makes it worth designing properly.

## 2. What it looks like

```
 Starfield (the player plays here)                 Fallout 4 (running in the background, unfocused, small window)
 ---------------------------------                 ------------------------------------------------------------------
 our dialogue line starts  --cue-->  pipe  --->     audio host plugin (F4SE) -> plays INFO 0x00012345 as voice type X
 player enters a location  --cue-->        --->     pushes the original MusicType for it (exploration, combat, ...)
 combat starts / ends      --cue-->        --->     combat music on / off
 radio on, station N       --cue-->        --->     the original radio station plays
                           <--duration, done, amplitude envelope (for mouths)---
```

- **The host:** one source game at a time, the one whose world the player is in (Fallout 4 for the Commonwealth, New
  Vegas for the Mojave once build 2 exists).
  - Our host plugin keeps it in an empty interior, the "audio room".
  - It runs in a small window at the lowest settings with a frame cap, and gets no input (section 4).
- **The Starfield side:** our SFSE plugin, which exists as the FOCC sidecar, or for now the verified Papyrus-to-plugin
  log bridge (`sfse/FO4SFBorder`). It sends a cue when our converted dialogue line starts, the music context changes,
  or the radio is switched.
- **The transport:** a local named pipe (Windows) with the small line protocol in section 5. The launcher starts the
  host game before Starfield and closes it after.

## 3. What each part needs, and how sure we are

| Need | How | Label |
|---|---|---|
| The host keeps running and playing sound while Starfield has focus | `[General] bAlwaysActive=1` in `Fallout4Custom.ini` keeps Fallout 4 running unfocused; players report it works (Steam community threads on Fallout 4 running in the background) | **supported hypothesis** (community reports; the PC check S0 confirms) |
| Two games at once | Steam runs several different games at once on one PC; it blocks the same account on two machines and some anti-cheat, neither of which applies | **supported hypothesis** (Steam community) |
| The host plays one specific voice line | (a) Papyrus `ObjectReference.Say(Topic, akActorToSpeakAs, ...)` makes a hidden speaker say a topic "as if it were the specified actor" (the Creation Kit wiki); the engine then picks the response and its voice file, so the line's conditions must pass in the audio room. (b) An engine call that plays a given voice file, which the Skyrim library has (`BSAudioManager::BuildSoundDataFromFile`, used by Skyrim plugins to play files directly); the Fallout 4 library has `BSAudioManager` but whether it has this call is unchecked | (a) **verified** that the function exists; that it plays a chosen line out of its quest is **unresolved**. (b) **unresolved** |
| Spatial sound | The host moves its hidden speaker to the same offset and heading from its player as the Starfield speaker has from ours; the original engine does the 3D panning and falloff | **supported hypothesis** (engine 3D audio is standard; the mirroring is ours) |
| Music | Papyrus `MusicType.Add()` / `Remove()` push and pop the original music types (exploration, location, combat, dungeon); Starfield's own music is silenced in our worlds | **supported hypothesis** (functions exist; the stack's behaviour in an empty cell is unchecked) |
| Radio | The host turns the original radio station on and off with the Pip-Boy radio functions | **unresolved** |
| Timing | Starfield shows the subtitle; the host reports the line's duration and its end, and Starfield holds the line until then, as Starfield Silent Voice does for unvoiced lines (`quests-dialogue-voice.md`) | **supported hypothesis** |
| Moving mouths | The host streams the line's loudness (about 100 samples a second) back, and our SFSE plugin opens and closes the speaker's mouth by it. Skyrim's AudioUtil does exactly this from a wav's amplitude envelope. No `.ffxanim`, and no lip file leaves the host | **supported hypothesis** for the idea; on Starfield's faces **unresolved** |
| Latency | a pipe message plus one script frame in the host: tens of milliseconds | **supported hypothesis**; S1 measures it |

## 4. Risks we already know

- **Input leaks into the background game.** With `bAlwaysActive` on, Fallout 4 forces itself "active", so its raw
  input polling stays on and clicks meant for another window reach the background game. A Fallout 4 multiplayer
  project fixed exactly this (F4Multiplayer PR 124: polling off whenever the window is not in front, devices
  cleared). The host plugin must do the same, or the player's clicks in Starfield fire guns in Fallout 4.
  **verified** that it happens (reading Fallout4.exe 1.11.240, per that PR).
- **Cost.** Two Creation Engine games at once. The owner's PC already runs near its RAM limit with the local model
  loaded (guardian at 87 to 89%). The host must run in an empty cell, at minimum settings, in a tiny window, with a
  low frame cap. Starting the host only when needed and closing the local model while playing may still be required.
  S0 measures it.
- **Alt-tab behaviour.** Bethesda games are known to misbehave when they lose focus (Steam threads). The host never
  takes focus: the launcher starts it minimised or off-screen and never brings it forward. **unresolved** how well
  that holds.
- **Versions.** The host plugin is a second script-extender plugin per game and needs its runtime pinned, as Starfield
  is: Fallout 4 has two live runtimes (old-gen 1.10.163 and next-gen); F4SE and the Address Library for F4SE exist
  for both. **supported hypothesis**
- **Each player must own and install each game** the host runs, which the build already requires to convert it. The
  launcher refuses without it.

## 5. The cue protocol (draft)

One line per message, UTF-8, fields separated by a single tab, over a named pipe
(`\\.\pipe\fo4sf-audio-<game>`):

| From Starfield | Meaning |
|---|---|
| `hello 1 <game>` | protocol version, the source game expected (`fo4`, `fnv`, `fo3`) |
| `say <cue id> <speaker id> <plugin>:<INFO form id> <voice type editor id> <dx> <dy> <dz> <heading>` | play this response as this voice type, at this offset from the listener (metres, Starfield axes) |
| `move <speaker id> <dx> <dy> <dz> <heading>` | the speaker moved while talking |
| `stop <speaker id>` | cut the line (the player skipped it) |
| `music <plugin>:<MUSC form id>` / `music off` | the music context |
| `combat on` / `combat off` | combat music |
| `radio <station>` / `radio off` | the radio |
| `volume <music 0..1> <voice 0..1>` | follows Starfield's own sliders |

| From the host | Meaning |
|---|---|
| `ready 1 <game> <runtime>` | the host is in its audio room |
| `started <cue id> <duration ms>` / `done <cue id>` / `failed <cue id> <reason>` | the line's life |
| `env <cue id> <0..255 per 10 ms, hex>` | the loudness envelope for mouths, streamed in chunks |

Ids are the source game's form ids, which the converter already keeps (the identity work). The Starfield side
learns, for every converted line, which source INFO and voice type it came from.

## 6. Per game

| Game | Engine and extender | Host | Notes |
|---|---|---|---|
| Fallout 4 | Creation Engine, F4SE, CommonLibF4 | first: F4SE plugin, a tiny `FO4SF_AudioHost.esp` (the audio room, a hidden speaker, one quest) | build 1's game; everything above is written for it |
| Fallout: New Vegas | Gamebryo, NVSE (JIP LN NVSE adds sound functions; unchecked here) | second | voice files are `.ogg` with `.lip`; music `.mp3`; 32-bit, lighter than Fallout 4 |
| Fallout 3 | Gamebryo, FOSE | through New Vegas when the player has Tale of Two Wastelands, which runs Fallout 3's content in New Vegas's engine from the player's own copies; otherwise its own FOSE host | one host could then serve both |
| Fallout 1 and 2 | Interplay's 2D engine; sfall for Fallout 2 | last, maybe never | little speech (the talking heads) and music in `.acm`; no Creation Engine dialogue to map to; an engine reimplementation (fallout1-ce / fallout2-ce) as the host is possible in principle, its licence is unchecked; the owner decides whether these two are worth it |

## 7. The other routes, for comparison

| Route | Pros | Cons |
|---|---|---|
| **A. Background host (this note)** | no audio leaves the original game; exact original playback and music logic; no Wwise | heavy (two games at once); host plugins per runtime; mouths need the envelope trick |
| B. Our own player reads the player's game archives and plays the files | light, simple | it reads and decodes the voice files outside their game, the "rip from your own copy" model Capital Wasteland was told is untenable |
| C. Convert to `.wem` at install (Wwise) and let Starfield play them | Starfield's own 3D audio and sliders | the Wwise licence for players' batch conversion is unresolved (`asset-pipeline.md`), and the rights question is the same as B's |

Recommendation: design and prototype A for Fallout 4 first. Keep B and C on paper for anything A cannot do. Put the
rights question to the owner now, since it decides between A and the rest more than any technical result does.

## 8. Stages, each with a go/no-go

- **S0, PC, no code, about an hour of the owner's time:**
  - set `bAlwaysActive=1` in Fallout 4, start it windowed at the lowest settings, load a save in a quiet interior,
    then start Starfield;
  - go if: both run; Fallout 4's music and an NPC's line can be heard while Starfield has focus; memory leaves the
    PC usable;
  - record whether Starfield clicks reach Fallout 4 (section 4).
- **S1, offline then PC: the Fallout 4 host:**
  - an F4SE plugin (CommonLibF4) serving the pipe, the audio room plugin, and `say` by Papyrus `Say(..., akActorToSpeakAs)`
    for five fixed lines; input polling off while unfocused;
  - a test client sends the cues: no Starfield needed;
  - go if: each line plays within 100 ms of its cue, `started` and `done` come back, no input leak, an hour without a
    crash.
- **S2: from Starfield:** our SFSE plugin (or the log bridge) sends the cues for one converted conversation; the
  subtitle is held for the host's duration. Go if the conversation plays in order and in time.
- **S3: music, spatial sound, and mouths:**
  - `music` and `combat` for one location;
  - the speaker mirrored for 3D sound;
  - the envelope driving one Starfield face.
- **S4: New Vegas (NVSE), then Fallout 3** through Tale of Two Wastelands or FOSE.

Offline work possible now, without the PC:
- the protocol as code with its tests;
- the converter side that records each converted line's source INFO and voice type;
- the launcher side that starts and stops the host, with its own setting, off by default.

## 9. Questions for the owner

1. **Rights (the big one):** is "the original game plays its own audio" the route to take to Bethesda, instead of
   converting audio?
2. Fallout 1 and 2: in scope, given how little voice they have?
3. Is a second running game acceptable on the minimum spec we tell players about, or only as an option?

## Sources (read 1 November 2026)

- Fallout 4 running unfocused with `bAlwaysActive=1`:
  https://steamcommunity.com/app/377160/discussions/0/3211505894126608236/ and
  https://steamcommunity.com/app/377160/discussions/0/1291817208497230051/
- The input leak under `bAlwaysActive`, and its fix: https://github.com/Jolley71717/F4Multiplayer/pull/124
- `ObjectReference.Say(Topic, akActorToSpeakAs, abSpeakInPlayersHead, akTarget)`:
  https://falloutck.uesp.net/wiki/ObjectReference_Script
- Playing audio files directly through `BSAudioManager::BuildSoundDataFromFile`, and an amplitude envelope driving the
  mouth (Skyrim): https://github.com/crajjjj/AudioUtil
- `BSAudioManager` member functions in CommonLibF4: https://github.com/Dear-Modding-FO4/commonlibf4/pull/28
- Several Steam games at once on one PC: https://steamcommunity.com/discussions/forum/0/1735465524697733891/
