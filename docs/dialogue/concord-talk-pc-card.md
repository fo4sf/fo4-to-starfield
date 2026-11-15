# Concord four-option talk — PC session

Scribe. Run after this branch is on the owner's game as a session kit, not as a permanent install. Script logging on.
No F10. Until the Vault 111 exit card lands, jump to Concord with the usual console command.

## Not this session

- Do not copy Fallout 4 interface files into Git.
- Do not post RVAs, decompiled text, or movie bytes.
- Do not treat a Starfield list as a pass.
- Do not install 48a3eb3d or 69ee810a (REPLACE with a movie of our own).
- Do not pack a DialogueMenu.swf we authored. Install packs a patched copy of the player's movie.

## Shape

Keep the game's `DialogueMenu` movie. Draw four slots over it. Do not REPLACE `Interface/DialogueMenu.swf`
with a movie of our own. The installer takes the player's own movie from their archive at install time
and overlays `fo4sfOpt*` inside `Menu_mc` next to `DialogueList_mc`. Host ABC stays.

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

## 2. Overlay install (no compile this slice)

Do not compile DialogueMenuFour.as as the host movie. Do not stage a DialogueMenu.swf of our own.
Game closed: stage the empty plugin, then install. The installer copies the player's DialogueMenu from
`Starfield - Interface.ba2` when that archive has it, overlays `fo4sfOpt*` inside `Menu_mc`, and packs
that patched copy. Host ABC stays. The four clips have no text and no extra ABC; the host list still
draws. Uninstall after. Do not run a kit session of 48a3eb3d or 69ee810a.

## 3. In game (one session, control then kit)

Same vanilla talk both times. Stop on the first crash. Script logging on. No F10.

1. Control, kit not installed: press E on a vanilla NPC. The host list may appear. If this crashes,
   FAIL (not our movie) and stop.
2. Game closed: overlay install as in §2 (not stage `--movie`). Same NPC, press E. This slice still
   shows the host list; the four clips are empty. No crash. If this crashes, FAIL and stop.

Concord DialogueConcordArea `000179F3` is not on this set. Do not treat reaching Concord as this
session's gate.

## Verdict

- PASS: four options visible on that Concord talk, logging on, hashes of files read unchanged. Not
  this session (plugin has no topic; slots have no bind yet).
- PARTIAL: kit did not crash; host list still draws; Concord not reached.
- FAIL: crash with the kit, control not run, or install overwrote a game file. A Starfield list on
  this overlay slice is not FAIL.
