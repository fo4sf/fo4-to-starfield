Scriptname FO4SF_CoreCandidateWalk extends Quest
{Test-profile exterior walk harness for gemini/core-candidate (docs/testing/core-candidate-pc-card.md).
 Refuses to run unless FO4SFCoreValues.esm FO4SF_TestModeEnabled (0x860) is non-zero, and is omitted
 completely from the player bundle profile. Drives FO4SFProgression's ApplyCreationSheet on the shared
 FO4SFCoreValues.esm store instead of maintaining parallel S.P.E.C.I.A.L. or ListDialogue skill copies.}

GlobalVariable Property TestModeGlobal Auto Const

string LogName = "FO4SFCoreCandidate"
string OwnPlugin = "FO4SFCoreCandidate.esm"
string CoreValuesPlugin = "FO4SFCoreValues.esm"
string NewGamePlugin = "FO4SFNewGame.esm"
string RadsPlugin = "FO4SFRads.esm"
string HardcorePlugin = "FO4SFHardcore.esm"
string WorkshopPlugin = "FO4SFWorkshop.esm"
string PaPlugin = "FO4SFPowerArmor.esm"
string ListDlgPlugin = "FO4SFListDialogue.esm"
string ProgPlugin = "FO4SFProgression.esm"
string CombatPlugin = "FO4SFCombat.esm"
string RepPlugin = "FO4SFReputation.esm"
string CompPlugin = "FO4SFCompanions.esm"
string PipboyProbePlugin = "FO4SFPipboyProbe.esm"
string PipboyTravelPlugin = "FO4SFPipboyTravel.esm"

int CoreTestModeGlobId = 0x860
int CoreStimpakId = 0x851
int CoreSpeechAvId = 0x82A
int CoreScienceAvId = 0x828
int CoreStrAvId = 0x810

int OwnKioskActiId = 0x801
int OwnMsgBgId = 0x802
int OwnMsgTrait1Id = 0x803
int OwnMsgTrait2Id = 0x804
int OwnChargenTokenId = 0x805
int OwnSpeechTokenId = 0x806

int NewGameQuestId = 0x800
int ProgQuestId = 0x880

int RadsEmitterId = 0x82A
int RadAwayId = 0x820
int RadXId = 0x821
int IrradFoodId = 0x822

int HcRifleAmmoId = 0x826
int HcWaterId = 0x821
int HcFoodId = 0x820

int WsCampKitId = 0x810
int WsSettlementKitId = 0x812
int WsScrapTokenId = 0x81B
int WsDeskFanId = 0x820
int WsDuctTapeId = 0x821
int WsHotPlateId = 0x822
int WsTinCanId = 0x823

int PaFusionCoreId = 0x809
int PaSalvagedBodyId = 0x81A
int PaSalvagedHelmId = 0x81B
int PaFrameRefId = 0x822
int PaExitChairRefId = 0x823

int DlgSpeakerRefId = 0x808

int CombatDoctorsBagId = 0x811
int CombatVatsTokenId = 0x816
int CombatAmmoTokenId = 0x817
int CombatFirstTargetRefId = 0x860

int RepVendorBaseId = 0x888
int RepTheftTokenId = 0x881
int RepAidTokenId = 0x882

int CompQuestId = 0x800
int CompRadioTokenId = 0x820
int CompFirstRecruitRefId = 0x835
int CompStoryRefId = 0x83A

int TIMER_POLL = 1
float POLL_S = 2.0

bool FieldLineStaged = false
bool RefusalLogged = false
bool BusyChargen = false
ObjectReference PlacedRadsRef = None
ObjectReference PlacedKioskRef = None
ObjectReference[] PlacedFireteamRefs
int ChargenRuns = 0

bool Function IsTestModeActive()
    if TestModeGlobal != None
        return TestModeGlobal.GetValue() != 0.0
    endif
    if Game.IsPluginInstalled(CoreValuesPlugin)
        GlobalVariable g = Game.GetFormFromFile(CoreTestModeGlobId, CoreValuesPlugin) as GlobalVariable
        if g != None
            return g.GetValue() != 0.0
        endif
    endif
    return false
EndFunction

bool Initialized = false

Event OnQuestInit()
    if Initialized
        return
    endif
    Initialized = true
    Debug.OpenUserLog(LogName)
    if !IsTestModeActive()
        RefusalLogged = true
        Trace("walk_refused reason=test_mode_disabled")
        return
    endif
    Actor p = Game.GetPlayer()
    if p != None
        RegisterPlayerEvents(p)
    endif
    Trace("init version=3 quest=" + GetFormID() + " test_mode=1")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if !IsTestModeActive()
        Trace("walk_refused reason=test_mode_disabled when=reload")
        return
    endif
    Actor p = Game.GetPlayer()
    if p != None
        RegisterPlayerEvents(p)
    endif
    if PlacedKioskRef != None
        RegisterForRemoteEvent(PlacedKioskRef, "OnActivate")
    endif
    if PlacedFireteamRefs != None
        int rIdx = 0
        while rIdx < PlacedFireteamRefs.Length
            if PlacedFireteamRefs[rIdx] != None
                RegisterForRemoteEvent(PlacedFireteamRefs[rIdx], "OnActivate")
            endif
            rIdx += 1
        endwhile
    endif
    Trace("reload staged=" + FieldLineStaged + " chargen_runs=" + ChargenRuns)
    if !FieldLineStaged
        StartTimer(POLL_S, TIMER_POLL)
    endif
EndEvent

Function RegisterPlayerEvents(Actor p)
    RegisterForRemoteEvent(p, "OnPlayerLoadGame")
    RegisterForRemoteEvent(p as ObjectReference, "OnItemRemoved")
EndFunction

Function Trace(string msg)
    string line = "FO4SFCANDIDATE rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if !IsTestModeActive()
        Trace("walk_refused stage=" + auiStageID + " reason=test_mode_disabled")
        return
    endif
    Actor p = Game.GetPlayer()
    if p != None
        RegisterPlayerEvents(p)
    endif
    if auiStageID == 10 && !FieldLineStaged
        StageFieldLine("stage10")
    elseif auiStageID == 20
        RunInteractiveChargen("stage20")
    elseif auiStageID == 30
        ApplySpeechPrimer("stage30")
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_POLL || FieldLineStaged
        return
    endif
    if !IsTestModeActive()
        if !RefusalLogged
            RefusalLogged = true
            Trace("walk_refused reason=test_mode_disabled")
        endif
        return
    endif
    if Game.IsPluginInstalled(NewGamePlugin)
        Quest ng = Game.GetFormFromFile(NewGameQuestId, NewGamePlugin) as Quest
        if ng != None && ng.GetStageDone(200)
            Actor p = Game.GetPlayer()
            if p != None && p.Is3DLoaded()
                StageFieldLine("newgame_stage200")
                return
            endif
        endif
    endif
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function GiveIfPresent(Actor p, string pluginName, int localId, int count)
    if p == None || !Game.IsPluginInstalled(pluginName)
        return
    endif
    Form item = Game.GetFormFromFile(localId, pluginName)
    if item != None
        p.AddItem(item, count, true)
    endif
EndFunction

Function StageFieldLine(string triggerReason)
    if !IsTestModeActive()
        Trace("walk_refused reason=test_mode_disabled trigger=" + triggerReason)
        return
    endif
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    FieldLineStaged = true

    float headingDeg = p.GetAngleZ()
    float fwdX = Math.Sin(headingDeg)
    float fwdY = Math.Cos(headingDeg)
    float rightX = Math.Cos(headingDeg)
    float rightY = -Math.Sin(headingDeg)

    GiveIfPresent(p, RadsPlugin, RadAwayId, 3)
    GiveIfPresent(p, RadsPlugin, RadXId, 1)
    GiveIfPresent(p, RadsPlugin, IrradFoodId, 2)

    GiveIfPresent(p, HardcorePlugin, HcRifleAmmoId, 100)
    GiveIfPresent(p, CoreValuesPlugin, CoreStimpakId, 6)
    GiveIfPresent(p, HardcorePlugin, HcWaterId, 2)
    GiveIfPresent(p, HardcorePlugin, HcFoodId, 2)

    GiveIfPresent(p, WorkshopPlugin, WsScrapTokenId, 1)
    GiveIfPresent(p, WorkshopPlugin, WsDeskFanId, 4)
    GiveIfPresent(p, WorkshopPlugin, WsDuctTapeId, 4)
    GiveIfPresent(p, WorkshopPlugin, WsHotPlateId, 4)
    GiveIfPresent(p, WorkshopPlugin, WsTinCanId, 4)
    GiveIfPresent(p, WorkshopPlugin, WsCampKitId, 1)
    GiveIfPresent(p, WorkshopPlugin, WsSettlementKitId, 1)

    GiveIfPresent(p, PaPlugin, PaFusionCoreId, 2)
    GiveIfPresent(p, PaPlugin, PaSalvagedBodyId, 1)
    GiveIfPresent(p, PaPlugin, PaSalvagedHelmId, 1)

    GiveIfPresent(p, OwnPlugin, OwnChargenTokenId, 1)
    GiveIfPresent(p, OwnPlugin, OwnSpeechTokenId, 1)

    GiveIfPresent(p, CombatPlugin, CombatDoctorsBagId, 4)
    GiveIfPresent(p, CombatPlugin, CombatVatsTokenId, 1)
    GiveIfPresent(p, CombatPlugin, CombatAmmoTokenId, 1)

    GiveIfPresent(p, CompPlugin, CompRadioTokenId, 1)

    bool radsPlaced = false
    if Game.IsPluginInstalled(RadsPlugin)
        Form radBase = Game.GetFormFromFile(RadsEmitterId, RadsPlugin)
        if radBase != None
            PlacedRadsRef = p.PlaceAtMe(radBase, 1, true, false, false)
            if PlacedRadsRef != None
                PlacedRadsRef.MoveTo(p, fwdX * 22.0, fwdY * 22.0, 0.0, true)
                PlacedRadsRef.EnableNoWait()
                radsPlaced = true
            endif
        endif
    endif

    bool paPlaced = false
    if Game.IsPluginInstalled(PaPlugin)
        Form frameBase = Game.GetFormFromFile(0x801, PaPlugin)
        if frameBase != None
            ObjectReference dynFrame = p.PlaceAtMe(frameBase, 1, true, false, false)
            if dynFrame != None
                dynFrame.MoveTo(p, fwdX * 28.0, fwdY * 28.0, 0.0, true)
                dynFrame.EnableNoWait()
                paPlaced = true
            endif
        endif
    endif

    bool dlgPlaced = false
    if Game.IsPluginInstalled(ListDlgPlugin)
        ObjectReference speakerRef = Game.GetFormFromFile(DlgSpeakerRefId, ListDlgPlugin) as ObjectReference
        if speakerRef != None
            speakerRef.MoveTo(p, fwdX * 34.0, fwdY * 34.0, 0.0, true)
            speakerRef.EnableNoWait()
            dlgPlaced = true
        endif
    endif

    bool kioskPlaced = false
    Form kioskBase = Game.GetFormFromFile(OwnKioskActiId, OwnPlugin)
    if kioskBase != None
        PlacedKioskRef = p.PlaceAtMe(kioskBase, 1, true, false, false)
        if PlacedKioskRef != None
            PlacedKioskRef.MoveTo(p, fwdX * 38.0, fwdY * 38.0, 0.0, true)
            PlacedKioskRef.EnableNoWait()
            RegisterForRemoteEvent(PlacedKioskRef, "OnActivate")
            kioskPlaced = true
        endif
    endif

    bool combatPlaced = false
    if Game.IsPluginInstalled(CombatPlugin)
        int ci = 0
        while ci < 12
            ObjectReference cref = Game.GetFormFromFile(CombatFirstTargetRefId + ci, CombatPlugin) as ObjectReference
            if cref != None
                float dist = 44.0
                if ci >= 8
                    dist = 41.0
                endif
                float lat = ((ci % 4) as float - 1.5) * 1.5
                float zOff = 0.0
                if ci < 8
                    zOff = 1.0
                endif
                cref.MoveTo(p, (fwdX * dist) + (rightX * lat), (fwdY * dist) + (rightY * lat), zOff, true)
                cref.EnableNoWait()
                combatPlaced = true
            endif
            ci += 1
        endwhile
    endif

    bool repPlaced = false
    if Game.IsPluginInstalled(RepPlugin)
        ActorBase repVendorBase = Game.GetFormFromFile(RepVendorBaseId, RepPlugin) as ActorBase
        if repVendorBase != None
            Actor repVendor = p.PlaceActorAtMe(repVendorBase, 1, None, true, false, false)
            if repVendor != None
                repVendor.MoveTo(p, fwdX * 50.0, fwdY * 50.0, 0.0, true)
                repPlaced = true
            endif
        endif
        Form theftTok = Game.GetFormFromFile(RepTheftTokenId, RepPlugin)
        Form aidTok = Game.GetFormFromFile(RepAidTokenId, RepPlugin)
        if theftTok != None
            ObjectReference t1 = p.PlaceAtMe(theftTok, 3, true, false, false)
            if t1 != None
                t1.MoveTo(p, (fwdX * 49.0) - (rightX * 1.0), (fwdY * 49.0) - (rightY * 1.0), 0.2, true)
            endif
        endif
        if aidTok != None
            ObjectReference a1 = p.PlaceAtMe(aidTok, 1, true, false, false)
            if a1 != None
                a1.MoveTo(p, (fwdX * 49.0) + (rightX * 1.0), (fwdY * 49.0) + (rightY * 1.0), 0.2, true)
            endif
        endif
    endif

    bool compPlaced = false
    if Game.IsPluginInstalled(CompPlugin)
        PlacedFireteamRefs = new ObjectReference[4]
        int fi = 0
        while fi < 4
            ObjectReference ftRef = Game.GetFormFromFile(CompFirstRecruitRefId + fi, CompPlugin) as ObjectReference
            if ftRef != None
                float lat = ((fi as float) - 1.5) * 1.6
                ftRef.MoveTo(p, (fwdX * 56.0) + (rightX * lat), (fwdY * 56.0) + (rightY * lat), 0.0, true)
                ftRef.EnableNoWait()
                PlacedFireteamRefs[fi] = ftRef
                RegisterForRemoteEvent(ftRef, "OnActivate")
                compPlaced = true
            endif
            fi += 1
        endwhile
        ObjectReference storyRef = Game.GetFormFromFile(CompStoryRefId, CompPlugin) as ObjectReference
        if storyRef != None
            storyRef.MoveTo(p, (fwdX * 56.0) + (rightX * 4.0), (fwdY * 56.0) + (rightY * 4.0), 0.0, true)
            storyRef.EnableNoWait()
        endif
    endif

    Trace("field_line_staged reason=" + triggerReason + " rads_zone=" + radsPlaced + " pa_frame=" + paPlaced + " list_speaker=" + dlgPlaced + " chargen_kiosk=" + kioskPlaced + " combat=" + combatPlaced + " rep=" + repPlaced + " comp=" + compPlaced)
EndFunction

bool Function IsPlacedFireteamRef(ObjectReference akCandidate)
    if akCandidate == None || PlacedFireteamRefs == None
        return false
    endif
    int i = 0
    while i < PlacedFireteamRefs.Length
        if PlacedFireteamRefs[i] == akCandidate
            return true
        endif
        i += 1
    endwhile
    return false
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if !IsTestModeActive() || akActionRef != Game.GetPlayer()
        return
    endif
    if akSender == PlacedKioskRef
        RunInteractiveChargen("kiosk_activate")
    elseif IsPlacedFireteamRef(akSender) && Game.IsPluginInstalled(CompPlugin)
        Quest compQuest = Game.GetFormFromFile(CompQuestId, CompPlugin) as Quest
        if compQuest != None && !compQuest.GetStageDone(20)
            compQuest.SetStage(20)
            Trace("fireteam_muster_requested actor=" + akSender.GetFormID())
        endif
    endif
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    if !IsTestModeActive() || akBaseItem == None || akDestContainer != None
        return
    endif
    Actor p = Game.GetPlayer()
    Form chargenTok = Game.GetFormFromFile(OwnChargenTokenId, OwnPlugin)
    Form speechTok = Game.GetFormFromFile(OwnSpeechTokenId, OwnPlugin)
    if akBaseItem == chargenTok
        if akItemReference != None
            akItemReference.DisableNoWait()
            akItemReference.Delete()
        endif
        if p != None
            p.AddItem(chargenTok, 1, true)
        endif
        RunInteractiveChargen("token_drop")
    elseif akBaseItem == speechTok
        if akItemReference != None
            akItemReference.DisableNoWait()
            akItemReference.Delete()
        endif
        ApplySpeechPrimer("token_drop")
    endif
EndEvent

Function ApplySpeechPrimer(string reason)
    if !IsTestModeActive()
        return
    endif
    Actor p = Game.GetPlayer()
    if p == None || !Game.IsPluginInstalled(CoreValuesPlugin)
        return
    endif
    ActorValue avSpeech = Game.GetFormFromFile(CoreSpeechAvId, CoreValuesPlugin) as ActorValue
    float speechNow = 0.0
    if avSpeech != None
        p.SetValue(avSpeech, 60.0)
        speechNow = p.GetValue(avSpeech)
    endif
    Trace("speech_primer_applied reason=" + reason + " speech=" + speechNow)
EndFunction

Function RunInteractiveChargen(string triggerWay)
    if !IsTestModeActive() || BusyChargen
        return
    endif
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    BusyChargen = true

    Message msgBg = Game.GetFormFromFile(OwnMsgBgId, OwnPlugin) as Message
    Message msgT1 = Game.GetFormFromFile(OwnMsgTrait1Id, OwnPlugin) as Message
    Message msgT2 = Game.GetFormFromFile(OwnMsgTrait2Id, OwnPlugin) as Message

    int bgChoice = 0
    int t1Choice = 0
    int t2Choice = 0
    if msgBg != None && triggerWay != "stage20"
        bgChoice = msgBg.Show()
        if bgChoice == 4
            BusyChargen = false
            Trace("chargen_cancelled trigger=" + triggerWay)
            return
        endif
        if msgT1 != None
            t1Choice = msgT1.Show()
        endif
        if msgT2 != None && t1Choice != 4
            t2Choice = msgT2.Show()
        else
            t2Choice = 4
        endif
    endif

    int bgIdx = 0
    string bgName = "VaultDweller"
    if bgChoice == 1
        bgIdx = 1
        bgName = "WastelandScavenger"
    elseif bgChoice == 2
        bgIdx = 3
        bgName = "FieldMedic"
    elseif bgChoice == 3
        bgIdx = 4
        bgName = "BrotherhoodScribe"
    endif

    int t0 = -1
    string trait1Name = "None"
    if t1Choice == 0
        t0 = 6
        trait1Name = "GoodNatured"
    elseif t1Choice == 1
        t0 = 0
        trait1Name = "SmallFrame"
    elseif t1Choice == 2
        t0 = 7
        trait1Name = "Skilled"
    elseif t1Choice == 3
        t0 = 1
        trait1Name = "TriggerDiscipline"
    endif

    int t1 = -1
    string trait2Name = "None"
    if t2Choice == 0
        t1 = 0
        trait2Name = "SmallFrame"
    elseif t2Choice == 1
        t1 = 6
        trait2Name = "GoodNatured"
    elseif t2Choice == 2
        t1 = 2
        trait2Name = "FastShot"
    elseif t2Choice == 3
        t1 = 8
        trait2Name = "WildWasteland"
    endif
    if t1 == t0
        t1 = -1
        trait2Name = "None"
    endif

    bool applied = false
    if Game.IsPluginInstalled(ProgPlugin)
        FO4SF_ProgressionQuest progQ = Game.GetFormFromFile(ProgQuestId, ProgPlugin) as FO4SF_ProgressionQuest
        if progQ != None
            ; Tag indices: 10=Speech, 8=Science, 7=Repair; 40-pt pool 7/5/6/6/6/5/5
            applied = progQ.ApplyCreationSheet(p, bgIdx, t0, t1, 7, 5, 6, 6, 6, 5, 5, 10, 8, 7)
        endif
    endif

    float speechVal = 0.0
    float scienceVal = 0.0
    float strVal = 0.0
    if Game.IsPluginInstalled(CoreValuesPlugin)
        ActorValue spAv = Game.GetFormFromFile(CoreSpeechAvId, CoreValuesPlugin) as ActorValue
        ActorValue scAv = Game.GetFormFromFile(CoreScienceAvId, CoreValuesPlugin) as ActorValue
        ActorValue stAv = Game.GetFormFromFile(CoreStrAvId, CoreValuesPlugin) as ActorValue
        if spAv != None
            speechVal = p.GetValue(spAv)
        endif
        if scAv != None
            scienceVal = p.GetValue(scAv)
        endif
        if stAv != None
            strVal = p.GetValue(stAv)
        endif
    endif

    int traitCount = 0
    if t0 >= 0
        traitCount += 1
    endif
    if t1 >= 0
        traitCount += 1
    endif
    ChargenRuns += 1
    BusyChargen = false

    Trace("chargen_applied ok=" + applied + " run=" + ChargenRuns + " trigger=" + triggerWay + " bg=" + bgName + " trait1=" + trait1Name + " trait2=" + trait2Name + " traits_count=" + traitCount + " special_sum=40 speech=" + speechVal + " science=" + scienceVal + " str=" + strVal)
EndFunction
