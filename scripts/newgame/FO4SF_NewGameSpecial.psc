Scriptname FO4SF_NewGameSpecial extends Quest
{Optional third script on FO4SF_NewGame (docs/newgame/vault111-start.md section 4a): SPECIAL at a vault terminal (NG-5
 / NG-C4, the owner's decision 2026-10-19: at the terminal for testing, the elevator version with the remade start).
 Once the looks are done (stage 20) and the player stands at the terminal, TerminalMessage asks "Set SPECIAL" or
 "Later"; Set runs the allocation on SpecialMessage: Fallout 4's numbers, SpecialBase in each stat, SpecialPoints to
 spend, SpecialMax at most per stat; one button per stat adds a point, Reset starts over, Confirm (all points spent)
 writes the seven actor values (our own AVIF, Special[0] Strength to Special[6] Luck) with Actor.SetValue, Leave keeps
 the defaults. The quest never waits on this: the player can ride the elevator with SPECIAL unset, and this script logs
 "special skipped" at stage 40. Every ending is logged as "special <how>" (make_newgame.py log reads it).
 Kept apart from FO4SF_NewGameQuest so that if a native here is not what Starfield's sources offer, only this script
 fails to compile and the build goes on without it (make_newgame.py stage --no-special).
 Unverified until the PC run: Actor.SetValue / GetValue with a plugin's own AVIF (FO4's Actor.psc has them, Starfield's
 is read by the precheck), the %.0f tokens of SpecialMessage taking Show's float arguments, and a ten-button message box.}

ActorValue[] Property Special Auto Const Mandatory
{The seven AVIF FO4SF_Special_<stat> (FO4SFNewGame.esm 0x810 to 0x816), Strength, Perception, Endurance, Charisma,
 Intelligence, Agility, Luck: the button order of SpecialMessage and the argument order of its text.}

Message Property TerminalMessage Auto Const Mandatory
{The prompt at the terminal (FO4SFNewGame.esm 0x803): button 0 sets SPECIAL, button 1 is later.}

Message Property SpecialMessage Auto Const Mandatory
{The allocation (FO4SFNewGame.esm 0x804): buttons 0 to 6 add a point to that stat, 7 resets, 8 confirms, 9 leaves.}

string Property VaultPlugin = "FO4Port.esm" Auto Const
int Property TerminalId = 0 Auto Const
{The port's reference of the terminal (0 when the port carries none): only logged, the prompt watches the spot below.}
float Property TerminalX Auto Const Mandatory
float Property TerminalY Auto Const Mandatory
float Property TerminalZ Auto Const Mandatory
{Where Fallout 4 places the terminal (metres, FO4 position / 70): standing within TerminalRadius of it shows the prompt.}
float Property TerminalRadius = 2.5 Auto Const

int Property SpecialBase = 1 Auto Const
int Property SpecialPoints = 21 Auto Const
int Property SpecialMax = 10 Auto Const
{Fallout 4's rule (make_newgame.py SPECIAL_BASE, SPECIAL_POINTS, SPECIAL_MAX, the same numbers, its special_press is
 the same rule): 1 in each stat, 21 points to spend, 10 at most in one stat.}
int Property MaxPresses = 300 Auto Const
{The allocation ends as Leave after this many presses without Confirm or Leave (make_newgame.py SPECIAL_MAX_PRESSES).
 A player needs about 22 per pass; this is the guard against a message box that returns at once (the ten-button box is
 unverified), which would otherwise spin.}

bool asked = false
bool done = false

Event OnQuestStarted()
    StartTimer(1.0, 3)                                       ; the startup quest's start (FO4SF_NewGameQuest.Begin)
EndEvent

Event OnQuestInit()
    StartTimer(1.0, 3)                                       ; whichever start event comes, the timer runs; a second call restarts it
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID != 3
        return
    endif
    int stage = GetStage()
    if stage == 1 || done
        return                                               ; stood down, or SPECIAL set
    endif
    if stage >= 40
        Trace("special skipped: left the vault with SPECIAL unset")
        return
    endif
    Actor player = Game.GetPlayer()
    if stage >= 20 && player.IsInInterior() && Near(player, TerminalX, TerminalY, TerminalZ, TerminalRadius)
        if !asked
            asked = true                                     ; asked once per visit to the terminal
            AtTerminal(player)
        endif
    else
        asked = false
    endif
    StartTimer(1.0, 3)
EndEvent

Function AtTerminal(Actor player)
    ObjectReference term = None
    if TerminalId > 0
        term = Game.GetFormFromFile(TerminalId, VaultPlugin) as ObjectReference
    endif
    Trace("at terminal ref=" + term + " pos=" + player.GetPositionX() + " " + player.GetPositionY() + " " + player.GetPositionZ() + " target=" + TerminalX + " " + TerminalY + " " + TerminalZ)
    int button = TerminalMessage.Show()
    Trace("terminal prompt button=" + button)
    if button != 0
        Trace("special later")
        return
    endif
    Allocate(player)
EndFunction

Function Allocate(Actor player)
{The allocation loop: the message shows the seven values and the points left, and returns the button pressed.}
    int[] values = new int[7]
    int left = ResetValues(values)
    int presses = 0
    while presses < MaxPresses
        presses += 1
        int button = SpecialMessage.Show(values[0], values[1], values[2], values[3], values[4], values[5], values[6], left)
        if button >= 0 && button < 7
            if left <= 0
                Debug.Notification("No points left")
            elseif values[button] >= SpecialMax
                Debug.Notification(SpecialMax + " is the most in one stat")
            else
                values[button] += 1
                left -= 1
            endif
        elseif button == 7
            left = ResetValues(values)
        elseif button == 8
            if left > 0
                Debug.Notification(left + " points left to spend")
            else
                Apply(player, values)
                return
            endif
        else
            Trace("special left: defaults kept, " + left + " points unspent")
            return
        endif
    endwhile
    Trace("special left: defaults kept, " + MaxPresses + " presses without Confirm or Leave")
EndFunction

int Function ResetValues(int[] values)
{Every stat back to SpecialBase; returns the points to spend.}
    int i = 0
    while i < values.Length
        values[i] = SpecialBase
        i += 1
    endwhile
    return SpecialPoints
EndFunction

Function Apply(Actor player, int[] values)
    int i = 0
    while i < Special.Length
        player.SetValue(Special[i], values[i] as float)
        i += 1
    endwhile
    done = true
    Trace("special set S=" + values[0] + " P=" + values[1] + " E=" + values[2] + " C=" + values[3] + " I=" + values[4] + " A=" + values[5] + " L=" + values[6] + " readback=" + player.GetValue(Special[0]) + " " + player.GetValue(Special[6]))
    Debug.Notification("S.P.E.C.I.A.L. set")
EndFunction

bool Function Near(Actor player, float x, float y, float z, float radius)
    float dx = player.GetPositionX() - x
    float dy = player.GetPositionY() - y
    float dz = player.GetPositionZ() - z
    return dx * dx + dy * dy <= radius * radius && dz < 3.0 && dz > -3.0
EndFunction

Function Trace(string msg)
    Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
