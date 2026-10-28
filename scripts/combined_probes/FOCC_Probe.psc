Scriptname FOCC_Probe Hidden
{Console entry points of the combined core's engine probes (fo4-to-starfield, docs/spikes/combined-core-probes.md).
 The console's cgf runs a global function of a loaded script (FO4SF_Probe.Pos, verified 2026-10-14/15); each function
 here resolves the probe quest FOCC_ProbeQuest (FO4SFCombinedProbe.esm 0x804 = 2052) with Game.GetFormFromFile, the
 pattern of FO4SF_Probe.Resolve and FO4SF_LoadDoor, and calls into it; the answers are the "FOCC rt=<s> <probe> ..."
 lines of the user log "focc" (FOCC_ProbeQuest.psc). A missing quest is logged as "FOCC rt=<s> <probe> refused
 quest=none" (the plugin is not loaded, or the id moved).
   cgf "FOCC_Probe.Hello"                      runtime ids of every probe record
   cgf "FOCC_Probe.P2Set" 37.0                 SetKeywordData on our LCTN + readback      (P2)
   cgf "FOCC_Probe.P2Link"                     AddLinkedLocation + IsLinkedLocation       (P2)
   cgf "FOCC_Probe.P2Read" / "FOCC_Probe.P2LinkRead"   after a relaunch                   (P2)
   cgf "FOCC_Probe.P3Set" 5.0 6.0              datum on the unparented and the chained LCTN (P3)
   cgf "FOCC_Probe.P3Read"                     after a relaunch                           (P3)
   cgf "FOCC_Probe.Where"                      player cell + current location             (P3 cells variant)
   cgf "FOCC_Probe.P4Run" 20 8.0               20 materialize/dissolve cycles, 8 s settle  (P4)
   cgf "FOCC_Probe.P5Tick" 10                  10 timed ticks over the 50 globals          (P5)
   cgf "FOCC_Probe.P6" 1.0 3                   datum 1 on the current location, 3 spawns   (P6)
   cgf "FOCC_Probe.P7" 3.0 3                   reputation tier 3, 3 spawns                 (P7)
   cgf "FOCC_Probe.P8Move" / "FOCC_Probe.P8Stage" 1                                       (P8)
   cgf "FOCC_Probe.P9Dest" 450.0 0.0 / "FOCC_Probe.P9Track" <actor id, signed decimal> 600 (P9)
   cgf "FOCC_P9Drive.Go" <actor id, signed decimal> 0      P9's scripted driver (FOCC_P9Drive.psc, its own compile)
   cgf "FOCC_Probe.P10Send" / "FOCC_Probe.P10State"                                       (P10)
 Form ids typed into cgf are ints: a runtime id FFxxxxxx is typed as the negative decimal Papyrus prints
 (src/fo4sf/combined/probes.py hex2dec).}

FOCC_ProbeQuest Function Q(string probe) global
    {The probe quest, or None (logged as "<probe> refused quest=none"). The log is opened here first: when the plugin
     is not loaded, FOCC_ProbeQuest.OnInit (the only other opener) never ran, and TraceUser to a log that was not
     opened writes nothing (FO4 Creation Kit Debug script docs; Starfield unverified, same Debug API). Reopening an
     open log is harmless per the same docs.}
    Debug.OpenUserLog("focc")
    Quest q = Game.GetFormFromFile(2052, "FO4SFCombinedProbe.esm") as Quest
    FOCC_ProbeQuest pq = q as FOCC_ProbeQuest
    if pq == None
        Debug.TraceUser("focc", "FOCC rt=" + Utility.GetCurrentRealTime() + " " + probe + " refused quest=none")
    endif
    return pq
EndFunction

Function Hello() global
    FOCC_ProbeQuest q = Q("hello")
    if q != None
        q.Hello()
    endif
EndFunction

Function P2Set(float v) global
    FOCC_ProbeQuest q = Q("p2")
    if q != None
        q.P2Set(v)
    endif
EndFunction

Function P2Read() global
    FOCC_ProbeQuest q = Q("p2")
    if q != None
        q.P2Read()
    endif
EndFunction

Function P2Link() global
    FOCC_ProbeQuest q = Q("p2")
    if q != None
        q.P2Link()
    endif
EndFunction

Function P2LinkRead() global
    FOCC_ProbeQuest q = Q("p2")
    if q != None
        q.P2LinkRead()
    endif
EndFunction

Function P3Set(float a, float b) global
    FOCC_ProbeQuest q = Q("p3")
    if q != None
        q.P3Set(a, b)
    endif
EndFunction

Function P3Read() global
    FOCC_ProbeQuest q = Q("p3")
    if q != None
        q.P3Read()
    endif
EndFunction

Function Where() global
    FOCC_ProbeQuest q = Q("where")
    if q != None
        q.Where()
    endif
EndFunction

Function P4Run(int cycles, float settle) global
    FOCC_ProbeQuest q = Q("p4")
    if q != None
        q.P4Run(cycles, settle)
    endif
EndFunction

Function P5Tick(int ticks) global
    FOCC_ProbeQuest q = Q("p5")
    if q != None
        q.P5Tick(ticks)
    endif
EndFunction

Function P6(float datum, int trials) global
    FOCC_ProbeQuest q = Q("p6")
    if q != None
        q.P6(datum, trials)
    endif
EndFunction

Function P7(float tier, int trials) global
    FOCC_ProbeQuest q = Q("p7")
    if q != None
        q.P7(tier, trials)
    endif
EndFunction

Function P8Move() global
    FOCC_ProbeQuest q = Q("p8")
    if q != None
        q.P8Move()
    endif
EndFunction

Function P8Stage(int s) global
    FOCC_ProbeQuest q = Q("p8")
    if q != None
        q.P8Stage(s)
    endif
EndFunction

Function P9Dest(float dx, float dy) global
    FOCC_ProbeQuest q = Q("p9")
    if q != None
        q.P9PlaceDest(dx, dy)
    endif
EndFunction

Function P9Track(int actorId, float seconds) global
    FOCC_ProbeQuest q = Q("p9")
    if q != None
        q.P9Track(actorId, seconds)
    endif
EndFunction

Function P10Send() global
    {Keyword.SendStoryEvent with FO4's signature (akLoc, akRef1, akRef2, aiValue1, aiValue2): whether Starfield's
     Keyword.psc declares it is settled by this script's compile (engine-feasibility.md P10); the Story Manager half
     by the "p10 quest started" line FOCC_P10Quest logs. Called as a statement: the PC compile at 2d53642 refused
     assigning its result to a bool (FOCC_Probe.psc(164,9), type mismatch), so Starfield's return is not a bool.}
    FOCC_ProbeQuest q = Q("p10")
    if q == None
        return
    endif
    Keyword k = q.P10Event
    if k == None
        Debug.TraceUser("focc", "FOCC rt=" + Utility.GetCurrentRealTime() + " p10 refused event=none")
        return
    endif
    k.SendStoryEvent(None, Game.GetPlayer(), None, 0, 0)
    Debug.TraceUser("focc", "FOCC rt=" + Utility.GetCurrentRealTime() + " p10 sent event=" + k.GetFormID())
EndFunction

Function P10State() global
    FOCC_ProbeQuest q = Q("p10")
    if q != None
        q.P10State()
    endif
EndFunction
