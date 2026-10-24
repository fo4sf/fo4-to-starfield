# Radio, music and sound (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Voice lines and lip sync are in [../next-phase/voice-lipsync-companions.md](../next-phase/voice-lipsync-companions.md);
this file covers sound effects, music, ambience, acoustics and radio.

## In short
- **FO4** plays files directly: SNDR sound descriptors list `.wav`/`.xwm` files with category (SNCT), output model
  (SOPM) and conditions; MUSC/MUST name music files. **Starfield** replaced that with **Wwise**: records carry Wwise
  event GUIDs (WWED, "sound references"), audio lives in `.bnk` soundbanks + `.wem` (**verified**, xEdit + archives).
- SNDR, SNCT, SOPM do not exist in Starfield.esm (**verified**, FORMAT-GAP). Every FO4 sound needs a Wwise event that
  plays it. Verdict: **rebuild** (audio conversion + Wwise authoring or a generic-event trick).
- **Radio carries as a mechanism**: the ACTI "Radio Receiver" (RADR) struct, the scene "Radio" action and the
  `IsPlayerRadioOn` / `GetPlayerRadioFrequency` conditions all exist in Starfield's definitions (**verified**, xEdit).
  The FO4 talking activator (TACT) and the reference radio data (XRDO) do not: Starfield.esm has no TACT (verified
  count) and xEdit's SF REFR has no XRDO. Verdict: **translate + script shim**; in-game behaviour **unresolved**.
- MUSC/MUST, REVB, ASPC, SOUN exist in both but their sound fields change from file paths/SNDR to Wwise references.

## How Fallout 4 does it

### Assets (verified: docs/measurements/fo4_ba2.json)
- `Fallout4 - Sounds.ba2`: 6,924 `.xwm` + 1,948 `.wav`; totals with DLC 7,380 `.xwm`, 2,060 `.wav`; `music` top dir
  471 files; `Startup.ba2` 25 `.xwm`. Paths like `Sound\FX\AMB\AMB_BasementVS_01_2D_LP.wav`.
- Voice: 122,857 `.fuz` (xWMA + lip), covered in the voice note.

### Records (verified: xEdit wbDefinitionsFO4.pas; counts fo4_esm.json)
| Record | Count | Key fields |
|---|---|---|
| SNDR Sound Descriptor | 5,476 | CNAM type (Standard / Compound / AutoWeapon), GNAM category SNCT, SNAM alternate-for, ANAM sound files, ONAM output model SOPM, conditions, LNAM looping (None/Loop/Envelope), BNAM frequency shift/variance, priority, dB variance, static attenuation, DNAM child descriptors, rates-of-fire file table |
| SNCT Sound Category | 50 | flags (mute submerged, menu slider, pause in menus, immune to time speedup), parent, menu slider category, static volume, default menu value |
| SOPM Sound Output Model | 311 | flags (distance attenuation, doppler, ducking...), reverb send %, HRTF or speaker type, channel matrix, dynamic attenuation curves |
| SOUN Sound Marker | 221 | SDSC descriptor (SNDR), REPT repeat min/max/stackable |
| MUSC Music Type | 111 | flags (plays one selection, abrupt, cycle, maintain order, ducks, doesn't queue), PNAM priority + ducking dB, WNAM fade, TNAM tracks |
| MUST Music Track | 552 | CNAM type (Palette / Single / Silent), FLTV duration, DNAM fade-out, ANAM track filename, BNAM finale filename, LNAM loop data, FNAM cue points, conditions, SNAM sub-tracks |
| REVB Reverb Parameters | 59 | DATA decay time, HF reference, room filters, reflections, delays, diffusion, density; ANAM reverb class |
| ASPC Acoustic Space | 84 | SNAM looping sound (SNDR), RDAT region sound (interiors), BNAM environment type (REVB), XTRI is interior, WNAM weather attenuation dB |
| KSSM | 139 | keyword to sound mapping |
| FSTP / FSTS / IPDS / IPCT | 133 / 30 / 293 / 619 | footsteps and impact sounds by material |
| WTHR SNAM | | weather sounds typed Default / Precipitation / Wind / Thunder |

Music location: WRLD ZNAM music, cell music, location and ASPC; combat and discovery music via MUSC priorities
(**supported hypothesis**).

### Radio (verified fields; workflow supported hypothesis)
| Piece | Fields (xEdit) |
|---|---|
| TACT Talking Activator (FO4-only record, 43 in Fallout4.esm) | record flag 17 "Radio Station", SNAM looping sound, VNAM voice type; the DJ "speaker" for dialogue |
| ACTI flag "Is a Radio" + RADR Radio Receiver | SOPM sound model, frequency, volume, starts active, no-signal static. Used by placed radios (workshop radios) |
| REFR XRDO Radio | frequency, min weak distance, max weak distance, flag "Ignores Distance Checks". The transmitter reference |
| SCEN action type "Radio" | DATA topic (DIAL), HTID play sound (SNDR), DMAX looping max, VENC dialogue subtype |
| Conditions | `IsPlayerRadioOn` (613), `GetPlayerRadioFrequency` (614) |
| AACT | `APR0`/`APR1` Pip-Boy radio off/on |

Workflow from a community radio tutorial (Nexus FO4 12996, **supported hypothesis**): a quest (priority 30) holds a
reference alias forced to a `RadioTransmitter` reference with RadioData (station number, "Ignores Distance
Checks"); a MESG gives the station name as the alias display name; a scene that begins on quest start runs one Radio
action per song (each a SNDR) between Timer actions and loops with a Start Scene action; workshop radios duplicate
the `RadioDiamondCityReceiver` activators with a matching frequency. DJ talk is dialogue said by the TACT/alias
through Radio actions (topic). Papyrus `Game.IsPlayerListening(float)` reports the Pip-Boy station only (forum report,
**supported hypothesis**).

## How Starfield does it

### Assets (verified: docs/measurements/sf_ba2.json)
- 325,246 `.wem` and 36 `.bnk` in `Starfield - WwiseSounds01..05.ba2` + Patch (and Voices); files are named by ID
  under `sound/soundbanks/` (e.g. `2344192837.bnk`, `1000628662.wem`), with `.json` sidecars per bank
  (e.g. `sound/soundbanks/2344192837.json`).
- The CK2 Tools ship the Wwise project `wwise\Starfield\Starfield.wproj` (Wwise 2021.1.x); WwiseConsole itself is a
  separate install (**verified**, PC Tools listing in the voice note).

### Records (verified: xEdit wbDefinitionsSF1.pas; counts sf_esm.json)
| Record | Count | Fields / change |
|---|---|---|
| WWED Wwise Event Data | 489 | WSED start event GUID, CNAM condition (CNDF), WTED end event GUID |
| "Sound reference" (subrecord type) | | either an Event Set (start GUID, stop GUID, CNDF condition) or a Form (WWED). Used by SOUN, MUST, ASPC, AMBS, WTHR, SCEN radio action |
| SOUN Sound Marker | 649 | SMLS sound reference, DEVT detection level + radius; adds keywords, components |
| MUSC | 83 | same flags and PNAM/WNAM as FO4; adds VNAM re-evaluate interval, UNAM stability interval |
| MUST | 235 | same CNAM/FLTV/DNAM/FNAM/SNAM; file names ANAM/BNAM and LNAM loop data gone; MTSH single-track sound reference instead |
| REVB | 41 | FO4's DATA reverb numbers gone; RABG Wwise aux bus GUID + ANAM class |
| ASPC Acoustic Space | 488 | ASLS loop, WED0/WED1 interior/exterior sound, AAMB ambience set, AMUS music type, BNAM environment (REVB), RTPC attenuation and ratio, is-interior |
| AMBS Ambience Set (new) | 292 | ordered ambient sound events with weather and marker keywords, a Wwise switch group, planet customization |
| WKMF Wwise Keyword Mapping (new) | 79 | templates Ship Engine / Cockpit / Grav Drive / Creature Anim |
| AOPF Audio Occlusion Primitive (new) | 18 | geometry for occlusion |
| STAG Animation Sound Tag Set | 11 (FO4 21) | kept |
| ACTI RADR | | frequency, volume, starts active, no-signal static (SOPM sound model field gone) |
| SCEN "Radio" action | | DATA topic, WED0 voice override, WED1 sound effect (sound references), VENC subtype |
| TACT | 0 in Starfield.esm | defined in xEdit (game code still knows it), unused by vanilla |

Starfield's music system is Wwise-driven with MUSC/MUST as the Creation Engine layer (tracks point at Wwise events);
interactive music states inside Wwise are **supported hypothesis**.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| `.wav` / `.xwm` | `.wem` in a soundbank or loose | rebuild (convert) | ffmpeg decode works (PR #361); encode PCM/ADPCM ourselves or Vorbis via user's Wwise |
| SNDR (5,476) | WWED + Wwise event | rebuild | each needs an event GUID in a `.bnk`; generating banks without Wwise is **unresolved** |
| SNDR variance, looping, attenuation | Wwise containers / RTPC | rebuild in Wwise | random containers replace multi-file SNDR |
| SNCT categories | Wwise busses | rebuild / drop | menu volume sliders map to Starfield busses |
| SOPM | Wwise attenuation / positioning | drop or rebuild | |
| SOUN | SOUN | translate | SDSC to SMLS sound reference |
| MUSC | MUSC | data copy + translate | flags and priority carry |
| MUST | MUST | translate | file names must become MTSH Wwise references |
| REVB | REVB | rebuild | pick a Starfield aux bus by class |
| ASPC | ASPC | translate | add AMBS where FO4 used region sounds |
| Weather sounds | WTHR WSLD | translate | needs events for rain, wind, thunder |
| TACT DJ | NPC or ACTI speaker | script shim | Starfield.esm has no TACT; test whether the record still works |
| XRDO transmitter | none | script shim | quest + alias + our own range logic, or RADR only |
| ACTI RADR | ACTI RADR | translate | drop SOPM field |
| Scene Radio action | Scene Radio action | translate | SNDR song to WED1 sound reference |
| Pip-Boy radio tab | none | rebuild (UI) | see [ui-pipboy-hud-menus.md](ui-pipboy-hud-menus.md) |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Audio conversion** of ~9.4k FO4 SFX/music files (plus DLC) on the player's PC.
- **Wwise authoring**: events and soundbanks for every FO4 sound. Options, best first: (1) one generic Wwise event
  per category that plays an external/loose `.wem` chosen by ID (the voice path already does this for dialogue; whether
  SFX can reuse it is **unresolved**); (2) user-installed Wwise + a copy of `Starfield.wproj` driven by WwiseConsole
  in the launcher; (3) writing `.bnk` files ourselves (format documented by vgmstream/wwiser, effort **unresolved**).
- **Radio**: a script shim for the station list, range and Pip-Boy tab; SFSE only if the radio UI is a custom menu.
- **CK2**: may be needed to regenerate the bank `.json` sidecars or `WWED` GUIDs consistently (**unresolved**).

## Port status and links
- Voice: 20 Codsworth lines converted to `.wem` end to end, playback unproven (PR #361; voice note).
- No SFX, music or radio work yet. docs/FORMAT-GAP.md lists SNDR as missing in Starfield.
- Weather sounds tie to [weather-time-climate.md](weather-time-climate.md).
- Community precedent (verified, mod pages, found by the framework research 2026-10-19): three SFSE plugins play
  radio outside Wwise by decoding MP3, OGG, FLAC or WAV themselves. Starfield Galactic Radio (station packs as data,
  e.g. The Other Starfield Radio); Star Radio Player (portable and placed radios built through the outpost menu, placed
  radios fade with distance and pan, music lowers during dialogue, jingles by filename prefix); Starfield Radio on
  Carbon UI (no game state). FO4's world radios could ride the same pattern instead of Wwise events. Question for the
  framework: Wwise events or our own SFSE player ([../framework/engine-mechanics.md](../framework/engine-mechanics.md)).

## Open questions and cheap checks
- Does a loose self-written PCM `.wem` play from a SOUN? Same test as the voice note's first step.
- How Starfield maps a voice line to its `.wem` without a per-line event: read one bank `.json` sidecar (PC).
- Does a plugin TACT still speak in Starfield? One test record in a test cell (game).
- Grep Starfield `Game.psc` in ContentResources.zip for `IsPlayerListening` and radio functions.
- Count FO4 SNDR by CNAM type and by SNCT to size the Wwise work (xEdit or Fo4Export, read-only).
- List FO4 radio quests: scenes with Radio actions in Fallout4.esm + DLC (Fo4Export, read-only).

## Sources
- Repo: docs/measurements/*.json, docs/FORMAT-GAP.md, voice note.
- xEdit (TES5Edit dev-4.1.6): `Core/wbDefinitionsFO4.pas`, `Core/wbDefinitionsSF1.pas`, `Core/wbDefinitionsCommon.pas`,
  https://github.com/TES5Edit/TES5Edit
- [FO4 CK wiki: TalkingActivator](https://falloutck.uesp.net/wiki/TalkingActivator)
- [Nexus FO4 12996: radio station tutorial](https://www.nexusmods.com/fallout4/mods/12996)
- [Nexus forum: radio on/off detection](https://forums.nexusmods.com/topic/6990131-how-to-know-whether-a-radio-station-is-turned-on-or-off)
- [GECK wiki: Creating Radio Stations (FNV, background)](https://geck.uesp.net/wiki/Creating_Radio_Stations)
