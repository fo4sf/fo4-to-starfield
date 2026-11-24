Scriptname FO4SF_R11P2Quest extends Quest

; R11 Probe P2: Concord Museum Roof Power Armor Frame, T-45 stand-in pieces,
; Fusion Core entry gate (0x0809), 0 fall damage perk (0x081E), in-world exit activator,
; FO4TerrainCore duplicate disable (0x008913 / 0x005119), and Vertibird Minigun activator.

ObjectReference Property RoofFrameRef Auto
ObjectReference Property RoofMinigunRef Auto
ObjectReference Property RoofSpareCoreRef Auto
ObjectReference Property RoofExitRef Auto
ObjectReference Property StreetExitRef Auto
ActorValue Property HealthAV Auto

bool Property EnableLog = true Auto
string Property LogName = "fo4sf_r11p2" Auto

string Property StarfieldPlugin = "Starfield.esm" AutoReadOnly
string Property CoreValuesPlugin = "FO4SFCoreValues.esm" AutoReadOnly
string Property PowerArmorPlugin = "FO4SFPowerArmor.esm" AutoReadOnly
string Property TerrainCorePlugin = "FO4TerrainCore.esm" AutoReadOnly

int Property MinigunWeapId = 0x0008A0 AutoReadOnly
int Property Ammo5mmId = 0x00089F AutoReadOnly
int Property CoreQuestId = 0x000805 AutoReadOnly
int Property FusionCoreId = 0x000809 AutoReadOnly
int Property InPaAvId = 0x00080A AutoReadOnly
int Property FusionChargeAvId = 0x00080B AutoReadOnly
int Property NoFallPerkId = 0x00081E AutoReadOnly
int Property TerrainFrameStaticId = 0x008913 AutoReadOnly
int Property TerrainMinigunActiId = 0x005119 AutoReadOnly
int Property HealthAvId = 0x0002D4 AutoReadOnly

float Property RoofAnchorX = -1990.58 AutoReadOnly
float Property RoofAnchorY = -1724.19 AutoReadOnly
float Property RoofAnchorZ = 97.56 AutoReadOnly

float Property RoofFrameX = -1995.73 AutoReadOnly
float Property RoofFrameY = -1723.10 AutoReadOnly
float Property RoofFrameZ = 97.54 AutoReadOnly
float Property RoofFrameYaw = 351.07 AutoReadOnly

float Property RoofMinigunX = -2004.72 AutoReadOnly
float Property RoofMinigunY = -1715.40 AutoReadOnly
float Property RoofMinigunZ = 102.68 AutoReadOnly
float Property RoofMinigunRotX = -0.86 AutoReadOnly
float Property RoofMinigunRotY = 13.47 AutoReadOnly
float Property RoofMinigunRotZ = 292.55 AutoReadOnly

float Property RoofCoreX = -1993.50 AutoReadOnly
float Property RoofCoreY = -1723.40 AutoReadOnly
float Property RoofCoreZ = 97.56 AutoReadOnly

float Property RoofExitX = -1992.20 AutoReadOnly
float Property RoofExitY = -1725.60 AutoReadOnly
float Property RoofExitZ = 97.44 AutoReadOnly
float Property RoofExitYaw = 315.0 AutoReadOnly

float Property StreetExitX = -1995.00 AutoReadOnly
float Property StreetExitY = -1735.00 AutoReadOnly
float Property StreetExitZ = 86.90 AutoReadOnly
float Property StreetExitYaw = 0.0 AutoReadOnly

int Property SyncTimerId = 1 AutoReadOnly
int Property DropTimerId = 2 AutoReadOnly

bool Initialized = false
bool RoofSyncedConcord = false
bool LoggedTerrainDupes = false
bool MinigunGrabbed = false
bool SpareCoreGrabbed = false

float LastStableHp = -1.0
float LastPosZ = 0.0
bool DropArmed = false
string DropMode = ""
float DropHpBefore = -1.0
float DropLastHpAfter = -1.0
int DropTicks = 0
int DropLandedTicks = 0

Function Trace(string msg)
    if EnableLog
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, "[FO4SF_R11P2] " + msg)
    endif
EndFunction

Function Say(string msg)
    Debug.Notification(msg)
EndFunction

string Function HexForm(Form f)
    if f == None
        return "None"
    endif
    return "" + f
EndFunction

Form Function CrossForm(int localId, string pluginName)
    return Game.GetFormFromFile(localId, pluginName)
EndFunction

FO4SF_PowerArmorCoreQuest Function PaQuest()
    return CrossForm(CoreQuestId, PowerArmorPlugin) as FO4SF_PowerArmorCoreQuest
EndFunction

ActorValue Function ResolveHealthAV()
    if HealthAV != None
        return HealthAV
    endif
    return CrossForm(HealthAvId, StarfieldPlugin) as ActorValue
EndFunction

float Function ReadHealth(Actor p)
    ActorValue hpAv = ResolveHealthAV()
    if p == None || hpAv == None
        return -1.0
    endif
    return p.GetValue(hpAv)
EndFunction

bool Function NearConcordRoof(Actor p)
    if p == None || p.IsInInterior()
        return false
    endif
    float dx = Math.abs(p.GetPositionX() - RoofAnchorX)
    float dy = Math.abs(p.GetPositionY() - RoofAnchorY)
    return (dx < 110.0 && dy < 110.0)
EndFunction

Function EnsureHooks()
    Actor p = Game.GetPlayer()
    if p != None
        RegisterForRemoteEvent(p, "OnPlayerLoadGame")
        RegisterForRemoteEvent(p, "OnLocationChange")
        RegisterForRemoteEvent(p, "OnPlayerFallLongDistance")
    endif
    if RoofFrameRef != None
        RoofFrameRef.BlockActivation(true, false)
        RegisterForRemoteEvent(RoofFrameRef, "OnActivate")
    endif
    if RoofMinigunRef != None
        RoofMinigunRef.BlockActivation(true, false)
        RegisterForRemoteEvent(RoofMinigunRef, "OnActivate")
    endif
    if RoofSpareCoreRef != None
        RegisterForRemoteEvent(RoofSpareCoreRef, "OnActivate")
    endif
    if RoofExitRef != None
        RoofExitRef.BlockActivation(true, false)
        RegisterForRemoteEvent(RoofExitRef, "OnActivate")
    endif
    if StreetExitRef != None
        StreetExitRef.BlockActivation(true, false)
        RegisterForRemoteEvent(StreetExitRef, "OnActivate")
    endif
EndFunction

Function PlaceRefExact(ObjectReference refObj, Actor p, float x, float y, float z, float rx, float ry, float rz)
    if refObj == None || p == None
        return
    endif
    refObj.EnableNoWait()
    refObj.MoveTo(p, 0.0, 0.0, 2.0, false)
    refObj.SetPosition(x, y, z)
    refObj.SetAngle(rx, ry, rz)
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
    ObjectReference terrainFrame = CrossForm(TerrainFrameStaticId, TerrainCorePlugin) as ObjectReference
    ObjectReference terrainMinigun = CrossForm(TerrainMinigunActiId, TerrainCorePlugin) as ObjectReference
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
        bool frameDis = (terrainFrame != None && terrainFrame.IsDisabled())
        bool mgDis = (terrainMinigun != None && terrainMinigun.IsDisabled())
        Trace("terrain_dupes_disabled frame_static=" + HexForm(terrainFrame) + " minigun_acti=" + HexForm(terrainMinigun) + " frame_disabled=" + frameDis + " minigun_disabled=" + mgDis + " reason=" + reason)
    endif
EndFunction

Function SyncRoofObjects(bool forceFallback)
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    EnsureHooks()
    FO4SF_PowerArmorCoreQuest pa = PaQuest()
    bool inPa = (pa != None && pa.IsInPowerArmor())

    if NearConcordRoof(p)
        DisableTerrainRoofDupes("sync_concord")
        if !RoofSyncedConcord
            if RoofFrameRef != None && !inPa
                PlaceRefExact(RoofFrameRef, p, RoofFrameX, RoofFrameY, RoofFrameZ, 0.0, 0.0, RoofFrameYaw)
            endif
            if RoofMinigunRef != None && !MinigunGrabbed
                PlaceRefExact(RoofMinigunRef, p, RoofMinigunX, RoofMinigunY, RoofMinigunZ, RoofMinigunRotX, RoofMinigunRotY, RoofMinigunRotZ)
            endif
            if RoofSpareCoreRef != None && !SpareCoreGrabbed
                PlaceRefExact(RoofSpareCoreRef, p, RoofCoreX, RoofCoreY, RoofCoreZ, 0.0, 0.0, 0.0)
            endif
            if RoofExitRef != None
                PlaceRefExact(RoofExitRef, p, RoofExitX, RoofExitY, RoofExitZ, 0.0, 0.0, RoofExitYaw)
            endif
            if StreetExitRef != None
                PlaceRefExact(StreetExitRef, p, StreetExitX, StreetExitY, StreetExitZ, 0.0, 0.0, StreetExitYaw)
            endif
            RoofSyncedConcord = true
            Trace("roof_synced mode=concord_exact inpa=" + inPa + " frame=" + HexForm(RoofFrameRef) + " minigun=" + HexForm(RoofMinigunRef) + " core=" + HexForm(RoofSpareCoreRef) + " roof_exit=" + HexForm(RoofExitRef) + " street_exit=" + HexForm(StreetExitRef))
        endif
    elseif forceFallback && !p.IsInInterior()
        float px = p.GetPositionX()
        float py = p.GetPositionY()
        float pz = p.GetPositionZ()
        if RoofFrameRef != None && !inPa
            PlaceRefExact(RoofFrameRef, p, px + 3.0, py + 3.0, pz, 0.0, 0.0, 0.0)
        endif
        if RoofMinigunRef != None && !MinigunGrabbed
            PlaceRefExact(RoofMinigunRef, p, px - 3.0, py + 3.0, pz + 0.8, 0.0, 0.0, 0.0)
        endif
        if RoofSpareCoreRef != None && !SpareCoreGrabbed
            PlaceRefExact(RoofSpareCoreRef, p, px + 1.5, py + 2.0, pz + 0.1, 0.0, 0.0, 0.0)
        endif
        if RoofExitRef != None
            PlaceRefExact(RoofExitRef, p, px + 2.5, py - 2.0, pz, 0.0, 0.0, 0.0)
        endif
        Trace("roof_synced mode=standalone_local inpa=" + inPa + " px=" + px + " py=" + py + " pz=" + pz)
    endif
EndFunction

Function GrabRoofMinigun(string triggerWay)
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    if MinigunGrabbed
        Say("Vertibird Minigun already taken.")
        return
    endif
    Form minigunForm = CrossForm(MinigunWeapId, CoreValuesPlugin)
    Form ammoForm = CrossForm(Ammo5mmId, CoreValuesPlugin)
    if minigunForm == None || ammoForm == None
        Trace("minigun_grab_failed reason=missing_corevalues minigun=" + HexForm(minigunForm) + " ammo=" + HexForm(ammoForm))
        Say("Error: FO4SFCoreValues Minigun or 5mm form missing.")
        return
    endif

    DisableTerrainRoofDupes("minigun_grab")
    FO4SF_PowerArmorCoreQuest pa = PaQuest()
    bool inPa = (pa != None && pa.IsInPowerArmor())
    p.AddItem(minigunForm, 1, false)
    p.AddItem(ammoForm, 1200, false)
    MinigunGrabbed = true
    if RoofMinigunRef != None
        RoofMinigunRef.DisableNoWait()
    endif
    int nWeap = p.GetItemCount(minigunForm)
    int nAmmo = p.GetItemCount(ammoForm)
    Trace("minigun_grabbed trigger=" + triggerWay + " inpa=" + inPa + " minigun=" + HexForm(minigunForm) + " ammo=" + HexForm(ammoForm) + " count_minigun=" + nWeap + " count_5mm=" + nAmmo)
    Say("Vertibird Minigun acquired (+1200 5mm).")
EndFunction

Function GrantSpareCore(string triggerWay)
    Actor p = Game.GetPlayer()
    Form coreForm = CrossForm(FusionCoreId, PowerArmorPlugin)
    if p == None || coreForm == None
        Trace("grant_core_failed trigger=" + triggerWay)
        return
    endif
    p.AddItem(coreForm, 1, false)
    int cores = p.GetItemCount(coreForm)
    Trace("core_granted trigger=" + triggerWay + " cores=" + cores)
    Say("Added 1 Fusion Core (total " + cores + ").")
EndFunction

Function ArmDropWatch(string mode)
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    FO4SF_PowerArmorCoreQuest pa = PaQuest()
    bool inPa = (pa != None && pa.IsInPowerArmor())
    Perk nfPerk = CrossForm(NoFallPerkId, PowerArmorPlugin) as Perk
    bool hasNf = (nfPerk != None && p.HasPerk(nfPerk))
    float hpNow = ReadHealth(p)
    DropArmed = true
    DropMode = mode
    DropHpBefore = hpNow
    DropLastHpAfter = hpNow
    DropTicks = 0
    DropLandedTicks = 0
    LastStableHp = hpNow
    Trace("drop_armed mode=" + mode + " inpa=" + inPa + " no_fall_perk=" + hasNf + " hp_before=" + hpNow + " z=" + p.GetPositionZ())
    StartTimer(0.5, DropTimerId)
EndFunction

Function LogSummary(string tag)
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    FO4SF_PowerArmorCoreQuest pa = PaQuest()
    bool inPa = (pa != None && pa.IsInPowerArmor())
    Form coreForm = CrossForm(FusionCoreId, PowerArmorPlugin)
    Form mgForm = CrossForm(MinigunWeapId, CoreValuesPlugin)
    Form ammoForm = CrossForm(Ammo5mmId, CoreValuesPlugin)
    Perk nfPerk = CrossForm(NoFallPerkId, PowerArmorPlugin) as Perk
    ActorValue inPaAv = CrossForm(InPaAvId, PowerArmorPlugin) as ActorValue
    ActorValue chgAv = CrossForm(FusionChargeAvId, PowerArmorPlugin) as ActorValue
    int cores = 0
    if coreForm != None
        cores = p.GetItemCount(coreForm)
    endif
    int nMg = 0
    if mgForm != None
        nMg = p.GetItemCount(mgForm)
    endif
    int nAmmo = 0
    if ammoForm != None
        nAmmo = p.GetItemCount(ammoForm)
    endif
    bool hasNf = false
    if nfPerk != None
        hasNf = p.HasPerk(nfPerk)
    endif
    float avInPa = 0.0
    if inPaAv != None
        avInPa = p.GetValue(inPaAv)
    endif
    float avChg = 0.0
    if chgAv != None
        avChg = p.GetValue(chgAv)
    endif
    float hpNow = ReadHealth(p)
    Form eqWeap = p.GetEquippedWeapon()
    Trace("summary tag=" + tag + " pos=(" + p.GetPositionX() + "," + p.GetPositionY() + "," + p.GetPositionZ() + ") inpa=" + inPa + " av_inpa=" + avInPa + " charge=" + avChg + " cores=" + cores + " no_fall_perk=" + hasNf + " hp_now=" + hpNow + " hp_before=" + DropHpBefore + " hp_after=" + DropLastHpAfter + " eq_weapon=" + HexForm(eqWeap) + " race=" + HexForm(p.GetRace()) + " minigun=" + nMg + " ammo_5mm=" + nAmmo + " roof_synced=" + RoofSyncedConcord + " minigun_grabbed=" + MinigunGrabbed)
EndFunction

Event OnQuestInit()
    Debug.OpenUserLog(LogName)
    Initialized = true
    EnsureHooks()
    Actor p = Game.GetPlayer()
    if p != None
        LastStableHp = ReadHealth(p)
        LastPosZ = p.GetPositionZ()
    endif
    Trace("init quest=" + HexForm(self) + " roof_frame=" + HexForm(RoofFrameRef) + " roof_minigun=" + HexForm(RoofMinigunRef) + " spare_core=" + HexForm(RoofSpareCoreRef) + " roof_exit=" + HexForm(RoofExitRef) + " street_exit=" + HexForm(StreetExitRef))
    SyncRoofObjects(false)
    StartTimer(2.0, SyncTimerId)
EndEvent

Event OnTimer(int aiTimerID)
    Actor p = Game.GetPlayer()
    if aiTimerID == SyncTimerId
        if p != None
            if !DropArmed && Math.abs(p.GetPositionZ() - LastPosZ) < 0.3
                float stableHp = ReadHealth(p)
                if stableHp >= 0.0
                    LastStableHp = stableHp
                endif
            endif
            LastPosZ = p.GetPositionZ()
            if NearConcordRoof(p)
                if !RoofSyncedConcord
                    SyncRoofObjects(false)
                else
                    DisableTerrainRoofDupes("poll")
                endif
            else
                LoggedTerrainDupes = false
            endif
        endif
        StartTimer(2.0, SyncTimerId)
    elseif aiTimerID == DropTimerId
        if !DropArmed || p == None
            return
        endif
        DropTicks += 1
        float curZ = p.GetPositionZ()
        if curZ < 91.0
            DropLandedTicks += 1
        endif
        if DropLandedTicks >= 2 || DropTicks >= 20
            FO4SF_PowerArmorCoreQuest pa = PaQuest()
            bool inPa = (pa != None && pa.IsInPowerArmor())
            Perk nfPerk = CrossForm(NoFallPerkId, PowerArmorPlugin) as Perk
            bool hasNf = (nfPerk != None && p.HasPerk(nfPerk))
            float hpAfter = ReadHealth(p)
            float hpBefore = DropHpBefore
            if hpBefore < 0.0
                hpBefore = hpAfter
            endif
            DropLastHpAfter = hpAfter
            LastStableHp = hpAfter
            DropArmed = false
            Trace("drop_settled mode=" + DropMode + " inpa=" + inPa + " no_fall_perk=" + hasNf + " hp_before=" + hpBefore + " hp_after=" + hpAfter + " hp_lost=" + (hpBefore - hpAfter) + " z=" + curZ)
        else
            StartTimer(0.5, DropTimerId)
        endif
    endif
EndEvent

Event Actor.OnLocationChange(Actor akSender, Location akOldLoc, Location akNewLoc)
    if NearConcordRoof(akSender)
        SyncRoofObjects(false)
    else
        LoggedTerrainDupes = false
    endif
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    LoggedTerrainDupes = false
    DropArmed = false
    EnsureHooks()
    if akSender != None
        LastStableHp = ReadHealth(akSender)
        LastPosZ = akSender.GetPositionZ()
    endif
    if NearConcordRoof(akSender)
        if !RoofSyncedConcord
            SyncRoofObjects(false)
        else
            DisableTerrainRoofDupes("load_game")
        endif
    endif
    StartTimer(2.0, SyncTimerId)
    LogSummary("load_game")
EndEvent

Event Actor.OnPlayerFallLongDistance(Actor akSender, float afDamage)
    Actor p = Game.GetPlayer()
    float hpAfter = ReadHealth(p)
    float hpBefore = DropHpBefore
    if !DropArmed || hpBefore < 0.0
        hpBefore = LastStableHp
    endif
    if hpBefore < 0.0
        hpBefore = hpAfter
    endif
    DropLastHpAfter = hpAfter
    LastStableHp = hpAfter
    FO4SF_PowerArmorCoreQuest pa = PaQuest()
    bool inPa = (pa != None && pa.IsInPowerArmor())
    Perk nfPerk = CrossForm(NoFallPerkId, PowerArmorPlugin) as Perk
    bool hasNf = (nfPerk != None && p != None && p.HasPerk(nfPerk))
    string mode = DropMode
    if mode == ""
        if inPa
            mode = "armored"
        else
            mode = "unarmored"
        endif
    endif
    float curZ = 0.0
    if p != None
        curZ = p.GetPositionZ()
    endif
    Trace("fall_long mode=" + mode + " inpa=" + inPa + " no_fall_perk=" + hasNf + " dmg_reported=" + afDamage + " hp_before=" + hpBefore + " hp_after=" + hpAfter + " hp_lost=" + (hpBefore - hpAfter) + " z=" + curZ)
    LogSummary("fall_long")
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor p = Game.GetPlayer()
    if akSender == None || p == None || akActionRef != (p as ObjectReference)
        return
    endif
    if akSender == RoofFrameRef
        DisableTerrainRoofDupes("frame_activate")
        FO4SF_PowerArmorCoreQuest pa = PaQuest()
        if pa != None
            pa.EnterFrame(RoofFrameRef, "p2_roof_frame_activate")
        else
            Trace("roof_frame_activate_failed reason=no_pa_quest")
        endif
    elseif akSender == RoofMinigunRef
        GrabRoofMinigun("p2_vertibird_activate")
    elseif akSender == RoofSpareCoreRef
        SpareCoreGrabbed = true
        Trace("spare_core_activated ref=" + HexForm(RoofSpareCoreRef))
    elseif akSender == RoofExitRef || akSender == StreetExitRef
        FO4SF_PowerArmorCoreQuest pa = PaQuest()
        if pa != None && pa.IsInPowerArmor()
            pa.ExitFrame("p2_inworld_exit_activate")
            Trace("inworld_exit_activated ref=" + HexForm(akSender))
        else
            Say("Not currently in Power Armor.")
            Trace("inworld_exit_ignored reason=not_in_pa ref=" + HexForm(akSender))
        endif
    endif
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 10
        DisableTerrainRoofDupes("p2_stage10")
        FO4SF_PowerArmorCoreQuest pa = PaQuest()
        if pa != None
            pa.EnterFrame(RoofFrameRef, "p2_stage10")
        endif
    elseif auiStageID == 20
        SyncRoofObjects(true)
    elseif auiStageID == 30
        FO4SF_PowerArmorCoreQuest pa = PaQuest()
        if pa != None
            pa.ExitFrame("p2_stage30")
        endif
    elseif auiStageID == 40
        GrantSpareCore("p2_stage40")
    elseif auiStageID == 50
        GrabRoofMinigun("p2_stage50")
    elseif auiStageID == 60
        MinigunGrabbed = false
        SpareCoreGrabbed = false
        RoofSyncedConcord = false
        LoggedTerrainDupes = false
        SyncRoofObjects(true)
    elseif auiStageID == 70
        LogSummary("p2_stage70")
    elseif auiStageID == 75
        ArmDropWatch("armored")
    elseif auiStageID == 80
        FO4SF_PowerArmorCoreQuest pa = PaQuest()
        if pa != None && pa.IsInPowerArmor()
            Say("Exit Power Armor first before unarmored control drop (bat p2c).")
            Trace("drop_control_blocked reason=still_in_pa")
        else
            ArmDropWatch("control_unarmored")
        endif
    endif
EndEvent
