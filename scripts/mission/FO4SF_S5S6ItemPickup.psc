Scriptname FO4SF_S5S6ItemPickup extends ObjectReference
{Reusable parameterized activator script for S4/S5/S6 pickups and basement terminal proxy in FO4SFMission.esm.
Avoids editing FO4Port.esm (Slot 1 locked) or duplicating per-item scripts: looks up real FO4SFCoreValues.esm /
FO4SFPowerArmor.esm forms via Game.GetFormFromFile on activate and notifies FO4SF_Min00Quest cleanly.}

string Property ItemKind = "" Auto Const
{One of: display_musket, fusion_cell, stimpak, caps, bobbypin, pipe_weapon, fusion_core, basement_terminal.}

string Property CoreValuesPlugin = "FO4SFCoreValues.esm" Auto Const
string Property PowerArmorPlugin = "FO4SFPowerArmor.esm" Auto Const
string Property MissionPlugin = "FO4SFMission.esm" Auto Const
int Property Min00QuestId = 0x000800 Auto Const
int Property PrimaryFormId = 0 Auto Const
int Property SecondaryFormId = 0 Auto Const
int Property FallbackFormId = 0 Auto Const
int Property PrimaryCount = 1 Auto Const
int Property SecondaryCount = 0 Auto Const
bool Property ConsumeOnActivate = True Auto Const

string LogName = "fo4sf_mission"
bool handled = False

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction

Form Function LookupForm(int fid, string pluginName)
    if fid <= 0 || pluginName == ""
        return None
    endif
    return Game.GetFormFromFile(fid, pluginName)
EndFunction

bool Function GrantEntry(Actor player, int fid, string pluginName, int count, int fallbackSfId = 0)
    if player == None || count <= 0
        return False
    endif
    Form item = LookupForm(fid, pluginName)
    if item == None && fallbackSfId > 0
        item = Game.GetFormFromFile(fallbackSfId, "Starfield.esm")
    endif
    if item == None
        return False
    endif
    player.AddItem(item, count, False)
    return True
EndFunction

Event OnActivate(ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if player == None || (akActionRef != None && akActionRef != player)
        return
    endif
    if ConsumeOnActivate && handled
        return
    endif

    FO4SF_Min00Quest min00 = Game.GetFormFromFile(Min00QuestId, MissionPlugin) as FO4SF_Min00Quest

    if ItemKind == "display_musket"
        handled = True
        if min00 != None
            min00.TryGrantS4FallenMinutemanMusket(player)
        else
            GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount)
            GrantEntry(player, SecondaryFormId, CoreValuesPlugin, SecondaryCount)
        endif
        DisableNoWait(False)
        Trace("pickup display_musket handled=true")
        return
    elseif ItemKind == "fusion_core"
        handled = True
        bool okCore = GrantEntry(player, PrimaryFormId, PowerArmorPlugin, PrimaryCount)
        DisableNoWait(False)
        if min00 != None
            min00.AdvanceS6FusionCorePicked()
        endif
        Trace("pickup fusion_core granted=" + okCore + " fid=" + PrimaryFormId)
        return
    elseif ItemKind == "basement_terminal"
        if min00 != None
            bool unlocked = min00.TryOpenS6BasementGate("terminal")
            Trace("pickup basement_terminal unlocked=" + unlocked)
        endif
        return
    elseif ItemKind == "fusion_cell"
        handled = True
        bool okFc = GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount)
        DisableNoWait(False)
        Trace("pickup fusion_cell count=" + PrimaryCount + " granted=" + okFc)
        return
    elseif ItemKind == "stimpak"
        handled = True
        bool okSt = GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount)
        DisableNoWait(False)
        Trace("pickup stimpak count=" + PrimaryCount + " granted=" + okSt)
        return
    elseif ItemKind == "caps"
        handled = True
        bool okCaps = GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount, FallbackFormId)
        DisableNoWait(False)
        Trace("pickup caps count=" + PrimaryCount + " granted=" + okCaps)
        return
    elseif ItemKind == "bobbypin"
        handled = True
        bool okPin = GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount, FallbackFormId)
        if okPin && FallbackFormId > 0
            Form sfPick = Game.GetFormFromFile(FallbackFormId, "Starfield.esm")
            if sfPick != None
                player.AddItem(sfPick, PrimaryCount, True)
            endif
        endif
        DisableNoWait(False)
        Trace("pickup bobbypin count=" + PrimaryCount + " granted=" + okPin)
        return
    elseif ItemKind == "pipe_weapon"
        handled = True
        bool okWp = GrantEntry(player, PrimaryFormId, CoreValuesPlugin, PrimaryCount)
        bool okAm = GrantEntry(player, SecondaryFormId, CoreValuesPlugin, SecondaryCount)
        DisableNoWait(False)
        Trace("pickup pipe_weapon granted=" + okWp + " ammo=" + okAm)
        return
    endif
EndEvent
