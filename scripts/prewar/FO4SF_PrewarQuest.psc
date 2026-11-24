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

Function Trace(string msg)
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction

Function BeginPrewarSanctuary()
    {Start S1 inside FO4SF_PrewarSanctuaryWorld at HouseSpawnMarker (19 Nov rule: Skip mirror/SPECIAL stat popups).}
    if PrewarActiveGlobal != None
        PrewarActiveGlobal.SetValue(1.0)
    endif
    SetStage(10)
    Actor player = Game.GetPlayer()
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
    Trace("s1 start stage=10 world=FO4SF_PrewarSanctuaryWorld (mirror and clipboard stat-menu skipped per 19 Nov rule)")
EndFunction

Function StartEvacuationSequence()
    {Advance S1 to stage 20: launch Beat (a) fleeing crowd and Beat (b) overhead Vertibirds.}
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
        SetStage(40)
        if VaultDoctorActor != None
            VaultDoctorActor.EnableNoWait()
        endif
        Game.FadeOutGame(false, true, 0.0, 1.0, false)
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
    SetStage(50)
    kelloggElapsedS = 0.0
    if StandIns != None
        StandIns.StartKelloggPodSequence()
    endif
    StartTimer(2.0, 21)
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
            ngScript.CallFunction("EnterVault", args)
        endif
        ng.SetStage(Stage20LooksDone)
        Trace("s1 stage20 handoff complete -> FO4SF_NewGame stage=" + Stage20LooksDone + " cell=FO4Port_Vault111Cryo")
    else
        Trace("s1 stage20 handoff missing NewGameQuest; standalone prewar complete")
    endif
    SetStage(200)
    CompleteQuest()
EndFunction

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
    endif
EndEvent
