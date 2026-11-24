Scriptname FO4SF_R11P6Quest extends Quest
{Round 11 Probe P6 (Full Arsenal Rows 1-20, Impacts, Laser Ash & Plasma Goo) telemetry and range quest.}

Group References
    ObjectReference Property TargetTrigger Auto
    {Persistent E-activator beside Vault 111 P6 firing line in FO4Port_Vault111Cryo.}

    Actor Property FleshDummy Auto
    {Persistent InitiallyDisabled unarmed restrained flesh target (turns Ash/Goo on Laser/Plasma kill).}

    Actor Property RobotDummy Auto
    {Persistent InitiallyDisabled unarmed restrained vanilla Starfield robot target (metal impacts).}

    Actor Property NoDisintDummy Auto
    {Persistent InitiallyDisabled target carrying NoDisintegrate (0x0022DB8F) to prove Ash/Goo suppression.}

    ObjectReference Property StoneTarget Auto
    {Persistent Starfield stone static target beside range for bullet/melee/energy surface impacts.}

    ObjectReference Property WoodTarget Auto
    {Persistent Starfield wood crate static target beside range for bullet/melee/energy surface impacts.}

    Weapon[] Property ShowcaseWeapons Auto
    {All 23 playable FO4 weapons in FO4SFCoreValues.esm (Rows 1-20).}

    string[] Property WeaponTags Auto
    {Short log tags matching ShowcaseWeapons indices.}

    Ammo[] Property ShowcaseAmmos Auto
    {All 13 playable FO4 ammo types in FO4SFCoreValues.esm.}

    string[] Property AmmoTags Auto
    {Short log tags matching ShowcaseAmmos indices.}

    int[] Property GrantAmmoCounts Auto
    {Fallback grant counts matching ShowcaseAmmos indices.}

    MiscObject Property CapsMisc Auto
    {FO4SFCoreValues.esm:0x0008A4 FO4_Caps.}

    MiscObject Property BobbyPinMisc Auto
    {FO4SFCoreValues.esm:0x0008A5 FO4_BobbyPin.}

    Potion Property StimpakAlch Auto
    {FO4SFCoreValues.esm:0x000851 FO4SF_Stimpak.}

    Spell Property CritPlasmaSpell Auto
    {FO4SFCoreValues.esm:0x0008C3 FO4_CritPlasma (spawns FO4_GooPile01 on non-NoDisintegrate kill).}

    Spell Property CritLaserSpell Auto
    {FO4SFCoreValues.esm:0x0008C4 FO4_CritLaser (spawns laser ash pile on non-NoDisintegrate kill).}

    Keyword Property NoDisintegrateKw Auto
    {Starfield.esm:0x0022DB8F NoDisintegrate.}

    ActorValue Property HealthAV Auto
    {Starfield.esm:0x0002D4 Health.}

    ActorValue Property HideSuitAV Auto
    {Starfield.esm:0x0B120E ActorShouldForceHideSpacesuit_AV.}

    int Property ArmoryCageDoorLocalId = 0x001539 Auto
    {Local FormID of FO4Port_SwitchDoorExSmLatch01 in FO4Port.esm (runtime GetFormFromFile).}

    string Property PortPlugin = "FO4Port.esm" Auto
    {Plugin hosting ArmoryCageDoorLocalId.}
EndGroup

Group Logging
    bool Property EnableLog = true Auto
    string Property LogName = "fo4sf_r11p6" Auto
EndGroup

int TIMER_POLL = 1
bool initLogged = false
int weaponsAcquiredCount = 0
int weaponsEquippedCount = 0
int fleshKills = 0
int robotKills = 0
int noDisintKills = 0
bool forceCritDisint = false
string lastEquippedTag = "none"

Event OnInit()
    EnsureInitialized("on_init")
EndEvent

Event OnQuestInit()
    EnsureInitialized("on_quest_init")
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    RegisterHooks()
    LogScorecard("load_game")
    StartTimer(1.0, TIMER_POLL)
EndEvent

Function EnsureInitialized(string source)
    RegisterHooks()
    if !initLogged
        initLogged = true
        Log("FO4SF_R11P6 init source=" + source + " weapons=" + ShowcaseWeapons.Length + " ammos=" + ShowcaseAmmos.Length + " targets=flesh,robot,nodisint,stone,wood")
        LogScorecard("init")
    endif
    StartTimer(1.0, TIMER_POLL)
EndFunction

Function RegisterHooks()
    Actor player = Game.GetPlayer()
    if player != None
        int wi = 0
        while wi < ShowcaseWeapons.Length
            if ShowcaseWeapons[wi] != None
                AddInventoryEventFilter(ShowcaseWeapons[wi])
            endif
            wi += 1
        endwhile
        int ai = 0
        while ai < ShowcaseAmmos.Length
            if ShowcaseAmmos[ai] != None
                AddInventoryEventFilter(ShowcaseAmmos[ai])
            endif
            ai += 1
        endwhile
        if CapsMisc != None
            AddInventoryEventFilter(CapsMisc)
        endif
        if BobbyPinMisc != None
            AddInventoryEventFilter(BobbyPinMisc)
        endif
        if StimpakAlch != None
            AddInventoryEventFilter(StimpakAlch)
        endif
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")
        RegisterForRemoteEvent(player, "OnItemEquipped")
    endif
    if TargetTrigger != None
        RegisterForRemoteEvent(TargetTrigger, "OnActivate")
    endif
    if FleshDummy != None
        RegisterForRemoteEvent(FleshDummy, "OnDying")
    endif
    if RobotDummy != None
        RegisterForRemoteEvent(RobotDummy, "OnDying")
    endif
    if NoDisintDummy != None
        RegisterForRemoteEvent(NoDisintDummy, "OnDying")
    endif
EndFunction

string Function EquippedWeaponTag(Actor player)
    if player == None
        return "none"
    endif
    Weapon curW = player.GetEquippedWeapon()
    if curW != None
        int curIdx = FindWeaponIndex(curW)
        if curIdx >= 0
            if curIdx < WeaponTags.Length
                return WeaponTags[curIdx]
            endif
            return "weap_" + curIdx
        endif
    endif
    int wi = 0
    while wi < ShowcaseWeapons.Length
        Weapon w = ShowcaseWeapons[wi]
        if w != None && player.IsEquipped(w)
            if wi < WeaponTags.Length
                return WeaponTags[wi]
            endif
            return "weap_" + wi
        endif
        wi += 1
    endwhile
    return "other"
EndFunction

int Function FindWeaponIndex(Form akForm)
    if akForm == None
        return -1
    endif
    int wi = 0
    while wi < ShowcaseWeapons.Length
        if ShowcaseWeapons[wi] == akForm
            return wi
        endif
        wi += 1
    endwhile
    return -1
EndFunction

int Function FindAmmoIndex(Form akForm)
    if akForm == None
        return -1
    endif
    int ai = 0
    while ai < ShowcaseAmmos.Length
        if ShowcaseAmmos[ai] == akForm
            return ai
        endif
        ai += 1
    endwhile
    return -1
EndFunction

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 10
        GrantAllShowcaseGear()
        LogScorecard("stage_10")
    elseif auiStageID == 15
        CycleNextArsenalWeapon()
    elseif auiStageID == 20
        SpawnOrResetTargets()
        LogScorecard("stage_20")
    elseif auiStageID == 25
        forceCritDisint = !forceCritDisint
        Log("FO4SF_R11P6 force_crit_disint=" + forceCritDisint)
    elseif auiStageID == 30
        LogScorecard("stage_30")
    endif
EndEvent

Function GrantAllShowcaseGear()
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    int wi = 0
    while wi < ShowcaseWeapons.Length
        Weapon w = ShowcaseWeapons[wi]
        if w != None && player.GetItemCount(w) <= 0
            player.AddItem(w, 1, true)
        endif
        wi += 1
    endwhile
    int ai = 0
    while ai < ShowcaseAmmos.Length
        Ammo am = ShowcaseAmmos[ai]
        if am != None
            int want = 50
            if ai < GrantAmmoCounts.Length && GrantAmmoCounts[ai] > 0
                want = GrantAmmoCounts[ai]
            endif
            int cur = player.GetItemCount(am)
            if cur < want
                player.AddItem(am, want - cur, true)
            endif
        endif
        ai += 1
    endwhile
    if StimpakAlch != None && player.GetItemCount(StimpakAlch) < 3
        player.AddItem(StimpakAlch, 3 - player.GetItemCount(StimpakAlch), true)
    endif
    if CapsMisc != None && player.GetItemCount(CapsMisc) < 25
        player.AddItem(CapsMisc, 25 - player.GetItemCount(CapsMisc), true)
    endif
    if BobbyPinMisc != None && player.GetItemCount(BobbyPinMisc) < 5
        player.AddItem(BobbyPinMisc, 5 - player.GetItemCount(BobbyPinMisc), true)
    endif
    Log("FO4SF_R11P6 grant_all complete weapons=" + ShowcaseWeapons.Length)
EndFunction

Function CycleNextArsenalWeapon()
    Actor player = Game.GetPlayer()
    if player == None || ShowcaseWeapons.Length <= 0
        return
    endif
    int curIdx = -1
    Weapon curW = player.GetEquippedWeapon()
    if curW != None
        curIdx = FindWeaponIndex(curW)
    endif
    if curIdx < 0
        int wi = 0
        while wi < ShowcaseWeapons.Length && curIdx < 0
            if ShowcaseWeapons[wi] != None && player.IsEquipped(ShowcaseWeapons[wi])
                curIdx = wi
            endif
            wi += 1
        endwhile
    endif
    int nextIdx = curIdx + 1
    if nextIdx >= ShowcaseWeapons.Length
        nextIdx = 0
    endif
    Weapon nextW = ShowcaseWeapons[nextIdx]
    if nextW != None
        if player.GetItemCount(nextW) <= 0
            player.AddItem(nextW, 1, true)
        endif
        player.EquipItem(nextW, false, true)
        string tag = "weap_" + nextIdx
        if nextIdx < WeaponTags.Length
            tag = WeaponTags[nextIdx]
        endif
        Log("FO4SF_R11P6 equip_cycle idx=" + nextIdx + " tag=" + tag)
    endif
EndFunction

Function ResetRangeActor(Actor target, float hp, string tag, bool hideSuit)
    if target == None
        return
    endif
    target.Enable(false)
    int w = 0
    while w < 20 && !target.Is3DLoaded()
        Utility.Wait(0.1)
        w += 1
    endwhile
    if target.IsDead()
        target.Resurrect()
    endif
    target.MoveToMyEditorLocation()
    target.StopCombat()
    target.RemoveAllItems(None, false)
    if hideSuit && HideSuitAV != None
        target.SetValue(HideSuitAV, 1.0)
    endif
    target.SetRestrained(true)
    if HealthAV != None
        float curHp = target.GetValue(HealthAV)
        if curHp < hp
            target.RestoreValue(HealthAV, hp - curHp)
            curHp = target.GetValue(HealthAV)
        endif
        if curHp > hp
            target.DamageValue(HealthAV, curHp - hp)
        endif
    endif
    bool hasNoDisint = (NoDisintegrateKw != None && target.HasKeyword(NoDisintegrateKw))
    Log("FO4SF_R11P6 target_reset tag=" + tag + " hp=" + hp + " no_disintegrate=" + hasNoDisint)
EndFunction

Function SpawnOrResetTargets()
    if ArmoryCageDoorLocalId != 0 && PortPlugin != ""
        ObjectReference cageDoor = Game.GetFormFromFile(ArmoryCageDoorLocalId, PortPlugin) as ObjectReference
        if cageDoor != None
            cageDoor.SetLockLevel(0)
            cageDoor.Lock(false, false)
            cageDoor.SetOpen(true)
            cageDoor.PlayGamebryoAnimation("Open", false, 0.0)
        endif
    endif
    ResetRangeActor(FleshDummy, 40.0, "flesh", true)
    ResetRangeActor(RobotDummy, 120.0, "robot_metal", false)
    ResetRangeActor(NoDisintDummy, 40.0, "nodisint", true)
    if StoneTarget != None
        StoneTarget.Enable(false)
    endif
    if WoodTarget != None
        WoodTarget.Enable(false)
    endif
EndFunction

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == TargetTrigger
        SetStage(20)
    endif
EndEvent

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if akSender != (player as ObjectReference) || player == None
        return
    endif
    int wi = FindWeaponIndex(akBaseItem)
    if wi >= 0
        weaponsAcquiredCount += 1
        player.EquipItem(akBaseItem, false, false)
        string wtag = "weap_" + wi
        if wi < WeaponTags.Length
            wtag = WeaponTags[wi]
        endif
        Log("FO4SF_R11P6 pickup weapon=" + wtag + " total_pickups=" + weaponsAcquiredCount)
        return
    endif
    int ai = FindAmmoIndex(akBaseItem)
    if ai >= 0
        string atag = "ammo_" + ai
        if ai < AmmoTags.Length
            atag = AmmoTags[ai]
        endif
        Log("FO4SF_R11P6 pickup ammo=" + atag + " count=" + aiItemCount)
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    if akSender != Game.GetPlayer()
        return
    endif
    int wi = FindWeaponIndex(akBaseObject)
    if wi >= 0
        weaponsEquippedCount += 1
        string wtag = "weap_" + wi
        if wi < WeaponTags.Length
            wtag = WeaponTags[wi]
        endif
        lastEquippedTag = wtag
        Log("FO4SF_R11P6 equipped weapon=" + wtag + " equip_events=" + weaponsEquippedCount)
    endif
EndEvent

Event Actor.OnDying(Actor akSender, ObjectReference akKiller)
    Actor player = Game.GetPlayer()
    string eq = EquippedWeaponTag(player)
    bool hasNoDisint = (NoDisintegrateKw != None && akSender != None && akSender.HasKeyword(NoDisintegrateKw))
    string forcedCrit = "none"
    if forceCritDisint && akSender != None && player != None
        bool isLaser = (eq == "lasermusket" || eq == "laserpistol" || eq == "laserrifle")
        bool isPlasma = (eq == "plasmapistol" || eq == "plasmarifle")
        if !hasNoDisint
            if isPlasma && CritPlasmaSpell != None
                CritPlasmaSpell.Cast(player, akSender)
                forcedCrit = "plasma"
            elseif isLaser && CritLaserSpell != None
                CritLaserSpell.Cast(player, akSender)
                forcedCrit = "laser"
            endif
        elseif isPlasma || isLaser
            forcedCrit = "suppressed_nodisint"
        endif
    endif
    if akSender == FleshDummy
        fleshKills += 1
        Log("FO4SF_R11P6 kill target=flesh eq=" + eq + " force_crit=" + forcedCrit + " total=" + fleshKills)
    elseif akSender == RobotDummy
        robotKills += 1
        Log("FO4SF_R11P6 kill target=robot eq=" + eq + " force_crit=" + forcedCrit + " total=" + robotKills)
    elseif akSender == NoDisintDummy
        noDisintKills += 1
        Log("FO4SF_R11P6 kill target=nodisint no_disintegrate=" + hasNoDisint + " eq=" + eq + " force_crit=" + forcedCrit + " total=" + noDisintKills)
    endif
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        StartTimer(1.0, TIMER_POLL)
    endif
EndEvent

Function LogScorecard(string tag)
    Actor player = Game.GetPlayer()
    int ownedWeapons = 0
    if player != None
        int wi = 0
        while wi < ShowcaseWeapons.Length
            if ShowcaseWeapons[wi] != None && player.GetItemCount(ShowcaseWeapons[wi]) > 0
                ownedWeapons += 1
            endif
            wi += 1
        endwhile
    endif
    string eq = EquippedWeaponTag(player)
    Log("FO4SF_R11P6 summary tag=" + tag + " eq=" + eq + " force_crit_disint=" + forceCritDisint + " owned_weapons=" + ownedWeapons + "/" + ShowcaseWeapons.Length + " flesh_kills=" + fleshKills + " robot_kills=" + robotKills + " nodisint_kills=" + noDisintKills)
EndFunction

Function Log(string msg)
    if EnableLog
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, msg)
    endif
EndFunction
