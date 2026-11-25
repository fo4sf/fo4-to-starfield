# Vault 111 Look Root-Cause Analysis & Fixes (`Vault111Cryo`)

Owner playtest (`25 Nov`, `#32` comment `7155932648`, Follow-Up NEXT 2) identified two visual faults in `FO4Port_Vault111Cryo`:
1. **Flashing ground textures in the restricted area**
2. **Lighting feels off**

Both were traced offline against `Fallout4.esm`, `Fallout4 - Meshes.ba2`, `Fallout4 - Materials.ba2`, `Fallout4 - Textures3.ba2`, `interiors_b10` `Vault111Cryo.json`, and installed `FO4Port.esm` / `FO4Port - Main.ba2`.

---

## 1. Root Causes Verified

### A. Flashing Restricted-Area Ground Textures
Three stacked causes combine in Vault 111's cryo/restricted-area corridors and security bays:

1. **Inline `BSLightingShaderProperty` decals converted as opaque slabs (`38` shapes in `Vault111Cryo`):**
   - `V111FloorStripeRestricted.nif` (`2` placements: `0556FE`, `1A78B1`), `V111FloorStripeRestricted02.nif` (`5` placements), `V111FloorGuide.nif` (`1` placement: `001907`), `V111SignLabelC01..C14.nif`, `DecalConcrete01..04.nif`, and `DecalMetal01..04.nif` carry **no `.bgsm` material string** (`mat == ""`).
   - Instead, their FO4 NIFs use an inline `BSShaderTextureSet` (`V111GreebsAlpha01_d.dds`, DXGI `77` with alpha channel) with `SLSF1_DECAL | SLSF1_DYNAMIC_DECAL` (`flags1 = 0x8C400201`, mask `0x0C000000`) and a `NiAlphaProperty` (`flags = 0x10ED`, `alpha_blend = True`, threshold `128`).
   - `Converter._shape_material` (`src/fo4sf/pipeline.py`) only routed `.bgsm` shapes through `decal_material()`. Texture-set shapes went straight to `texture_set_material()`, cloning opaque `MetalIronCast01.mat` with `Opacity = None`.
   - Worse, `V111FloorStripeRestricted.nif`, `02.nif`, `V111FloorGuide.nif`, and `V111FloorStripeRestricted03.nif` all have vertices at **`local z = 0.0000`** with `+Z` normals — sitting coplanar on top of `V111RMid01.nif`'s `V111FloorTiles01` (`z = 0.0000`), creating severe opaque Z-fighting on the floor.

2. **Planar decals at exact `z = 0.0000` with zero surface offset:**
   - Even `V111FloorStripeRestricted03.nif` (`17` placements, `Materials\Interiors\Vault\Vault111\V111LabelSet03.BGSM`, converted to `1LayerStandardDecal` via `AKDecalPrintedTechWall01.mat`) sits at `local z = 0.0000` (`4` placements `1B5EBD..1B5EC0` at world `z = 0.06` FO4 units = `0.00086 m` above the cryo floor). Applying a `+0.002 m` vertex-normal bias (`DECAL_NORMAL_OFFSET_M`) to flat planar decal shapes eliminates depth-buffer fighting with coplanar floor/wall tiles.

3. **Exact duplicate overlapping placements in `Vault111Cryo`:**
   - `Vault111Cryo` has identical duplicated static/decal placements inherited from FO4 (where precombines/previs merged or culled them, whereas Starfield draws each `REFR` individually):
     - `V111Hall01` duplicated at `[-2432, 1920, 0]`, `rot = [0, 0, 4.712]` (`0AD65D:Fallout4.esm` and `23B9CE:Fallout4.esm` — entire hallway floor/wall module overlapping itself in the restricted/overseer wing!).
     - `V111FloorStripeRestricted03` duplicated at `[-1664.78, -1787.54, -51.33]` (`1B5EBA:Fallout4.esm` and `1B5EBB:Fallout4.esm`).

### B. Vault 111 Lighting Off
1. **`XESP` (`enable_parent`) state ignored when writing `FO4Port.esm`:**
   - `Fallout4.esm` `Vault111Cryo` (`000016D8`) has `88` `XESP` references (`51` inverted `opposite = 1`), notably **`25` Pre-War `PreWarPlayerHouseLightCool*` lights (`0x000481D4`, initially disabled, `opposite = 0`)** and **`3` post-door/klaxon lights (`0x002075E4`, initially disabled, `opposite = 0`)**.
   - `Fo4Export` already exports `enable_parent` (`ReferenceExport.cs:51-55`), but `dotnet/PluginSpike/Program.cs` ignored it and kept all `25` Pre-War lights enabled alongside the post-war Vault lighting (`849 -> 132` merged omni placements).
2. **All Vault light colors/templates flattened in `PluginSpike` + `interiors_b10/lighting.json`:**
   - `Vault111Cryo` (`XCLL` + `LGTM 00036DCD` `Vault_CryoLT`: `ambient=[41,49,54]`, `dir=[21,33,43]`, `fog=[56,63,71]`, cool blue `VaultCryoAmb` `(156,179,209)`, `VaultCryoLightCool01NS` `(149,194,208)`, warm accent `VaultCryoUnderLight01NS` `(250,213,171)`) is overridden to `LIGHTING_TEMPLATE = 06BCF8` (`KreetBase01LGTtemplate`) + `LIGHT_MERGE_M = 3` (dropping lights inside 3 m regardless of color), with all active lights placed as one neutral white omni (`03D38C` `LGT_ShipInterior_Omni_NS_Neutral_2k`).

---

## 2. Implemented Fixes (Offline Pipeline & Writer)

Default `PluginSpike` behavior with no extra `lighting.json` keys stays **byte-identical** so existing `cd03411a` parity checks remain green. The new fixes operate as follows:

1. **`src/fo4sf/pipeline.py` & `src/fo4sf/convert_static.py`:**
   - `parse_ni_alpha(src, s.alpha_ref)` decodes `NiAlphaProperty` blend/alpha-test bits + threshold (`<HB` at offset 12).
   - Inline `BSLightingShaderProperty` shapes carrying `SLSF1_DECAL | SLSF1_DYNAMIC_DECAL` (`0x0C000000`) or `NiAlphaProperty` alpha blend now route to `texture_set_material(..., decal=True)` (cloning `1LayerStandardDecal` via `DECAL_TEMPLATE_MAT` with `texdecals/` / `vatexdecals/aNN/` stems and vertex-alpha scaling).
   - Inline `NiAlphaProperty` alpha-test shapes (cutouts without decal/blend) route to `texture_set_material(..., alpha_test=True, alpha_ref=thresh)` (`texcutouts/` stem).
   - Planar decal shapes (`is_decal_material_path(mat)` with local Z span `< 0.01` FO4 units) pass `normal_offset_m = 0.002` to `convert_static.shape_to_mesh`, lifting decal quads `2 mm` along their vertex normal above coplanar floor/wall geometry.

2. **`dotnet/PluginSpike/Program.cs` (opt-in `lighting.json` switches):**
   - `RESOLVE_ENABLE_PARENTS = "1"`: computes initial disabled state across `enable_parent` chains (`parentDisabled ^ opposite`), sets `0x800` on disabled refs, and omits disabled lights before `LIGHT_MERGE_M` filtering.
   - `DEDUP_EXACT_REFS = "1"`: skips exact duplicate enabled non-light placements sharing `(baseFormKey, pos_cm, rot_crad, scale_milli)`.

---

## 3. Recommended `lighting.json` Config for Next `FO4Port.esm` / Vault 111 Rebuild

```json
{
  "*": {
    "LIGHTING_TEMPLATE": "006658",
    "IMAGE_SPACE": "122393",
    "LIGHT_MERGE_M": "2"
  },
  "Vault111Cryo": {
    "LIGHTING_TEMPLATE": "06BCF8",
    "IMAGE_SPACE": "122393",
    "LIGHT_MERGE_M": "2",
    "RESOLVE_ENABLE_PARENTS": "1",
    "DEDUP_EXACT_REFS": "1"
  }
}
```

**Note on runtime delivery:** Because `FO4Port.esm`, `FO4Port - Main.ba2`, and `FO4Port - Textures.ba2` live in the base interior port install rather than `candidate-2g`'s quest bundle, an offline interior rebuild (`convert_batch.py` + `PluginSpike` with the `lighting.json` settings above and schema-3 `Vault111Cryo.json`) is required to bake these updated NIFs/MATs and filtered/deduped Vault 111 `REFR`s into `FO4Port`. Follow-up work (per-FO4 `LIGH` color/radius port for interiors matching `fo4light.py` exterior light conversion) will bring back `Vault_CryoLT`'s cool blue vs warm accent contrast.
