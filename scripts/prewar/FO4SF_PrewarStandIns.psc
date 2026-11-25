Scriptname FO4SF_PrewarStandIns extends Quest
{Labelled animation stand-in helpers for S1 Pre-War beats (a)-(e):
  (a) Running Sanctuary crowd (HumanRace patrol/pathing to hilltop markers)
  (b) Overhead Vertibirds (TranslateTo flight passes + optional Wwise flyby cue)
  (c) ExtVaultElevator platform descent (TranslateTo -21.6 m + non-blocking arrival into PrewarVault111)
  (d) Distant nuke flash & shockwave (Starfield REFL IMAD + FadeOutGame + ShakeCamera + blast Wwise cue)
  (e) Cryo-pod view of Kellogg (player pod hold + pod-front markers + scene + gunshot/freeze fade)
All beats trace explicit "animation stand-in" tags for owner evidence parity.}

Group CrowdStandIn
    Actor[] Property CrowdRunners Auto Const
    ObjectReference Property CrowdBridgeMarker Auto Const
    ObjectReference Property CrowdHillGoalMarker Auto Const
    WwiseEvent Property CrowdPanicSound Auto Const
    ObjectReference Property CrowdPanicEmitter Auto Const
EndGroup

Group VertibirdStandIn
    ObjectReference Property Vertibird01 Auto Const
    ObjectReference Property Vertibird02 Auto Const
    ObjectReference[] Property Vertibird01Waypoints Auto Const
    ObjectReference[] Property Vertibird02Waypoints Auto Const
    float Property VertibirdSpeed = 18.0 Auto Const
    WwiseEvent Property VertibirdFlybySound Auto Const
EndGroup

Group ElevatorAndNukeStandIn
    ObjectReference Property ExtElevatorPlatform Auto Const
    ObjectReference Property ExtElevatorStartMarker Auto Const
    float Property ExtElevatorDropM = 21.6 Auto Const
    float Property ExtElevatorDurationS = 9.8 Auto Const
    float Property NukeTriggerDelayS = 4.2 Auto Const
    ImageSpaceModifier Property NukeExplosionFlashImod Auto Const
    ImageSpaceModifier Property NukeExplosionMainImod Auto Const
    ImageSpaceModifier Property NukeFadeToBlackImod Auto Const
    WwiseEvent Property NukeExplosionSound Auto Const
    ObjectReference Property NukeSoundEmitter Auto Const
    ObjectReference Property NukeLookMarker Auto Const
EndGroup

Group KelloggPodStandIn
    ObjectReference Property PlayerPodHoldMarker Auto Const
    ObjectReference Property SpousePodActorMarker Auto Const
    ObjectReference Property KelloggPodMarker Auto Const
    ObjectReference Property InstMalePodMarker Auto Const
    ObjectReference Property InstFemalePodMarker Auto Const
    Actor Property SpouseActor Auto Const
    Actor Property SpouseMaleActor Auto Const
    Actor Property KelloggActor Auto Const
    Actor Property InstMaleActor Auto Const
    Actor Property InstFemaleActor Auto Const
    Scene Property KelloggSequenceScene Auto Const
    WwiseEvent Property KelloggGunshotSound Auto Const
EndGroup

string LogName = "fo4sf_prewar"
bool crowdStarted = false
bool vertibirdsStarted = false
bool descentActive = false
bool nukeFired = false
bool kelloggStarted = false
int vb01Idx = 0
int vb02Idx = 0
int vbPasses = 0

Function TraceBeat(string msg)
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction

Function StartCrowdBeat()
    {Beat (a) animation stand-in: move HumanRace neighbors toward hill evacuation markers.}
    if crowdStarted
        return
    endif
    crowdStarted = true
    TraceBeat("beat (a) [animation stand-in] running_crowd start runners=" + CrowdRunners.Length)
    if CrowdPanicSound != None && CrowdPanicEmitter != None
        CrowdPanicSound.Play(CrowdPanicEmitter)
    endif
    int i = 0
    while CrowdRunners != None && i < CrowdRunners.Length
        Actor runner = CrowdRunners[i]
        if runner != None
            runner.EnableNoWait()
            if CrowdBridgeMarker != None
                runner.PathToReference(CrowdBridgeMarker, 1.0, 1.0, 1.5, false)
            elseif CrowdHillGoalMarker != None
                runner.PathToReference(CrowdHillGoalMarker, 1.0, 1.0, 2.0, false)
            endif
        endif
        i += 1
    endwhile
    StartTimer(6.0, 10)
EndFunction

Function AdvanceCrowdToHill()
    int i = 0
    while CrowdRunners != None && i < CrowdRunners.Length
        Actor runner = CrowdRunners[i]
        if runner != None && CrowdHillGoalMarker != None
            runner.PathToReference(CrowdHillGoalMarker, 1.0, 1.0, 2.0, false)
        endif
        i += 1
    endwhile
    TraceBeat("beat (a) [animation stand-in] running_crowd sprint_to_hill")
EndFunction

Function StartVertibirdBeat()
    {Beat (b) animation stand-in: drive converted Vertibird props via TranslateTo along orbit waypoints.}
    if vertibirdsStarted
        return
    endif
    vertibirdsStarted = true
    vbPasses = 0
    TraceBeat("beat (b) [animation stand-in] overhead_vertibirds start")
    if Vertibird01 != None
        Vertibird01.EnableNoWait()
    endif
    if Vertibird02 != None
        Vertibird02.EnableNoWait()
    endif
    AdvanceVertibirdStep()
EndFunction

Function AdvanceVertibirdStep()
    if !vertibirdsStarted || vbPasses >= 6
        return
    endif
    vbPasses += 1
    if Vertibird01 != None && Vertibird01Waypoints != None && Vertibird01Waypoints.Length > 0
        ObjectReference wp1 = Vertibird01Waypoints[vb01Idx % Vertibird01Waypoints.Length]
        if wp1 != None
            Vertibird01.TranslateTo(wp1.GetPositionX(), wp1.GetPositionY(), wp1.GetPositionZ(), 0.0, 0.0, wp1.GetAngleZ(), VertibirdSpeed, 25.0)
            if VertibirdFlybySound != None
                VertibirdFlybySound.Play(Vertibird01)
            endif
        endif
        vb01Idx += 1
    endif
    if Vertibird02 != None && Vertibird02Waypoints != None && Vertibird02Waypoints.Length > 0
        ObjectReference wp2 = Vertibird02Waypoints[vb02Idx % Vertibird02Waypoints.Length]
        if wp2 != None
            Vertibird02.TranslateTo(wp2.GetPositionX(), wp2.GetPositionY(), wp2.GetPositionZ(), 0.0, 0.0, wp2.GetAngleZ(), VertibirdSpeed, 25.0)
        endif
        vb02Idx += 1
    endif
    StartTimer(4.5, 11)
EndFunction

Function StartElevatorDescentWithNuke()
    {Beat (c) animation stand-in: TranslateTo ExtVaultElevator platform descent + timed Beat (d) nuke flash.}
    if descentActive
        return
    endif
    descentActive = true
    nukeFired = false
    Actor player = Game.GetPlayer()
    Game.SetPlayerOnElevator(true)
    if ExtElevatorPlatform != None
        float px = ExtElevatorPlatform.GetPositionX()
        float py = ExtElevatorPlatform.GetPositionY()
        float pz = ExtElevatorPlatform.GetPositionZ()
        float speed = ExtElevatorDropM / ExtElevatorDurationS
        if speed < 0.5
            speed = 2.2
        endif
        TraceBeat("beat (c) [animation stand-in] ext_elevator_descent start z=" + pz + " drop_m=" + ExtElevatorDropM + " speed=" + speed)
        ExtElevatorPlatform.TranslateTo(px, py, pz - ExtElevatorDropM, 0.0, 0.0, ExtElevatorPlatform.GetAngleZ(), speed, 0.0)
    else
        TraceBeat("beat (c) [animation stand-in] ext_elevator_descent missing_platform fallback_timer")
    endif
    if player != None && NukeLookMarker != None
        player.SetLookAt(NukeLookMarker, false)
    endif
    StartTimer(NukeTriggerDelayS, 12)
EndFunction

Function TriggerNukeFlashAndShockwave()
    {Beat (d) animation stand-in: Starfield IMAD flash/nuke + FadeOutGame pulse + ShakeCamera + blast Wwise cue.}
    if nukeFired
        return
    endif
    nukeFired = true
    TraceBeat("beat (d) [animation stand-in] nuke_flash_shockwave imad=0x064C26/0x02458E")
    if NukeExplosionSound != None
        if NukeSoundEmitter != None
            NukeExplosionSound.Play(NukeSoundEmitter)
        else
            NukeExplosionSound.Play(Game.GetPlayer())
        endif
    endif
    if NukeExplosionFlashImod != None
        NukeExplosionFlashImod.Apply(1.0)
    endif
    if NukeExplosionMainImod != None
        NukeExplosionMainImod.ApplyCrossFade(0.8)
    endif
    Game.ShakeCamera(NukeSoundEmitter, 0.85, 2.6)
    ; Brief white-out pulse followed by black fade-in transition before entering PrewarVault111
    Game.FadeOutGame(true, false, 0.15, 0.65, false)
    StartTimer(2.2, 13)
EndFunction

Function FinishDescentFadeOut()
    if NukeFadeToBlackImod != None
        NukeFadeToBlackImod.Apply(1.0)
    endif
    Game.FadeOutGame(true, true, 0.0, 0.9, true)
    Game.SetPlayerOnElevator(false)
    Actor player = Game.GetPlayer()
    if player != None
        player.ClearLookAt()
    endif
    TraceBeat("beat (c)+(d) [animation stand-in] descent_complete ready_for_prewar_vault")
EndFunction

Function StartKelloggPodSequence()
    {Beat (e) animation stand-in: lock player at cryo pod facing Spouse pod + Kellogg sequence across aisle.}
    if kelloggStarted
        return
    endif
    kelloggStarted = true
    Actor player = Game.GetPlayer()
    TraceBeat("beat (e) [animation stand-in] kellogg_cryo_pod_view start (replaces MultiActorFurniture .hkx)")
    if player != None
        Game.SetPlayerAIDriven(true)
        if PlayerPodHoldMarker != None
            player.MoveTo(PlayerPodHoldMarker, 0.0, 0.0, 0.0, true, false)
        endif
        if SpousePodActorMarker != None
            player.SetLookAt(SpousePodActorMarker, false)
        endif
    endif
    Actor activeSpouse = SpouseActor
    if player != None && player.GetLeveledActorBase() != None && player.GetLeveledActorBase().GetSex() == 1 && SpouseMaleActor != None
        activeSpouse = SpouseMaleActor
    endif
    if activeSpouse != None && SpousePodActorMarker != None
        activeSpouse.EnableNoWait()
        activeSpouse.MoveTo(SpousePodActorMarker, 0.0, 0.0, 0.0, true, false)
    endif
    if KelloggActor != None && KelloggPodMarker != None
        KelloggActor.EnableNoWait()
        KelloggActor.MoveTo(KelloggPodMarker, 0.0, 0.0, 0.0, true, false)
    endif
    if InstMaleActor != None && InstMalePodMarker != None
        InstMaleActor.EnableNoWait()
        InstMaleActor.MoveTo(InstMalePodMarker, 0.0, 0.0, 0.0, true, false)
    endif
    if InstFemaleActor != None && InstFemalePodMarker != None
        InstFemaleActor.EnableNoWait()
        InstFemaleActor.MoveTo(InstFemalePodMarker, 0.0, 0.0, 0.0, true, false)
    endif
    if KelloggSequenceScene != None
        KelloggSequenceScene.Start()
    endif
EndFunction

Function FireKelloggGunshotAndRefreeze()
    TraceBeat("beat (e) [animation stand-in] kellogg_shot_and_refreeze")
    if KelloggGunshotSound != None && KelloggActor != None
        KelloggGunshotSound.Play(KelloggActor)
    endif
    if NukeFadeToBlackImod != None
        NukeFadeToBlackImod.Apply(1.0)
    endif
    Game.FadeOutGame(true, true, 0.25, 1.8, true)
    Actor player = Game.GetPlayer()
    if player != None
        player.ClearLookAt()
        Game.SetPlayerAIDriven(false)
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == 10
        AdvanceCrowdToHill()
    elseif aiTimerID == 11
        AdvanceVertibirdStep()
    elseif aiTimerID == 12
        TriggerNukeFlashAndShockwave()
    elseif aiTimerID == 13
        FinishDescentFadeOut()
    endif
EndEvent
