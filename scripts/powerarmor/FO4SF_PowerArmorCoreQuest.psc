Scriptname FO4SF_PowerArmorCoreQuest extends Quest
{Fallout 4 climb-in Power Armor frame + 6-limb BPTD + FusionCore drain + prior outfit restore + save/reload re-sync +
 FNV Salvaged NCR worn heavy ARMO support (docs/powerarmor/power-armor-core.md).
 Attached to QUST FO4SF_PowerArmorCoreQuest (0x805) in FO4SFPowerArmor.esm (StartGameEnabled, zero properties; every form
 is resolved via Game.GetFormFromFile). Non-intrusive in normal gameplay: never teleports the player automatically.
 Stages:
   10 = climb into nearest / persistent FO4SF_PowerArmorFrameFurn
   20 = log status snapshot and apply a deterministic 50-point test drain pulse while in frame
   30 = exit frame anywhere in the world, leave FURN standing at exit spot, and restore prior worn outfit
   40 = deploy / move persistent FO4SF_PowerArmorFrameFurnRef in front of player anywhere in the world
 User log: My Games\Starfield\Logs\Script\User\FO4SFPACore.0.log ("FO4SFPACORE rt=<rt> <event> key=value ... end=true").}

; ---------------------------------------------------------------- layout (held equal with dotnet/PowerArmorCore/Program.cs)

string LogName = "FO4SFPACore"
string CorePlugin = "FO4SFPowerArmor.esm"
string NewGamePlugin = "FO4SFNewGame.esm"
string StarfieldPlugin = "Starfield.esm"

int CellId = 0x800
int FrameFurnId = 0x801
int RaceId = 0x802
int BodyPartDataId = 0x803
int SkinId = 0x804
int QuestId = 0x805
int ArmorKeywordId = 0x806
int SalvagedKeywordId = 0x807
int FrameFurnKeywordId = 0x808
int FusionCoreId = 0x809
int InPaAvId = 0x80A
int FusionChargeAvId = 0x80B

int CondHeadId = 0x810
int CondTorsoId = 0x811
int CondLeftArmId = 0x812
int CondRightArmId = 0x813
int CondLeftLegId = 0x814
int CondRightLegId = 0x815

int FrameArmorId = 0x816
int PaTorsoId = 0x817
int PaHelmetId = 0x818
int PaPackId = 0x819
int SalvagedBodyId = 0x81A
int SalvagedHelmId = 0x81B
int SalvagedAgiEnchId = 0x81C
int SalvagedAgiMgefId = 0x81D

int ArrivalRefId = 0x820
int CocRefId = 0x821
int FrameFurnRefId = 0x822
int ExitChairRefId = 0x823

int SfAgilityAvId = 0x0002C7
int SfCarryWeightAvId = 0x0002DC
int NewGameSpecialAgiId = 0x0815

; ---------------------------------------------------------------- persistent runtime state (serialized in .sfs saves)

int TIMER_POLL = 1
int TIMER_STOP_RECORD = 2
float POLL_S = 1.0
float RECORD_WINDOW_S = 1.5
float NEAR_FURN_DIST = 2.0
float MOVE_MIN_DIST = 0.15
float MOVE_MAX_STEP = 25.0
float DRAIN_PER_UNIT = 1.2
float DRAIN_PER_ACTIVE_TICK = 0.6
float DEPLETED_CARRY_PENALTY = 10000.0

bool InSuit = false
bool RecordingWorn = false
bool DepletedPenaltyApplied = false
bool SalvagedSpecialAgiApplied = false
bool TestCellAnnounced = false
bool Stage10Handled = false
bool Stage20Handled = false
bool Stage30Handled = false
bool Stage40Handled = false

Form[] SavedWornGear = None
int SavedWornCount = 0
Race SavedOrigRace = None
ObjectReference ActiveFrameRef = None
Cell LastPlayerCell = None
float LastPosX = 0.0
float LastPosY = 0.0
float LastPosZ = 0.0
int LastLoggedChargeBucket = -1
int Cycle = 0

; ---------------------------------------------------------------- init & logging

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    if SavedWornGear == None
        SavedWornGear = new Form[64]
    endif
    if p != None
        if SavedOrigRace == None
            SavedOrigRace = p.GetRace()
        endif
        SyncLastPos(p)
        RegisterPlayerEvents(p)
    endif
    Trace("init version=1 quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(CorePlugin) + " parace=" + Id(Thing(RaceId)) + " bptd=" + Id(Thing(BodyPartDataId)) + " framefurn=" + Id(Ref(FrameFurnRefId)) + " core=" + Id(Thing(FusionCoreId)) + " salvaged=" + Id(Thing(SalvagedBodyId)))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function RegisterPlayerEvents(Actor p)
    if p == None
        return
    endif
    RegisterForRemoteEvent(p, "OnItemUnequipped")
    RegisterForRemoteEvent(p, "OnItemEquipped")
    RegisterForRemoteEvent(p, "OnSit")
    RegisterForRemoteEvent(p, "OnPlayerLoadGame")
EndFunction

Function Trace(string msg)
    string line = "FO4SFPACORE rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form itemForm)
    if itemForm == None
        return "none"
    endif
    return "" + itemForm.GetFormID()
EndFunction

Form Function Thing(int localId)
    return Game.GetFormFromFile(localId, CorePlugin)
EndFunction

ObjectReference Function Ref(int localId)
    return Game.GetFormFromFile(localId, CorePlugin) as ObjectReference
EndFunction

ActorValue Function OwnAv(int localId)
    return Game.GetFormFromFile(localId, CorePlugin) as ActorValue
EndFunction

ActorValue Function SfAv(int sfLocalId)
    return Game.GetFormFromFile(sfLocalId, StarfieldPlugin) as ActorValue
EndFunction

float Function GetOwnAv(Actor p, int localId)
    ActorValue avObj = OwnAv(localId)
    if p == None || avObj == None
        return 0.0
    endif
    return p.GetValue(avObj)
EndFunction

Function SetOwnAv(Actor p, int localId, float val)
    ActorValue avObj = OwnAv(localId)
    if p != None && avObj != None
        p.SetValue(avObj, val)
    endif
EndFunction

float Function GetSfAvVal(Actor p, int sfLocalId)
    ActorValue avObj = SfAv(sfLocalId)
    if p == None || avObj == None
        return 0.0
    endif
    return p.GetValue(avObj)
EndFunction

Function SyncLastPos(Actor p)
    if p == None
        return
    endif
    LastPlayerCell = p.GetParentCell()
    LastPosX = p.GetPositionX()
    LastPosY = p.GetPositionY()
    LastPosZ = p.GetPositionZ()
EndFunction

; ---------------------------------------------------------------- piece & furniture helpers

bool Function IsPaPiece(Form itemForm)
    if itemForm == None
        return false
    endif
    return itemForm == Thing(FrameArmorId) || itemForm == Thing(PaTorsoId) || itemForm == Thing(PaHelmetId) || itemForm == Thing(PaPackId)
EndFunction

bool Function IsSalvagedPiece(Form itemForm)
    if itemForm == None
        return false
    endif
    return itemForm == Thing(SalvagedBodyId) || itemForm == Thing(SalvagedHelmId)
EndFunction

bool Function IsSalvagedWorn(Actor p)
    if p == None
        return false
    endif
    return p.IsEquipped(Thing(SalvagedBodyId)) || p.IsEquipped(Thing(SalvagedHelmId))
EndFunction

int Function EquippedPaCount(Actor p)
    if p == None
        return 0
    endif
    int n = 0
    if p.IsEquipped(Thing(FrameArmorId))
        n += 1
    endif
    if p.IsEquipped(Thing(PaTorsoId))
        n += 1
    endif
    if p.IsEquipped(Thing(PaHelmetId))
        n += 1
    endif
    if p.IsEquipped(Thing(PaPackId))
        n += 1
    endif
    return n
EndFunction

bool Function IsSavedGear(Form itemForm)
    int i = 0
    while i < SavedWornCount
        if SavedWornGear[i] == itemForm
            return true
        endif
        i += 1
    endwhile
    return false
EndFunction

bool Function IsFrameFurniture(ObjectReference furnRef)
    if furnRef == None
        return false
    endif
    if furnRef == Ref(FrameFurnRefId) || furnRef == ActiveFrameRef
        return true
    endif
    Keyword frameKwObj = Thing(FrameFurnKeywordId) as Keyword
    if frameKwObj != None && furnRef.HasKeyword(frameKwObj)
        return true
    endif
    return false
EndFunction

Function InitLimbConditions(Actor p)
    int[] limbIds = new int[6]
    limbIds[0] = CondHeadId
    limbIds[1] = CondTorsoId
    limbIds[2] = CondLeftArmId
    limbIds[3] = CondRightArmId
    limbIds[4] = CondLeftLegId
    limbIds[5] = CondRightLegId
    int i = 0
    while i < 6
        float cur = GetOwnAv(p, limbIds[i])
        if cur <= 0.0 || cur > 100.0
            SetOwnAv(p, limbIds[i], 100.0)
        endif
        i += 1
    endwhile
EndFunction

float Function MinLimbCondition(Actor p)
    float minVal = GetOwnAv(p, CondHeadId)
    float v1 = GetOwnAv(p, CondTorsoId)
    if v1 < minVal
        minVal = v1
    endif
    float v2 = GetOwnAv(p, CondLeftArmId)
    if v2 < minVal
        minVal = v2
    endif
    float v3 = GetOwnAv(p, CondRightArmId)
    if v3 < minVal
        minVal = v3
    endif
    float v4 = GetOwnAv(p, CondLeftLegId)
    if v4 < minVal
        minVal = v4
    endif
    float v5 = GetOwnAv(p, CondRightLegId)
    if v5 < minVal
        minVal = v5
    endif
    return minVal
EndFunction

; ---------------------------------------------------------------- FusionCore drain & depleted slow-walk penalty

Function ApplyDepletedPenalty(Actor p)
    if p == None || DepletedPenaltyApplied
        return
    endif
    ActorValue cwAv = SfAv(SfCarryWeightAvId)
    if cwAv != None
        p.ModValue(cwAv, -DEPLETED_CARRY_PENALTY)
        DepletedPenaltyApplied = true
    endif
EndFunction

Function ClearDepletedPenalty(Actor p)
    if p == None || !DepletedPenaltyApplied
        return
    endif
    ActorValue cwAv = SfAv(SfCarryWeightAvId)
    if cwAv != None
        p.ModValue(cwAv, DEPLETED_CARRY_PENALTY)
    endif
    DepletedPenaltyApplied = false
EndFunction

Function LoadOrDepleteCore(Actor p, string reason)
    Form coreItem = Thing(FusionCoreId)
    int heldCores = p.GetItemCount(coreItem)
    if heldCores > 0
        p.RemoveItem(coreItem, 1, true)
        SetOwnAv(p, FusionChargeAvId, 100.0)
        LastLoggedChargeBucket = 20
        ClearDepletedPenalty(p)
        int leftCores = p.GetItemCount(coreItem)
        Trace("core_reload reason=" + reason + " charge=100.0 remaining_cores=" + leftCores)
        Say("Fusion Core loaded (charge 100%, spare cores: " + leftCores + ").")
    else
        SetOwnAv(p, FusionChargeAvId, 0.0)
        LastLoggedChargeBucket = 0
        ApplyDepletedPenalty(p)
        Trace("core_depleted reason=" + reason + " charge=0.0 remaining_cores=0 slow_walk=" + DepletedPenaltyApplied)
        Say("Fusion Core depleted (0% charge, 0 spare cores): slow-walk penalty active.")
    endif
EndFunction

Function ApplyChargeDrain(Actor p, float amount, string sourceTag)
    if !InSuit || p == None
        return
    endif
    Form coreItem = Thing(FusionCoreId)
    float beforeCharge = GetOwnAv(p, FusionChargeAvId)
    if beforeCharge <= 0.0
        if p.GetItemCount(coreItem) > 0
            LoadOrDepleteCore(p, "pickup_reload")
        elseif !DepletedPenaltyApplied
            LoadOrDepleteCore(p, "empty_check")
        endif
        return
    endif

    float nextCharge = beforeCharge - amount
    if nextCharge <= 0.0
        LoadOrDepleteCore(p, sourceTag)
        return
    endif

    SetOwnAv(p, FusionChargeAvId, nextCharge)
    int bucket = (nextCharge / 5.0) as int
    if bucket != LastLoggedChargeBucket || sourceTag == "stage20"
        LastLoggedChargeBucket = bucket
        Trace("drain source=" + sourceTag + " charge=" + nextCharge + " remaining_cores=" + p.GetItemCount(coreItem) + " slow_walk=" + DepletedPenaltyApplied)
    endif
EndFunction

; ---------------------------------------------------------------- climb-in & exit

Function EnterFrame(ObjectReference targetFurn, string triggerWay)
    Actor p = Game.GetPlayer()
    if p == None || InSuit
        return
    endif
    if SavedWornGear == None
        SavedWornGear = new Form[64]
    endif
    if targetFurn != None
        ActiveFrameRef = targetFurn
    else
        ActiveFrameRef = Ref(FrameFurnRefId)
    endif

    Race curRace = p.GetRace()
    Race paRaceObj = Thing(RaceId) as Race
    if curRace != None && curRace != paRaceObj
        SavedOrigRace = curRace
    endif

    SavedWornCount = 0
    RecordingWorn = true
    InitLimbConditions(p)

    ; Equip all 4 disjoint PA pieces while RecordingWorn=true so displaced player gear is captured via OnItemUnequipped
    Form framePiece = Thing(FrameArmorId)
    Form torsoPiece = Thing(PaTorsoId)
    Form helmPiece = Thing(PaHelmetId)
    Form packPiece = Thing(PaPackId)
    p.AddItem(framePiece, 1, true)
    p.AddItem(torsoPiece, 1, true)
    p.AddItem(helmPiece, 1, true)
    p.AddItem(packPiece, 1, true)
    p.EquipItem(framePiece, false, true)
    p.EquipItem(torsoPiece, false, true)
    p.EquipItem(helmPiece, false, true)
    p.EquipItem(packPiece, false, true)

    ; Swap to FO4SF_PowerArmorRace (wired to 6-limb FO4SF_PowerArmorBodyPartData + FO4SF_PowerArmorSkin + dual-race ARMAs)
    if paRaceObj != None && p.GetRace() != paRaceObj
        p.SetRace(paRaceObj)
        ; Re-assert equip on PA race in case SetRace refreshed biped state
        p.EquipItem(framePiece, false, true)
        p.EquipItem(torsoPiece, false, true)
        p.EquipItem(helmPiece, false, true)
        p.EquipItem(packPiece, false, true)
    endif

    float existingCharge = GetOwnAv(p, FusionChargeAvId)
    if existingCharge > 0.0
        ClearDepletedPenalty(p)
        LastLoggedChargeBucket = (existingCharge / 5.0) as int
    else
        LoadOrDepleteCore(p, "climb_in")
    endif

    SetOwnAv(p, InPaAvId, 1.0)
    InSuit = true
    SyncLastPos(p)
    if ActiveFrameRef != None && p.GetSitState() == 0 && !ActiveFrameRef.IsDisabled()
        ActiveFrameRef.DisableNoWait()
    endif
    StartTimer(RECORD_WINDOW_S, TIMER_STOP_RECORD)
    Trace("climb_in cycle=" + Cycle + " trigger=" + triggerWay + " race=" + Id(p.GetRace()) + " orig_race=" + Id(SavedOrigRace) + " equipped_pa=" + EquippedPaCount(p) + " charge=" + GetOwnAv(p, FusionChargeAvId) + " limbs_min=" + MinLimbCondition(p) + " inpa=" + GetOwnAv(p, InPaAvId))
    Say("Power Armor ON (charge " + GetOwnAv(p, FusionChargeAvId) + "%, limbs 100%). Stand up if seated and move to test drain.")
EndFunction

Function RestorePriorOutfit(Actor p)
    int i = 0
    while i < SavedWornCount
        Form gearItem = SavedWornGear[i]
        if gearItem != None && p.GetItemCount(gearItem) > 0
            p.EquipItem(gearItem, false, true)
        endif
        i += 1
    endwhile
EndFunction

Function ExitFrame(string triggerWay)
    Actor p = Game.GetPlayer()
    if p == None || !InSuit
        return
    endif
    RecordingWorn = false
    ClearDepletedPenalty(p)
    SetOwnAv(p, InPaAvId, 0.0)
    InSuit = false

    Form framePiece = Thing(FrameArmorId)
    Form torsoPiece = Thing(PaTorsoId)
    Form helmPiece = Thing(PaHelmetId)
    Form packPiece = Thing(PaPackId)
    p.UnequipItem(framePiece, false, true)
    p.UnequipItem(torsoPiece, false, true)
    p.UnequipItem(helmPiece, false, true)
    p.UnequipItem(packPiece, false, true)
    if p.GetItemCount(framePiece) > 0
        p.RemoveItem(framePiece, p.GetItemCount(framePiece), true)
    endif
    if p.GetItemCount(torsoPiece) > 0
        p.RemoveItem(torsoPiece, p.GetItemCount(torsoPiece), true)
    endif
    if p.GetItemCount(helmPiece) > 0
        p.RemoveItem(helmPiece, p.GetItemCount(helmPiece), true)
    endif
    if p.GetItemCount(packPiece) > 0
        p.RemoveItem(packPiece, p.GetItemCount(packPiece), true)
    endif

    if SavedOrigRace != None && p.GetRace() != SavedOrigRace
        p.SetRace(SavedOrigRace)
    endif

    if ActiveFrameRef == None
        ActiveFrameRef = Ref(FrameFurnRefId)
    endif
    bool frameStanding = false
    if ActiveFrameRef != None
        ObjectReference exitChair = Ref(ExitChairRefId)
        float offX = 0.0
        float offY = 1.6
        if exitChair != None && p.GetParentCell() == exitChair.GetParentCell() && p.GetDistance(exitChair) < 2.5
            offX = 2.2
            offY = 0.0
        endif
        ActiveFrameRef.MoveTo(p, offX, offY, 0.0, true)
        ActiveFrameRef.EnableNoWait()
        frameStanding = !ActiveFrameRef.IsDisabled()
    endif

    RestorePriorOutfit(p)
    SyncLastPos(p)
    Trace("exit_complete cycle=" + Cycle + " trigger=" + triggerWay + " restored_worn=" + SavedWornCount + " equipped_pa=" + EquippedPaCount(p) + " inpa=" + GetOwnAv(p, InPaAvId) + " race=" + Id(p.GetRace()) + " frame_standing=" + frameStanding + " charge_kept=" + GetOwnAv(p, FusionChargeAvId))
    Say("Power Armor OFF: frame left standing, restored " + SavedWornCount + " prior outfit item(s).")
    Cycle += 1
EndFunction

Function DeployFrameAtPlayer()
    Actor p = Game.GetPlayer()
    ObjectReference frameRef = Ref(FrameFurnRefId)
    if p == None || frameRef == None
        return
    endif
    ActiveFrameRef = frameRef
    frameRef.MoveTo(p, 0.0, 2.0, 0.0, true)
    frameRef.EnableNoWait()
    Trace("frame_deployed ref=" + Id(frameRef) + " cell=" + Id(p.GetParentCell()))
    Say("Power Armor frame deployed 2 m ahead.")
EndFunction

; ---------------------------------------------------------------- remote events (outfit capture, salvaged NCR, climb-in, save/reload)

Event Actor.OnItemUnequipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    Actor p = Game.GetPlayer()
    if akBaseObject == None || p == None
        return
    endif
    if RecordingWorn && !IsPaPiece(akBaseObject) && SavedWornCount < 64 && !IsSavedGear(akBaseObject)
        SavedWornGear[SavedWornCount] = akBaseObject
        SavedWornCount += 1
        Trace("captured_worn item=" + Id(akBaseObject) + " count=" + SavedWornCount)
    endif
    if akBaseObject == Thing(SalvagedBodyId)
        if SalvagedSpecialAgiApplied && Game.IsPluginInstalled(NewGamePlugin)
            ActorValue specialAgi = Game.GetFormFromFile(NewGameSpecialAgiId, NewGamePlugin) as ActorValue
            if specialAgi != None
                p.ModValue(specialAgi, 1.0)
            endif
            SalvagedSpecialAgiApplied = false
        endif
        Trace("salvaged_unequip item=" + Id(akBaseObject) + " inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " agi=" + GetSfAvVal(p, SfAgilityAvId))
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    Actor p = Game.GetPlayer()
    if akBaseObject == None || p == None
        return
    endif
    if IsSalvagedPiece(akBaseObject)
        if akBaseObject == Thing(SalvagedBodyId) && !SalvagedSpecialAgiApplied && Game.IsPluginInstalled(NewGamePlugin)
            ActorValue specialAgi = Game.GetFormFromFile(NewGameSpecialAgiId, NewGamePlugin) as ActorValue
            if specialAgi != None
                p.ModValue(specialAgi, -1.0)
                SalvagedSpecialAgiApplied = true
            endif
        endif
        Trace("salvaged_equip item=" + Id(akBaseObject) + " inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " agi=" + GetSfAvVal(p, SfAgilityAvId) + " charge=" + GetOwnAv(p, FusionChargeAvId))
    endif
EndEvent

Event Actor.OnSit(Actor akSender, ObjectReference akFurniture)
    if akFurniture == None
        return
    endif
    if !InSuit && IsFrameFurniture(akFurniture)
        EnterFrame(akFurniture, "onsit_frame")
    elseif InSuit && akFurniture == Ref(ExitChairRefId)
        ExitFrame("onsit_exitchair")
    endif
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    RegisterPlayerEvents(p)
    SyncLastPos(p)
    if InSuit
        SetOwnAv(p, InPaAvId, 1.0)
        InitLimbConditions(p)
        ; Re-verify PA pieces remain equipped without overwriting SavedWornGear
        RecordingWorn = false
        if p.GetItemCount(Thing(FrameArmorId)) > 0 && !p.IsEquipped(Thing(FrameArmorId))
            p.EquipItem(Thing(FrameArmorId), false, true)
        endif
        if p.GetItemCount(Thing(PaTorsoId)) > 0 && !p.IsEquipped(Thing(PaTorsoId))
            p.EquipItem(Thing(PaTorsoId), false, true)
        endif
        if p.GetItemCount(Thing(PaHelmetId)) > 0 && !p.IsEquipped(Thing(PaHelmetId))
            p.EquipItem(Thing(PaHelmetId), false, true)
        endif
        if p.GetItemCount(Thing(PaPackId)) > 0 && !p.IsEquipped(Thing(PaPackId))
            p.EquipItem(Thing(PaPackId), false, true)
        endif
        if ActiveFrameRef != None && p.GetSitState() == 0 && !ActiveFrameRef.IsDisabled()
            ActiveFrameRef.DisableNoWait()
        endif
    else
        SetOwnAv(p, InPaAvId, 0.0)
        ClearDepletedPenalty(p)
    endif
    StartTimer(POLL_S, TIMER_POLL)
    Trace("reload_sync inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " equipped_pa=" + EquippedPaCount(p) + " charge=" + GetOwnAv(p, FusionChargeAvId) + " saved_worn=" + SavedWornCount + " salvaged_worn=" + IsSalvagedWorn(p) + " limbs_min=" + MinLimbCondition(p) + " race=" + Id(p.GetRace()))
EndEvent

; ---------------------------------------------------------------- timer & movement-drain poll

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_STOP_RECORD
        RecordingWorn = false
        Actor p = Game.GetPlayer()
        Trace("outfit_saved saved_worn=" + SavedWornCount + " equipped_pa=" + EquippedPaCount(p))
    elseif aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif

    ; Quest stage commands (usable anywhere in the world)
    if GetStageDone(40) && !Stage40Handled
        Stage40Handled = true
        DeployFrameAtPlayer()
    endif
    if GetStageDone(10) && !Stage10Handled
        Stage10Handled = true
        EnterFrame(ActiveFrameRef, "stage10")
    endif
    if GetStageDone(20) && !Stage20Handled
        Stage20Handled = true
        Trace("status inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " equipped_pa=" + EquippedPaCount(p) + " charge=" + GetOwnAv(p, FusionChargeAvId) + " saved_worn=" + SavedWornCount + " salvaged_worn=" + IsSalvagedWorn(p) + " limbs_min=" + MinLimbCondition(p))
        if InSuit
            ApplyChargeDrain(p, 50.0, "stage20")
        endif
    endif
    if GetStageDone(30) && !Stage30Handled
        Stage30Handled = true
        ExitFrame("stage30")
    endif

    Cell curCell = p.GetParentCell()
    Cell testRoom = Thing(CellId) as Cell
    if testRoom != None && curCell == testRoom && !TestCellAnnounced
        TestCellAnnounced = true
        Say("PA test room: Fusion Cores & Salvaged armor on right (-Y); Frame ahead (+X); Exit chair on left (+Y).")
    endif

    ; SitState backup trigger in case OnSit fired while cell refs were settling
    int sitNow = p.GetSitState()
    if !InSuit && sitNow == 3
        ObjectReference frameRef = Ref(FrameFurnRefId)
        if frameRef != None && curCell == frameRef.GetParentCell() && p.GetDistance(frameRef) <= NEAR_FURN_DIST
            EnterFrame(frameRef, "sitstate_frame")
            return
        endif
    elseif InSuit && sitNow == 3
        ObjectReference exitRef = Ref(ExitChairRefId)
        if exitRef != None && curCell == exitRef.GetParentCell() && p.GetDistance(exitRef) <= NEAR_FURN_DIST
            ExitFrame("sitstate_exitchair")
            return
        endif
    endif

    if InSuit
        ; Hide empty frame furniture as soon as player stands up after climbing in
        if ActiveFrameRef != None && sitNow == 0 && !ActiveFrameRef.IsDisabled()
            ActiveFrameRef.DisableNoWait()
        endif

        ; FusionCore movement drain (clamped per tick and skipped across cell transitions)
        float curX = p.GetPositionX()
        float curY = p.GetPositionY()
        float curZ = p.GetPositionZ()
        if curCell == LastPlayerCell
            float dx = curX - LastPosX
            float dy = curY - LastPosY
            float dz = curZ - LastPosZ
            float dist = Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz))
            if dist >= MOVE_MIN_DIST && dist <= MOVE_MAX_STEP
                ApplyChargeDrain(p, (dist * DRAIN_PER_UNIT) + DRAIN_PER_ACTIVE_TICK, "move")
            elseif GetOwnAv(p, FusionChargeAvId) <= 0.0 && p.GetItemCount(Thing(FusionCoreId)) > 0
                LoadOrDepleteCore(p, "pickup_reload")
            endif
        endif
        LastPlayerCell = curCell
        LastPosX = curX
        LastPosY = curY
        LastPosZ = curZ
    else
        SyncLastPos(p)
    endif
EndFunction
