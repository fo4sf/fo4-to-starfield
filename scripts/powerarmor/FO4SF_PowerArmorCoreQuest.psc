Scriptname FO4SF_PowerArmorCoreQuest extends Quest
{Fallout 4 climb-in Power Armor frame + 6-limb BPTD + FusionCore drain + prior outfit restore + save/reload re-sync +
 FNV Salvaged NCR worn heavy ARMO support (docs/powerarmor/power-armor-core.md).
 Attached to QUST FO4SF_PowerArmorCoreQuest (0x805) in FO4SFPowerArmor.esm (StartGameEnabled; SpecialAgilityAV and
 TestModeGlobal bound to FO4SFCoreValues.esm; local forms resolved via Game.GetFormFromFile). Non-intrusive in normal
 gameplay: never teleports the player automatically, and stages 10/20/30/40 require TestModeGlobal != 0.
 Stages (TestModeGlobal != 0):
   10 = climb into nearest / persistent FO4SF_PowerArmorFrameFurn
   20 = log status snapshot and apply a deterministic 50-point test drain pulse while in frame
   30 = exit frame anywhere in the world, leave FURN standing at exit spot, and restore prior worn outfit
   40 = deploy / move persistent FO4SF_PowerArmorFrameFurnRef in front of player anywhere in the world
 User log: My Games\Starfield\Logs\Script\User\FO4SFPACore.0.log ("FO4SFPACORE rt=<rt> <event> key=value ... end=true").}

; ---------------------------------------------------------------- CoreValues properties (bound on QUST VMAD)

ActorValue Property SpecialAgilityAV Auto Const
GlobalVariable Property TestModeGlobal Auto Const

; ---------------------------------------------------------------- layout (held equal with dotnet/PowerArmorCore/Program.cs)

string LogName = "FO4SFPACore"
string CorePlugin = "FO4SFPowerArmor.esm"
string StarfieldPlugin = "Starfield.esm"
string TerrainCorePlugin = "FO4TerrainCore.esm"
string P2ProbePlugin = "FO4SF_R11P2PowerArmor.esm"

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
int NoFallPerkId = 0x81E

int ArrivalRefId = 0x820
int CocRefId = 0x821
int FrameFurnRefId = 0x822
int ExitChairRefId = 0x823

int PaLeftArmId = 0x82A
int PaRightArmId = 0x82B
int PaLeftLegId = 0x82C
int PaRightLegId = 0x82D

int SfCarryWeightAvId = 0x0002DC
int SfHealthAvId = 0x0002D4
int TerrainFrameStaticId = 0x008913
int TerrainMinigunActiId = 0x005119
float ConcordRoofAnchorX = -1990.58
float ConcordRoofAnchorY = -1724.19

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
bool TransitionBusy = false
bool RecordingWorn = false
bool DepletedPenaltyApplied = false
bool SalvagedSpecialAgiApplied = false
bool TestCellAnnounced = false
bool Stage10Handled = false
bool Stage20Handled = false
bool Stage30Handled = false
bool Stage40Handled = false
bool Initialized = false

Form[] SavedWornGear = None
int SavedWornCount = 0
Race SavedOrigRace = None
ObjectReference ActiveFrameRef = None
bool ActiveFrameDynamic = false
Cell LastPlayerCell = None
float LastPosX = 0.0
float LastPosY = 0.0
float LastPosZ = 0.0
int LastLoggedChargeBucket = -1
int Cycle = 0
bool LoggedTerrainDupes = false
float LastStableHp = -1.0

; ---------------------------------------------------------------- init & logging

Event OnQuestInit()
    if Initialized
        return
    endif
    Initialized = true
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
        LastStableHp = GetPlayerHealth(p)
        RegisterPlayerEvents(p)
        DisableTerrainRoofDupes("quest_init")
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
    RegisterForRemoteEvent(p, "OnLocationChange")
    RegisterForRemoteEvent(p, "OnPlayerFallLongDistance")
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

float Function GetSpecialAgiVal(Actor p)
    if p == None || SpecialAgilityAV == None
        return 0.0
    endif
    return p.GetValue(SpecialAgilityAV)
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

float Function GetPlayerHealth(Actor p)
    ActorValue hpAv = SfAv(SfHealthAvId)
    if p == None || hpAv == None
        return -1.0
    endif
    return p.GetValue(hpAv)
EndFunction

bool Function NearConcordRoof(Actor p)
    if p == None || p.IsInInterior()
        return false
    endif
    float dx = Math.abs(p.GetPositionX() - ConcordRoofAnchorX)
    float dy = Math.abs(p.GetPositionY() - ConcordRoofAnchorY)
    return (dx < 110.0 && dy < 110.0)
EndFunction

Function DisableTerrainRoofDupes(string reason)
    Actor p = Game.GetPlayer()
    if p == None || !Game.IsPluginInstalled(TerrainCorePlugin)
        return
    endif
    if !NearConcordRoof(p)
        LoggedTerrainDupes = false
        return
    endif
    if !Game.IsPluginInstalled(P2ProbePlugin) && !InSuit
        return
    endif
    ObjectReference terrainFrame = Game.GetFormFromFile(TerrainFrameStaticId, TerrainCorePlugin) as ObjectReference
    ObjectReference terrainMinigun = Game.GetFormFromFile(TerrainMinigunActiId, TerrainCorePlugin) as ObjectReference
    bool didDisable = false
    if terrainFrame != None && !terrainFrame.IsDisabled()
        terrainFrame.DisableNoWait(false)
        didDisable = true
    endif
    if terrainMinigun != None && !terrainMinigun.IsDisabled()
        terrainMinigun.DisableNoWait(false)
        didDisable = true
    endif
    if (terrainFrame != None || terrainMinigun != None) && (!LoggedTerrainDupes || didDisable)
        LoggedTerrainDupes = (terrainFrame != None && terrainMinigun != None)
        Trace("terrain_dupes_disabled frame_static=" + Id(terrainFrame) + " minigun_acti=" + Id(terrainMinigun) + " reason=" + reason)
    endif
EndFunction

; ---------------------------------------------------------------- piece & furniture helpers

bool Function IsPaPiece(Form itemForm)
    if itemForm == None
        return false
    endif
    return itemForm == Thing(FrameArmorId) || itemForm == Thing(PaTorsoId) || itemForm == Thing(PaHelmetId) || itemForm == Thing(PaPackId) || itemForm == Thing(PaLeftArmId) || itemForm == Thing(PaRightArmId) || itemForm == Thing(PaLeftLegId) || itemForm == Thing(PaRightLegId)
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
    int[] pieceIds = new int[8]
    pieceIds[0] = FrameArmorId
    pieceIds[1] = PaTorsoId
    pieceIds[2] = PaHelmetId
    pieceIds[3] = PaPackId
    pieceIds[4] = PaLeftArmId
    pieceIds[5] = PaRightArmId
    pieceIds[6] = PaLeftLegId
    pieceIds[7] = PaRightLegId
    int idx = 0
    while idx < 8
        Form pf = Thing(pieceIds[idx])
        if pf != None && p.IsEquipped(pf)
            n += 1
        endif
        idx += 1
    endwhile
    return n
EndFunction

Function EquipAllPaPieces(Actor p, bool addMissing)
    if p == None
        return
    endif
    int[] pieceIds = new int[8]
    pieceIds[0] = FrameArmorId
    pieceIds[1] = PaTorsoId
    pieceIds[2] = PaHelmetId
    pieceIds[3] = PaPackId
    pieceIds[4] = PaLeftArmId
    pieceIds[5] = PaRightArmId
    pieceIds[6] = PaLeftLegId
    pieceIds[7] = PaRightLegId
    int idx = 0
    while idx < 8
        Form pf = Thing(pieceIds[idx])
        if pf != None
            if addMissing && p.GetItemCount(pf) == 0
                p.AddItem(pf, 1, true)
            endif
            if p.GetItemCount(pf) > 0 && !p.IsEquipped(pf)
                p.EquipItem(pf, false, true)
            endif
        endif
        idx += 1
    endwhile
EndFunction

Function RemoveAllPaPieces(Actor p)
    if p == None
        return
    endif
    int[] pieceIds = new int[8]
    pieceIds[0] = FrameArmorId
    pieceIds[1] = PaTorsoId
    pieceIds[2] = PaHelmetId
    pieceIds[3] = PaPackId
    pieceIds[4] = PaLeftArmId
    pieceIds[5] = PaRightArmId
    pieceIds[6] = PaLeftLegId
    pieceIds[7] = PaRightLegId
    int idx = 0
    while idx < 8
        Form pf = Thing(pieceIds[idx])
        if pf != None
            p.UnequipItem(pf, false, true)
            int cnt = p.GetItemCount(pf)
            if cnt > 0
                p.RemoveItem(pf, cnt, true)
            endif
        endif
        idx += 1
    endwhile
EndFunction

Function ApplyNoFallDamagePerk(Actor p, bool enableImmunity)
    if p == None
        return
    endif
    Perk nfPerk = Thing(NoFallPerkId) as Perk
    if nfPerk == None
        return
    endif
    if enableImmunity
        if !p.HasPerk(nfPerk)
            p.AddPerk(nfPerk, false)
        endif
    else
        if p.HasPerk(nfPerk)
            p.RemovePerk(nfPerk)
        endif
    endif
EndFunction

bool Function IsInPowerArmor()
    return InSuit
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
    Form frameBase = Thing(FrameFurnId)
    if frameBase != None && furnRef.GetBaseObject() == frameBase
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
    if p == None || InSuit || TransitionBusy
        return
    endif
    float existingCharge = GetOwnAv(p, FusionChargeAvId)
    Form coreItem = Thing(FusionCoreId)
    int heldCores = 0
    if coreItem != None
        heldCores = p.GetItemCount(coreItem)
    endif
    if existingCharge <= 0.0 && heldCores < 1
        Stage10Handled = false
        Trace("entry_refused cycle=" + Cycle + " trigger=" + triggerWay + " reason=no_fusion_core charge=" + existingCharge + " cores=" + heldCores)
        Say("Fusion Core required to enter Power Armor (0 cores).")
        return
    endif

    TransitionBusy = true
    Trace("enter_standin_begin cycle=" + Cycle + " mode=fade_equip_standin trigger=" + triggerWay)
    Game.FadeOutGame(true, true, 0.0, 0.35, true)
    Utility.Wait(0.35)

    if SavedWornGear == None
        SavedWornGear = new Form[64]
    endif
    if targetFurn != None
        if targetFurn != ActiveFrameRef
            ActiveFrameDynamic = false
        endif
        if targetFurn == Ref(FrameFurnRefId)
            ActiveFrameDynamic = false
        endif
        ActiveFrameRef = targetFurn
    else
        ActiveFrameRef = Ref(FrameFurnRefId)
        ActiveFrameDynamic = false
    endif

    Race curRace = p.GetRace()
    Race paRaceObj = Thing(RaceId) as Race
    if curRace != None && curRace != paRaceObj
        SavedOrigRace = curRace
    endif

    SavedWornCount = 0
    RecordingWorn = true
    InitLimbConditions(p)

    ; Equip all 8 disjoint FO4 PA + T-45 stand-in pieces while RecordingWorn=true so player gear is captured
    EquipAllPaPieces(p, true)

    ; Swap to FO4SF_PowerArmorRace (wired to 6-limb BPTD + FO4SF_PowerArmorSkin + RACE.NAM4 0x0009150B)
    if paRaceObj != None && p.GetRace() != paRaceObj
        p.SetRace(paRaceObj)
        ; Re-assert equip on PA race in case SetRace refreshed biped state
        EquipAllPaPieces(p, false)
    endif

    ApplyNoFallDamagePerk(p, true)

    if existingCharge > 0.0
        ClearDepletedPenalty(p)
        LastLoggedChargeBucket = (existingCharge / 5.0) as int
    else
        LoadOrDepleteCore(p, "climb_in")
    endif

    SetOwnAv(p, InPaAvId, 1.0)
    InSuit = true
    Stage30Handled = false
    SyncLastPos(p)
    LastStableHp = GetPlayerHealth(p)
    DisableTerrainRoofDupes("enter_frame")
    if ActiveFrameRef != None && p.GetSitState() == 0 && !ActiveFrameRef.IsDisabled()
        ActiveFrameRef.DisableNoWait()
    endif
    Game.FadeOutGame(false, true, 0.0, 0.35, false)
    TransitionBusy = false
    StartTimer(RECORD_WINDOW_S, TIMER_STOP_RECORD)
    Trace("climb_in cycle=" + Cycle + " trigger=" + triggerWay + " mode=fade_equip_standin fall_perk=" + (p.HasPerk(Thing(NoFallPerkId) as Perk)) + " race=" + Id(p.GetRace()) + " orig_race=" + Id(SavedOrigRace) + " equipped_pa=" + EquippedPaCount(p) + " charge=" + GetOwnAv(p, FusionChargeAvId) + " limbs_min=" + MinLimbCondition(p) + " inpa=" + GetOwnAv(p, InPaAvId))
    Say("Power Armor ON (T-45/fade stand-in; charge " + GetOwnAv(p, FusionChargeAvId) + "%, 0 fall dmg).")
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
    if p == None || !InSuit || TransitionBusy
        return
    endif
    TransitionBusy = true
    Trace("exit_standin_begin cycle=" + Cycle + " mode=fade_equip_standin trigger=" + triggerWay)
    Game.FadeOutGame(true, true, 0.0, 0.35, true)
    Utility.Wait(0.35)

    RecordingWorn = false
    ApplyNoFallDamagePerk(p, false)
    ClearDepletedPenalty(p)
    SetOwnAv(p, InPaAvId, 0.0)
    InSuit = false
    Stage10Handled = false

    RemoveAllPaPieces(p)

    if SavedOrigRace != None && p.GetRace() != SavedOrigRace
        p.SetRace(SavedOrigRace)
    endif

    if ActiveFrameRef != None
        ActiveFrameRef.DisableNoWait()
        if ActiveFrameDynamic && ActiveFrameRef != Ref(FrameFurnRefId)
            ActiveFrameRef.Delete()
        endif
        ActiveFrameRef = None
        ActiveFrameDynamic = false
    endif
    bool frameStanding = false
    Form frameBase = Thing(FrameFurnId)
    if frameBase != None
        ActiveFrameRef = p.PlaceAtMe(frameBase, 1, true, false, false)
        ActiveFrameDynamic = (ActiveFrameRef != None)
        BindStandinFrameActivation(ActiveFrameRef)
        frameStanding = (ActiveFrameRef != None && !ActiveFrameRef.IsDisabled())
    endif

    RestorePriorOutfit(p)
    SyncLastPos(p)
    LastStableHp = GetPlayerHealth(p)
    DisableTerrainRoofDupes("exit_frame")
    Game.FadeOutGame(false, true, 0.0, 0.35, false)
    TransitionBusy = false
    Trace("exit_complete cycle=" + Cycle + " trigger=" + triggerWay + " mode=fade_equip_standin restored_worn=" + SavedWornCount + " equipped_pa=" + EquippedPaCount(p) + " inpa=" + GetOwnAv(p, InPaAvId) + " race=" + Id(p.GetRace()) + " frame_standing=" + frameStanding + " charge_kept=" + GetOwnAv(p, FusionChargeAvId))
    Say("Power Armor OFF: frame left standing, restored " + SavedWornCount + " prior outfit item(s).")
    Cycle += 1
EndFunction

Function BindStandinFrameActivation(ObjectReference frameRef)
    if frameRef == None
        return
    endif
    frameRef.BlockActivation(true, false)
    RegisterForRemoteEvent(frameRef, "OnActivate")
EndFunction

Function DeployFrameAtPlayer()
    Actor p = Game.GetPlayer()
    Form frameBase = Thing(FrameFurnId)
    if p == None || frameBase == None
        return
    endif
    if ActiveFrameRef != None
        ActiveFrameRef.DisableNoWait()
        if ActiveFrameDynamic && ActiveFrameRef != Ref(FrameFurnRefId)
            ActiveFrameRef.Delete()
        endif
    endif
    ActiveFrameRef = p.PlaceAtMe(frameBase, 1, true, false, false)
    ActiveFrameDynamic = (ActiveFrameRef != None)
    BindStandinFrameActivation(ActiveFrameRef)
    Trace("frame_deployed ref=" + Id(ActiveFrameRef) + " cell=" + Id(p.GetParentCell()))
    Say("Power Armor frame deployed at player.")
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
        if SalvagedSpecialAgiApplied
            if SpecialAgilityAV != None
                p.ModValue(SpecialAgilityAV, 1.0)
            endif
            SalvagedSpecialAgiApplied = false
        endif
        Trace("salvaged_unequip item=" + Id(akBaseObject) + " inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " agi=" + GetSpecialAgiVal(p))
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    Actor p = Game.GetPlayer()
    if akBaseObject == None || p == None
        return
    endif
    if IsSalvagedPiece(akBaseObject)
        Trace("salvaged_equip item=" + Id(akBaseObject) + " inpa=" + InSuit + " pa_av=" + GetOwnAv(p, InPaAvId) + " agi=" + GetSpecialAgiVal(p) + " charge=" + GetOwnAv(p, FusionChargeAvId))
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

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor p = Game.GetPlayer()
    if akSender == None || p == None || akActionRef != (p as ObjectReference)
        return
    endif
    if !InSuit && IsFrameFurniture(akSender)
        EnterFrame(akSender, "activate_frame")
    endif
EndEvent

Event Actor.OnPlayerFallLongDistance(Actor akSender, float afDamage)
    Actor p = Game.GetPlayer()
    bool hasImmunity = false
    float hpAfter = -1.0
    float hpBefore = LastStableHp
    if p != None
        Perk nfPerk = Thing(NoFallPerkId) as Perk
        if nfPerk != None
            hasImmunity = p.HasPerk(nfPerk)
        endif
        hpAfter = GetPlayerHealth(p)
        if hpBefore < 0.0
            hpBefore = hpAfter
        endif
        LastStableHp = hpAfter
    endif
    Trace("fall_long inpa=" + InSuit + " dmg_reported=" + afDamage + " immunity_perk=" + hasImmunity + " hp_before=" + hpBefore + " hp_after=" + hpAfter)
EndEvent

Event Actor.OnLocationChange(Actor akSender, Location akOldLoc, Location akNewLoc)
    DisableTerrainRoofDupes("location_change")
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    TransitionBusy = false
    LoggedTerrainDupes = false
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    RegisterPlayerEvents(p)
    SyncLastPos(p)
    LastStableHp = GetPlayerHealth(p)
    DisableTerrainRoofDupes("load_game")
    if InSuit
        SetOwnAv(p, InPaAvId, 1.0)
        InitLimbConditions(p)
        ; Re-verify PA pieces and 0 fall damage perk remain active without overwriting SavedWornGear
        RecordingWorn = false
        EquipAllPaPieces(p, false)
        ApplyNoFallDamagePerk(p, true)
        if ActiveFrameRef != None && p.GetSitState() == 0 && !ActiveFrameRef.IsDisabled()
            ActiveFrameRef.DisableNoWait()
        endif
    else
        SetOwnAv(p, InPaAvId, 0.0)
        ApplyNoFallDamagePerk(p, false)
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
    if Math.abs(p.GetPositionZ() - LastPosZ) < 0.3
        float stableHp = GetPlayerHealth(p)
        if stableHp >= 0.0
            LastStableHp = stableHp
        endif
    endif
    DisableTerrainRoofDupes("poll")

    ; Quest stage commands (gated behind FO4SF_TestModeEnabled != 0)
    if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
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
    endif

    Cell curCell = p.GetParentCell()
    Cell testRoom = Thing(CellId) as Cell
    if testRoom != None && curCell == testRoom && !TestCellAnnounced
        TestCellAnnounced = true
        Say("PA test room: Fusion Cores & Salvaged armor on right (-Y); Frame ahead (+X); Exit chair on left (+Y).")
    endif

    ; SitState backup trigger in case OnSit fired while cell refs were settling
    int sitNow = p.GetSitState()
    if !InSuit && !TransitionBusy && sitNow == 3
        ObjectReference frameRef = Ref(FrameFurnRefId)
        if frameRef != None && curCell == frameRef.GetParentCell() && p.GetDistance(frameRef) <= NEAR_FURN_DIST
            EnterFrame(frameRef, "sitstate_frame")
            return
        elseif ActiveFrameRef != None && curCell == ActiveFrameRef.GetParentCell() && p.GetDistance(ActiveFrameRef) <= NEAR_FURN_DIST
            EnterFrame(ActiveFrameRef, "sitstate_active_frame")
            return
        endif
    elseif InSuit && !TransitionBusy && sitNow == 3
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
