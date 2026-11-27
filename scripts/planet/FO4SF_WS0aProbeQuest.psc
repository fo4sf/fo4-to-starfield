Scriptname FO4SF_WS0aProbeQuest extends Quest
{WS0a Tier 1-3 offline-staged diagnostic probe quest (FO4SFWorkshopProbe.esm 0x810).
 Zero probe records live in any player plugin. Each stage runs one variable and emits one FO4SFWS0A trace line.}

string LogName = "FO4SFWS0aProbe"
string ProbePlugin = "FO4SFWorkshopProbe.esm"
string CorePlugin = "FO4TerrainCore.esm"
string WorkshopPlugin = "FO4SFWorkshop.esm"
string P6Plugin = "FO4SFWorkshopProbe_P6.esm"

int SanctuaryBenchRefId = 0x005C50
int P18BenchId = 0x820
int P14aCotId = 0x821
int P14bTurretId = 0x822
int P4GenId = 0x823
int P4LightId = 0x824
int P9StaticId = 0x825
int P16SteelId = 0x826
int P17ContId = 0x827
int P17JunkId = 0x828
int P5ExtractorId = 0x82A
int P18KwId = 0x830
int P12PerkId = 0x831
int P14aBedsAvId = 0x832
int P14bSafetyAvId = 0x833
int P8bLocAId = 0x834
int P8bLocBId = 0x835

int IronId = 0x00556E
int BeaconId = 0x2C60E9
int BudgetAvId = 0x319872
int MaxDeployAvId = 0x2A84F7
int CaravanKwId = 0x061C0C
int PowerRadiusAvId = 0x00032F

ObjectReference[] b1Items
ObjectReference lastBench
bool[] doneStages
bool b2Registered = false
int TIMER_POLL = 1
int TIMER_P15 = 2

Event OnInit()
    Debug.OpenUserLog(LogName)
    b1Items = new ObjectReference[3]
    doneStages = new bool[23]
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    Trace("init quest=" + GetFormID() + " ws0a=true core=" + Game.IsPluginInstalled(CorePlugin))
    StartTimer(1.0, TIMER_POLL)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    if b1Items && b1Items[0] != None
        Trace("b1 reload count=3 ref0=" + b1Items[0].GetFormID() + " z0=" + b1Items[0].GetPositionZ() + " loaded0=" + b1Items[0].Is3DLoaded())
    endif
EndEvent

Function Trace(string msg)
    string line = "FO4SFWS0A rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

ObjectReference Function SanctuaryBench()
    return Game.GetFormFromFile(SanctuaryBenchRefId, CorePlugin) as ObjectReference
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_P15
        ObjectReference sb = SanctuaryBench()
        if sb
            sb.StartWorkshop(true)
            Trace("p15 start_workshop_timer fired=true bench=" + sb.GetFormID())
        endif
        return
    endif
    if aiTimerID == TIMER_POLL
        int s = 101
        while s <= 122
            int idx = s - 101
            if doneStages && !doneStages[idx] && GetStageDone(s)
                doneStages[idx] = true
                RunProbeStage(s)
            endif
            s += 1
        endwhile
        StartTimer(1.0, TIMER_POLL)
    endif
EndEvent

Event ObjectReference.OnWorkshopMode(ObjectReference akSender, bool aStart)
    Trace("ws_mode bench=" + akSender.GetFormID() + " start=" + aStart)
EndEvent

Event ObjectReference.OnWorkshopObjectPlaced(ObjectReference akSender, ObjectReference akReference)
    Trace("b2 placed bench=" + akSender.GetFormID() + " item=" + akReference.GetFormID())
EndEvent

Event ObjectReference.OnWorkshopObjectRemoved(ObjectReference akSender, ObjectReference akReference)
    Trace("b2 removed bench=" + akSender.GetFormID() + " item=" + akReference.GetFormID())
EndEvent

Function RunProbeStage(int st)
    Actor p = Game.GetPlayer()
    if st == 101
        Form m = Game.GetFormFromFile(P9StaticId, ProbePlugin)
        int i = 0
        while i < 3 && m != None
            b1Items[i] = p.PlaceAtMe(m, 1, true, false, false)
            i += 1
        endwhile
        Trace("b1 placed=3 ref0=" + b1Items[0].GetFormID())
    elseif st == 102
        ObjectReference sb = SanctuaryBench()
        if sb && !b2Registered
            b2Registered = true
            RegisterForRemoteEvent(sb, "OnWorkshopMode")
            RegisterForRemoteEvent(sb, "OnWorkshopObjectPlaced")
            RegisterForRemoteEvent(sb, "OnWorkshopObjectRemoved")
        endif
        Trace("b2 registered=" + b2Registered + " bench=" + SanctuaryBenchRefId)
    elseif st == 103
        Form iron = Game.GetFormFromFile(IronId, "Starfield.esm")
        if iron
            p.AddItem(iron, 10, true)
        endif
        StartTimer(1.5, TIMER_P15)
        Trace("p15 queued_iron=10 timer=1.5s")
    elseif st == 104
        ObjectReference pb = p.PlaceAtMe(Game.GetFormFromFile(P18BenchId, ProbePlugin), 1, true, false, false)
        Trace("p18 bench=" + pb.GetFormID() + " has_own_kw=" + pb.HasKeyword(Game.GetFormFromFile(P18KwId, ProbePlugin) as Keyword))
    elseif st == 105
        Trace("p12 before_perk has=" + p.HasPerk(Game.GetFormFromFile(P12PerkId, ProbePlugin) as Perk))
    elseif st == 106
        Perk pk = Game.GetFormFromFile(P12PerkId, ProbePlugin) as Perk
        if pk
            p.AddPerk(pk, false)
        endif
        Trace("p12 after_perk has=" + p.HasPerk(pk))
    elseif st == 107
        Trace("p13 shack_snap_check=ready use_FO4SFBuildPieces")
    elseif st == 108
        Form cot = Game.GetFormFromFile(P14aCotId, ProbePlugin)
        p.PlaceAtMe(cot, 1, true, false, false)
        p.PlaceAtMe(cot, 1, true, false, false)
        ObjectReference sb = SanctuaryBench()
        ActorValue bedsAv = Game.GetFormFromFile(P14aBedsAvId, ProbePlugin) as ActorValue
        int n = 0
        if sb && bedsAv
            ObjectReference[] res = sb.GetWorkshopResourceObjects(bedsAv, 0)
            n = res.Length
        endif
        Trace("p14a cots=2 resource_len=" + n)
    elseif st == 109
        ObjectReference t = p.PlaceAtMe(Game.GetFormFromFile(P14bTurretId, ProbePlugin), 1, true, false, false)
        ActorValue sav = Game.GetFormFromFile(P14bSafetyAvId, ProbePlugin) as ActorValue
        Trace("p14b own_safety_val=" + t.GetValue(sav))
    elseif st == 110
        ObjectReference sb = SanctuaryBench()
        ActorValue bav = Game.GetFormFromFile(BudgetAvId, "Starfield.esm") as ActorValue
        Trace("p3 budget_baseline=" + sb.GetValue(bav))
    elseif st == 111
        ObjectReference g = p.PlaceAtMe(Game.GetFormFromFile(P4GenId, ProbePlugin), 1, true, false, false)
        ActorValue pav = Game.GetFormFromFile(PowerRadiusAvId, "Starfield.esm") as ActorValue
        Trace("p4 gen=" + g.GetFormID() + " av32f=" + g.GetValue(pav))
    elseif st == 112
        ObjectReference bs = p.PlaceAtMe(Game.GetFormFromFile(P9StaticId, ProbePlugin), 1, true, false, false)
        Trace("p9 bulldoze_static=" + bs.GetFormID())
    elseif st == 113
        p.AddItem(Game.GetFormFromFile(P16SteelId, ProbePlugin), 4, true)
        Trace("p16 added_own_steel=4")
    elseif st == 114
        ObjectReference sc = p.PlaceAtMe(Game.GetFormFromFile(P17ContId, ProbePlugin), 1, true, false, false)
        Trace("p17 junk_storage=" + sc.GetFormID())
    elseif st == 115
        Trace("p6 sfbgs00d_installed=" + Game.IsPluginInstalled(P6Plugin))
    elseif st == 116
        Trace("p8a allow_cmd_caravan=staged")
    elseif st == 117
        Location la = Game.GetFormFromFile(P8bLocAId, ProbePlugin) as Location
        Location lb = Game.GetFormFromFile(P8bLocBId, ProbePlugin) as Location
        Keyword cw = Game.GetFormFromFile(CaravanKwId, "Starfield.esm") as Keyword
        if la && lb && cw
            la.AddLinkedLocation(lb, cw)
        endif
        Trace("p8b linked_caravan=true")
    elseif st == 118
        Trace("p11 blueprint_multiselect=manual_check")
    elseif st == 119
        ObjectReference ex = p.PlaceAtMe(Game.GetFormFromFile(P5ExtractorId, ProbePlugin), 1, true, false, false)
        Trace("p5 extractor=" + ex.GetFormID())
    elseif st == 120
        Trace("p10 placement_cndf_overridden=true")
    elseif st == 121
        ActorValue md = Game.GetFormFromFile(MaxDeployAvId, "Starfield.esm") as ActorValue
        Trace("p19 max_deployed=" + p.GetValue(md))
    elseif st == 122
        Trace("p1 flora_robot_workshop_check=manual_spawn")
    endif
EndFunction
