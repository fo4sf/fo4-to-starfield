# WS0a Decision Note: Category Tabs and Bench-Base Routing (Design Only)

- **Scope:** Round 14 `WS0a` (`gemini/r14-workshop`, stacked on `#852`).
- **Rule 12 status:** Pending owner / build-lead approval. **No default changed in this note.**
- **Labels:** `VERIFIED` = directly inspected in repository code or `Starfield.esm`; `UNVERIFIED` = in-game runtime behavior awaiting `P18` / Tier-1 run.

---

## 1. Build-Menu Tab Routing (`C` / `B` / `A`)

Today `#852` (`dotnet/WorkshopCore/Program.cs:804-805`) appends `FO4SF_WorkshopCategorySanctuary` (`KYWD 0x000848`) to two vanilla `FormList` overrides (`FLST 0x058606` `OutpostRecipeCategories` and `0x1A5507` `OutpostFollowCameraCategoryList`), which conflicts with zero-vanilla-override layering (`docs/core/port-requirements.md:24`).

| Route | Mechanism | Vanilla Override? | Dependencies | Recommendation |
|---|---|---|---|---|
| **Route C** (Workbench keyword + Starfield filter fallback) | Tag settlement benches with `WorkshopKeyword` (`0x054BA7`) + our own workbench keyword; file FO4 recipes under Starfield's existing category filters read from `FLST 0x058606` (`OutpostCategoryStructures`, `OutpostCategoryFurniture`, `OutpostCategoryMiscellaneous`, etc., **VERIFIED** 15 entries in `Starfield.esm`) with our workbench keyword as `BNAM`. | **Zero vanilla overrides** | Runtime proof from **P18** (`FO4SFWorkshopProbe.esm` staged for owner/Claude run) that `WorkshopMenu` scopes recipes strictly by bench `BNAM` even when `FNAM` reuses a vanilla category filter. (**UNVERIFIED**) | **RECOMMENDED IF P18 PASSES** |
| **Route B** (SFSE in-memory `FLST` append) | Keep `FO4SFWorkshop.esm` free of `FLST` overrides and patch `OutpostRecipeCategories` (`0x058606`) in memory via an SFSE plugin after `Starfield.esm` loads. | Zero ESM overrides | Unbuilt SFSE native hook targeting Starfield's loaded `BGSListForm` array (**UNVERIFIED**; version-coupled to `Starfield.exe` updates). | Fallback if **P18** shows `WorkshopMenu` merges recipes across `WorkshopKeyword` regardless of `BNAM`. |
| **Route A** (`#852` `fix4` `FLST` overrides + conflict checker) | Keep the two `FLST` overrides (`0x058606`, `0x1A5507`) in `FO4SFWorkshop.esm`, keep `HeaderFlag.Localized` cleared and `FULL` stripped (`fix4` `E6` fix), and add a launcher/installer load-order compatibility warning if another mod overrides either `FLST`. | Overrides `0x058606` & `0x1A5507` | Works in `fix4` (**VERIFIED** offline; clean-bench placeable runtime check `WS0-14` still **UNVERIFIED**). Lowest isolation across external outpost mods. | Least preferred long-term; kept unchanged until `P18` runs. |

---

## 2. Workbench Base Ownership (`0x0A2ECD` & FO4 `00246F86`)

- **Constraint (`VERIFIED`):** `scripts/terrain/make_core64c.py:3302` enforces `masters == ["Starfield.esm"]` on `FO4TerrainCore*.esm`. `FO4TerrainCore*.esm` **cannot** master `FO4SFWorkshop.esm` or embed `FO4SF_*` keywords without breaking core self-containment.
- **Recommended route — Title-Layer FO4 Workshop Overlay Plugin (`FO4SF_WorkshopTitleOverlay.esm` / per-core variant or stacked after `#858`):**
  - Masters `Starfield.esm`, the active terrain core (`FO4TerrainCore.esm` / variant, or unified host `#858`), and `FO4SFWorkshop.esm`.
  - Overrides **only** our own core bench activator bases (`ACTI 0x0A2ECD` and any base emitted from FO4 `00246F86`) to strip unwanted vanilla `OutpostCategory*` keywords and attach our FO4 workbench keyword. Never overrides `LCTN`, `STDT`, `PNDT`, or vanilla `Starfield.esm` forms.
  - Core plugins stay cleanly mastered to `Starfield.esm` only, while all 29 core bench `REFR`s inherit the base change cleanly without touching terrain cell data.
- **Alternative (Claude's terrain-core master change):** Add a workshop-keyword master dependency or inject our keyword directly in `FO4TerrainCore*.esm` builders. Larger blast radius because every terrain build and `make_core64c.py` master contract would change across variants.
