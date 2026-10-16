Scriptname FO4SF_Probe Hidden
{Console-callable global functions of the bridge (docs/ai/test-queue.md "Bridge"): the console's cgf runs a global
 function of a loaded script, so the runner can ask the game about any reference by form id and read the answer in
 the bridge's user log, with no screenshot and no prid:
   cgf "FO4SF_Probe.Pos" 50338816        -> FO4SF ref=50338816 pos=.. ang=.. cell=.. disabled=.. loaded=.. (decimal form id)
   cgf "FO4SF_Probe.Ack" "walk-leg-3"    -> FO4SF ack walk-leg-3
 Whether the VM loads an unattached script for cgf on this build is a supported hypothesis until the first run
 (Debug.TraceUser through cgf worked on 2026-10-14).}

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
