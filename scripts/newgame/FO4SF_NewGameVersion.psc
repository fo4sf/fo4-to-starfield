Scriptname FO4SF_NewGameVersion extends ReferenceAlias
{Optional alias script on FO4SF_NewGame (docs/newgame/vault111-start.md section 4b): the save version check (NG-15 /
 NG-L2, the owner's decision 2026-10-19). The quest's alias 0 is forced to the player; this script runs on it. When the
 alias fills (a new game) it records the build's version number, GLOB FO4SF_NewGameVersion, in SavedVersion, which the
 save keeps. On every load (OnPlayerLoadGame) it reads the GLOB again (constant, so the installed plugin's value, not the
 save's) and compares: both go to the log, and a mismatch shows a notification. It changes nothing else: no stage, no
 value, no move. Kept apart from FO4SF_NewGameQuest so that if a native here is not what Starfield's sources offer, only
 this script fails to compile and the build goes on without it (make_newgame.py stage --no-version).
 Verified (PC read, 19 Oct): OnPlayerLoadGame() is declared on Actor and on ReferenceAlias. Whether the alias stays
 filled after the quest completes (stage 200), and so still receives the event, is unverified until the PC run: the
 "version load" line on a reload is the proof.}

GlobalVariable Property BuildVersion Auto Const Mandatory
{The build's version number (FO4SFNewGame.esm 0x805, constant): the writer's --build-version, default 1.}

float Property SavedVersion = -1.0 Auto
{The version this save was started with: written once when the alias fills, then saved with the quest. -1 until then,
 so a save that gained the plugin with the quest already running reads "unknown" rather than a false match.}

string Property LogName = "fo4sf_newgame" Auto Const

Event OnInit()
    if SavedVersion < 0.0
        SavedVersion = BuildVersion.GetValue()
        Trace("version saved=" + SavedVersion + " (new game)")
    endif
EndEvent

Event OnPlayerLoadGame()
    Debug.OpenUserLog(LogName)                               ; a new game session: the log is opened again
    float installed = BuildVersion.GetValue()
    Trace("version load saved=" + SavedVersion + " installed=" + installed)
    if SavedVersion != installed
        Trace("version mismatch")
        Debug.Notification("Fallout 4 new game: this save is from build " + (SavedVersion as int) + ", the installed build is " + (installed as int))
    endif
EndEvent

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
