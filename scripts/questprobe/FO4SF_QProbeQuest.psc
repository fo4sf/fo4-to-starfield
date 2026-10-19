Scriptname FO4SF_QProbeQuest extends Quest
{The quest-engine probe (fo4-to-starfield, docs/questprobe/engine-questions.md). Start game enabled, it idles until the
 player stands in the probe's cell (by default the converted Boston Public Library, FO4Port.esm), then asks five
 questions once and writes the answers to the user log "fo4sf_qprobe" (My Games\Starfield\Logs\Script\User):
   E1 fragment     does the stage 10 fragment (FO4SF_QProbeFragments) run when SetStage(10) is called?
   E2 onstageset   does this script's OnStageSet event fire for stages 10 and 20?
   E3 alias        does ForceRefTo fill the Target alias (the objective's marker then shows on the compass: a screenshot)?
   E4 questtype    is the quest listed under its own "Commonwealth" heading in the Missions tab (a screenshot)?
   E5 storymanager does our keyword's story event start FO4SF_QProbeSM through our own Story Manager branch?
 Walking to the marked door completes the objective and the quest (stage 100). Nothing is moved, spawned or changed.
 The places come from FO4Port.esm by plugin-local form id (the FO4SF_LoadDoor contract): Starfield.esm is the only
 master, so a rebuilt port never needs this plugin rebuilt while those ids stay.}

ReferenceAlias Property TargetAlias Auto Const Mandatory
{Alias 0 "Target", optional and empty in the plugin: forced here, at run time, to the target door.}
string Property PortPlugin = "FO4Port.esm" Auto Const
int Property AnchorId Auto Const Mandatory
{The probe cell's COC marker: the player is "there" when they share its parent cell.}
int Property TargetId Auto Const Mandatory
{The marker's target: the cell's farthest load door, else a door or object on the COC marker's floor in reach.}
Keyword Property SMEvent Auto Const
{FO4SFQuestProbe.esm's story event keyword (None in a --no-sm build: E5 is skipped).}
Quest Property SMQuest Auto Const
{FO4SF_QProbeSM, which only our Story Manager branch can start.}
float Property ReachRadius = 3.0 Auto Const

string LogName = "fo4sf_qprobe"
bool started = false
bool done = false
int fragmentStage = 0
float fragmentAt = 0.0
int stageEvents = 0
string stageEventList = ""
float setAt = 0.0
ObjectReference target = None

Event OnQuestInit()
    Debug.OpenUserLog(LogName)
    Trace("init anchor=" + PortPlugin + ":" + AnchorId + " target=" + PortPlugin + ":" + TargetId + " sm=" + (SMEvent != None))
    StartTimer(5.0, 1)
EndEvent

Event OnStageSet(int auiStageID, int auiItemID)
    stageEvents += 1
    stageEventList += " " + auiStageID
    Trace("onstageset stage=" + auiStageID + " item=" + auiItemID + " after=" + (Utility.GetCurrentRealTime() - setAt))
EndEvent

Function FragmentRan(int stage)
{Called by FO4SF_QProbeFragments' stage fragment: proof that it ran, and when.}
    fragmentStage = stage
    fragmentAt = Utility.GetCurrentRealTime()
    Trace("fragment ran stage=" + stage + " after=" + (fragmentAt - setAt))
EndFunction

Event OnTimer(int aiTimerID)
    Actor player = Game.GetPlayer()
    if aiTimerID == 1
        if !started && InProbeCell(player)
            started = true
            Probe(player)
            StartTimer(5.0, 2)
        elseif !started
            StartTimer(5.0, 1)
        endif
    elseif aiTimerID == 2
        Report()
        StartTimer(2.0, 3)
    elseif aiTimerID == 3 && !done
        if target != None && player.GetDistance(target) <= ReachRadius
            done = true
            SetObjectiveCompleted(10)
            Trace("reached target distance=" + player.GetDistance(target))
            SetStage(100)
        else
            StartTimer(2.0, 3)
        endif
    endif
EndEvent

bool Function InProbeCell(Actor player)
    ObjectReference anchor = Game.GetFormFromFile(AnchorId, PortPlugin) as ObjectReference
    return anchor != None && player.GetParentCell() == anchor.GetParentCell()
EndFunction

Function Probe(Actor player)
    Trace("probe start cell=" + player.GetParentCell())
    ; E1 and E2: one SetStage; the fragment and the event report back on their own
    setAt = Utility.GetCurrentRealTime()
    SetStage(10)
    Trace("setstage 10 stage=" + GetStage() + " done10=" + GetStageDone(10) + " fragment_by_now=" + fragmentStage)
    ; E3: the objective's marker follows the alias
    target = Game.GetFormFromFile(TargetId, PortPlugin) as ObjectReference
    if target != None
        TargetAlias.ForceRefTo(target)
    endif
    SetObjectiveDisplayed(10)
    SetActive(True)
    Trace("alias target=" + target + " filled=" + (target != None && TargetAlias.GetReference() == target) + " distance=" + player.GetDistance(target))
    ; E5: our keyword's story event, through our own branch
    if SMEvent != None
        ; Starfield returns the quests the event started (Quest[], PC precheck 19 Oct), not FO4's bool
        Quest[] startedBy = SMEvent.SendStoryEventAndWait()
        int count = 0
        if startedBy
            count = startedBy.Length
        endif
        Trace("story event started=" + count + " ours=" + (count > 0 && startedBy.Find(SMQuest) >= 0) + " sm_running=" + SMQuest.IsRunning())
    endif
    SetStage(20)
EndFunction

Function Report()
    string e1 = "FAIL"
    if fragmentStage == 10
        e1 = "PASS"
    endif
    string e2 = "FAIL"
    if stageEvents > 0
        e2 = "PASS"
    endif
    string e3 = "FAIL"
    if target != None && TargetAlias.GetReference() == target
        e3 = "FILLED"
    endif
    string e5 = "SKIPPED"
    if SMEvent != None
        e5 = "FAIL"
        if SMQuest.IsRunning() || SMQuest.IsCompleted()
            e5 = "PASS"
        endif
    endif
    Trace("result E1_fragment=" + e1 + " E2_onstageset=" + e2 + " (" + stageEvents + ":" + stageEventList + ") E3_alias=" + e3 + " E4_questtype=LOOK E5_storymanager=" + e5)
    Debug.Notification("Quest probe done: check the compass marker and the Missions tab")
EndFunction

Function Trace(string msg)
    Debug.TraceUser(LogName, "FO4SF_QPROBE rt=" + Utility.GetCurrentRealTime() + " " + msg)
EndFunction
