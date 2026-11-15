# Concord four-option talk — PC session

Scribe. Run after this branch is on the owner's game as a session kit, not as a permanent install. Script logging on.
No F10. Until the Vault 111 exit card lands, jump to Concord with the usual console command.

## Not this session

- Do not copy Fallout 4 interface files into Git.
- Do not post RVAs, decompiled text, or movie bytes.
- Do not treat a Starfield list as a pass.

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

## 2. Install

From a staged folder (`python scripts/dialogue/make_concord_talk.py stage <dir>`):

    python scripts/dialogue/concord_talk_install.py install --dir <dir> --starfield <game dir>

Game closed. If a loose `Interface/DialogueMenu.swf` already exists, the install must refuse. Uninstall after the
session.

## 3. In game

Load a save that can talk. First any talk: the list is not the result; four slots (ONE TWO THREE FOUR, or host text
in those four places) is the movie half.

Then Concord, DialogueConcordArea `000179F3`: after leaving Vault 111 (or the usual jump), one talk shows four
options. Selecting one fires the host `DialogueMenu` select path (KEEP plumbing). A Starfield list fail.

## Verdict

- PASS: four options visible on that Concord talk, logging on, hashes of files read unchanged.
- PARTIAL: four slots on some other talk, Concord talk not reached, or host names differ and the boxes stayed empty.
- FAIL: still a list, or install overwrote a game file.
