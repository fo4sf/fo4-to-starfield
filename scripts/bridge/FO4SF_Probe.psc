Scriptname FO4SF_Probe Hidden
{Console-callable global functions of the bridge (docs/ai/test-queue.md "Bridge"): the console's cgf runs a global
 function of a loaded script, so the runner can ask the game about any reference by form id and read the answer in
 the bridge's user log, with no screenshot and no prid:
   cgf "FO4SF_Probe.Pos" 50338816        -> FO4SF ref=50338816 pos=.. ang=.. cell=.. disabled=.. loaded=.. (decimal form id)
   cgf "FO4SF_Probe.Ack" "walk-leg-3"    -> FO4SF ack walk-leg-3
   cgf "FO4SF_Probe.Resolve" "FO4TerrainCore.esm" 2048
       -> FO4SF resolve plugin=FO4TerrainCore.esm id=2048 form=<runtime id>|none [ref=true|false pos=.. ang=.. cell=..
          cellname=.. world=.. worldname=.. disabled=.. loaded=..]
   cgf "FO4SF_Probe.MoveTo" "FO4TerrainCore.esm" 2048 -1200.0 -2700.0 0.0
       -> FO4SF target ... (MoveTo's own lookup, as resolve), then FO4SF moveto plugin=.. id=.. offset=dx dy dz
          phase=before|after|settled pos=.. ang=.. cell=.. cellname=.. world=.. worldname=.. loaded=..
          (phase=refused when the lookup gave no reference)
 Pos and Ack were verified in game (2026-10-14/15). Resolve and MoveTo (2026-10-16, the scripted door's Step 0) take the
 plugin's file name and the PLUGIN-LOCAL form id, the contract of scripts/door_bridge/FO4SF_LoadDoor.psc, and MoveTo
 makes that script's call (match rotation, no rotated offset); whether Starfield resolves a plugin-local id this way,
 and where the player lands, is what their first run shows. cellname / worldname come from GetFormEditorID, a
 DebugOnly native: empty where the game keeps no editor id; it is asked last, so the ids are never lost to it.}

Function Ack(string tag) global
    Debug.TraceUser("fo4sf", "FO4SF ack " + tag)
EndFunction

Function Pos(int formId) global
    Form f = Game.GetForm(formId)
    ObjectReference r = f as ObjectReference
    if r == None
        Debug.TraceUser("fo4sf", "FO4SF ref=" + formId + " none")
        return
    endif
    string line = "FO4SF ref=" + formId + " pos=" + r.GetPositionX() + " " + r.GetPositionY() + " " + r.GetPositionZ()
    line += " ang=" + r.GetAngleZ()
    Cell c = r.GetParentCell()
    if c
        line += " cell=" + c.GetFormID()
    else
        line += " cell=none"
    endif
    line += " disabled=" + r.IsDisabled() + " loaded=" + r.Is3DLoaded()
    Debug.TraceUser("fo4sf", line)
EndFunction

Function Player() global
    Actor p = Game.GetPlayer()
    Debug.TraceUser("fo4sf", "FO4SF player pos=" + p.GetPositionX() + " " + p.GetPositionY() + " " + p.GetPositionZ() + " ang=" + p.GetAngleZ())
EndFunction

string Function EditorId(Form f) global
    {The form's editor id, "" for none (GetFormEditorID is DebugOnly: its own function, so a failure there only empties the name).}
    if f == None
        return ""
    endif
    return f.GetFormEditorID()
EndFunction

string Function Where(ObjectReference r) global
    {" pos=x y z ang=deg cell=<id>|none cellname=<editor id> world=<id>|none worldname=<editor id>" (ids decimal, as Pos prints them).}
    string s = " pos=" + r.GetPositionX() + " " + r.GetPositionY() + " " + r.GetPositionZ() + " ang=" + r.GetAngleZ()
    Cell c = r.GetParentCell()
    if c
        s += " cell=" + c.GetFormID()
    else
        s += " cell=none"
    endif
    WorldSpace w = r.GetWorldSpace()
    string ws = " world=none"
    if w
        ws = " world=" + w.GetFormID()
    endif
    return s + " cellname=" + EditorId(c) + ws + " worldname=" + EditorId(w)
EndFunction

ObjectReference Function Lookup(string kind, string plugin, int id) global
    {Game.GetFormFromFile(id, plugin) logged as one line "FO4SF <kind> plugin=.. id=.. form=<runtime id>|none ...";
     returns the reference, or None (no form, or a form that is not a reference).}
    Form f = Game.GetFormFromFile(id, plugin)
    string line = "FO4SF " + kind + " plugin=" + plugin + " id=" + id
    if f == None
        Debug.TraceUser("fo4sf", line + " form=none")
        return None
    endif
    line += " form=" + f.GetFormID()
    ObjectReference r = f as ObjectReference
    if r == None
        Debug.TraceUser("fo4sf", line + " ref=false")
        return None
    endif
    line += " ref=true" + Where(r) + " disabled=" + r.IsDisabled() + " loaded=" + r.Is3DLoaded()
    Debug.TraceUser("fo4sf", line)
    return r
EndFunction

Function Resolve(string plugin, int id) global
    {Does this plugin-local form id resolve to a reference now, and where is it? (the scripted door's destination lookup)}
    Lookup("resolve", plugin, id)
EndFunction

Function MoveTo(string plugin, int id, float dx, float dy, float dz) global
    {The player to that reference plus (dx, dy, dz), matching its rotation, as FO4SF_LoadDoor moves the player; the
     player's position, cell and worldspace before, right after MoveTo returns, and after one second of game time.}
    ObjectReference target = Lookup("target", plugin, id)
    string tag = "FO4SF moveto plugin=" + plugin + " id=" + id + " offset=" + dx + " " + dy + " " + dz
    if target == None
        Debug.TraceUser("fo4sf", tag + " phase=refused")
        return
    endif
    Actor p = Game.GetPlayer()
    Debug.TraceUser("fo4sf", tag + " phase=before" + Where(p) + " loaded=" + p.Is3DLoaded())
    p.MoveTo(target, dx, dy, dz, True, False)
    Debug.TraceUser("fo4sf", tag + " phase=after" + Where(p) + " loaded=" + p.Is3DLoaded())
    Utility.Wait(1.0)
    Debug.TraceUser("fo4sf", tag + " phase=settled" + Where(p) + " loaded=" + p.Is3DLoaded())
EndFunction
