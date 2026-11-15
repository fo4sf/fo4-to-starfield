Scriptname FO4SF_COMPreston Hidden
{Test-only stand-in for the Concord talk (phase plan row 2, DialogueConcordArea). Not story recruitment.
 Fallout 4's companion quest is COMPreston 0007925B. This is not that record, and it does not start the host
 follower quest 0000D773 or fill an ActiveFollowers alias. Affinity is out of this slice.
 The command arms both mission instances so the museum-door restraint cannot come back, releases that restraint,
 points Preston's linked ref at the player, fills alias 0 Preston on QUST FO4SF_COMPreston (FO4SFMission.esm 0x815)
 and re-evaluates packages. That alias carries only Starfield.esm DefaultMaster_FollowPackage 000301C5, the host
 package a linked player selected on 1 Nov (combined-core probes). The alias is optional and allows a reserved
 reference because FO4SF_Min00 already reserves the same actor for its objective marker.
   cgf "FO4SF_COMPreston.FollowTest"
 The line "follow preston test-only" is the evidence the command ran. A later "hold preston" means the door hold won.}

Function FollowTest() global
{TEST-ONLY. The Concord talk will call the same steps. Do not treat this as the story recruiting Preston.
 Ids are plugin-local: 2048 = FO4SF_Min00 0x800, 2068 = FO4SF_CodsworthKeeper 0x814, 2069 = FO4SF_COMPreston 0x815.}
    FO4SF_Min00Quest mission = Game.GetFormFromFile(2048, "FO4SFMission.esm") as FO4SF_Min00Quest
    FO4SF_Min00Quest keeper = Game.GetFormFromFile(2068, "FO4SFMission.esm") as FO4SF_Min00Quest
    if mission == None && keeper == None
        return
    endif
    ; Arm both instances before the release. Each has its own flag, and either one still places and restrains him.
    if mission != None
        mission.BeginFollow()
    endif
    if keeper != None
        keeper.BeginFollow()
    endif
    Actor preston = None
    if mission != None
        preston = mission.Preston
    endif
    if preston == None && keeper != None
        preston = keeper.Preston
    endif
    Actor player = Game.GetPlayer()
    Quest com = Game.GetFormFromFile(2069, "FO4SFMission.esm") as Quest
    int gotPreston = 0
    int gotPlayer = 0
    int gotQuest = 0
    if preston != None
        gotPreston = 1
    endif
    if player != None
        gotPlayer = 1
    endif
    if com != None
        gotQuest = 1
    endif
    if preston == None || player == None || com == None
        Debug.OpenUserLog("fo4sf_mission")
        Debug.TraceUser("fo4sf_mission", "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " follow preston test-only refused preston=" + gotPreston + " player=" + gotPlayer + " quest=" + gotQuest)
        return
    endif
    bool released = preston.SetRestrained(False)
    preston.SetLinkedRef(player)
    ReferenceAlias followAlias = com.GetAlias(0) as ReferenceAlias
    int filled = 0
    if followAlias != None
        followAlias.ForceRefTo(preston)
        filled = 1
    endif
    preston.EvaluatePackage()
    Debug.OpenUserLog("fo4sf_mission")
    Debug.TraceUser("fo4sf_mission", "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " follow preston test-only alias=Preston filled=" + filled + " linked=player released=" + released + " quest=" + com.GetFormID())
    ; The 1 Nov package probe read GetCurrentPackage two seconds after the link. A wait lets the package start.
    ; Timers can run during the wait; both instances are already armed, so PlacePreston does not put the hold back.
    Utility.Wait(2.0)
    Package pk = preston.GetCurrentPackage()
    int packageId = 0
    if pk != None
        packageId = pk.GetFormID()
    endif
    Debug.OpenUserLog("fo4sf_mission")
    Debug.TraceUser("fo4sf_mission", "FO4SF_MISSION rt=" + Utility.GetCurrentRealTime() + " follow preston package=" + packageId)
EndFunction
