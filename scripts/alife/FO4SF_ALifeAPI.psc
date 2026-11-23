Scriptname FO4SF_ALifeAPI Hidden
{Global modder API for the standalone A-Life simulation (FO4SF_ALifeSimQuest, plugin-local quest 0x800). Every
 function takes an optional plugin file name; empty means StarfieldALife.esm. Faction and node arguments are the
 indices of the A-Life config. Console examples:
   cgf "FO4SF_ALifeAPI.Status"
   cgf "FO4SF_ALifeAPI.Enable"  /  cgf "FO4SF_ALifeAPI.Disable"
   cgf "FO4SF_ALifeAPI.Spawn" <faction> <node>
   cgf "FO4SF_ALifeAPI.Raid" <faction> <node>
   cgf "FO4SF_ALifeAPI.Capture" <node> <faction>
   cgf "FO4SF_ALifeAPI.StatusFor" "MyALife.esm"}

; Calls from other mods: FO4SF_ALifeAPI.OrderRaid(1, 7, "MyALife.esm"). Functions return -1 / False / "" when the
; simulation quest is not found (plugin not loaded or renamed), so callers can soft-depend on this mod.

string Function DefaultPlugin() global
    return "StarfieldALife.esm"
EndFunction

FO4SF_ALifeSimQuest Function GetController(string asPlugin = "") global
    string p = asPlugin
    if p == ""
        p = DefaultPlugin()
    endif
    FO4SF_ALifeSimQuest q = Game.GetFormFromFile(2048, p) as FO4SF_ALifeSimQuest
    if q == None
        Debug.Trace("FO4SF_ALifeAPI: no A-Life simulation quest in " + p)
    endif
    return q
EndFunction

bool Function IsRunning(string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    return q != None && q.IsSimRunning()
EndFunction

bool Function SetEnabled(bool abEnabled, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return False
    endif
    q.SetSimEnabled(abEnabled)
    return True
EndFunction

int Function SpawnSquadAtNode(int aiFaction, int aiNode, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.ApiSpawnSquad(aiFaction, aiNode)
EndFunction

int Function OrderRaid(int aiFaction, int aiTargetNode, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.ApiOrderRaid(aiFaction, aiTargetNode)
EndFunction

int Function GetNodeOwner(int aiNode, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetOwnerOfNode(aiNode)
EndFunction

bool Function SetNodeOwner(int aiNode, int aiFaction, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return False
    endif
    return q.SetOwnerOfNode(aiNode, aiFaction)
EndFunction

int Function GetActiveSquadCount(string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetActiveSquads()
EndFunction

int Function GetNodeCount(string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetNodeTotal()
EndFunction

int Function GetFactionCount(string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetFactionTotal()
EndFunction

int Function GetSquadState(int aiSquad, string asPlugin = "") global
    {0 empty, 1 garrisoned, 2 marching_offline, 3 online_3d, 4 in_combat_offline, 5 dead_cooldown; -1 unknown.}
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetSquadStateId(aiSquad)
EndFunction

int Function GetSquadFaction(int aiSquad, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetSquadFactionId(aiSquad)
EndFunction

int Function GetSquadNode(int aiSquad, string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        return -1
    endif
    return q.GetSquadNodeId(aiSquad)
EndFunction

string Function PrintStatusSummary(string asPlugin = "") global
    FO4SF_ALifeSimQuest q = GetController(asPlugin)
    if q == None
        Debug.Notification("A-Life: simulation quest not found")
        return ""
    endif
    string s = q.LogStatus()
    Debug.Notification("A-Life " + s)
    return s
EndFunction

; ---------------------------------------------------------------- console entry points (cgf)

Function Status() global
    PrintStatusSummary("")
EndFunction

Function StatusFor(string asPlugin) global
    PrintStatusSummary(asPlugin)
EndFunction

Function Enable() global
    SetEnabled(True, "")
EndFunction

Function Disable() global
    SetEnabled(False, "")
EndFunction

Function Spawn(int aiFaction, int aiNode) global
    SpawnSquadAtNode(aiFaction, aiNode, "")
EndFunction

Function Raid(int aiFaction, int aiTargetNode) global
    OrderRaid(aiFaction, aiTargetNode, "")
EndFunction

Function Capture(int aiNode, int aiFaction) global
    SetNodeOwner(aiNode, aiFaction, "")
EndFunction
