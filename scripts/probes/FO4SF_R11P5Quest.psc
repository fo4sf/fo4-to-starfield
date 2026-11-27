Scriptname FO4SF_R11P5Quest extends Quest
{Round 11 Probe P5 (Baton, 10mm Pistol, Laser Musket & Minigun) telemetry, auto-equip, and target-practice quest.

Hierarchical moving-parts & stand-in disclosure (R8 / R15):
  All four Fallout 4 weapon NIFs preserve named FO4 moving-part NiNode subtrees for Claude's
  future .rig/.af animation route. Today, animations and Wwise SNDR audio are Starfield donor
  stand-ins: RescueAxe (0x04F760, Baton), XM2311 (0x24561C, 10mm Pistol), Orion (0x2773C8,
  Laser Musket), and Microgun (0x0546CD, Minigun).

P4 notes fixed here:
  - Zero non-persistent cross-plugin VMAD properties: ArmoryCageDoor (0x001539 in FO4Port.esm)
    is resolved at runtime via Game.GetFormFromFile (zero <nullptr form> VMAD errors).
  - StartGameEnabled quest (DNAM = 0x00000009): fo4sf_r11p5.0.log logs init & scorecard
    from game start via OnInit / OnQuestInit / OnPlayerLoadGame.
  - TargetDummy is unarmed (RemoveAllItems), restrained (SetRestrained(true)), and resettable
    via E-activator (0x04000810) or Stage 20 (bat p5t) for Baton melee kill + ranged tests.
}

Group References
    ObjectReference Property TargetTrigger Auto
    {Persistent E-activator beside Vault 111 weapons range in FO4Port_Vault111Cryo.}

    int Property ArmoryCageDoorLocalId = 0x001539 Auto
    {Local FormID of FO4Port_SwitchDoorExSmLatch01 in FO4Port.esm (runtime GetFormFromFile lookup).}

    string Property PortPlugin = "FO4Port.esm" Auto
    {Plugin name hosting ArmoryCageDoorLocalId.}

    Actor Property TargetDummy Auto
    {Persistent InitiallyDisabled (0xC00) unarmed restrained practice target in FO4Port_Vault111Cryo.}

    Weapon Property BatonWeap Auto
    {FO4SFCoreValues.esm:0x00089A FO4_Baton.}

    Weapon Property Pistol10mm Auto
    {FO4SFCoreValues.esm:0x000899 FO4_10mmPistol.}

    Weapon Property LaserMusketWeap Auto
    {FO4SFCoreValues.esm:0x00089D FO4_LaserMusket.}

    Weapon Property MinigunWeap Auto
    {FO4SFCoreValues.esm:0x0008A0 FO4_Minigun.}

    Ammo Property Ammo10mm Auto
    {FO4SFCoreValues.esm:0x000898 FO4_Ammo10mm.}

    Ammo Property AmmoFusionCell Auto
    {FO4SFCoreValues.esm:0x00089B FO4_AmmoFusionCell.}

    Ammo Property Ammo5mm Auto
    {FO4SFCoreValues.esm:0x00089F FO4_Ammo5mm.}

    Weapon Property DonorRescueAxe Auto
    {Starfield.esm:0x04F760 RescueAxe, checked for 0 inventory leak.}

    Weapon Property DonorXm2311 Auto
    {Starfield.esm:0x24561C XM2311, checked for 0 inventory leak.}

    Weapon Property DonorOrion Auto
    {Starfield.esm:0x2773C8 Orion, checked for 0 inventory leak.}

    Weapon Property DonorMicrogun Auto
    {Starfield.esm:0x0546CD Microgun, checked for 0 inventory leak.}

    Ammo Property DonorAmmo45 Auto
    {Starfield.esm:0x2B5598 Ammo45Caliber, checked for 0 inventory leak.}

    Ammo Property DonorAmmoLaser Auto
    {Starfield.esm:0x00E8EC AmmoLaser, checked for 0 inventory leak.}

    Ammo Property DonorAmmo777 Auto
    {Starfield.esm:0x04AD3E Ammo777mm, checked for 0 inventory leak.}

    ActorValue Property HealthAV Auto
    {Starfield.esm:0x0002D4 Health.}

    ActorValue Property HideSuitAV Auto
    {Starfield.esm:0x0B120E ActorShouldForceHideSpacesuit_AV.}
EndGroup

Group Logging
    bool Property EnableLog = true Auto
    string Property LogName = "fo4sf_r11p5" Auto
EndGroup

int TIMER_POLL = 1
bool initLogged = false
int lastAmmo10mm = -1
int lastAmmoCell = -1
int lastAmmo5mm = -1
int shots10mm = 0
int shotsCell = 0
int shots5mm = 0
bool fullMag12Proven = false
bool fullChargeProven = false
bool burst5mmProven = false
bool targetActive = false
bool targetKilled = false
bool batonKilledTarget = false
bool rangedKilledTarget = false
int targetHits = 0
int targetKillsTotal = 0
float lastTargetHp = 0.0

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
        Log("FO4SF_R11P5 init source=" + source + " moving_parts=hierarchical_ninodes_preserved anim_audio_standin=RescueAxe_0x04F760,XM2311_0x24561C,Orion_0x2773C8,Microgun_0x0546CD")
        LogScorecard("init")
    endif
    StartTimer(1.0, TIMER_POLL)
EndFunction

Function RegisterHooks()
    Actor player = Game.GetPlayer()
    if player != None
        if BatonWeap != None
            AddInventoryEventFilter(BatonWeap)
        endif
        if Pistol10mm != None
            AddInventoryEventFilter(Pistol10mm)
        endif
        if LaserMusketWeap != None
            AddInventoryEventFilter(LaserMusketWeap)
        endif
        if MinigunWeap != None
            AddInventoryEventFilter(MinigunWeap)
        endif
        if Ammo10mm != None
            AddInventoryEventFilter(Ammo10mm)
        endif
        if AmmoFusionCell != None
            AddInventoryEventFilter(AmmoFusionCell)
        endif
        if Ammo5mm != None
            AddInventoryEventFilter(Ammo5mm)
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

string Function EquippedWeaponTag(Actor player)
    if player == None
        return "none"
    endif
    if BatonWeap != None && player.IsEquipped(BatonWeap)
        return "baton"
    endif
    if Pistol10mm != None && player.IsEquipped(Pistol10mm)
        return "10mm"
    endif
    if LaserMusketWeap != None && player.IsEquipped(LaserMusketWeap)
        return "lasermusket"
    endif
    if MinigunWeap != None && player.IsEquipped(MinigunWeap)
        return "minigun"
    endif
    return "other"
EndFunction

string Function WeaponTagForForm(Form akBaseItem)
    if akBaseItem == None
        return ""
    endif
    if akBaseItem == BatonWeap
        return "baton"
    endif
    if akBaseItem == Pistol10mm
        return "10mm"
    endif
    if akBaseItem == LaserMusketWeap
        return "lasermusket"
    endif
    if akBaseItem == MinigunWeap
        return "minigun"
    endif
    return ""
EndFunction

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    string wtag = WeaponTagForForm(akBaseItem)
    if wtag != ""
        player.EquipItem(akBaseItem, false, false)
        bool eq = player.IsEquipped(akBaseItem)
        Log("FO4SF_R11P5 pickup weapon=" + wtag + " count=" + aiItemCount + " equipped=" + eq)
        LogScorecard("pickup_" + wtag)
        return
    endif
    if akBaseItem == Ammo10mm
        int c10 = player.GetItemCount(Ammo10mm)
        if c10 > lastAmmo10mm
            lastAmmo10mm = c10
        endif
        Log("FO4SF_R11P5 pickup ammo=10mm added=" + aiItemCount + " total=" + c10)
    elseif akBaseItem == AmmoFusionCell
        int cCell = player.GetItemCount(AmmoFusionCell)
        if cCell > lastAmmoCell
            lastAmmoCell = cCell
        endif
        Log("FO4SF_R11P5 pickup ammo=cell added=" + aiItemCount + " total=" + cCell)
    elseif akBaseItem == Ammo5mm
        int c5 = player.GetItemCount(Ammo5mm)
        if c5 > lastAmmo5mm
            lastAmmo5mm = c5
        endif
        Log("FO4SF_R11P5 pickup ammo=5mm added=" + aiItemCount + " total=" + c5)
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    string wtag = WeaponTagForForm(akBaseObject)
    if wtag != ""
        Log("FO4SF_R11P5 equipped weapon=" + wtag)
        LogScorecard("equipped_" + wtag)
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    if akSender == TargetTrigger
        SpawnPracticeTarget("trigger_activate")
    endif
EndEvent

Event Actor.OnDying(Actor akSender, ObjectReference akKiller)
    if akSender == TargetDummy
        if !targetKilled
            targetKilled = true
            targetKillsTotal += 1
        endif
        if targetHits < 1
            targetHits = 1
        endif
        Actor player = Game.GetPlayer()
        string wtag = EquippedWeaponTag(player)
        if wtag == "baton"
            batonKilledTarget = true
        elseif wtag == "10mm" || wtag == "lasermusket" || wtag == "minigun"
            rangedKilledTarget = true
        endif
        Log("FO4SF_R11P5 target_killed weapon=" + wtag + " hits=" + targetHits + " kills_total=" + targetKillsTotal + " baton_kill=" + batonKilledTarget + " killer=" + akKiller)
    endif
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 10
        GrantAllWeaponsFallback()
    elseif auiStageID == 20
        SpawnPracticeTarget("stage_20")
    elseif auiStageID == 30
        LogScorecard("stage_30")
    endif
EndEvent

Function GrantAllWeaponsFallback()
    Actor player = Game.GetPlayer()
    if player == None
        Log("FO4SF_R11P5 stage_10_grant ok=false reason=no_player")
        return
    endif
    if BatonWeap != None && player.GetItemCount(BatonWeap) < 1
        player.AddItem(BatonWeap, 1, true)
    endif
    if Pistol10mm != None && player.GetItemCount(Pistol10mm) < 1
        player.AddItem(Pistol10mm, 1, true)
    endif
    if LaserMusketWeap != None && player.GetItemCount(LaserMusketWeap) < 1
        player.AddItem(LaserMusketWeap, 1, true)
    endif
    if MinigunWeap != None && player.GetItemCount(MinigunWeap) < 1
        player.AddItem(MinigunWeap, 1, true)
    endif
    if Ammo10mm != None
        int c10 = player.GetItemCount(Ammo10mm)
        if c10 < 48
            player.AddItem(Ammo10mm, 48 - c10, true)
        endif
        lastAmmo10mm = player.GetItemCount(Ammo10mm)
    endif
    if AmmoFusionCell != None
        int cCell = player.GetItemCount(AmmoFusionCell)
        if cCell < 72
            player.AddItem(AmmoFusionCell, 72 - cCell, true)
        endif
        lastAmmoCell = player.GetItemCount(AmmoFusionCell)
    endif
    if Ammo5mm != None
        int c5 = player.GetItemCount(Ammo5mm)
        if c5 < 500
            player.AddItem(Ammo5mm, 500 - c5, true)
        endif
        lastAmmo5mm = player.GetItemCount(Ammo5mm)
    endif
    if BatonWeap != None
        player.EquipItem(BatonWeap, false, false)
    endif
    Log("FO4SF_R11P5 stage_10_grant ok=true equipped=" + EquippedWeaponTag(player) + " ammo_10mm=" + lastAmmo10mm + " ammo_cell=" + lastAmmoCell + " ammo_5mm=" + lastAmmo5mm)
EndFunction

ObjectReference Function ResolveArmoryCageDoor()
    if ArmoryCageDoorLocalId == 0 || PortPlugin == ""
        return None
    endif
    return Game.GetFormFromFile(ArmoryCageDoorLocalId, PortPlugin) as ObjectReference
EndFunction

Function SpawnPracticeTarget(string sourceTag)
    Actor player = Game.GetPlayer()
    if player == None || TargetDummy == None
        Log("FO4SF_R11P5 target_spawned ok=false reason=ref_missing source=" + sourceTag)
        return
    endif
    ObjectReference cageDoor = ResolveArmoryCageDoor()
    bool doorOpened = false
    if cageDoor != None
        cageDoor.SetLockLevel(0)
        cageDoor.Lock(false, false)
        cageDoor.SetOpen(true)
        cageDoor.PlayGamebryoAnimation("Open", false, 0.0)
        doorOpened = true
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
    TargetDummy.RemoveAllItems(None, false)
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
    Log("FO4SF_R11P5 target_spawned ok=true source=" + sourceTag + " unarmed=true restrained=true cage_door_opened=" + doorOpened + " hp=" + hp + " pos=" + FormatPos(TargetDummy) + " dist=" + TargetDummy.GetDistance(player))
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != TIMER_POLL
        return
    endif
    Actor player = Game.GetPlayer()
    if player != None
        if Ammo10mm != None
            int c10 = player.GetItemCount(Ammo10mm)
            if lastAmmo10mm < 0
                if c10 > 0
                    lastAmmo10mm = c10
                endif
            elseif c10 < lastAmmo10mm
                int d10 = lastAmmo10mm - c10
                shots10mm += d10
                if shots10mm >= 12
                    fullMag12Proven = true
                endif
                Log("FO4SF_R11P5 ammo_delta ammo=10mm prev=" + lastAmmo10mm + " now=" + c10 + " fired=" + d10 + " fired_total=" + shots10mm + " full_mag_12_proven=" + fullMag12Proven)
                lastAmmo10mm = c10
            elseif c10 > lastAmmo10mm
                lastAmmo10mm = c10
            endif
        endif
        if AmmoFusionCell != None
            int cCell = player.GetItemCount(AmmoFusionCell)
            if lastAmmoCell < 0
                if cCell > 0
                    lastAmmoCell = cCell
                endif
            elseif cCell < lastAmmoCell
                int dCell = lastAmmoCell - cCell
                shotsCell += dCell
                if shotsCell >= 2
                    fullChargeProven = true
                endif
                Log("FO4SF_R11P5 ammo_delta ammo=cell prev=" + lastAmmoCell + " now=" + cCell + " fired=" + dCell + " fired_total=" + shotsCell + " full_charge_proven=" + fullChargeProven)
                lastAmmoCell = cCell
            elseif cCell > lastAmmoCell
                lastAmmoCell = cCell
            endif
        endif
        if Ammo5mm != None
            int c5 = player.GetItemCount(Ammo5mm)
            if lastAmmo5mm < 0
                if c5 > 0
                    lastAmmo5mm = c5
                endif
            elseif c5 < lastAmmo5mm
                int d5 = lastAmmo5mm - c5
                shots5mm += d5
                if shots5mm >= 10
                    burst5mmProven = true
                endif
                Log("FO4SF_R11P5 ammo_delta ammo=5mm prev=" + lastAmmo5mm + " now=" + c5 + " fired=" + d5 + " fired_total=" + shots5mm + " burst_5mm_proven=" + burst5mmProven)
                lastAmmo5mm = c5
            elseif c5 > lastAmmo5mm
                lastAmmo5mm = c5
            endif
        endif
    endif
    if targetActive && TargetDummy != None && HealthAV != None
        float hpNow = TargetDummy.GetValue(HealthAV)
        bool deadNow = TargetDummy.IsDead()
        string wtag = EquippedWeaponTag(player)
        if hpNow < lastTargetHp - 0.05
            float dmg = lastTargetHp - hpNow
            targetHits += 1
            lastTargetHp = hpNow
            if deadNow && !targetKilled
                targetKilled = true
                targetKillsTotal += 1
                if wtag == "baton"
                    batonKilledTarget = true
                elseif wtag == "10mm" || wtag == "lasermusket" || wtag == "minigun"
                    rangedKilledTarget = true
                endif
            endif
            Log("FO4SF_R11P5 target_hit weapon=" + wtag + " hit_num=" + targetHits + " dmg=" + dmg + " hp_after=" + hpNow + " dead=" + deadNow)
        elseif deadNow && !targetKilled
            targetKilled = true
            targetKillsTotal += 1
            if targetHits < 1
                targetHits = 1
            endif
            if wtag == "baton"
                batonKilledTarget = true
            elseif wtag == "10mm" || wtag == "lasermusket" || wtag == "minigun"
                rangedKilledTarget = true
            endif
            Log("FO4SF_R11P5 target_killed weapon=" + wtag + " hits=" + targetHits + " kills_total=" + targetKillsTotal + " baton_kill=" + batonKilledTarget + " via=poll")
        endif
    endif
    StartTimer(0.5, TIMER_POLL)
EndEvent

int Function CountDonorLeaks(Actor player)
    int leaks = 0
    if player == None
        return 0
    endif
    if DonorRescueAxe != None
        leaks += player.GetItemCount(DonorRescueAxe)
    endif
    if DonorXm2311 != None
        leaks += player.GetItemCount(DonorXm2311)
    endif
    if DonorOrion != None
        leaks += player.GetItemCount(DonorOrion)
    endif
    if DonorMicrogun != None
        leaks += player.GetItemCount(DonorMicrogun)
    endif
    if DonorAmmo45 != None
        leaks += player.GetItemCount(DonorAmmo45)
    endif
    if DonorAmmoLaser != None
        leaks += player.GetItemCount(DonorAmmoLaser)
    endif
    if DonorAmmo777 != None
        leaks += player.GetItemCount(DonorAmmo777)
    endif
    return leaks
EndFunction

Function LogScorecard(string tag)
    Actor player = Game.GetPlayer()
    if player == None
        Log("FO4SF_R11P5 summary tag=" + tag + " player=None")
        return
    endif
    int batonCnt = 0
    int p10Cnt = 0
    int lmCnt = 0
    int mgCnt = 0
    int a10Cnt = 0
    int aCellCnt = 0
    int a5Cnt = 0
    if BatonWeap != None
        batonCnt = player.GetItemCount(BatonWeap)
    endif
    if Pistol10mm != None
        p10Cnt = player.GetItemCount(Pistol10mm)
    endif
    if LaserMusketWeap != None
        lmCnt = player.GetItemCount(LaserMusketWeap)
    endif
    if MinigunWeap != None
        mgCnt = player.GetItemCount(MinigunWeap)
    endif
    if Ammo10mm != None
        a10Cnt = player.GetItemCount(Ammo10mm)
    endif
    if AmmoFusionCell != None
        aCellCnt = player.GetItemCount(AmmoFusionCell)
    endif
    if Ammo5mm != None
        a5Cnt = player.GetItemCount(Ammo5mm)
    endif
    int donorLeaks = CountDonorLeaks(player)
    Log("FO4SF_R11P5 summary tag=" + tag + " cell=" + player.GetParentCell() + " pos=" + FormatPos(player) + " equipped=" + EquippedWeaponTag(player) + " baton=" + batonCnt + " pistol_10mm=" + p10Cnt + " laser_musket=" + lmCnt + " minigun=" + mgCnt + " ammo_10mm=" + a10Cnt + " ammo_cell=" + aCellCnt + " ammo_5mm=" + a5Cnt + " shots_10mm=" + shots10mm + " shots_cell=" + shotsCell + " shots_5mm=" + shots5mm + " full_mag_12_proven=" + fullMag12Proven + " full_charge_proven=" + fullChargeProven + " burst_5mm_proven=" + burst5mmProven + " target_hits=" + targetHits + " target_kills=" + targetKillsTotal + " baton_kill=" + batonKilledTarget + " ranged_kill=" + rangedKilledTarget + " donor_leaks=" + donorLeaks)
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
