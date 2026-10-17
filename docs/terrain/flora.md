# Flora: FO4 harvestable plants (FLOR) -> Starfield FLOR

Author: Grok, 2026-10-17. Status: **implemented, offline**. Listing + cluster + TerrainOverlays writer are on
`grok/flor-research` (PR #290). Nothing deployed; nothing run in game. Labels as in the other terrain docs:
**verified** = read from files, **supported** = hypothesis with evidence, **unresolved** = open. Owner playtest row
14 (Sanctuary melon plants placed as statics).

## What hangs today

`exterior.CONVERT_TYPES` includes `Flora`, so every placed FO4 plant is converted as a **STAT** (visuals only). Core
`selected.json` (`terrain_core64c_work_fix3`, read-only): **3,520** Flora references of **48** bases before
exclusion (2 initially-disabled refs dropped, so **3,518** / **47** in the writer; FloraInstituteGourdVine01
leaves), of 649,596 converted refs. They are not a promotion class (`objects.json` has containers / items /
activators / terminals / workshops / benches / doors / lights; no flora). Activating a melon does nothing.

Crop counts in that core (editor id contains the crop name): tato 320, mutfruit 328, gourd 251, corn 230, melon 199,
tarberry 134, razorgrain 106. Also wild / decorative flora (HubFlower 504, BloodLeaf 303, glowing fungus 345, ferns,
silt bean, carrot, brain fungus) and a handful of greenhouse planters (`GreenHsPlanter*`).

## Starfield FLOR (**verified**, Starfield.esm 1.16.244)

300 `FLOR` records in the top group. Harvest is still the `PFIG` ingredient plus `PFPC` seasonal production, the same
names FO4 uses.

| Kind | Count | Keyword | Typical `PFIG` |
|---|---|---|---|
| Organic plants | 169 | `FloraTypeOrganic` 00222E03 | `OrgCommonFiber` 000055AF or `OrgCommonNutrient_Seed` 00260DF2 |
| Inorganic deposits | 125 | `FloraTypeInorganic` 00222E04 | mineral MISC / LVLI |
| Of the organic set, farmable | 106 | also `OutpostCanDomesticate` 002AC11D | fiber or seed |

All 106 organic+domesticate records share:

- form version 32, flags 0
- model `Landscape\Flora\Flora01.nif`
- `PNAM` bytes `CC 4C 33 00` (the same marker colour TerrainOverlays writes on ACTI)
- `FNAM` 0, `JNAM` 0x0168 = 360 (the same activation angle as the ACTI majority)
- `PFPC` 100,100,100,100 (all seasons)
- `PRPS` one property `HandScannerPlantReproduction` (AVIF 0023E905) = 5.0
- keywords `OutpostCanDomesticate`, `FloraTypeOrganic`

Crop-shaped templates already exist: `FloraMaizeCrop01` 000EC886 / `02` / `03`, `FloraAkilaWheat01` / `02` / `03`.
Those six `PFIG` `OrgCommonNutrient_Seed`. `FloraBloodStoneTall` 000242F8 is the same shader/model family with fiber.

A typical plant also carries object-template blocks (`APPR`, `OBTE`, `OBTF`, `OBTS`, `STOP`) and fade (`FMAH` /
`FMIH` / `FMAG` / `FMIG`). Mineral deposits add `ANAM`, `BFCB`/`BFCE`, `FloraTypeGas`/`Liquid`/`Solid`.

Activate prompt: `ATTX` is a localization id on vanilla records (28041 on BloodStone). Workshops write an inline
`FULL` string; flora can do the same for the plant name.

## FO4 FLOR

`Fallout4.esm` is on this machine at the Steam depot path lights / workshops / benches already use
(`C:/Program Files (x86)/Steam/steamapps/content/app_377160/depot_377163/Data/Fallout4.esm`; **verified** exists,
330,745,373 bytes). A produce table is still **unresolved** as a product mapping: this writer and vanilla Starfield
`PFIG` take `MISC` / `LVLI`; FO4 harvest items are `ALCH`.

**Supported** (shared field names that Starfield still uses, CK / UESP naming, the 48 editor ids in `selected.json`):

- FO4 `FLOR` is the harvestable plant record. `PFIG` is the ingredient (usually `ALCH`), `PFPC` four seasonal
  percentages, `MODL` the plant, `FULL` the name, `SNAM` a harvest sound.
- Almost every FO4 flora is harvestable (the record type is the harvest). HubFlower / BloodLeaf / ferns give flower
  or herb items; `FloraWildMelonVine01` / `FloraMelonVine01` are the Sanctuary melons of row 14.
- FO4 workshop food resources are a separate workshop-layer on some of these bases; outpost domestication is the
  Starfield analogue (`OutpostCanDomesticate`), not required for a one-shot harvest.

## Path (built; overlay not run in game)

Same shape as [stations.md](stations.md): one native Starfield base per FO4 base; the REFR keeps its slot.

```
python scripts/terrain/make_cluster.py flora --work <core64c work> --build <core64k> --out flora.json
python scripts/terrain/make_cluster.py merge --out cluster.json ... flora.json
python scripts/terrain/make_core64c.py stage ... --cluster cluster.json
```

1. **`make_cluster.py flora`** lists every placed FO4 `Flora` reference (band export type `Flora` ∩ `objects.json`
   unpromoted refs). One entry per reference: `src`, FO4 base editor id, converted model, name (humanized editor id
   until `export-names` / FO4 `FULL` is available), `slot`. Optional `--table` later maps FO4 base -> Starfield
   ingredient; without it every plant uses the maize crop's seed (`00260DF2:Starfield.esm`).
2. **`make_core64c.py stage --cluster`** (`cluster_flora` + `cluster_promote`): edid `FO4Core_flor_<6 hex>_<plugin>`,
   converted model, name, ingredient form; `reference_index` on the same unpromoted list as the other classes. A
   source in two classes is refused.
3. **`TerrainOverlays`** writes one `FLOR` per edid after the workshop ACTI block (new signature, so it does not
   share an ACTI pool). Clone vanilla `FloraMaizeCrop01` (crop template): keep its keywords, `PNAM`/`FNAM`/`JNAM`,
   `PFPC`, scanner `PRPS`, object-template and fade fields; replace `EDID`, `FULL`, `MODL`, `PFIG`. Each REFR is
   temporary in its reserved slot, `NAME` = that FLOR. `formids.json` `"flora": {src: {"base", "ref"}}`.
4. **`check`**: slots retained; `FLOR` count = distinct flora edids; every flora REFR names that FLOR; the FLOR has
   `FloraTypeOrganic`, `PFIG` the declared ingredient, `MODL` the converted model. Against `Starfield.esm`: the
   ingredient exists (MISC or LVLI).

Mutagen 0.55.0-alpha.67 `Flora.Ingredient` **does** write `PFIG`: the default seed `00260DF2` and a custom MISC
(`000055AF`) both serialize; a STAT ingredient is refused before the plugin is published. `IHarvestTarget` is
`MiscItem` and `LeveledItem`, which matches the vanilla `PFIG` targets. No byte patch is needed for these cases.

## Why not the other shapes

- **Vanilla Starfield flora at the slot** (the bench pattern): the maize crop mesh is `Flora01.nif`, not a melon.
  Row 14 is a look problem as well as a harvest problem.
- **ACTI + VMAD additem**: workshops opened build mode with **no** script. Harvest is already a native FLOR
  activate. A script is extra moving parts.
- **Outpost farming first**: `OutpostCanDomesticate` is on the template so a cloned crop stays a crop; whether our
  overlay's temporary REFRs domesticate is **unresolved** and not the row-14 bar. The bar is activate -> item.

## Open

- FO4 `PFIG` per base (needs `Fallout4.esm`). Until then every plant yields `OrgCommonNutrient_Seed`.
- Harvest animation / hide-until-reset on a converted FO4 NIF (**unresolved** in game). Claude looks after a
  scratch overlay with one Sanctuary melon.
- `GreyscaleToPalette_Alpha`, vertex-colour V, and row 13 walls are not this class.
- Do not reconvert into the pinned `core64k` / `work_fix3` trees.
