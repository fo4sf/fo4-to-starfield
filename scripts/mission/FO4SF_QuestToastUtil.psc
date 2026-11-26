Scriptname FO4SF_QuestToastUtil Hidden
{Shared one-shot objective display helper for FO4SF mission quests so duplicate HUD toasts stay muted.}

bool Function ShowObjectiveOnce(Quest q, int obj, bool mute = True, bool alreadyDisplayed = False, bool atTop = False) Global
{Displays objective `obj` on quest `q` without duplicate HUD toasts when `mute` is true.
 Returns true when `q.IsObjectiveDisplayed(obj)` succeeds.}
    if q == None
        return False
    endif
    if mute && alreadyDisplayed
        return q.IsObjectiveDisplayed(obj)
    endif
    bool displayedNow = q.IsObjectiveDisplayed(obj)
    if mute
        if !displayedNow
            q.SetObjectiveDisplayed(obj, True, False)
            q.SetActive(True)
            displayedNow = q.IsObjectiveDisplayed(obj)
            if displayedNow && atTop && !alreadyDisplayed
                q.SetObjectiveDisplayedAtTop(obj)
            endif
        else
            q.SetActive(True)
        endif
        return displayedNow
    endif
    q.SetObjectiveDisplayed(obj, True, True)
    q.SetActive(True)
    displayedNow = q.IsObjectiveDisplayed(obj)
    if displayedNow && atTop
        q.SetObjectiveDisplayedAtTop(obj)
    endif
    return displayedNow
EndFunction
