"""Fallout 4 land texture -> vanilla Starfield land texture (docs/terrain/ground-textures.md 3).

Method: every FO4 LTEX gets a ground category by hand (from its EditorID and its diffuse texture). Each category has a
list of Earth-like vanilla Starfield LTEX (no _Red / _Mars / _Volcanic / _Purple / glow variants). Within the category
the Starfield texture whose average albedo is nearest to the FO4 diffuse average (CIE76 colour difference, sRGB means
in linear light; `ground_textures.py palette` + `suggest`) was taken, then the table was reviewed by eye on texture
previews; review changes are marked in REVIEWED. The FO4 average colours themselves are not in the repo (game data).

Starfield FormIDs are Starfield.esm LTEX records (raw read of Starfield.esm 1.16.244, verified: EditorID and BNAM
material file per FormID). All are used through the BTD's LTEX table only; no plugin record is added.
"""
# Quadrant without BTXT, or LTEX 0 in an ATXT. Treated as CommonwealthDefault01 (LTEX LCWDefault01Grass01/02, TXST
# LandscapeCommonWealthDefault01): supported, not verified. The Commonwealth WRLD has no default-texture field and no
# DOBJ entry names one; fo76utils' render examples pass -deftxt 0x000AB07E (LCWDefault01Grass02) for Fallout 4.
FO4_DEFAULT = "(FO4 default)"

# ---------------------------------------------------------------------------------------- Starfield side (verified)
SF_FORMID = {
    "LGrassDeadWet01": 0x0028EB36, "LGrassDeadWet02": 0x0028EB37, "LGrassLive01": 0x0018A896,
    "LGrassLive02": 0x0018A893, "LGrassWeeds01": 0x00238B40, "LGrassWeeds02": 0x001C6B76,
    "LGrassClover01": 0x00238B41, "LGrassLiveSparse02": 0x0018A894, "LGrassAridSparse01_Dead": 0x000E7DFA,
    "LGrassAridSparse02_Dead": 0x000E7DFB, "LMossDried01": 0x0022881C, "LMossDebris02": 0x00220E59,
    "LMossForest01": 0x000714D4,
    "LGravelAsphaltRoad01": 0x001235C0, "LGravelRoad01": 0x001235C1, "LGravelDecorative01": 0x001235BF,
    "LDirtGravel01": 0x00021336, "LRockCracked01": 0x00057EC0, "LRockWorn01": 0x000557E2,
    "LDirtPacked01_Gray": 0x00231A95, "LDirtPacked05_Gray": 0x002073E6, "LDirtFootprints01_Gray": 0x0012132A,
    "LLooseRocksForest01": 0x000714D2, "LLooseRocksForest01_DarkGray": 0x0016D719, "LLooseRocksSharp01": 0x0029B94A,
    "LLooseRocksSharp01_Forest": 0x00172585, "LRiverRocks01": 0x0024F06C, "LRiverRocks01_Pale": 0x001E9BF3,
    "LRiverRocks01_Gray": 0x00214967, "LGravelSmoothLarge03": 0x000557C7,
    "LDirtPacked01": 0x0003013A, "LDirtPacked02": 0x000557C1, "LDirtPacked04": 0x000557C2,
    "LDirtPacked06": 0x0005592C, "LDirtPacked07": 0x0005592D, "LDirtPacked08": 0x00056375,
    "LDirtPacked09": 0x00251B78, "LDirtPacked10": 0x001CC5CB, "LDirtPacked05_Tan": 0x002073E4,
    "LDirtPacked09_Brown": 0x002073DB, "LDirtPacked04_Brown": 0x002073EB, "LDirtPacked02_Pale": 0x002073ED, "LDirtPacked04_Pale": 0x002073E9,
    "LDirtPacked08_GrayRocks": 0x0021615B, "LDirtPacked09_GrayRocks": 0x0021615A,
    "LDirtForestPacked01": 0x000714D3, "LDirtForestPacked01_Dark": 0x00145441, "LDirtForestPine01": 0x002C1C79,
    "LDirtForestRoots01": 0x00273167, "LDirtForestRoots02": 0x00172586, "LLeavesPineNeedles01": 0x00286AF9,
    "LLeavesTropical01": 0x0022B2E1,
    "LDirtMudPacked01": 0x0022881E, "LDirtMudPacked01_Brown": 0x0016884E, "LDirtMudPacked01_DarkBrown": 0x0032C317,
    "LDirtMudPacked02": 0x00194845, "LDirtMudPacked02_Brown": 0x0016884D, "LDirtMudPacked02_DarkBrown": 0x001F00A1,
    "LDirtMudRough01": 0x002777B5, "LDirtMudRough02": 0x0028EB35, "LDirtMudFootprints01": 0x0029B44F,
    "LDirtMudDebris01": 0x00220E5C,
    "LSandPacked03": 0x000557E3, "LSandPacked04": 0x000557E4, "LSandPacked05": 0x00058177,
    "LSandFine01_Tan": 0x002024C5, "LSandFine01_Gray": 0x002024C7, "LSandPacked03_Gray": 0x002024C9,
    "LDebrisPile01": 0x0020A82D, "LScrapPile01": 0x0020A82C, "LTrash01": 0x002E57E6,
    "LDirtFootprints01": 0x001235C2,
}

# The six placeholder LTEX that every vanilla BTD with an LTEX table carries (verified: survey, ground-textures.md 2.2),
# and the table of exp2b2's BTD (copied from a vanilla template; verified in game to render LDirtFootprints01), in its
# order. No BIOM names the placeholders; they stand for the planet biome's ground (supported).
PLACEHOLDERS = ["LDefault001Solid", "LDefault002Talus", "LDefault003FlatIn", "LDefault004FlatOut", "LDefault005Flow",
                "LDefault006Base"]
PLACEHOLDER_FORMID = {"LDefault001Solid": 0x0001085C, "LDefault002Talus": 0x0001085D, "LDefault003FlatIn": 0x0001085E,
                      "LDefault004FlatOut": 0x0001085F, "LDefault005Flow": 0x00010860, "LDefault006Base": 0x00010861}
TEMPLATE_TABLE = ["LDefault006Base", "LDefault005Flow", "LDefault004FlatOut", "LDefault003FlatIn", "LDefault002Talus",
                  "LDefault001Solid", "LDirtFootprints01"]

SF_CANDIDATES = {
    "grass": ["LGrassDeadWet01", "LGrassDeadWet02", "LGrassLive01", "LGrassLive02", "LGrassWeeds01", "LGrassWeeds02",
              "LGrassClover01", "LGrassLiveSparse02", "LGrassAridSparse01_Dead", "LGrassAridSparse02_Dead",
              "LMossDried01", "LMossDebris02"],
    "lawn": ["LGrassLive01", "LGrassLive02", "LGrassWeeds01", "LGrassWeeds02", "LGrassClover01", "LMossForest01"],
    "paved": ["LGravelAsphaltRoad01", "LGravelRoad01", "LRockCracked01", "LRockWorn01", "LDirtPacked01_Gray",
              "LDirtPacked05_Gray", "LDirtFootprints01_Gray", "LGravelDecorative01"],
    "gravel": ["LDirtGravel01", "LGravelRoad01", "LGravelDecorative01", "LLooseRocksForest01",
               "LLooseRocksForest01_DarkGray", "LLooseRocksSharp01", "LLooseRocksSharp01_Forest", "LRiverRocks01",
               "LRiverRocks01_Pale", "LRiverRocks01_Gray", "LGravelSmoothLarge03", "LDirtPacked08_GrayRocks",
               "LDirtPacked09_GrayRocks"],
    "dirt": ["LDirtPacked01", "LDirtPacked02", "LDirtPacked04", "LDirtPacked06", "LDirtPacked07", "LDirtPacked08",
             "LDirtPacked09", "LDirtPacked10", "LDirtPacked05_Tan", "LDirtPacked09_Brown", "LDirtPacked02_Pale",
             "LDirtPacked04_Pale", "LDirtForestPacked01", "LDirtMudPacked02"],
    "forest": ["LDirtForestPacked01", "LDirtForestPacked01_Dark", "LDirtForestPine01", "LDirtForestRoots01",
               "LDirtForestRoots02", "LLeavesPineNeedles01", "LLeavesTropical01", "LMossDebris02"],
    "mud": ["LDirtMudPacked01", "LDirtMudPacked01_Brown", "LDirtMudPacked01_DarkBrown", "LDirtMudPacked02",
            "LDirtMudPacked02_Brown", "LDirtMudPacked02_DarkBrown", "LDirtMudRough01", "LDirtMudRough02",
            "LDirtMudFootprints01", "LDirtMudDebris01"],
    "sand": ["LSandPacked03", "LSandPacked04", "LSandPacked05", "LSandFine01_Tan", "LSandFine01_Gray",
             "LSandPacked03_Gray"],
    "debris": ["LDebrisPile01", "LScrapPile01", "LTrash01", "LDirtMudDebris01", "LLooseRocksSharp01",
               "LGravelSmoothLarge03"],
}

# ------------------------------------------------------------------------------------------ Fallout 4 side (by hand)
FO4_CATEGORY = {
    FO4_DEFAULT: "dirt",
    "LAsphalt01": "paved", "LCobblestone01": "paved", "LCitySW01": "paved", "LQuaryMarble01": "paved",
    "LDriedGrass01": "grass", "LDriedGrass01NoGrass": "grass", "LDriedGrass02Weeds": "grass", "LDriedGrass03": "grass",
    "LCWDefault01Grass01": "dirt", "LCWDefault01Grass02": "dirt",
    "LNF_ScrubGrass01": "grass", "LNF_ScrubGrass01_NoGrass": "grass", "LNFoothillsDriedGrass01": "grass",
    "LNFoothillsDriedGrass01NoGrass": "grass", "LNF_MountainScrub01": "grass",
    "LBlastedForestGrass01": "grass", "LBlastedForestGrass01_NoGrass": "grass",
    "LMarshGrass01": "grass", "LMarshGrass01_NoGrass": "grass",
    "LCoastGrassSand01": "grass", "LCoastGrassSand01NoGrass": "grass",
    "LPreWarGreenLawn01": "lawn", "LPreWarGreenLawn01NoGrass": "lawn", "LPreWarWildGrass01": "lawn",
    "LPreWarWildGrass02": "lawn",
    "LNF_Dirt01": "dirt", "LNFoothillsDirt01": "dirt", "LNFoothillsDirt01Grass01": "dirt",
    "LNFoothillsDirt01Grass02": "dirt", "LDirtPath01": "dirt", "LPreWarDirt01": "dirt", "LBlastedForestDirt01": "dirt",
    "LCrackedMud01": "dirt", "LRootsEroded01": "dirt", "LRootsEroded01Grass01": "dirt", "LRootsEroded01Rocks01": "dirt",
    "LRootsEroded02": "dirt", "LNFoothillsRootsEroded01": "dirt", "LNFoothillsRootsEroded01Rocks01": "dirt",
    "LGlowingSeaCorrosion01": "dirt", "LGlowingSeaCorrosion02": "dirt", "LGlowingSeaCrackedMud01": "dirt",
    "LGlowingSeaCrackedMud01NoGrass": "dirt",
    "LDirtGravel01": "gravel", "LDirtGravel01Grass": "gravel", "LBlastedForestGravel01": "gravel",
    "LBlastedForestGravel01_NoRocks": "gravel", "LRubbleRock01": "gravel", "LRubbleRock01Grass": "gravel",
    "LNFoothillsRubbleRock01": "gravel", "LNFoothillsRubbleRock01Grass": "gravel",
    "LRiverbedRocks01": "gravel", "LRiverbedRocks01Grass": "gravel", "LRiverbedRocks01Wet": "gravel",
    "LRiverbedRocks01WetGrass": "gravel", "LRiverbedRocks01WetGrass02": "gravel", "LRiverbedRocks02": "gravel",
    "LRiverbedRocks02Grass": "gravel", "LRiverbedRocks02Wet": "gravel", "LRiverbedRocks02WetGrass": "gravel",
    "LCoastWetRockSand01": "gravel", "LCoastWetRockSand01NoGrass": "gravel",
    "LForestFloor01": "forest", "LFallenLeaves01": "forest", "LPreWarFallenLeaves01": "forest",
    "LMuddyLeaves01Wet": "forest", "LBlastedForestFloor01": "forest", "LBlastedForestFloor02": "forest",
    "LBlastedForestFloor02_NoTwigs": "forest", "LNF_ForestFloor01": "forest", "LMarshHighGround01": "forest",
    "LRiverbedSilt01": "mud", "LRiverbedSilt01Grass01": "mud", "LRiverbedSilt01Wet": "mud",
    "LMarshMudFloor01": "mud", "LMarshMudFloor01Grass": "mud", "LMarshMudTrash01": "mud", "LGlowingSeaMud01": "mud",
    "LGlowingSeaMud01NoGrass": "mud", "LOceanFloor01": "mud", "LOceanFloor01ShortKelp": "mud",
    "LOceanFloor01TallKelp": "mud", "LMirelurkNest01": "mud",
    "LCoastSandDry01": "sand", "LCoastSandWet01": "mud", "LCoastSandRipples01": "mud",    # wet sand: dark, like mud
    "LDebrisGround": "debris", "LDebrisGround01Trash01": "debris", "LDebrisGround01Wood01": "debris",
    "LDebrisRubble01": "debris", "LDebrisRubble01NoGrass": "debris", "LDebrisRubble02": "debris",
    "LDebrisRubbleBrick01": "debris", "LDebrisRubbleBrick01NoGrass": "debris", "LDebrisRubbleHightech": "debris",
    "LDebrisRubbleHightechChunk01": "debris", "LDebrisRubbleHightechGrass01": "debris", "LDebrisRubblePlain": "debris",
    "LDebrisCrater01": "debris", "LDebrisCrater01NoGrass": "debris", "LDebrisCraterBrickRed": "debris",
    "LDebrisCraterBrickTan": "debris", "LDiamondTrash01": "debris", "LGlowingSeaRubble01": "debris",
    "LGlowingSeaRubble01NoGrass": "debris",
}

# Frozen result (suggest + review, 2026-10-11). Keys missing here fall back to the category's first candidate.
MAP = {
    FO4_DEFAULT: "LDirtPacked09_Brown", "LAsphalt01": "LGravelDecorative01",
    "LBlastedForestDirt01": "LDirtPacked09_Brown", "LBlastedForestFloor01": "LDirtForestPacked01_Dark",
    "LBlastedForestFloor02": "LDirtForestPacked01_Dark", "LBlastedForestFloor02_NoTwigs": "LDirtForestPacked01_Dark",
    "LBlastedForestGrass01": "LGrassDeadWet02", "LBlastedForestGrass01_NoGrass": "LGrassDeadWet02",
    "LBlastedForestGravel01": "LGravelRoad01", "LBlastedForestGravel01_NoRocks": "LGravelRoad01",
    "LCWDefault01Grass01": "LDirtPacked09_Brown", "LCWDefault01Grass02": "LDirtPacked09_Brown",
    "LCitySW01": "LDirtPacked05_Gray", "LCoastGrassSand01": "LGrassDeadWet02",
    "LCoastGrassSand01NoGrass": "LGrassDeadWet02", "LCoastSandDry01": "LSandPacked03_Gray",
    "LCoastSandRipples01": "LDirtMudPacked02_DarkBrown", "LCoastSandWet01": "LDirtMudPacked02_DarkBrown",
    "LCoastWetRockSand01": "LRiverRocks01_Gray", "LCoastWetRockSand01NoGrass": "LRiverRocks01_Gray",
    "LCobblestone01": "LGravelDecorative01", "LCrackedMud01": "LDirtPacked10", "LDebrisCrater01": "LDebrisPile01",
    "LDebrisCrater01NoGrass": "LDebrisPile01", "LDebrisCraterBrickRed": "LDirtMudDebris01",
    "LDebrisCraterBrickTan": "LDebrisPile01", "LDebrisGround": "LDebrisPile01",
    "LDebrisGround01Trash01": "LDebrisPile01", "LDebrisGround01Wood01": "LDebrisPile01",
    "LDebrisRubble01": "LLooseRocksSharp01", "LDebrisRubble01NoGrass": "LLooseRocksSharp01",
    "LDebrisRubble02": "LLooseRocksSharp01", "LDebrisRubbleBrick01": "LLooseRocksSharp01",
    "LDebrisRubbleBrick01NoGrass": "LLooseRocksSharp01", "LDebrisRubbleHightech": "LScrapPile01",
    "LDebrisRubbleHightechChunk01": "LScrapPile01", "LDebrisRubbleHightechGrass01": "LScrapPile01",
    "LDebrisRubblePlain": "LScrapPile01", "LDiamondTrash01": "LDebrisPile01", "LDirtGravel01": "LDirtGravel01",
    "LDirtGravel01Grass": "LDirtGravel01", "LDirtPath01": "LDirtPacked10", "LDriedGrass01": "LGrassDeadWet01",
    "LDriedGrass01NoGrass": "LGrassDeadWet01", "LDriedGrass02Weeds": "LGrassDeadWet01",
    "LDriedGrass03": "LGrassDeadWet01", "LFallenLeaves01": "LDirtForestRoots02",
    "LForestFloor01": "LDirtForestPacked01_Dark", "LGlowingSeaCorrosion01": "LDirtPacked09",
    "LGlowingSeaCorrosion02": "LDirtMudPacked02", "LGlowingSeaCrackedMud01": "LDirtPacked09_Brown",
    "LGlowingSeaCrackedMud01NoGrass": "LDirtPacked09_Brown", "LGlowingSeaMud01": "LDirtMudPacked01_DarkBrown",
    "LGlowingSeaMud01NoGrass": "LDirtMudPacked01_DarkBrown", "LGlowingSeaRubble01": "LDirtMudDebris01",
    "LGlowingSeaRubble01NoGrass": "LDirtMudDebris01", "LMarshGrass01": "LGrassDeadWet02",
    "LMarshGrass01_NoGrass": "LGrassDeadWet02", "LMarshHighGround01": "LDirtForestPacked01_Dark",
    "LMarshMudFloor01": "LDirtMudPacked01_Brown", "LMarshMudFloor01Grass": "LDirtMudPacked01_Brown",
    "LMarshMudTrash01": "LDirtMudPacked02_DarkBrown", "LMirelurkNest01": "LDirtMudPacked01_Brown",
    "LMuddyLeaves01Wet": "LDirtForestRoots02", "LNF_Dirt01": "LDirtPacked09_Brown",
    "LNF_ForestFloor01": "LDirtForestPacked01_Dark", "LNF_MountainScrub01": "LMossDebris02",
    "LNF_ScrubGrass01": "LMossDebris02", "LNF_ScrubGrass01_NoGrass": "LMossDebris02",
    "LNFoothillsDirt01": "LDirtPacked09_Brown", "LNFoothillsDirt01Grass01": "LDirtPacked09_Brown",
    "LNFoothillsDirt01Grass02": "LDirtPacked09_Brown", "LNFoothillsDriedGrass01": "LMossDebris02",
    "LNFoothillsDriedGrass01NoGrass": "LMossDebris02", "LNFoothillsRootsEroded01": "LDirtPacked09_Brown",
    "LNFoothillsRootsEroded01Rocks01": "LDirtPacked09_Brown", "LNFoothillsRubbleRock01": "LGravelRoad01",
    "LNFoothillsRubbleRock01Grass": "LGravelRoad01", "LOceanFloor01": "LDirtMudPacked02_Brown",
    "LOceanFloor01ShortKelp": "LDirtMudPacked02_Brown", "LOceanFloor01TallKelp": "LDirtMudPacked02_Brown",
    "LPreWarDirt01": "LDirtForestPacked01", "LPreWarFallenLeaves01": "LDirtForestPacked01_Dark",
    "LPreWarGreenLawn01": "LMossForest01", "LPreWarGreenLawn01NoGrass": "LMossForest01",
    "LPreWarWildGrass01": "LMossForest01", "LPreWarWildGrass02": "LMossForest01",
    "LQuaryMarble01": "LDirtPacked05_Gray",
    "LRiverbedRocks01": "LDirtPacked08_GrayRocks", "LRiverbedRocks01Grass": "LDirtPacked08_GrayRocks",
    "LRiverbedRocks01Wet": "LRiverRocks01_Gray", "LRiverbedRocks01WetGrass": "LRiverRocks01_Gray",
    "LRiverbedRocks01WetGrass02": "LRiverRocks01_Gray", "LRiverbedRocks02": "LGravelRoad01",
    "LRiverbedRocks02Grass": "LGravelRoad01", "LRiverbedRocks02Wet": "LGravelRoad01",
    "LRiverbedRocks02WetGrass": "LGravelRoad01", "LRiverbedSilt01": "LDirtMudPacked01_Brown",
    "LRiverbedSilt01Grass01": "LDirtMudPacked01_Brown", "LRiverbedSilt01Wet": "LDirtMudPacked01_Brown",
    "LRootsEroded01": "LDirtPacked04", "LRootsEroded01Grass01": "LDirtPacked04",
    "LRootsEroded01Rocks01": "LDirtPacked04", "LRootsEroded02": "LDirtPacked09_Brown",
    "LRubbleRock01": "LGravelRoad01", "LRubbleRock01Grass": "LGravelRoad01",
}
# FO4 EditorID -> why the reviewed choice is not the nearest colour
REVIEWED = {
    "LQuaryMarble01": "nearest LRockCracked01 (dE 7.0) has a pink-purple cast that stands out in the top-down render; "
                      "the neutral LDirtPacked05_Gray (dE 8.0) is as close in lightness",
    "LDirtGravel01": "same material name; nearest LLooseRocksForest01_DarkGray (dE 3.6) is a forest texture, "
                     "LDirtGravel01 (dE 7.8) is the gravel lot look (Red Rocket's lot)",
    "LDirtGravel01Grass": "as LDirtGravel01",
    "LMuddyLeaves01Wet": "nearest LLeavesTropical01 (dE 2.9) shows green tropical leaves; LDirtForestRoots02 is the "
                         "brown leaf litter used for LFallenLeaves01 (dE 1.6 there)",
}
# FO4 EditorID -> a note on a choice that is the nearest colour but not the obvious name
NOTES = {
    "LAsphalt01": "nearest colour (dE 7.0); the paved list also holds vanilla LGravelAsphaltRoad01, the semantic match, "
                  "but its albedo averages (47, 46, 45) against FO4 Asphalt01's (115, 111, 100): FO4's lots are "
                  "sun-bleached grey, so the light grey gravel was kept",
}
FALLBACK = "LDirtPacked02"

# exp2t variants ta / tb (ground-textures.md 5): every FO4 texture folded onto four Starfield LTEX by its category.
# ta: four LTEX that vanilla gameplay BTD tables carry (sb016templeworld, sb013templeworld, akilacity,
#     overlaytraitprimordialnetworksm01). tb: four LTEX of the full mapping that no vanilla BTD table carries (all named
#     by BIOMs). With exp2b2's 7-entry template table both make 11 entries, the size of akilacity's table.
FOLD = {
    "ta": {"grass": "LGrassAridSparse01_Dead", "lawn": "LGrassAridSparse01_Dead", "gravel": "LLooseRocksForest01",
           "paved": "LLooseRocksForest01", "debris": "LLooseRocksForest01", "dirt": "LDirtPacked04_Brown",
           "mud": "LDirtPacked04_Brown", "sand": "LDirtPacked04_Brown", "forest": "LDirtForestPacked01"},
    "tb": {"grass": "LGrassDeadWet01", "lawn": "LGrassDeadWet01", "gravel": "LGravelDecorative01",
           "paved": "LGravelDecorative01", "debris": "LGravelDecorative01", "dirt": "LDirtPacked04", "mud": "LDirtPacked04",
           "sand": "LDirtPacked04", "forest": "LDirtForestPacked01_Dark"},
}


def category(fo4_edid):
    return FO4_CATEGORY.get(fo4_edid, "dirt")


def formid(sf_edid):
    """Starfield.esm FormID of a mapped LTEX or a placeholder."""
    return SF_FORMID[sf_edid] if sf_edid in SF_FORMID else PLACEHOLDER_FORMID[sf_edid]


def folded(variant, fo4_edid):
    """Starfield LTEX of a FO4 LTEX in a folded variant (FOLD)."""
    return FOLD[variant][category(fo4_edid)]


def sf_for(fo4_edid):
    """Starfield LTEX EditorID for a FO4 LTEX EditorID (or FO4_DEFAULT)."""
    if fo4_edid in MAP:
        return MAP[fo4_edid]
    cands = SF_CANDIDATES.get(category(fo4_edid))
    return cands[0] if cands else FALLBACK
