Scriptname FO4SF_Bridge extends Quest
{The runner's observation bridge (fo4-to-starfield, docs/ai/test-queue.md "Bridge"): every Interval seconds one line
 to the user log "fo4sf" (My Games\Starfield\Logs\Script\User\fo4sf.0.log) with the real-time clock, the player's
 position and heading, parent cell and worldspace form ids (decimal) and whether the player's 3D is loaded; a change
 of the global FO4SF_Cmd (set from the console: "set FO4SF_Cmd to 7") is echoed on the next line as cmd=7, so a
 console command is acknowledged by the game itself instead of by a screenshot.}

GlobalVariable Property FO4SF_Cmd Auto Const Mandatory
{Set from the console; its value is echoed once when it changes.}

float Property Interval = 0.5 Auto Const
{Seconds between lines.}

int lastCmd = -1
int lines = 0

Event OnInit()
    Debug.OpenUserLog("fo4sf")
    Debug.TraceUser("fo4sf", "FO4SF init rt=" + Utility.GetCurrentRealTime())
    StartTimer(Interval, 1)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 1
        return
    endif
    Actor p = Game.GetPlayer()
    string line = "FO4SF rt=" + Utility.GetCurrentRealTime()
    line += " pos=" + p.GetPositionX() + " " + p.GetPositionY() + " " + p.GetPositionZ()
    line += " ang=" + p.GetAngleZ()
    Cell c = p.GetParentCell()
    if c
        line += " cell=" + c.GetFormID()
    else
        line += " cell=none"
    endif
    WorldSpace w = p.GetWorldSpace()
    if w
        line += " world=" + w.GetFormID()
    else
        line += " world=none"
    endif
    line += " loaded=" + p.Is3DLoaded()
    int cmd = FO4SF_Cmd.GetValueInt()
    if cmd != lastCmd
        lastCmd = cmd
        line += " cmd=" + cmd
    endif
    lines += 1
    line += " n=" + lines
    Debug.TraceUser("fo4sf", line)
    StartTimer(Interval, 1)
EndEvent
