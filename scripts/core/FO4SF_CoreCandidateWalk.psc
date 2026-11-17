Scriptname FO4SF_CoreCandidateWalk extends Quest
{Unified console-free exterior walk harness for gemini/core-candidate (docs/testing/core-candidate-pc-card.md).
 Attached to QUST FO4SF_CoreCandidateWalkQuest (0x800 in FO4SFCoreCandidate.esm, StartGameEnabled):
   - Zero mandatory script properties: resolves FO4SFNewGame.esm, FO4SFRads.esm, FO4SFHardcore.esm,
     FO4SFWorkshop.esm, FO4SFPowerArmor.esm, FO4SFListDialogue.esm, FO4SFProgression.esm, FO4SFCombat.esm,
     FO4SFReputation.esm, FO4SFCompanions.esm, and FO4SFPipboyProbe.esm/FO4SFPipboyTravel.esm dynamically via
     Game.GetFormFromFile so every slice remains decoupled.
   - Polls gently (2.0 s) until FO4SFNewGame.esm QUST 0x800 completes stage 200 (Commonwealth landing),
     then places a clean 7-station console-free verification line 12..56 m ahead of the player and adds the
     starter field kit to inventory so all 12 walk steps run with zero console commands.}

string LogName = "FO4SFCoreCandidate"
string OwnPlugin = "FO4SFCoreCandidate.esm"
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
string StarfieldPlugin = "Starfield.esm"

int OwnKioskActiId = 0x801
int OwnMsgBgId = 0x802
int OwnMsgTrait1Id = 0x803
int OwnMsgTrait2Id = 0x804
int OwnChargenTokenId = 0x805
int OwnSpeechTokenId = 0x806

int NewGameQuestId = 0x800

int RadsEmitterId = 0x82A
int RadAwayId = 0x820
int RadXId = 0x821
int IrradFoodId = 0x822

int HcRifleAmmoId = 0x826
int HcStimpakId = 0x822
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

int DlgSpeechAvId = 0x800
int DlgScienceAvId = 0x801
int DlgBgVaultDwellerId = 0x802
int DlgTraitGoodNaturedId = 0x803
int DlgSpeakerRefId = 0x808

int ProgStrAvId = 0x800
int ProgPerAvId = 0x801
int ProgEndAvId = 0x802
int ProgChaAvId = 0x803
int ProgIntAvId = 0x804
int ProgAgiAvId = 0x805
int ProgLckAvId = 0x806
int ProgKarmaAvId = 0x807
int ProgCadenceGlobId = 0x809
int ProgSkillBaseId = 0x810
int ProgSpeechAvId = 0x81A
int ProgScienceAvId = 0x818
int ProgMedicineAvId = 0x815
int ProgRepairAvId = 0x817
int ProgLockpickAvId = 0x814
int ProgSurvivalAvId = 0x81B
int ProgGunsAvId = 0x813
int ProgEnergyAvId = 0x811

int ProgBgVaultDwellerId = 0x820
int ProgBgScavengerId = 0x821
int ProgBgMedicId = 0x823
int ProgBgScribeId = 0x824

int ProgTraitSmallFrameId = 0x830
int ProgTraitTriggerDiscId = 0x831
int ProgTraitFastShotId = 0x832
int ProgTraitGoodNaturedId = 0x836
int ProgTraitSkilledId = 0x837
int ProgTraitWildWastelandId = 0x838

int SfCarryWeightAvId = 0x0002DC
int SfHealthAvId = 0x0002D4
int SfStrengthAvId = 0x0002C2

int TIMER_POLL = 1
float POLL_S = 2.0

bool FieldLineStaged = false
bool BusyChargen = false
ObjectReference PlacedRadsRef = None
ObjectReference PlacedKioskRef = None
ObjectReference[] PlacedFireteamRefs
int ChargenRuns = 0

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    if p != None
        RegisterPlayerEvents(p)
    endif
    Trace("init version=2 quest=" + GetFormID() + " ng=" + Game.IsPluginInstalled(NewGamePlugin) + " rads=" + Game.IsPluginInstalled(RadsPlugin) + " hc=" + Game.IsPluginInstalled(HardcorePlugin) + " ws=" + Game.IsPluginInstalled(WorkshopPlugin) + " pa=" + Game.IsPluginInstalled(PaPlugin) + " dlg=" + Game.IsPluginInstalled(ListDlgPlugin) + " prog=" + Game.IsPluginInstalled(ProgPlugin) + " combat=" + Game.IsPluginInstalled(CombatPlugin) + " rep=" + Game.IsPluginInstalled(RepPlugin) + " comp=" + Game.IsPluginInstalled(CompPlugin) + " pb=" + Game.IsPluginInstalled(PipboyProbePlugin) + " pb_travel=" + Game.IsPluginInstalled(PipboyTravelPlugin))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
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
    if auiStageID == 10 && !FieldLineStaged
        StageFieldLine("stage10")
    elseif auiStageID == 20
        RunInteractiveChargen("stage20")
    elseif auiStageID == 30
        ApplySpeechPrimer("stage30")
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_POLL
        return
    endif
    if FieldLineStaged
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

    ; 1. Starter inventory kit for console-free Rads, Hardcore, Workshop, PA, Dialogue & Chargen
    GiveIfPresent(p, RadsPlugin, RadAwayId, 3)
    GiveIfPresent(p, RadsPlugin, RadXId, 1)
    GiveIfPresent(p, RadsPlugin, IrradFoodId, 2)

    GiveIfPresent(p, HardcorePlugin, HcRifleAmmoId, 100)
    GiveIfPresent(p, HardcorePlugin, HcStimpakId, 2)
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

    GiveIfPresent(p, CombatPlugin, 0x811, 4) ; FO4SF_DoctorsBag
    GiveIfPresent(p, CombatPlugin, 0x813, 4) ; FO4SF_CombatStimpak
    GiveIfPresent(p, CombatPlugin, 0x816, 1) ; FO4SF_VatsTriggerToken
    GiveIfPresent(p, CombatPlugin, 0x817, 1) ; FO4SF_AmmoCycleToken

    GiveIfPresent(p, CompPlugin, 0x820, 1)   ; FO4SF_SquadRadioToken

    ; 2. Station A (12 m ahead): Radiation Emitter Zone
    bool radsPlaced = false
    if Game.IsPluginInstalled(RadsPlugin)
        Form radBase = Game.GetFormFromFile(RadsEmitterId, RadsPlugin)
        if radBase != None
            PlacedRadsRef = p.PlaceAtMe(radBase, 1, true, false, false)
            if PlacedRadsRef != None
                PlacedRadsRef.MoveTo(p, fwdX * 12.0, fwdY * 12.0, 0.0, true)
                PlacedRadsRef.EnableNoWait()
                radsPlaced = true
            endif
        endif
    endif

    ; 3. Station C (28 m ahead): Power Armor Climb-In Frame + Exit Chair (persistent refs in FO4SFPowerArmor.esm)
    bool paPlaced = false
    if Game.IsPluginInstalled(PaPlugin)
        ObjectReference frameRef = Game.GetFormFromFile(PaFrameRefId, PaPlugin) as ObjectReference
        ObjectReference chairRef = Game.GetFormFromFile(PaExitChairRefId, PaPlugin) as ObjectReference
        if frameRef != None
            frameRef.MoveTo(p, fwdX * 28.0, fwdY * 28.0, 0.0, true)
            frameRef.EnableNoWait()
            paPlaced = true
        endif
        if chairRef != None
            chairRef.MoveTo(p, (fwdX * 28.0) + (rightX * 3.0), (fwdY * 28.0) + (rightY * 3.0), 0.0, true)
            chairRef.EnableNoWait()
        endif
    endif

    ; 4. Station D1 (34 m ahead): Silent-Player List Dialogue Speaker (persistent ref 0x808 in FO4SFListDialogue.esm)
    bool dlgPlaced = false
    if Game.IsPluginInstalled(ListDlgPlugin)
        ObjectReference speakerRef = Game.GetFormFromFile(DlgSpeakerRefId, ListDlgPlugin) as ObjectReference
        if speakerRef != None
            speakerRef.MoveTo(p, fwdX * 34.0, fwdY * 34.0, 0.0, true)
            speakerRef.EnableNoWait()
            dlgPlaced = true
        endif
    endif

    ; 5. Station D2 (38 m ahead): Console-Free Wasteland Character Rebuild Kiosk
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

    ; 6. Station E (44 m ahead): Combat Core Firing Range (6-Zone Silhouette, DT=18 Target, VATS, Pedestals)
    bool combatPlaced = false
    if Game.IsPluginInstalled(CombatPlugin)
        ObjectReference zHead = Game.GetFormFromFile(0x860, CombatPlugin) as ObjectReference
        ObjectReference zTorso = Game.GetFormFromFile(0x861, CombatPlugin) as ObjectReference
        ObjectReference zLArm = Game.GetFormFromFile(0x862, CombatPlugin) as ObjectReference
        ObjectReference zRArm = Game.GetFormFromFile(0x863, CombatPlugin) as ObjectReference
        ObjectReference zLLeg = Game.GetFormFromFile(0x864, CombatPlugin) as ObjectReference
        ObjectReference zRLeg = Game.GetFormFromFile(0x865, CombatPlugin) as ObjectReference
        ObjectReference armTgt = Game.GetFormFromFile(0x866, CombatPlugin) as ObjectReference
        ObjectReference vatsTgt = Game.GetFormFromFile(0x867, CombatPlugin) as ObjectReference
        ObjectReference ammoPed = Game.GetFormFromFile(0x868, CombatPlugin) as ObjectReference
        ObjectReference legTrap = Game.GetFormFromFile(0x869, CombatPlugin) as ObjectReference
        ObjectReference hcSw = Game.GetFormFromFile(0x86A, CombatPlugin) as ObjectReference
        ObjectReference supRack = Game.GetFormFromFile(0x86B, CombatPlugin) as ObjectReference
        if zHead != None
            zHead.MoveTo(p, (fwdX * 44.0) - (rightX * 2.5), (fwdY * 44.0) - (rightY * 2.5), 1.85, true)
            zHead.EnableNoWait()
            combatPlaced = true
        endif
        if zTorso != None
            zTorso.MoveTo(p, (fwdX * 44.0) - (rightX * 2.5), (fwdY * 44.0) - (rightY * 2.5), 1.15, true)
            zTorso.EnableNoWait()
        endif
        if zLArm != None
            zLArm.MoveTo(p, (fwdX * 44.0) - (rightX * 3.2), (fwdY * 44.0) - (rightY * 3.2), 1.25, true)
            zLArm.EnableNoWait()
        endif
        if zRArm != None
            zRArm.MoveTo(p, (fwdX * 44.0) - (rightX * 1.8), (fwdY * 44.0) - (rightY * 1.8), 1.25, true)
            zRArm.EnableNoWait()
        endif
        if zLLeg != None
            zLLeg.MoveTo(p, (fwdX * 44.0) - (rightX * 2.85), (fwdY * 44.0) - (rightY * 2.85), 0.45, true)
            zLLeg.EnableNoWait()
        endif
        if zRLeg != None
            zRLeg.MoveTo(p, (fwdX * 44.0) - (rightX * 2.15), (fwdY * 44.0) - (rightY * 2.15), 0.45, true)
            zRLeg.EnableNoWait()
        endif
        if armTgt != None
            armTgt.MoveTo(p, fwdX * 44.0, fwdY * 44.0, 1.0, true)
            armTgt.EnableNoWait()
        endif
        if vatsTgt != None
            vatsTgt.MoveTo(p, (fwdX * 44.0) + (rightX * 2.5), (fwdY * 44.0) + (rightY * 2.5), 1.0, true)
            vatsTgt.EnableNoWait()
        endif
        if supRack != None
            supRack.MoveTo(p, (fwdX * 41.0) - (rightX * 2.0), (fwdY * 41.0) - (rightY * 2.0), 0.0, true)
            supRack.EnableNoWait()
        endif
        if ammoPed != None
            ammoPed.MoveTo(p, fwdX * 41.0, fwdY * 41.0, 0.0, true)
            ammoPed.EnableNoWait()
        endif
        if legTrap != None
            legTrap.MoveTo(p, (fwdX * 41.0) + (rightX * 1.8), (fwdY * 41.0) + (rightY * 1.8), 0.0, true)
            legTrap.EnableNoWait()
        endif
        if hcSw != None
            hcSw.MoveTo(p, (fwdX * 41.0) + (rightX * 3.0), (fwdY * 41.0) + (rightY * 3.0), 0.0, true)
            hcSw.EnableNoWait()
        endif
    endif

    ; 7. Station F (50 m ahead): Reputation & Karma Vendor + Walk Tokens
    bool repPlaced = false
    if Game.IsPluginInstalled(RepPlugin)
        ActorBase repVendorBase = Game.GetFormFromFile(0x888, RepPlugin) as ActorBase
        if repVendorBase != None
            Actor repVendor = p.PlaceActorAtMe(repVendorBase, 1, None, true, false, false)
            if repVendor != None
                repVendor.MoveTo(p, fwdX * 50.0, fwdY * 50.0, 0.0, true)
                repPlaced = true
            endif
        endif
        Form theftTok = Game.GetFormFromFile(0x881, RepPlugin)
        Form aidTok = Game.GetFormFromFile(0x882, RepPlugin)
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

    ; 8. Station G (56 m ahead): 4-NPC Warfare Fireteam + Story Companion
    bool compPlaced = false
    if Game.IsPluginInstalled(CompPlugin)
        PlacedFireteamRefs = new ObjectReference[4]
        int fi = 0
        while fi < 4
            ObjectReference ftRef = Game.GetFormFromFile(0x835 + fi, CompPlugin) as ObjectReference
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
        ObjectReference storyRef = Game.GetFormFromFile(0x83A, CompPlugin) as ObjectReference
        if storyRef != None
            storyRef.MoveTo(p, (fwdX * 56.0) + (rightX * 4.0), (fwdY * 56.0) + (rightY * 4.0), 0.0, true)
            storyRef.EnableNoWait()
        endif
    endif

    Trace("field_line_staged reason=" + triggerReason + " rads_zone=" + radsPlaced + " pa_frame=" + paPlaced + " list_speaker=" + dlgPlaced + " chargen_kiosk=" + kioskPlaced + " combat=" + combatPlaced + " rep=" + repPlaced + " comp=" + compPlaced)
    Debug.Notification("FO4SF Core Walk ready ahead: Rads (12m)..Chargen (38m), Combat (44m), Reputation (50m), Squad (56m).")
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
    if akActionRef != Game.GetPlayer()
        return
    endif
    if akSender == PlacedKioskRef
        RunInteractiveChargen("kiosk_activate")
    elseif IsPlacedFireteamRef(akSender) && Game.IsPluginInstalled(CompPlugin)
        Quest compQuest = Game.GetFormFromFile(0x800, CompPlugin) as Quest
        if compQuest != None && !compQuest.GetStageDone(20)
            compQuest.SetStage(20)
            Trace("fireteam_muster_requested actor=" + akSender.GetFormID())
            Debug.Notification("Mustering 4-NPC Warfare Fireteam (wait 2s, then drop Tactical Fireteam Radio).")
        endif
    endif
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    if akBaseItem == None || akDestContainer != None
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
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    float dlgSpeech = 0.0
    if Game.IsPluginInstalled(ListDlgPlugin)
        ActorValue avDlg = Game.GetFormFromFile(DlgSpeechAvId, ListDlgPlugin) as ActorValue
        if avDlg != None
            p.SetValue(avDlg, 60.0)
            dlgSpeech = p.GetValue(avDlg)
        endif
    endif
    if Game.IsPluginInstalled(ProgPlugin)
        ActorValue avProg = Game.GetFormFromFile(ProgSpeechAvId, ProgPlugin) as ActorValue
        if avProg != None
            p.SetValue(avProg, 60.0)
        endif
    endif
    Trace("speech_primer_applied reason=" + reason + " speech=" + dlgSpeech)
    Debug.Notification("Speech raised to 60 ([Speech 50] list check unlocked).")
EndFunction

Function SetProgAv(Actor p, int localId, float val)
    if !Game.IsPluginInstalled(ProgPlugin)
        return
    endif
    ActorValue av = Game.GetFormFromFile(localId, ProgPlugin) as ActorValue
    if av != None
        p.SetValue(av, val)
    endif
EndFunction

Function ClearAndAddPerk(Actor p, int[] poolIds, int chosenId1, int chosenId2)
    if !Game.IsPluginInstalled(ProgPlugin)
        return
    endif
    int i = 0
    while i < poolIds.Length
        Perk pk = Game.GetFormFromFile(poolIds[i], ProgPlugin) as Perk
        if pk != None && p.HasPerk(pk)
            p.RemovePerk(pk)
        endif
        i += 1
    endwhile
    if chosenId1 > 0
        Perk pk1 = Game.GetFormFromFile(chosenId1, ProgPlugin) as Perk
        if pk1 != None && !p.HasPerk(pk1)
            p.AddPerk(pk1)
        endif
    endif
    if chosenId2 > 0 && chosenId2 != chosenId1
        Perk pk2 = Game.GetFormFromFile(chosenId2, ProgPlugin) as Perk
        if pk2 != None && !p.HasPerk(pk2)
            p.AddPerk(pk2)
        endif
    endif
EndFunction

Function RunInteractiveChargen(string triggerWay)
    if BusyChargen
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

    ; 40-point SPECIAL preset (STR=7, PER=5, END=6, CHA=6, INT=6, AGI=5, LCK=5 => sum = 40)
    float sStr = 7.0
    float sPer = 5.0
    float sEnd = 6.0
    float sCha = 6.0
    float sInt = 6.0
    float sAgi = 5.0
    float sLck = 5.0
    float specialSum = sStr + sPer + sEnd + sCha + sInt + sAgi + sLck

    int bgPerkId = ProgBgVaultDwellerId
    string bgName = "VaultDweller"
    if bgChoice == 1
        bgPerkId = ProgBgScavengerId
        bgName = "WastelandScavenger"
    elseif bgChoice == 2
        bgPerkId = ProgBgMedicId
        bgName = "FieldMedic"
    elseif bgChoice == 3
        bgPerkId = ProgBgScribeId
        bgName = "BrotherhoodScribe"
    endif

    int trait1Id = 0
    string trait1Name = "None"
    if t1Choice == 0
        trait1Id = ProgTraitGoodNaturedId
        trait1Name = "GoodNatured"
    elseif t1Choice == 1
        trait1Id = ProgTraitSmallFrameId
        trait1Name = "SmallFrame"
    elseif t1Choice == 2
        trait1Id = ProgTraitSkilledId
        trait1Name = "Skilled"
    elseif t1Choice == 3
        trait1Id = ProgTraitTriggerDiscId
        trait1Name = "TriggerDiscipline"
    endif

    int trait2Id = 0
    string trait2Name = "None"
    if t2Choice == 0
        trait2Id = ProgTraitSmallFrameId
        trait2Name = "SmallFrame"
    elseif t2Choice == 1
        trait2Id = ProgTraitGoodNaturedId
        trait2Name = "GoodNatured"
    elseif t2Choice == 2
        trait2Id = ProgTraitFastShotId
        trait2Name = "FastShot"
    elseif t2Choice == 3
        trait2Id = ProgTraitWildWastelandId
        trait2Name = "WildWasteland"
    endif
    if trait2Id == trait1Id
        trait2Id = 0
        trait2Name = "None"
    endif

    bool hasSmallFrame = (trait1Id == ProgTraitSmallFrameId || trait2Id == ProgTraitSmallFrameId)
    bool hasGoodNatured = (trait1Id == ProgTraitGoodNaturedId || trait2Id == ProgTraitGoodNaturedId)
    bool hasSkilled = (trait1Id == ProgTraitSkilledId || trait2Id == ProgTraitSkilledId)

    float effAgi = sAgi
    if hasSmallFrame
        effAgi += 1.0
    endif

    SetProgAv(p, ProgStrAvId, sStr)
    SetProgAv(p, ProgPerAvId, sPer)
    SetProgAv(p, ProgEndAvId, sEnd)
    SetProgAv(p, ProgChaAvId, sCha)
    SetProgAv(p, ProgIntAvId, sInt)
    SetProgAv(p, ProgAgiAvId, effAgi)
    SetProgAv(p, ProgLckAvId, sLck)

    ActorValue sfStr = Game.GetFormFromFile(SfStrengthAvId, StarfieldPlugin) as ActorValue
    if sfStr != None
        p.SetValue(sfStr, sStr)
    endif

    int[] bgPool = new int[4]
    bgPool[0] = ProgBgVaultDwellerId
    bgPool[1] = ProgBgScavengerId
    bgPool[2] = ProgBgMedicId
    bgPool[3] = ProgBgScribeId
    ClearAndAddPerk(p, bgPool, bgPerkId, 0)

    int[] trPool = new int[6]
    trPool[0] = ProgTraitSmallFrameId
    trPool[1] = ProgTraitTriggerDiscId
    trPool[2] = ProgTraitFastShotId
    trPool[3] = ProgTraitGoodNaturedId
    trPool[4] = ProgTraitSkilledId
    trPool[5] = ProgTraitWildWastelandId
    ClearAndAddPerk(p, trPool, trait1Id, trait2Id)

    float skilledBonus = 0.0
    if hasSkilled
        skilledBonus = 5.0
    endif
    float socialBonus = 0.0
    float combatDelta = 0.0
    if hasGoodNatured
        socialBonus = 5.0
        combatDelta = -5.0
    endif

    ; Compute 13 NV skills (2 + 2*Gov + ceil(LCK/2)=3 + BG(+10) + Tag(+15 Speech/Science/Repair))
    float speechVal = 5.0 + (2.0 * sCha) + 15.0 + skilledBonus + socialBonus
    float scienceVal = 5.0 + (2.0 * sInt) + 15.0 + skilledBonus + socialBonus
    float medicineVal = 5.0 + (2.0 * sInt) + skilledBonus + socialBonus
    float repairVal = 5.0 + (2.0 * sInt) + 15.0 + skilledBonus + socialBonus
    float gunsVal = 5.0 + (2.0 * effAgi) + skilledBonus + combatDelta
    if bgPerkId == ProgBgVaultDwellerId
        speechVal += 10.0
        scienceVal += 10.0
        medicineVal += 10.0
    elseif bgPerkId == ProgBgScavengerId
        repairVal += 10.0
    elseif bgPerkId == ProgBgMedicId
        medicineVal += 10.0
        scienceVal += 10.0
    elseif bgPerkId == ProgBgScribeId
        scienceVal += 10.0
        repairVal += 10.0
    endif

    int idx = 0
    while idx < 13
        SetProgAv(p, ProgSkillBaseId + idx, 18.0 + skilledBonus)
        idx += 1
    endwhile
    SetProgAv(p, ProgSpeechAvId, speechVal)
    SetProgAv(p, ProgScienceAvId, scienceVal)
    SetProgAv(p, ProgMedicineAvId, medicineVal)
    SetProgAv(p, ProgRepairAvId, repairVal)
    SetProgAv(p, ProgGunsAvId, gunsVal)

    ; Sync Speech, Science, Vault Dweller & Good Natured onto FO4SFListDialogue.esm so list checks match live sheet
    if Game.IsPluginInstalled(ListDlgPlugin)
        ActorValue dSp = Game.GetFormFromFile(DlgSpeechAvId, ListDlgPlugin) as ActorValue
        ActorValue dSc = Game.GetFormFromFile(DlgScienceAvId, ListDlgPlugin) as ActorValue
        Perk dBg = Game.GetFormFromFile(DlgBgVaultDwellerId, ListDlgPlugin) as Perk
        Perk dGn = Game.GetFormFromFile(DlgTraitGoodNaturedId, ListDlgPlugin) as Perk
        if dSp != None
            p.SetValue(dSp, speechVal)
        endif
        if dSc != None
            p.SetValue(dSc, scienceVal)
        endif
        if dBg != None
            if bgPerkId == ProgBgVaultDwellerId && !p.HasPerk(dBg)
                p.AddPerk(dBg)
            elseif bgPerkId != ProgBgVaultDwellerId && p.HasPerk(dBg)
                p.RemovePerk(dBg)
            endif
        endif
        if dGn != None
            if hasGoodNatured && !p.HasPerk(dGn)
                p.AddPerk(dGn)
            elseif !hasGoodNatured && p.HasPerk(dGn)
                p.RemovePerk(dGn)
            endif
        endif
    endif

    int traitCount = 0
    if trait1Id > 0
        traitCount += 1
    endif
    if trait2Id > 0
        traitCount += 1
    endif
    ChargenRuns += 1
    BusyChargen = false

    Trace("chargen_applied run=" + ChargenRuns + " trigger=" + triggerWay + " bg=" + bgName + " trait1=" + trait1Name + " trait2=" + trait2Name + " traits_count=" + traitCount + " special_sum=" + specialSum + " speech=" + speechVal + " science=" + scienceVal + " str=" + sStr)
    Debug.Notification("Character built: " + bgName + " (" + traitCount + " trait(s), Speech " + (speechVal as int) + ", 40-pt SPECIAL).")
EndFunction
