# Materials, textures, decals and lights (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

This is a mechanism summary. Verified project work it builds on:
[S3-materials.md](../../spikes/S3-materials.md) (texture formats, the `.mat` component database, in game),
[S1-mesh-writer.md](../../spikes/S1-mesh-writer.md) (the NIF names its material by path; `MaterialID` CRC32),
[FORMAT-GAP.md](../../FORMAT-GAP.md), docs/JOURNAL.md 2026-10-08 (glass, interior lighting, metalness fix, decals) and
2026-10-17 (greyscale palettes, two-sided vines), docs/terrain/exterior-lights.md (FO4 LIGH to Starfield LIGH field
table). The breadth plan for lighting is [../next-phase/lighting.md](../next-phase/lighting.md): this file does not
repeat it. Record layouts are **verified with xEdit** (`wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`, dev-4.1.6)
unless marked otherwise.

## In short
- **Materials are a rebuild.** FO4 has 7,077 `.bgsm` + 295 `.bgem` files (spec / gloss); Starfield ships one compiled
  `materials/materialsbeta.cdb` and also loads loose `.mat` JSON component files (PBR: albedo, normal, roughness,
  metal, AO, opacity) (**verified**, FORMAT-GAP.md, S3). The port clones a vanilla `.mat` per FO4 material on the
  player's PC (**verified** in game).
- **Material swaps change model**: FO4's MSWP (path-to-path swaps, colour remap index) is FO4-only; Starfield uses
  LMSW "layered material swap" records (12,966) whose body is an opaque reflection blob (**verified**, xEdit). Verdict:
  **rebuild** (generate LMSW or bake swapped materials); LMSW content is **unresolved**.
- **Decals change model**: FO4 decals are texture sets (TXST + decal data) and alpha-blended shapes; Starfield adds
  PDCL projected decal records that point at a MTPT material path (**verified**, xEdit). The port turns FO4 blended
  overlays into `1LayerStandardDecal` materials (**verified** in game, Vault 81 placards).
- **Lights translate with a physical scale**: Starfield LIGH adds colour temperature (K), luminous power (lm), light
  type, barndoors and light layers (**verified**, xEdit). The port maps FO4 fade and radius to lumens (**supported
  hypothesis** rule, looks good in game per the owner).
- **Image spaces do not translate field by field**: FO4 IMGS is a plain struct, Starfield IMGS is a reflection blob
  (**verified**, xEdit). Use vanilla Starfield image spaces by cell family (lighting note).

## How Fallout 4 does it

### Material files and NIF shaders (verified, S3 and journal)
- A shape's `BSLightingShaderProperty` names a `.bgsm` (or carries an inline `BSShaderTextureSet`); effects use
  `BSEffectShaderProperty` with a `.bgem` or inline textures (glass, glow, frost, dust).
- Maps: `_d` colour (DXT5 / BC1, sRGB), `_n` normal (BC5 `BC5U`), `_s` specular (R) + smoothness (G), plus glow,
  environment / cube maps, greyscale-to-palette gradients (`bGrayscaleToPaletteColor`, BGSM byte 62; NIF flags1 bit
  0x10; journal 2026-10-17).

### Records
| Record | Key fields (verified, xEdit) | Count |
|---|---|---:|
| TXST texture set | `TX00` diffuse, `TX01` normal / gloss, `TX03` glow, `TX04` height, `TX05` environment, `TX02` wrinkles, `TX06` multilayer, `TX07` smooth spec; `DODT` decal data; `DNAM` flags (No Specular Map, Facegen Textures, Has Model Space Normal Map); `MNAM` material path | 382 |
| MSWP material swap | record flag Custom Swap; `FNAM` tree folder; per substitution `BNAM` original material, `SNAM` replacement, `CNAM` colour remapping index. Used by REFR `XMSP`, model `MODS` (and `MO2S`-`MO5S` on biped / world models), destruction models `DMDS` | 2,537 |
| MATO material object | FO4-only (**verified** counts); shader data for directional materials (snow, moss): **supported hypothesis** | 26 |
| LIGH light | `DATA` time, radius (u32 units), colour, flags (Can be Carried, Flicker, Off By Default, Pulse, Shadow Spotlight, Shadow Hemisphere, Shadow OmniDirectional, NonShadow Spotlight, Non Specular, Attenuation Only, NonShadow Box, Ignore Roughness, No Rim Lighting, Ambient Only), falloff exponent, FOV, near clip, flicker period / amplitudes, constant / scalar / exponent, god rays near clip, value, weight; `FNAM` fade; `NAM0` gobo; `SNAM` sound; `LNAM` lens; `WGDR` god rays | 801 |
| IMGS image space | `ENAM` data, `HNAM` HDR, `CNAM` cinematic, `TNAM` tint, `DNAM` depth of field, `TX00` LUT | 293 |
| IMAD image space adapter | animated image-space changes | 247 |
| CELL `XCLL` | ambient, directional, fog colours and distances, directional fade, fog power / max, **ambient colour cube**, light fade begin / end, **Inherits** flags (which fields come from the template), height fog | per interior |
| LGTM, LENS, GDRY, EFSH | lighting templates 66, lens flares 35, god rays 61 (FO4-only), effect shaders 63 | |
| REFR light fields | `XRDS` radius delta, `XLIG` FOV / fade / end cap / shadow bias / near clip / volumetric, `XEMI` emittance (**verified**, fo4light.py) | |
| REFR `XPDD` | projected decal width / height scale | |

## How Starfield does it

### Material files (verified, S3, S1, journal)
- `.mat` is JSON: a component database (`Objects` with `res:` ids, `Edges`, typed `Components`) plus an informational
  `Summary`. The engine reads the components, not the Summary (journal 2026-10-08 metalness fix).
- Texture-replacement slot map: 0 albedo, 1 normal, 2 opacity, 3 roughness, 4 metalness, 5 AO (**verified**, journal).
- Formats: `_color` BC1 sRGB (DX10 header), `_normal` BC5 SNORM, `_rough` BC4 UNORM (1 = rough); metalness a
  constant or map (S3).
- Shader models seen: single-layer PBR, `1LayerStandardDecal` (1,133 vanilla mats), `1LayerEffectGlassNoFrost`,
  `TwoSided1Layer` (journal). Layered materials (several layers blended by masks) exist; the project has not decoded
  how layers are authored (**unresolved**).
- The NIF's shader block is just the `.mat` path; `NiIntegerExtraData "MaterialID"` = CRC32 of the lowercase path
  (S1). The Creation Kit reads loose `.mat` with `bUseCompiledDB=0` (docs/RISKS.md; **supported hypothesis**).

### Records (verified, xEdit; counts sf_esm.json)
| Record | Same as FO4 | Changed / new | Count |
|---|---|---|---:|
| TXST | TX00 diffuse, TX01 normal, DODT, DNAM flags, MNAM | slots `TX08` metal, `TX09` rough, `TX17` AO, `TX19` opacity; glow / height / env / wrinkle slots not seen; flag Default To Box Decal | 23 |
| LMSW layered material swap | (replaces MSWP) | body is `REFL` reflection data; used by REFR `XLMS`, model `MOLM`, biomes (`NAM1`), pack-ins, skin swaps | 12,966 |
| MTPT material path | new | `REFL` reflection data; PDCL's `DODT` points at it | 877 |
| PDCL projected decal | new | `DODT` material (MTPT), `DATA` min / max width and height, depth, cutoff angle; IPCT lists PDCLs | 706 |
| LIGH | time, radius (now float), colour, Can be Carried, Off by Default, falloff, FOV, near clip, flicker, gobo, lens | `DAT2`: flags Disable Specular, Disable Distance Attenuation, Is Direct Spotlight, Use PBR Value, Focus Spotlight Beam, Externally Controlled; shadow offset, inner FOV, **PBR temperature (K)**, **luminous power (lm)**, **light type** (Omni, Shadow Spotlight, NonShadow Spotlight), flicker type (None / Flicker / Pulse), adaptive lighting (EV100 min / max), radius falloff exponent; `FLBD` barndoors; `LLLD` light layer (default, helmet light, ship interior / exterior); volumetric scale; Wwise sound. No god-rays link, no shadow omni / hemisphere flag | 1,575 |
| IMGS | | `REFL` reflection data + `RFDP` reflection parent | 232 |
| CELL `XCLL` | ambient, directional, fog colours and distances, fog power / max, light fade, height fog | offset 28 is **Gravity Scale** (FO4: directional fade); no ambient cube; no Inherits flags; adds Interior Type (Interior, Ship Cell, Space Cell, PackIn, Instanceable) | |
| LGTM | DATA lighting struct | | 6 |
| REFR light fields | `XRDS`, `XLIG` (FOV, luminous scale, end cap, near clip, inner FOV, shadow offset), `XEMI` | `XLFD` flicker, `XLBD` barndoors, `XLCD` colours, `XLSM` static shadow map, `XLLD` layer, `XLVD` volumetric, gobo animation | |
| REFR `XPDD` | width / height scale | `XPDO` projected decal references | |

## Mapping for the port

| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| `.bgsm` colour / normal / spec-gloss | cloned `.mat` + BC1 / BC5 / BC4 DDS | rebuild (automatic) | done; metalness constant 0 |
| `.bgem` glass | glass `.mat` clone | rebuild | done (opacity 0.15) |
| `.bgem` glow, animated effects, emissive maps | emissive / effect `.mat` | rebuild | **not done**: glowing signs, strobe, oil puddle skipped |
| Greyscale-to-palette | baked into the colour map | rebuild | done (journal 2026-10-17) |
| Alpha test, two-sided | `TwoSided1Layer` clone with opacity | rebuild | done |
| Alpha-blended overlays, effect grime | `1LayerStandardDecal` clone | rebuild | done; FO4 gradient palettes on stains not reproduced |
| TXST on models | `.mat` per texture set | rebuild | done ("texture-set materials", journal 2026-10-08) |
| TXST as impact decal (IPCT DNAM) | PDCL + MTPT | rebuild | not done; needs a way to write MTPT |
| MSWP / XMSP / MODS | LMSW / XLMS / MOLM, or a baked `.mat` per swap | rebuild | not done; baking a converted material per used swap needs no LMSW decoding |
| CNAM colour remapping index | Starfield `MODS` colour remapping index (float on models) | translate | **supported hypothesis**: same idea, not tested |
| LIGH | LIGH | translate | done for exteriors (fo4light.py); interiors use vanilla omnis plus FO4 lights |
| FO4 shadow omni / hemisphere, god rays | none | drop | 10 Commonwealth refs carry them (exterior-lights.md) |
| IMGS, IMAD | vanilla Starfield IMGS / IMAD | substitute | today one image space for every interior |
| XCLL, LGTM | XCLL / LGTM | translate with care | different layout; whether the engine honours a per-cell XCLL is **unresolved** |
| EFSH | EFSH | translate | not surveyed |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild: emissive and animated materials, material swaps, impact decals (PDCL / MTPT), image spaces, layered
  materials if FO4's multi-layer looks (snow, moss MATO) are wanted.
- CK2: the safe way to author new LMSW or MTPT records may be the Creation Kit, since their bodies are reflection data
  xEdit does not decode (**supported hypothesis**). Loose `.mat` files need no CK. SFSE: none known.

## Port status and links
- **In game (verified):** textured chair (S3, 2026-10-07); Vault 111 colours after the metalness and tint fixes, glass
  in cryo pods, Vault 81 decal placards, interiors lit with a fixed template, image space and cubemap (journal
  2026-10-08; owner 18 Oct "Lighting looks fine"); exterior FO4 lights "look really good" (lighting note).
- **Offline only:** greyscale palettes, two-sided vines, wall stains as decals.
- **Not done:** emissive / glow, material swaps, impact decals, per-cell lighting, weathers.
- Plan: [../next-phase/lighting.md](../next-phase/lighting.md). Related:
  [weather-time-climate.md](weather-time-climate.md) (exterior light and weather),
  [physics-and-collision.md](physics-and-collision.md) (IPCT, MATT).

## Open questions and cheap checks
- Dump one vanilla LMSW and one MTPT `REFL` blob next to the `.mat` they name (xEdit or a raw walk) to see whether a
  generated record is feasible.
- Count the FO4 MSWPs actually used by placed refs in the cells we build (Fo4Export `XMSP`, model `MODS`).
- List vanilla emissive `.mat` files in ContentResources.zip (grep for an emissive component) to pick a template.
- Does a per-cell XCLL change a Starfield interior (one test cell with an extreme ambient colour)?
- Which FO4 cells use MATO directional materials (xEdit references of the 26 MATOs)?

## Sources
- xEdit dev-4.1.6: `wbDefinitionsFO4.pas` CELL XCLL 5994, TXST 6984, IMGS 7393, LIGH 9871, MSWP 12437, model MODS 4250;
  `wbDefinitionsSF1.pas` CELL XCLL 10633, LIGH 13795, LGTM 13758, LMSW 13902, MTPT 14747, PDCL 15829, IMGS 12712, TXST
  18430, IPCT 13147, REFR XLMS 8994, model MOLM 7000.
- Repo: docs/spikes/S3-materials.md, S1-mesh-writer.md, docs/FORMAT-GAP.md, docs/RISKS.md, docs/JOURNAL.md
  (2026-10-07, 10-08, 10-17), docs/terrain/exterior-lights.md, src/fo4sf/convert_material.py, pipeline.py, fo4light.py;
  docs/measurements/fo4_esm.json, sf_esm.json.
- Plan: [../next-phase/lighting.md](../next-phase/lighting.md).
