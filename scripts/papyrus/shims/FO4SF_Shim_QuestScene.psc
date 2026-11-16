Scriptname FO4SF_Shim_QuestScene Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Game.GetCommonProperties, Location Cleared->Explored renames, EncounterZone->Location queries, Keyword.SendStoryEventAndWait bool conversion, and external ScriptObject SelfOnly dispatch helpers.}

Quest Function GetCommonPropertiesQuest() Global
    return Game.GetFormFromFile(0x000337F0, "FO4Port.esm") as Quest
EndFunction

bool Function IsCleared(Location akLoc) Global
    return akLoc != None && akLoc.IsExplored()
EndFunction

Function SetCleared(Location akLoc, bool abCleared = true) Global
    if akLoc != None
        akLoc.SetExplored(abCleared)
    endif
EndFunction

bool Function HasEverBeenCleared(Location akLoc) Global
    return akLoc != None && akLoc.HasEverBeenExplored()
EndFunction

bool Function SendStoryEventAndWait(Keyword akKeyword, Location akLoc = None, ObjectReference akRef1 = None, ObjectReference akRef2 = None, int aiValue1 = 0, int aiValue2 = 0) Global
    if akKeyword == None
        return false
    endif
    Quest[] started = akKeyword.SendStoryEventAndWait(akLoc, akRef1, akRef2, aiValue1, aiValue2)
    return started != None && started.Length > 0
EndFunction

Function ResetEncounterZone(EncounterZone akZone) Global
    if akZone != None
        akZone.Reset()
    endif
EndFunction

; Safe external-receiver fallbacks when an FO4 script invokes a Starfield Protected SelfOnly method on a base Native ScriptObject reference
Function RelayGotoState(ScriptObject akTarget, string asNewState) Global
    ; Non-native script receivers route to injected FO4SF_Relay_GotoState; base Native ScriptObject has no Papyrus states.
EndFunction

string Function RelayGetState(ScriptObject akTarget) Global
    return ""
EndFunction

Function RelayStartTimer(ScriptObject akTarget, float afInterval, int aiTimerID = 0) Global
EndFunction

Function RelayStartTimerGameTime(ScriptObject akTarget, float afInterval, int aiTimerID = 0) Global
EndFunction

Function RelayCancelTimer(ScriptObject akTarget, int aiTimerID = 0) Global
EndFunction

Function RelayCancelTimerGameTime(ScriptObject akTarget, int aiTimerID = 0) Global
EndFunction

Function RelayRegisterForCustomEvent(ScriptObject akTarget, ScriptObject akSender, string asEventName) Global
EndFunction

Function RelayUnregisterForCustomEvent(ScriptObject akTarget, ScriptObject akSender, string asEventName) Global
EndFunction

Function RelaySendCustomEvent(ScriptObject akTarget, string asEventName, Var[] akArgs = None) Global
EndFunction

bool Function RelayRegisterForRemoteEvent(ScriptObject akTarget, ScriptObject akEventSource, string asEventName) Global
    return akTarget != None && akEventSource != None
EndFunction

Function RelayUnregisterForRemoteEvent(ScriptObject akTarget, ScriptObject akEventSource, string asEventName) Global
EndFunction

bool Function RelayRegisterForAnimationEvent(ScriptObject akTarget, ObjectReference akSender, string asEventName) Global
    return akTarget != None && akSender != None
EndFunction

Function RelayUnregisterForAnimationEvent(ScriptObject akTarget, ObjectReference akSender, string asEventName) Global
EndFunction

Function RelayRegisterForHitEvent(ScriptObject akTarget, ScriptObject akAggressorFilterTarget, ScriptObject akSourceFilter = None, Form akProjectileFilter = None, int aiPowerFilter = -1, int aiSneakFilter = -1, int aiBashFilter = -1, int aiBlockFilter = -1, bool abMatch = true) Global
EndFunction

Function RelayUnregisterForHitEvent(ScriptObject akTarget, ScriptObject akAggressorFilterTarget, ScriptObject akSourceFilter = None, Form akProjectileFilter = None, int aiPowerFilter = -1, int aiSneakFilter = -1, int aiBashFilter = -1, int aiBlockFilter = -1, bool abMatch = true) Global
EndFunction

Function RelayUnregisterForAllHitEvents(ScriptObject akTarget, ScriptObject akFilterTarget = None) Global
EndFunction

Function RelayRegisterForDistanceLessThanEvent(ScriptObject akTarget, ScriptObject akObj1, ScriptObject akObj2, float afDistance, int aiEventID = 0) Global
EndFunction

Function RelayRegisterForDistanceGreaterThanEvent(ScriptObject akTarget, ScriptObject akObj1, ScriptObject akObj2, float afDistance, int aiEventID = 0) Global
EndFunction

Function RelayUnregisterForDistanceEvents(ScriptObject akTarget, ScriptObject akObj1, ScriptObject akObj2, int aiEventID = -1) Global
EndFunction

Function RelayRegisterForTutorialEvent(ScriptObject akTarget, string asEventName) Global
EndFunction

Function RelayUnregisterForTutorialEvent(ScriptObject akTarget, string asEventName) Global
EndFunction

Function RelayRegisterForPlayerSleep(ScriptObject akTarget) Global
EndFunction

Function RelayUnregisterForPlayerSleep(ScriptObject akTarget) Global
EndFunction

Function RelayRegisterForLOS(ScriptObject akTarget, ObjectReference akViewer, ObjectReference akTargetRef) Global
EndFunction

Function RelayUnregisterForLOS(ScriptObject akTarget, ObjectReference akViewer = None, ObjectReference akTargetRef = None) Global
EndFunction
