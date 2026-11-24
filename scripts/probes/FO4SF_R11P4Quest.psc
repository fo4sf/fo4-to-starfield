Scriptname FO4SF_R11P4Quest extends Quest
{Round 11 Probe P4 (Part 1 - 10mm Pistol ALONE) telemetry and target-practice quest.

Rigid-parts & stand-in disclosure:
  Welded moving parts (10mm pistol slide/bolt, hammer, trigger, mag release, and detachable
  magazine) are rigid and do not move; firing/reload animations and Wwise SNDR audio are
  Starfield XM2311 (0x24561C) stand-ins.

Stages & in-world triggers:
  - Natural Vault 111 Overseer desk pickup (0x0820 + 0x0821) OR Stage 10 (bat p4g):
    equips FO4_10mmPistol into hand and verifies 0 XM2311 / .45 Caliber stand-in leaks.
  - Press E on 10mm Target Practice activator (0x04000810) OR Stage 20 (bat p4t):
    unlocks & opens Vault 111 armory cage gate (0x01001539) and enables InitiallyDisabled
    TargetDummy (0x04000811) at (-48.80, 30.00, 0.15) with 30 HP for 2-shot hit & kill check.
  - Stage 30 (bat p4s): writes complete Probe P4 scorecard snapshot to fo4sf_r11p4.0.log.
}

Group References
    ObjectReference Property TargetTrigger Auto
    {Persistent activator beside Overseer desk in FO4Port_Vault111Cryo.}

    string Property PortPlugin = "FO4Port.esm" Auto
    {Plugin owning Vault 111 armory cage door (resolved via Game.GetFormFromFile, zero nullptr VMAD ref).}

    int Property ArmoryCageDoorLocalId = 0 Auto
    {Local FormID (0x001539 via VMAD) of Vault 111 armory cage latch door in PortPlugin.}

    Actor Property TargetDummy Auto
    {Persistent InitiallyDisabled (0xC00) practice target in FO4Port_Vault111Cryo.}

    Weapon Property Pistol10mm Auto
    {FO4SFCoreValues.esm:0x000899 FO4_10mmPistol.}

    Ammo Property Ammo10mm Auto
    {FO4SFCoreValues.esm:0x000898 FO4_Ammo10mm.}

    Weapon Property DonorXm2311 Auto
    {Starfield.esm:0x24561C XM2311, checked for 0 inventory leak.}

    Ammo Property DonorAmmo45 Auto
    {Starfield.esm:0x2B5598 Ammo45Caliber, checked for 0 inventory leak.}

    ActorValue Property HealthAV Auto
    {Starfield.esm:0x0002D4 Health.}

    ActorValue Property HideSuitAV Auto
    {Starfield.esm:0x0B120E ActorShouldForceHideSpacesuit_AV.}
EndGroup

Group Logging
    bool Property EnableLog = true Auto
    string Property LogName = "fo4sf_r11p4" Auto
EndGroup

bool started = false
int TIMER_POLL = 1
int lastAmmoCount = -1
int shotsFiredTotal = 0
bool fullMag12Proven = false
bool targetActive = false
bool targetKilled = false
int targetHits = 0
float lastTargetHp = 0.0

Event OnInit()
    EnsureStarted("on_init")
EndEvent

Event OnQuestInit()
    EnsureStarted("quest_init")
EndEvent

Event OnQuestStarted()
    EnsureStarted("quest_started")
EndEvent

Function EnsureStarted(string sourceTag)
    RegisterHooks()
    if !started
        started = true
        Log("FO4SF_R11P4 init rigid_parts=slide_bolt_hammer_trigger_and_mag_do_not_move anim_audio_standin=XM2311_0x24561C")
        LogScorecard("init")
    else
        LogScorecard(sourceTag)
    endif
    StartTimer(1.0, TIMER_POLL)
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    RegisterHooks()
    LogScorecard("load_game")
    StartTimer(1.0, TIMER_POLL)
EndEvent

Function RegisterHooks()
    Actor player = Game.GetPlayer()
    if player != None
        if Pistol10mm != None
            AddInventoryEventFilter(Pistol10mm)
        endif
        if Ammo10mm != None
            AddInventoryEventFilter(Ammo10mm)
        endif
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")
        RegisterForRemoteEvent(player, "OnItemEquipped")
    endif
    if TargetTrigger != None
        RegisterForRemoteEvent(TargetTrigger, "OnActivate")
    endif
    if TargetDummy != None
        RegisterForRemoteEvent(TargetDummy, "OnDying")
    endif
EndFunction

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    if akBaseItem == Pistol10mm || akBaseItem == Ammo10mm
        Actor player = Game.GetPlayer()
        if player != None && Ammo10mm != None
            int curAmmo = player.GetItemCount(Ammo10mm)
            if curAmmo > lastAmmoCount
                lastAmmoCount = curAmmo
            endif
        endif
        LogScorecard("item_added")
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    if akBaseObject == Pistol10mm
        Actor player = Game.GetPlayer()
        if player != None && Ammo10mm != None && lastAmmoCount < 0
            lastAmmoCount = player.GetItemCount(Ammo10mm)
        endif
        LogScorecard("pistol_equipped")
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == TargetTrigger
        SpawnPracticeTarget("trigger_activate")
    endif
EndEvent

Event Actor.OnDying(Actor akSender, ObjectReference akKiller)
    if akSender == TargetDummy
        targetKilled = true
        if targetHits < 1
            targetHits = 1
        endif
        Actor player = Game.GetPlayer()
        bool eq = false
        if player != None && Pistol10mm != None
            eq = player.IsEquipped(Pistol10mm)
        endif
        Log("FO4SF_R11P4 target_killed hits=" + targetHits + " killer=" + akKiller + " pistol_equipped=" + eq)
    endif
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 10
        GrantAndEquipFallback()
    elseif auiStageID == 20
        SpawnPracticeTarget("stage_20")
    elseif auiStageID == 30
        LogScorecard("stage_30")
    endif
EndEvent

Function GrantAndEquipFallback()
    Actor player = Game.GetPlayer()
    if player == None || Pistol10mm == None || Ammo10mm == None
        Log("FO4SF_R11P4 stage_10_equip ok=false reason=missing_refs")
        return
    endif
    if player.GetItemCount(Pistol10mm) < 1
        player.AddItem(Pistol10mm, 1, true)
    endif
    int curAmmo = player.GetItemCount(Ammo10mm)
    if curAmmo < 48
        player.AddItem(Ammo10mm, 48 - curAmmo, true)
    endif
    player.EquipItem(Pistol10mm, false, false)
    lastAmmoCount = player.GetItemCount(Ammo10mm)
    Log("FO4SF_R11P4 stage_10_equip ok=true equipped=" + player.IsEquipped(Pistol10mm) + " ammo_10mm=" + lastAmmoCount)
EndFunction

Function SpawnPracticeTarget(string sourceTag)
    Actor player = Game.GetPlayer()
    if player == None || TargetDummy == None
        Log("FO4SF_R11P4 target_spawned ok=false reason=ref_missing source=" + sourceTag)
        return
    endif
    ObjectReference cageDoor = None
    if PortPlugin != "" && ArmoryCageDoorLocalId > 0
        cageDoor = Game.GetFormFromFile(ArmoryCageDoorLocalId, PortPlugin) as ObjectReference
    endif
    if cageDoor != None
        cageDoor.SetLockLevel(0)
        cageDoor.Lock(false, false)
        cageDoor.SetOpen(true)
        cageDoor.PlayGamebryoAnimation("Open", false, 0.0)
    endif
    TargetDummy.Enable(false)
    int w = 0
    while w < 20 && !TargetDummy.Is3DLoaded()
        Utility.Wait(0.1)
        w += 1
    endwhile
    if TargetDummy.IsDead()
        TargetDummy.Resurrect()
    endif
    TargetDummy.RemoveAllItems(None, false, true)
    if HideSuitAV != None
        TargetDummy.SetValue(HideSuitAV, 1.0)
    endif
    TargetDummy.SetRestrained(true)
    TargetDummy.SetPosition(-48.80, 30.00, 0.15)
    TargetDummy.SetAngle(0.0, 0.0, 270.0)
    float hp = 30.0
    if HealthAV != None
        float curHp = TargetDummy.GetValue(HealthAV)
        if curHp < 30.0
            TargetDummy.RestoreValue(HealthAV, 30.0 - curHp)
            curHp = TargetDummy.GetValue(HealthAV)
        endif
        if curHp > 30.0
            TargetDummy.DamageValue(HealthAV, curHp - 30.0)
        endif
        hp = TargetDummy.GetValue(HealthAV)
    endif
    lastTargetHp = hp
    targetHits = 0
    targetKilled = false
    targetActive = true
    Log("FO4SF_R11P4 target_spawned ok=true source=" + sourceTag + " hp=" + hp + " pos=" + FormatPos(TargetDummy) + " dist=" + TargetDummy.GetDistance(player))
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_POLL
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None && Pistol10mm != None && Ammo10mm != None
        int curAmmo = player.GetItemCount(Ammo10mm)
        if lastAmmoCount < 0
            if curAmmo > 0
                lastAmmoCount = curAmmo
            endif
        elseif curAmmo < lastAmmoCount
            int delta = lastAmmoCount - curAmmo
            shotsFiredTotal += delta
            if shotsFiredTotal >= 12
                fullMag12Proven = true
            endif
            Log("FO4SF_R11P4 ammo_delta prev=" + lastAmmoCount + " now=" + curAmmo + " fired=" + delta + " fired_total=" + shotsFiredTotal + " full_mag_12_proven=" + fullMag12Proven)
            lastAmmoCount = curAmmo
        elseif curAmmo > lastAmmoCount
            lastAmmoCount = curAmmo
        endif
    endif
    if targetActive && TargetDummy != None && HealthAV != None
        float hpNow = TargetDummy.GetValue(HealthAV)
        bool deadNow = TargetDummy.IsDead()
        if hpNow < lastTargetHp - 0.05
            float dmg = lastTargetHp - hpNow
            targetHits += 1
            lastTargetHp = hpNow
            if deadNow
                targetKilled = true
            endif
            Log("FO4SF_R11P4 target_hit hit_num=" + targetHits + " dmg=" + dmg + " hp_after=" + hpNow + " dead=" + deadNow)
        elseif deadNow && !targetKilled
            targetKilled = true
            if targetHits < 1
                targetHits = 1
            endif
            Log("FO4SF_R11P4 target_killed hits=" + targetHits + " hp_after=" + hpNow + " via=poll")
        endif
    endif
    StartTimer(0.5, TIMER_POLL)
EndEvent

Function LogScorecard(string tag)
    Actor player = Game.GetPlayer()
    if player == None
        Log("FO4SF_R11P4 summary tag=" + tag + " player=None")
        return
    endif
    int pCnt = 0
    int aCnt = 0
    int xCnt = 0
    int c45Cnt = 0
    bool eq = false
    if Pistol10mm != None
        pCnt = player.GetItemCount(Pistol10mm)
        eq = player.IsEquipped(Pistol10mm)
    endif
    if Ammo10mm != None
        aCnt = player.GetItemCount(Ammo10mm)
    endif
    if DonorXm2311 != None
        xCnt = player.GetItemCount(DonorXm2311)
    endif
    if DonorAmmo45 != None
        c45Cnt = player.GetItemCount(DonorAmmo45)
    endif
    Log("FO4SF_R11P4 summary tag=" + tag + " cell=" + player.GetParentCell() + " pos=" + FormatPos(player) + " equipped=" + eq + " pistol_10mm=" + pCnt + " ammo_10mm=" + aCnt + " fired_total=" + shotsFiredTotal + " full_mag_12_proven=" + fullMag12Proven + " target_hits=" + targetHits + " target_killed=" + targetKilled + " xm2311_leak=" + xCnt + " cal45_leak=" + c45Cnt + " rigid_parts=non_moving_slide_and_mag")
EndFunction

string Function FormatPos(ObjectReference r)
    return r.GetPositionX() + " " + r.GetPositionY() + " " + r.GetPositionZ()
EndFunction

Function Log(string msg)
    if !EnableLog
        return
    endif
    Debug.OpenUserLog(LogName)
    Debug.TraceUser(LogName, msg)
EndFunction
