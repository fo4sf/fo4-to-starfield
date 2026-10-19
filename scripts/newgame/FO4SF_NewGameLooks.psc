Scriptname FO4SF_NewGameLooks extends Quest
{Optional second script on FO4SF_NewGame (docs/newgame/vault111-start.md): once the player stands in Vault 111 (stage
 10) it opens Starfield's character creation, in place of Fallout 4's bathroom mirror, then sets stage 20 once the call
 returns. Kept apart from FO4SF_NewGameQuest so that if Game.ShowRaceMenu is not what Starfield's Game.psc offers,
 only this script fails to compile and the build goes on without it (make_newgame.py stage --no-looks); the quest moves on after LooksWait.}

float Property MenuDelay = 2.0 Auto Const
{Seconds after stage 10 before the menu opens, so the vault has drawn.}

bool shown = false

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
        Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " looks menu")
        Game.ShowRaceMenu()
        ; Starfield's Utility has no IsInMenuMode (precheck on the PC, 19 Oct), so the menu's close is not awaited: stage
        ; 20 only arms the console and platform checks, which need the player to walk there after the menu anyway
        Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " looks returned")
        SetStage(20)
        return
    endif
    StartTimer(1.0, 2)
EndEvent
