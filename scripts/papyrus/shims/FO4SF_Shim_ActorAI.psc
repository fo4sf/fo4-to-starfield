Scriptname FO4SF_Shim_ActorAI Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Actor and ActorBase functions: GetActorBase, IsBleedingOut, PathToReference, companion convenience wrappers, animation archetype setters, and ActorBase invulnerability.}

ActorBase Function GetActorBase(Actor akActor) Global
    if akActor == None
        return None
    endif
    return akActor.GetBaseObject() as ActorBase
EndFunction

bool Function IsBleedingOut(Actor akActor) Global
    return akActor != None && akActor.IsBleedingOut() != 0
EndFunction

int Function PathToReference(Actor akActor, ObjectReference akTarget, float afWalkRunPercent, float afTurnRadius = -1.0) Global
    if akActor == None || akTarget == None
        return -1
    endif
    return akActor.PathToReference(akTarget, afWalkRunPercent, 1.0, afTurnRadius, false)
EndFunction

Function AllowCompanion(Actor akActor, bool MakeCompanionIfNoneCurrently = true, bool ForceCompanion = false) Global
    if akActor == None
        return
    endif
    if ForceCompanion || MakeCompanionIfNoneCurrently
        akActor.SetPlayerTeammate(true, true)
    endif
    akActor.EvaluatePackage()
EndFunction

Function DisallowCompanion(Actor akActor, bool SuppressDismissMessage = false) Global
    if akActor == None
        return
    endif
    akActor.SetPlayerTeammate(false, false)
    akActor.EvaluatePackage()
EndFunction

Function SetCompanion(Actor akActor, bool SetCompanion = true, bool FillCompanionAlias = true) Global
    if akActor == None
        return
    endif
    akActor.SetPlayerTeammate(SetCompanion, SetCompanion)
    akActor.EvaluatePackage()
EndFunction

Function SetAvailableToBeCompanion(Actor akActor) Global
    if akActor != None
        akActor.EvaluatePackage()
    endif
EndFunction

Function FollowerFollow(Actor akActor) Global
    if akActor != None
        akActor.SetPlayerTeammate(true, true)
        akActor.EvaluatePackage()
    endif
EndFunction

Function FollowerWait(Actor akActor) Global
    if akActor != None
        akActor.EvaluatePackage()
    endif
EndFunction

Function FollowerSetDistanceNear(Actor akActor) Global
    if akActor != None
        akActor.EvaluatePackage()
    endif
EndFunction

Function FollowerSetDistanceMedium(Actor akActor) Global
    if akActor != None
        akActor.EvaluatePackage()
    endif
EndFunction

Function FollowerSetDistanceFar(Actor akActor) Global
    if akActor != None
        akActor.EvaluatePackage()
    endif
EndFunction

Function SetAnimArchetypeNeutral(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeConfident(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeDepressed(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeElderly(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeFriendly(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeIrritated(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetAnimArchetypeNervous(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetDogAnimArchetypeNeutral(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetDogAnimArchetypeAgitated(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetDogAnimArchetypeAlert(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

Function SetDogAnimArchetypePlayful(Actor akActor) Global
    if akActor != None
        akActor.ChangeAnimArchetype(None)
    endif
EndFunction

bool Function IsInvulnerable(ActorBase akBase) Global
    return false
EndFunction

Function SetInvulnerable(ActorBase akBase, bool abInvulnerable = true) Global
    Actor player = Game.GetPlayer()
    if akBase != None && player != None && player.GetBaseObject() == akBase
        ActorValue invAV = Game.GetInvulnerableAV()
        if invAV != None
            if abInvulnerable
                player.SetValue(invAV, 1.0)
            else
                player.SetValue(invAV, 0.0)
            endif
        endif
    endif
EndFunction
