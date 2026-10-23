# Original engine as an audio player (feasibility, 2026-10-19)

Owner's question (22:54Z): music and some content cannot be converted for legal reasons, so how possible is it to strip
down each Fallout game's own engine to play its voice lines and music, the way Oblivion Remastered keeps the original
engine underneath? Research only: no code, no PC job, no outside contact. Labels: **verified** (source read),
**supported hypothesis**, **inferred** (my reasoning, not checked), **unresolved**. This is a reading, not legal advice.

Voice position at the time of writing: Fallout 3 and New Vegas are a known no for voice conversion (owner 22:38Z and
22:54Z); Fallout 4 and 76 are open until Bethesda answers the letter; no 76 work until then (fo76-terms.md).

## Short answer

1. **Oblivion Remastered is not the pattern we could copy.** It is one program built by the rights holder with the
   original source code: the old engine is compiled into the Unreal Engine 5 game. We have no source code, so our
   version would be two separate games running side by side and talking to each other.
2. **Technically it is possible for Fallout 4, New Vegas and Fallout 3, and not for 76.** The player's own copy of the
   old game would run in the background with a script extender plugin that plays a line or song when our Starfield
   plugin asks. It works, but costs a second game in memory, has no lip sync and no 3D positioning without extra work,
   and is a large fragile build (two script extenders, two game versions to pin).
3. **Legally it most likely changes nothing for voice lines** (inferred). The problem Bethesda raised with Capital
   Wasteland was using the actors' performances in another game, not the file conversion, and the player's own copy did
   not save it. A voice line from New Vegas spoken by a character in our Starfield world is the same use whichever
   program decodes it. So this does not reopen New Vegas or Fallout 3 voices.
4. **The one place it plausibly differs is radio** (inferred). The player's own Fallout 4 playing its own radio
   station unchanged, with our mod only choosing the station, keeps licensed songs inside the game they were licensed
   for. No precedent tests this; it would need Bethesda's word before any release.
5. **Recommendation:** do not build it now. Keep the door open cheaply: one audio interface in the core with
   interchangeable sources (silent, converted, played from the player's own files, played by the original game), plus
   each silent voice file sized to the original line's length. Whatever Bethesda answers then slots in without a
   rebuild. If the owner wants, the radio idea is a good follow-up question for Bethesda (the owner approves any text).

## 1. What Oblivion Remastered actually does

- Virtuos' executive producer Alex Murphy: "We think of the *Oblivion* game engine as the brain, and Unreal Engine 5 as
  the body." **verified** ([HotHardware](https://hothardware.com/news/oblivion-remaster-released)). Wikipedia's
  infobox lists Unreal Engine 5 for graphics and Gamebryo for gameplay, and PC Gamer says Gamebryo handles the core
  such as physics and combat **verified** that they say so
  ([Wikipedia](https://en.wikipedia.org/wiki/The_Elder_Scrolls_IV:_Oblivion_Remastered), citing
  [PC Gamer](https://www.pcgamer.com/games/the-elder-scrolls/hot-damn-the-oblivion-remaster-is-125-gb-2600-percent-heavier-than-the-original-game-from-2006/)).
- The original data ships inside the remaster: `OblivionRemastered\Content\Dev\ObvData\Data\Oblivion.esm`, with the
  original ESM, ESP and BSA files, INI files and the music folder; the voice BSAs are larger because of added voice
  work; the old executable is gone. **verified** ([Vortex extension page](https://nexusmods.com/site/mods/1270);
  [Shazoo](https://shazoo.ru/2025/04/24/166941/v-failax-oblivion-remastered-skryvaetsia-pocti-ves-originalnyi-oblivion-slovno-kosti-dinozavra-pod-sloem-pocvy)).
  Classic `.esp` plugins load, and a script extender (OBSE64) exists **verified** (Vortex page).
- Audio: re-recorded ambient sounds and effects, "limited redone voice work", the original score kept. **verified**
  (Wikipedia, citing The Verge, Kotaku and PC Gamer).
- What that means for us (**inferred**): it is a single process and the two engines share memory and code, built with
  source access and with Bethesda owning or licensing every asset. None of those three conditions holds for us. Its
  legal position comes from being Bethesda's own product, so it is no precedent for a mod.

## 2. How our version would work (all games)

The player runs two games at once: Starfield in front (our build), and the old Fallout game in the background as an
"audio host".

- **Talking between them:** a small script extender plugin in each game (SFSE on our side, F4SE, xNVSE or FOSE on the
  host side) connected by a local named pipe or shared memory. Messages like "play line X", "stop", "volume". Local
  messages arrive in well under a millisecond; the host handles them on its next frame, so a line starts roughly one
  frame plus an audio buffer late, tens of milliseconds (**inferred**, not measured). Fine for dialogue and radio.
- **Starting two games:** Steam lets one account run several different games on one PC at once **supported hypothesis**
  (users say so; no Valve statement read: [Steam forum](https://steamcommunity.com/discussions/forum/10/2270319347573688560)).
- **Background running:** Fallout 4 pauses when it loses focus. `bAlwaysActive=1` under `[General]` is the usual fix;
  reports conflict on whether it works and nobody says whether audio keeps playing **unresolved**
  ([Steam thread](https://steamcommunity.com/app/377160/discussions/0/4778901811094055005)). A host plugin could also
  patch the pause, but that is unwritten work.
- **"Stripped down":** none of these engines has a headless or audio-only mode that I found (**unresolved**: absence not
  proven). Stripping means the host still starts its renderer and loads its data, then sits at the main menu or in an
  empty cell, ideally in a tiny or minimised window. Cost: a second game's memory (likely a few GB for Fallout 4, much
  less for the 32-bit New Vegas and Fallout 3, **inferred**, needs a measurement) and some GPU time, on top of
  Starfield, on the player's machine.
- **Lip sync:** the host plays sound only; Starfield's faces need Starfield lip files. Making those means running
  LipGenerator and FaceFX over the original audio, which is a converted derivative of the voice line again
  (**inferred**), so the clean version has unmoving mouths (or a generic jaw flap).
- **3D sound:** the host's 3D audio needs a speaker inside the host's world. Simplest is to play the line flat and set
  volume and left-right balance from the Starfield speaker's position ourselves (**inferred**).
- **Timing:** Starfield's conversation waits for its own voice file. If each silent file we already plan is cut to the
  original line's length (read from the file header, no audio copied), Starfield's pacing and subtitles match the host's
  playback (**inferred**; whether a length counts as derived data is part of the legal question).
- **Failure modes:** host crash means silence (Starfield carries on); alt-tab and focus edge cases; two script extender
  versions to keep in step; the player must keep the old game installed and at a supported version.

## 3. Game by game

| Game | Can it be an audio host? | Voice (owner position) | Music | Verdict |
|---|---|---|---|---|
| **Fallout 4** | Yes, with F4SE (we already pin 1.10.163). Voice files are `.fuz` (lip data plus xWMA), music and radio `.xwm` **verified** (engine-mechanics/radio-music-sound.md, next-phase/voice-lipsync-companions.md). Background pause **unresolved**. | Open until Bethesda answers. If yes, plain conversion is simpler and gives lip sync; if no, a host does not obviously fix it (section 4). | The best case for a host: Fallout 4's own radio stations played by Fallout 4 (section 4). | Possible; only worth it for radio, and only on Bethesda's word. |
| **New Vegas** | Yes, with xNVSE (exists, **supported hypothesis**: widely used, its page not re-read here). Voice `.ogg` plus `.lip`, music `.ogg` **verified** (findings/asset-conversion.md Q36). 32-bit, so lighter. | Known no (owner 22:54Z). A host is the only way NV voices could ever play, since the files never leave NV, but the reason for the no (actors' licensed performances used in another game) still applies (**inferred**). F4NV, the NV-into-FO4 port, re-recorded voices and music "to avoid legal ramifications" **verified** (findings/precedents.md section 6). | Radio New Vegas licensed songs: same reasoning as Fallout 4 radio. | Technically possible; does not change the no. Only Bethesda's word could. |
| **Fallout 3** | Yes in principle, with FOSE. Same audio formats as NV (asset-conversion Q36). Older and more fragile on modern Windows (**inferred**, not checked). | Known no: Capital Wasteland extracted Fallout 3 audio; Bethesda staff hinted it was illegal, a lawyer called it "sketchy as all hell", the voice acting is licensed, not owned, and players extracting from their own copies was "also deemed unworkable" **verified** (findings/precedents.md section 5). | Galaxy News Radio licensed songs: same reasoning as above. | No for voice; radio only on Bethesda's word. |
| **Fallout 76** | No. Online only, no offline mode, and Bethesda has banned accounts for running third-party programs, including a shader mod, as "cheating" **verified** ([HotHardware, 2018](https://hothardware.com/news/bethesda-bans-modders)). Driving a logged-in 76 client from another program risks the player's account and breaks the Terms of Service (fo76-terms.md). | Open, but no 76 work until Bethesda answers. | Same. | Not feasible; do not pursue. |

## 4. What it changes legally (reading, not advice)

- **Voice lines:** the documented objection is the use, not the method. Capital Wasteland's halt was "entirely related
  to audio" and the performances are licensed to Bethesda for that game (findings/precedents.md section 5). A Nexus
  moderator called re-recording audio from gameplay "essentially the same as just using the original audio assets"
  (findings/legal-policy.md item 10). By the same logic, having the original game decode the line while the character
  speaks in our world is the same use (**inferred**). So the host does not reopen New Vegas or Fallout 3 voices, and for
  Fallout 4 it only helps if Bethesda's answer draws that exact line.
- **Licensed songs** (the radio stations' period records) are a separate question from Bethesda's own recordings:
  Bethesda licenses them from labels and publishers for each game; the terms are not public (**unresolved**). A Nexus
  moderator's ruling that "requiring the user to have both installed would be different" (legal-policy item 10) is a
  forum post, not policy. The strongest form of the host idea is radio: the player's own Fallout 4 plays its own
  station, unchanged, from its own files; our mod only picks the station and volume, and nothing is copied out of the
  game. That keeps the songs inside the product they were licensed for, which is the one place where running the old
  engine is plausibly different from converting (**inferred**; no precedent found either way). The DJ's news lines
  would follow the host's own quest state, not ours, unless we drive the host's quests, which is more cross-game use.
- **Bethesda's own score** (non-licensed music): ownership terms not checked (**unresolved**); it sits with the voice
  question in the letter rather than with the licensed songs.
- **Simpler alternative with the same legal standing:** an SFSE plugin that reads the player's own archives at play time
  and decodes the audio itself, the way three existing Starfield radio plugins already play MP3 and OGG outside Wwise
  (findings/fallout-systems-precedents.md F6). No second game, no copies written to disk, but legally it is the voice
  question again (**inferred**). For licensed music, the established safe route stays "bring your own music": radio
  frameworks that play the player's own files (same F6 table).

## 5. What would make it worth building

- Bethesda answers the letter in a way that distinguishes "played by the original game" from "converted" (unlikely to
  come unprompted). If the owner wants to ask, the radio case is the clean question; any text needs the owner's approval
  of the exact wording, and nothing is sent by a thread.
- Cost if it ever goes ahead (**inferred**, rough): a host plugin per game, one SFSE client, an audio interface in the
  core, background-running and focus fixes, and a measured memory budget. A proof of concept for Fallout 4 radio alone
  is the smallest useful slice.

## 6. Cheap groundwork now (no decision needed)

- One audio interface in the core with interchangeable sources: silent, converted, runtime-decoded from the player's
  files, original-game host. The current silent plan is just the first source. This fits the owner's rule of getting a
  choice right early where a wrong one would mean a rebuild.
- A stable line id map (source game, dialogue record and response number to our line) and each silent file cut to the
  original line's length, so any later audio source plays in sync without touching quests or dialogue.
- Radio stations as data (station, track list by id, DJ lines) rather than baked audio, matching the radio frameworks.

## Question rows for the Framework thread to record (suggested)

- Does running the player's own original game as an audio host change the voice answer for any game? Suggested answer:
  no for Fallout 3 and New Vegas; for Fallout 4 only if Bethesda says so. (ties to REL-26)
- Should a later message to Bethesda ask specifically about the player's own Fallout 4 playing its own radio stations
  while our build runs? Owner decision; owner approves any text.
- Should the core's audio layer take interchangeable sources from the start? Suggested: yes, cheap now, a rebuild later.
- Fallout 76 as an audio host: closed (online only, ban risk, Terms of Service).

## Sources

[HotHardware: Oblivion Remastered](https://hothardware.com/news/oblivion-remaster-released) ·
[Wikipedia: Oblivion Remastered](https://en.wikipedia.org/wiki/The_Elder_Scrolls_IV:_Oblivion_Remastered) ·
[PC Gamer: 125 GB](https://www.pcgamer.com/games/the-elder-scrolls/hot-damn-the-oblivion-remaster-is-125-gb-2600-percent-heavier-than-the-original-game-from-2006/) ·
[Nexus: Oblivion Remastered Vortex extension](https://nexusmods.com/site/mods/1270) ·
[Shazoo: original files inside the remaster](https://shazoo.ru/2025/04/24/166941/v-failax-oblivion-remastered-skryvaetsia-pocti-ves-originalnyi-oblivion-slovno-kosti-dinozavra-pod-sloem-pocvy) ·
[HotHardware: Fallout 76 bans](https://hothardware.com/news/bethesda-bans-modders) ·
[Steam: Fallout 4 bAlwaysActive](https://steamcommunity.com/app/377160/discussions/0/4778901811094055005) ·
[Steam: two games at once](https://steamcommunity.com/discussions/forum/10/2270319347573688560) ·
project notes: findings/precedents.md (sections 5 and 6), findings/legal-policy.md (item 10),
findings/fallout-systems-precedents.md (F6), findings/fo76-terms.md, findings/asset-conversion.md (Q36),
release-community-legal.md (REL-26, REL-27), engine-mechanics/radio-music-sound.md,
next-phase/voice-lipsync-companions.md.
