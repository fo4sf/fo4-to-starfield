# Concord four-option talk — PC session

Scribe. Run after this branch is on the owner's game as a session kit, not as a permanent install. Script logging on.
No F10. Until the Vault 111 exit card lands, jump to Concord with the usual console command.

## Not this session

- Do not copy Fallout 4 interface files into Git.
- Do not post RVAs, decompiled text, or movie bytes.
- Do not treat a Starfield list as a pass.
- Do not install 48a3eb3d or 69ee810a (REPLACE host movie). Do not pack `Interface/DialogueMenu.swf`.

## Shape

Keep the game's `DialogueMenu` movie. Draw four slots over it. Do not REPLACE `Interface/DialogueMenu.swf`.
Host-root stubs on a replacement still crashed (PC FAIL 69ee810a, control list OK, kit same null UI read).
Overlay load (SFSE after host LoadMovie) is the next native slice; this commit only stops packing the host movie.

## Concord

This slice's plugin stays empty. DialogueConcordArea topics are not on the owner's current set.
The Vault 111 exit card is geography, not those topics, so waiting on it does not make Concord
talkable. Concord becomes reachable when a later commit on this branch adds a synthetic topic in
this plugin (ONE TWO THREE FOUR), not converted lines. Until that topic exists, the stated in-game
target is four slots on any vanilla talk, recorded as PARTIAL.

## 1. Names only (no launch if a file read is enough)

On this Starfield build, list the instance names inside the host `DialogueMenu` movie. On the player's Fallout 4
install, list the instance names inside Fallout 4's `DialogueMenu` movie. Names and a yes/no: do four of them match
this slice's `fo4sfOptN` / `fo4sfOptE` / `fo4sfOptS` / `fo4sfOptW`? If no, write the four host names. Stop before
installing if the host class cannot fill unnamed slots.

Count scenes on DialogueConcordArea `000179F3`: inventory said 8, an earlier spike said 15. Number only.

### 1b. Shuttle payload names (no launch if a file read is enough)

On this Starfield build, list the data-shuttle payload field names the host `DialogueMenu` movie consumes
(BSUIDataManager / UIDataShuttleConnector). Names only: the fields that carry list rows into `DialogueList_mc`.
Do not post decompiled methods, RVAs, or movie bytes. If the names cannot be read without launching, stop and
say UNREAD. Do not install until those names are on the Scribe card: a guessed bind is not this session.

PC PASS §1b (file read): `DialogueListData.aChoices[].sChoiceText` / `uEntryID`; select key `selectedIndex`.

## 2. Compile then install

Do not install the no-DoABC wheel. Do not copy the host or Fallout 4 movie. Do not stage the wheel and then
replace the twin: stage rewrites it. Ask the owner before downloading a compiler.

Compiler: Apache Flex SDK 4.16.1, command `mxmlc` (https://flex.apache.org/download-binaries.html). Ask the
owner before downloading it. The .as imports only playerglobal types: `flash.display.DisplayObject`,
`flash.display.DisplayObjectContainer`, `flash.display.MovieClip`, `flash.events.MouseEvent`,
`flash.text.TextField`, `flash.text.TextFormat`, and `flash.utils.getDefinitionByName`. No other library.
The host shuttle class is not imported: `getDefinitionByName("BSUIDataManager")` at runtime, fail closed if
missing. The constructor creates `fo4sfOptN/E/S/W` as TextFields (N/E/S/W around a 1920x1080 stage), so this
compiled movie has the four slots; do not stage the no-DoABC wheel. Use `-target-player=32.0` (the 11.1
playerglobal is no longer served). Get `playerglobal32_0.swc` from Adobe's download host
`https://fpdownload.macromedia.com/get/flashplayer/updaters/32/playerglobal32_0.swc` and put it in the SDK as
`frameworks/libs/player/32.0/playerglobal.swc`. mxmlc reads `{playerglobalHome}/32.0/playerglobal.swc`, so set
`PLAYERGLOBAL_HOME` to that SDK's `frameworks/libs/player` (the directory that contains `32.0/`, not the version
subdirectory). Ask the owner before downloading it. Do not commit the SWC.

From the repo root, with `mxmlc` on PATH (bin of that SDK) and `PLAYERGLOBAL_HOME` set:

    mxmlc -strict=true -swf-version=12 -target-player=32.0 -static-link-runtime-shared-libraries=true -default-size 1920 1080 -output DialogueMenuFour.swf scripts/ui/DialogueMenuFour.as

Then, game closed:

    python scripts/dialogue/make_concord_talk.py stage <dir> --movie DialogueMenuFour.swf
    python scripts/dialogue/concord_talk_install.py install --dir <dir> --starfield <game dir>

If a staged folder contains `Interface/DialogueMenu.swf`, the install must refuse. Uninstall after the session.
Do not run a kit session of a DialogueMenu twin. Overlay load is not in this commit.

## 3. In game (one session, control then kit)

Same vanilla talk both times. Stop on the first crash. Script logging on. No F10.

1. Control, kit not installed: press E on a vanilla NPC. The host list may appear. If this crashes,
   FAIL (not our movie) and stop.
2. Game closed: stage `--movie` and install as in §2. Same NPC, press E. Four slots, not a list, no
   crash. Selecting one (mouse click on a slot; no key/controller path in this movie) fires the host
   `DialogueMenu` select path (KEEP plumbing). If this crashes, FAIL and stop.

Concord DialogueConcordArea `000179F3` is not on this set. Do not treat reaching Concord as this
session's gate.

## Verdict

- PASS: four options visible on that Concord talk, logging on, hashes of files read unchanged. Not
  this session (plugin has no topic).
- PARTIAL: four slots on any vanilla talk after the control did not crash; Concord not reached.
- FAIL: crash with the kit, still a list with the kit, control not run, or install overwrote a game
  file.
