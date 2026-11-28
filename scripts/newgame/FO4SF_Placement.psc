Scriptname FO4SF_Placement Hidden
{Owner rule 6 shared placement helper for transitions across the Vault / exterior boundary.
Every 2h-5 boundary MoveTo, SetPosition, frame conversion, core-cell match, and held transfer fade routes here:
  - Merged frame offset: (-1200.0, -2700.0)
  - Authored merged footprint box: x in [-4400.0, 2000.0], y in [-5900.0, 500.0] (plain XY bounds check)
  - Runtime guard refuses any exterior MoveTo whose target sits inside the merged footprint (BGSPlanet::Manager deadlock prevention).}

float Function MergedOffsetX() Global
    return -1200.0
EndFunction

float Function MergedOffsetY() Global
    return -2700.0
EndFunction

float Function FootprintMinX() Global
    return -4400.0
EndFunction

float Function FootprintMaxX() Global
    return 2000.0
EndFunction

float Function FootprintMinY() Global
    return -5900.0
EndFunction

float Function FootprintMaxY() Global
    return 500.0
EndFunction

float Function ToMergedX(float rawX, float mergeOffX = -1200.0) Global
    return rawX + mergeOffX
EndFunction

float Function ToMergedY(float rawY, float mergeOffY = -2700.0) Global
    return rawY + mergeOffY
EndFunction

float Function ToRawX(float mergedX, float mergeOffX = -1200.0) Global
    return mergedX - mergeOffX
EndFunction

float Function ToRawY(float mergedY, float mergeOffY = -2700.0) Global
    return mergedY - mergeOffY
EndFunction

bool Function IsInsideMergedFootprint(float x, float y) Global
{Plain XY bounds test over [-4400..2000] x [-5900..500] (never uses SqrtF).}
    return (x >= -4400.0) && (x <= 2000.0) && (y >= -5900.0) && (y <= 500.0)
EndFunction

int Function CoreCellGridX(float mergedX, float mergeOffX = -1200.0) Global
{Core local cell grid X derived from unmerged position (merged - mergeOffX).}
    return Math.Floor((mergedX - mergeOffX) / 100.0)
EndFunction

int Function CoreCellGridY(float mergedY, float mergeOffY = -2700.0) Global
{Core local cell grid Y derived from unmerged position (merged - mergeOffY).}
    return Math.Floor((mergedY - mergeOffY) / 100.0)
EndFunction

bool Function IsCoreCellMatch(Cell afterCell, ObjectReference anchor) Global
{Verifies afterCell carries the same load-order plugin index as the persistent core anchor.}
    if afterCell == None || anchor == None
        return false
    endif
    int cellMod = afterCell.GetFormID() / 16777216
    int anchorMod = anchor.GetFormID() / 16777216
    return cellMod == anchorMod
EndFunction

Function BeginHeldTransferFade() Global
    Game.FadeOutGame(True, True, 0.0, 0.2, True)
EndFunction

Function HoldPlainBlackFrame() Global
    Game.FadeOutGame(True, True, 0.0, 0.05, True)
EndFunction

Function EndHeldTransferFade(float fadeSec = 0.5) Global
    Game.FadeOutGame(False, True, 0.0, fadeSec, False)
EndFunction

Function LogPlace(string logName, string msg) Global
    if logName == ""
        return
    endif
    Debug.OpenUserLog(logName)
    Debug.TraceUser(logName, msg)
EndFunction

bool Function MovePlayerToExteriorAnchor(Actor player, ObjectReference anchor, string what, string logName = "fo4sf_newgame", bool holdFade = true) Global
{Moves the player to a raw-frame exterior anchor outside the merged footprint under held black fade.}
    if player == None || anchor == None
        return false
    endif
    float ax = anchor.GetPositionX()
    float ay = anchor.GetPositionY()
    float az = anchor.GetPositionZ()
    bool inside = IsInsideMergedFootprint(ax, ay)
    Cell anchorCell = anchor.GetParentCell()
    LogPlace(logName, "place move=" + what + " target=" + ax + " " + ay + " " + az + " frame=raw inside_footprint=" + inside + " cell=" + anchorCell)
    if inside
        LogPlace(logName, "place refused reason=inside_merged_footprint move=" + what + " target=" + ax + " " + ay + " " + az + " cell=" + anchorCell)
        return false
    endif
    if holdFade
        BeginHeldTransferFade()
    endif
    anchor.Enable(False)
    player.MoveTo(anchor, 0.0, 0.0, 0.0, True, False)
    return true
EndFunction

bool Function SetPlayerMergedPosition(Actor player, float rawX, float rawY, float z, float headingDeg, float mergeOffX, float mergeOffY, string what, string logName = "fo4sf_newgame") Global
{Shifts player from raw procedural landing into merged FO4TerrainCore frame and logs placement coordinates.}
    if player == None
        return false
    endif
    float mx = ToMergedX(rawX, mergeOffX)
    float my = ToMergedY(rawY, mergeOffY)
    player.SetPosition(mx, my, z)
    player.SetAngle(0.0, 0.0, headingDeg)
    LogPlace(logName, "place move=" + what + " target=" + mx + " " + my + " " + z + " frame=merged inside_footprint=" + IsInsideMergedFootprint(mx, my) + " cell=" + player.GetParentCell())
    return true
EndFunction

bool Function RelocateDiscoveryMarker(ObjectReference marker, Actor player, float mx, float my, float mz, string what, string logName = "fo4sf_newgame") Global
{Moves the dedicated silent-discovery marker (never ExitAnchorId or load-door anchors) into the player's runtime exterior world.}
    if marker == None || player == None
        return false
    endif
    float px = player.GetPositionX()
    float py = player.GetPositionY()
    float pz = player.GetPositionZ()
    WorldSpace pw = player.GetWorldSpace()
    marker.Enable(False)
    marker.MoveTo(player, mx - px, my - py, mz - pz, False, False)
    if pw != None && marker.GetWorldSpace() == pw
        marker.SetPosition(mx, my, mz)
    endif
    LogPlace(logName, "place move=" + what + " target=" + mx + " " + my + " " + mz + " frame=merged inside_footprint=" + IsInsideMergedFootprint(mx, my) + " cell=" + marker.GetParentCell())
    return true
EndFunction
