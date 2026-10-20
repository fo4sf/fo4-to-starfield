Scriptname FO4SF_NewGameLooks extends Quest
{Optional second script on FO4SF_NewGame (docs/newgame/vault111-start.md): once the player stands in Vault 111 (stage
 10) it asks "Create character" or "Quick start" (StartMessage, NG-6 / NG-C9). Create opens Starfield's character
 creation, in place of Fallout 4's bathroom mirror, and waits for the creator ("ChargenMenu") to close; quick start
 keeps the preset the player already has and skips the creator. Either way it sets stage 20; the quest sets stage 20
 itself after LooksWait if this script never does (the fallback), and the log says which ended the wait.
 Kept apart from FO4SF_NewGameQuest so that if a native here is not what Starfield's sources offer, only this script
 fails to compile and the build goes on without it (make_newgame.py stage --no-looks).
 Verified (PC read, 19 Oct): Game.ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0, ...) and
 RegisterForMenuOpenCloseEvent(string) on ScriptObject, menu name "ChargenMenu". OnMenuOpenCloseEvent is written with
 Fallout 4's signature (string asMenuName, bool abOpening); the compile on the PC is its check.}

Message Property StartMessage Auto Const Mandatory
{The opening choice (FO4SFNewGame.esm 0x802): button 0 creates the character, button 1 is the quick start.}

int Property RaceMenuMode = 0 Auto Const
{The uiMode passed to Game.ShowRaceMenu (the writer's --race-menu-mode). 0 is the full creator. The modes are FO4's
 (1 remake, 2 haircut, 3 surgery, 4 face paint); which one is looks-only, the owner's choice (NG-C3), is unverified
 until the in-game C1 test decides it.}

float Property MenuDelay = 2.0 Auto Const
{Seconds after stage 10 before the choice shows, so the vault has drawn.}

string Property MenuName = "ChargenMenu" Auto Const
{The creator's menu name (9 vanilla registrations, PC read 19 Oct).}

bool shown = false
bool waiting = false

Event OnQuestInit()
    StartTimer(1.0, 2)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 2
        return
    endif
    int stage = GetStage()
    if stage == 1 || stage >= 20
        return                                               ; stood down, or already past the looks
    endif
    if stage == 10 && !shown
        shown = true
        Utility.Wait(MenuDelay)
        int button = StartMessage.Show()
        Trace("start choice button=" + button)
        if button == 1
            Trace("quick start: preset kept, creator skipped")
            Done("quick start")
            return
        endif
        ; registered before the menu opens so its close is not missed; the event sets stage 20 (Done). The quest's
        ; LooksWait timer is the fallback when the event never comes
        RegisterForMenuOpenCloseEvent(MenuName)
        waiting = true
        Trace("looks menu mode=" + RaceMenuMode)
        Game.ShowRaceMenu(None, RaceMenuMode)
        Trace("looks returned stage=" + GetStage())
        return
    endif
    StartTimer(1.0, 2)
EndEvent

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
    Trace("menu " + asMenuName + " opening=" + abOpening)
    if asMenuName == MenuName && !abOpening && waiting
        waiting = false
        Done("creator closed")
    endif
EndEvent

Function Done(string how)
{Stage 20 once, with what ended the wait (the quest logs "looks: no stage 20 after ..." when its LooksWait does).}
    if GetStage() >= 20
        return
    endif
    Trace("looks done: " + how)
    SetStage(20)
EndFunction

Function Trace(string msg)
    Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
