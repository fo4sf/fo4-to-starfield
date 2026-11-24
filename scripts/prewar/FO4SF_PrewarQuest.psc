Scriptname FO4SF_PrewarQuest extends Quest
{Main S1 Pre-War quest controller (War Never Changes stand-in sequence) with confirmed-arrival vault entry
and Stage 20 handoff to FO4SF_NewGame in post-war FO4Port_Vault111Cryo while preserving fo4_vault111 (Skip Pre-War).}

Group PrewarRefs
    ObjectReference Property HouseSpawnMarker Auto Const Mandatory
    ObjectReference Property PrewarVaultArrivalMarker Auto Const Mandatory
    int Property PrewarVaultCellId = 0 Auto Const
    string Property PortPlugin = "FO4Port.esm" Auto Const
    Actor Property CodsworthActor Auto Const
    Actor Property SpouseActor Auto Const
    Actor Property VaultTecRepActor Auto Const
    Actor Property SoldierCheckerActor Auto Const
    Actor Property VaultDoctorActor Auto Const
    FO4SF_PrewarStandIns Property StandIns Auto Const
EndGroup

Group NewGameHandoff
    Quest Property NewGameQuest Auto Const
    string Property NewGamePlugin = "FO4SFNewGame.esm" Auto Const
    int Property NewGameQuestId = 0x000800 Auto Const
    int Property Stage20LooksDone = 20 Auto Const
    GlobalVariable Property PrewarActiveGlobal Auto Const
    float Property KelloggSceneTimeoutS = 24.0 Auto Const
EndGroup

string LogName = "fo4sf_prewar"
bool enteredPrewarVault = false
int vaultEntryTries = 0
bool handoffDone = false
float kelloggElapsedS = 0.0
bool loadHookRegistered = false
bool evacStarted = false
bool elevatorStarted = false
bool kelloggStarted = false
float exteriorElapsedS = 0.0
float vaultElapsedS = 0.0

Function Trace(string msg)
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction

Function EnsurePrewarLoadHook(Actor player)
    if player != None && !loadHookRegistered
        loadHookRegistered = true
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    endif
EndFunction

Function BeginPrewarSanctuary()
    {Start S1 inside FO4SF_PrewarSanctuaryWorld at HouseSpawnMarker (19 Nov rule: Skip mirror/SPECIAL stat popups).}
    enteredPrewarVault = false
    vaultEntryTries = 0
    handoffDone = false
    kelloggElapsedS = 0.0
    evacStarted = false
    elevatorStarted = false
    kelloggStarted = false
    exteriorElapsedS = 0.0
    vaultElapsedS = 0.0
    if PrewarActiveGlobal != None
        PrewarActiveGlobal.SetValue(1.0)
    endif
    SetStage(10)
    Actor player = Game.GetPlayer()
    EnsurePrewarLoadHook(player)
    if player != None && HouseSpawnMarker != None
        player.MoveTo(HouseSpawnMarker, 0.0, 0.0, 0.0, true, false)
    endif
    if CodsworthActor != None
        CodsworthActor.EnableNoWait()
    endif
    if SpouseActor != None
        SpouseActor.EnableNoWait()
    endif
    if VaultTecRepActor != None
        VaultTecRepActor.EnableNoWait()
    endif
    StartTimer(2.0, 22)
    Trace("s1 start stage=10 world=FO4SF_PrewarSanctuaryWorld (mirror and clipboard stat-menu skipped per 19 Nov rule)")
EndFunction

Function StartEvacuationSequence()
    {Advance S1 to stage 20: launch Beat (a) fleeing crowd and Beat (b) overhead Vertibirds.}
    if evacStarted || handoffDone || GetStage() >= 20
        return
    endif
    evacStarted = true
    SetStage(20)
    if StandIns != None
        StandIns.StartCrowdBeat()
        StandIns.StartVertibirdBeat()
    endif
    if SoldierCheckerActor != None
        SoldierCheckerActor.EnableNoWait()
    endif
    Trace("s1 stage=20 evacuation started (crowd + vertibirds [animation stand-in])")
EndFunction

Function StartElevatorAndNukeBeat()
    {Advance S1 to stage 30: start Beat (c) ExtVaultElevator descent + Beat (d) nuke flash, then confirmed PrewarVault111 arrival.}
    if elevatorStarted || handoffDone || GetStage() >= 30
        return
    endif
    elevatorStarted = true
    SetStage(30)
    if StandIns != None
        StandIns.StartElevatorDescentWithNuke()
    endif
    vaultEntryTries = 0
    StartTimer(7.5, 20)
EndFunction

Function MoveIntoPrewarVaultConfirmed()
    {Non-blocking confirmed-arrival transition into FO4Port_PrewarVault111S1 (mirrors FO4SF_ConfirmedLoadDoor).}
    if enteredPrewarVault
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None || PrewarVaultArrivalMarker == None
        Trace("s1 prewar_vault arrival aborted: missing player or marker")
        return
    endif
    vaultEntryTries += 1
    player.MoveTo(PrewarVaultArrivalMarker, 0.0, 0.0, 0.0, true, false)
    Cell wantCell = PrewarVaultArrivalMarker.GetParentCell()
    if wantCell != None && player.GetParentCell() == wantCell
        enteredPrewarVault = true
        vaultElapsedS = 0.0
        SetStage(40)
        if VaultDoctorActor != None
            VaultDoctorActor.EnableNoWait()
        endif
        Game.FadeOutGame(false, true, 0.0, 1.0, false)
        StartTimer(2.0, 22)
        Trace("s1 prewar_vault arrival confirmed tries=" + vaultEntryTries + " cell=" + wantCell)
    elseif vaultEntryTries < 8
        Trace("s1 prewar_vault retry=" + vaultEntryTries)
        StartTimer(0.5, 20)
    else
        Trace("s1 prewar_vault arrival failed after tries=" + vaultEntryTries)
    endif
EndFunction

Function StartKelloggPodBeat()
    {Advance S1 to stage 50: Beat (e) pod-locked Kellogg sequence -> refreeze -> Stage 20 Vault111Cryo handoff.}
    if kelloggStarted || handoffDone || GetStage() >= 50
        return
    endif
    kelloggStarted = true
    SetStage(50)
    kelloggElapsedS = 0.0
    if StandIns != None
        StandIns.StartKelloggPodSequence()
    endif
    StartTimer(2.0, 21)
EndFunction

Function StepPrewarProgression()
    {Drive S1 stage progression by player proximity to Sanctuary/Vault anchors with elapsed fallback timers.}
    if handoffDone
        return
    endif
    int st = GetStage()
    if st < 10 || st >= 50
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None
        StartTimer(2.0, 22)
        return
    endif
    EnsurePrewarLoadHook(player)
    if st == 10 && !evacStarted
        exteriorElapsedS += 2.0
        float distHouse = 0.0
        if HouseSpawnMarker != None
            distHouse = player.GetDistance(HouseSpawnMarker)
        endif
        if (distHouse >= 12.0 && distHouse < 10000.0) || exteriorElapsedS >= 8.0
            StartEvacuationSequence()
        endif
        StartTimer(2.0, 22)
    elseif st == 20 && !elevatorStarted
        exteriorElapsedS += 2.0
        bool nearGateOrLift = false
        if SoldierCheckerActor != None
            float dGate = player.GetDistance(SoldierCheckerActor)
            if dGate >= 0.0 && dGate <= 22.0
                nearGateOrLift = true
            endif
        endif
        if !nearGateOrLift && StandIns != None && StandIns.ExtElevatorPlatform != None
            float dLift = player.GetDistance(StandIns.ExtElevatorPlatform)
            if dLift >= 0.0 && dLift <= 18.0
                nearGateOrLift = true
            endif
        endif
        if nearGateOrLift || exteriorElapsedS >= 24.0
            StartElevatorAndNukeBeat()
        endif
        StartTimer(2.0, 22)
    elseif st == 30
        StartTimer(2.0, 22)
    elseif st == 40 && !kelloggStarted
        vaultElapsedS += 2.0
        bool nearPod = false
        if StandIns != None && StandIns.PlayerPodHoldMarker != None
            float dPod = player.GetDistance(StandIns.PlayerPodHoldMarker)
            if dPod >= 0.0 && dPod <= 8.0
                nearPod = true
            endif
        endif
        if nearPod || vaultElapsedS >= 6.0
            StartKelloggPodBeat()
        else
            StartTimer(2.0, 22)
        endif
    endif
EndFunction

Function HandoffToVault111CryoStage20()
    {Advance S1 to stage 60/200 and hand off to FO4SF_NewGame Stage 20 in post-war FO4Port_Vault111Cryo.
     Never alters fo4_vault111 (Skip Pre-War), which calls EnterVault directly.}
    if handoffDone
        return
    endif
    handoffDone = true
    if StandIns != None
        StandIns.FireKelloggGunshotAndRefreeze()
    endif
    SetStage(60)
    if PrewarActiveGlobal != None
        PrewarActiveGlobal.SetValue(0.0)
    endif
    Quest ng = NewGameQuest
    if ng == None
        ng = Game.GetFormFromFile(NewGameQuestId, NewGamePlugin) as Quest
    endif
    Actor player = Game.GetPlayer()
    if ng != None
        ScriptObject ngScript = ng.CastAs("FO4SF_NewGameQuest")
        if ngScript != None && player != None
            Var[] args = new Var[1]
            args[0] = player
            ngScript.CallFunction("CompletePrewarHandoffStage20", args)
        else
            ng.SetStage(Stage20LooksDone)
        endif
        Trace("s1 stage20 handoff complete -> FO4SF_NewGame stage=" + Stage20LooksDone + " cell=FO4Port_Vault111Cryo")
    else
        Trace("s1 stage20 handoff missing NewGameQuest; standalone prewar complete")
    endif
    SetStage(200)
    CompleteQuest()
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if akSender == None || akSender != Game.GetPlayer()
        return
    endif
    int st = GetStage()
    if handoffDone || st < 10 || st >= 200
        return
    endif
    Trace("s1 reload re-arm stage=" + st)
    if st < 40
        StartTimer(2.0, 22)
        if elevatorStarted && !enteredPrewarVault
            StartTimer(0.5, 20)
        endif
    elseif st < 50
        StartTimer(2.0, 22)
    elseif st < 60
        StartTimer(2.0, 21)
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 20
        MoveIntoPrewarVaultConfirmed()
    elseif aiTimerID == 21
        kelloggElapsedS += 2.0
        bool playing = false
        if StandIns != None && StandIns.KelloggSequenceScene != None
            playing = StandIns.KelloggSequenceScene.IsPlaying()
        endif
        if playing && kelloggElapsedS < KelloggSceneTimeoutS
            StartTimer(2.0, 21)
        else
            HandoffToVault111CryoStage20()
        endif
    elseif aiTimerID == 22
        StepPrewarProgression()
    endif
EndEvent
