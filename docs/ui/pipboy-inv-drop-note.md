# Pip-Boy `INV` Drop (`RemoveItem` Slot `0x8B`) & `DATA` `WorkshopsList` Note

## 1. `TESObjectREFR::RemoveItem` Virtual Slot & `RawRemoveItemRequest` Layout (`A13`)

`DropInvItemMainThread` in `sfse/FO4SFPipboyMenu/src/main.cpp` invokes `RE::TESObjectREFR::RemoveItem` only when `InvDataAnswers=1` (default `0`).

### Source Citation (`CommonLibSF` `9d090c4c521f4f2c1aa00bb05923c380d47ae596`, Starfield `1.16.244.0`)

- **Primary `RE::TESObjectREFR` vtable slot `0x8B` (`kRefrRemoveItemSlot = 0x8B`):**
  - Declared in `include/RE/T/TESObjectREFR.h` (line `201`):
    ```cpp
    virtual void RemoveItem(std::uint32_t& a_outHandle, const RemoveItemRequest& a_request); // 08B
    ```
  - Verified at runtime before calling: `CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)`, `InImage(primaryVt, (kRefrRemoveItemSlot + 1) * 8)`, and `InImage(removeFn, 1)`.

- **`0x40`-byte `RE::RemoveItemRequest` (`RawRemoveItemRequest`, `static_assert(sizeof == 0x40)`):**
  - Declared in `include/RE/T/TESObjectREFR.h` (lines `50-62`, `102-115`):

| Offset | Field | Type | Value Passed by `DropInvItemMainThread` |
| :--- | :--- | :--- | :--- |
| `+0x00` | `object` | `TESBoundObject*` | `objForm` (RTTI-checked `TESBoundObject@@` + concrete item `formType`) |
| `+0x08` | `instanceData` | `BSTSmartPointer<TBO_InstanceData>` | `0` (`nullptr`) |
| `+0x10` | `extra` | `ExtraDataList*` | `nullptr` |
| `+0x18` | `inventoryIndex` | `std::int32_t` | `target.invIndex` |
| `+0x1C` | `count` | `std::int32_t` | `std::min(a_count, target.count)` (`>= 1`) |
| `+0x20` | `reason` | `ITEM_TRANSFER_REASON` (`std::uint32_t`) | `3` (`ITEM_TRANSFER_REASON::kDropping`) |
| `+0x24` | `pad24` | `std::uint32_t` | `0` |
| `+0x28` | `moveTo` | `TESObjectREFR*` | `nullptr` |
| `+0x30` | `dropLocation` | `NiPoint3*` | `&worldPos` (`3` finite floats read from `player + kPositionAt` `+0x8C`) |
| `+0x38` | `dropRotation` | `NiPoint3*` | `&worldRot` (`3` finite floats read from `player + kAngleAt` `+0x80`, or `nullptr`) |

### Concrete Item `formType` Gate & Verification Card Boundary

- Before calling slot `0x8B`, `DropInvItemMainThread` reads `RE::TESForm::formType` (`+0x2E`) and requires `IsDroppableItemFormType(formType)` to match a concrete inventory item record type (`0x22 ARMO`, `0x23 BOOK`, `0x26 INGR`, `0x28 MISC`, `0x30 WEAP`, `0x31 AMMO`, `0x35 KEYM`, `0x36 ALCH`, `0x39 NOTE`, `0x3D SLGM`, `0x98 OMOD`, `0x9F IRES`), refusing non-item `TESBoundObject` subtypes (such as statics, activators, furniture, or doors).
- `DropItem` (`step=inv_drop`) remains withheld from Lead Verification Card D until tested separately on a throwaway item in game.

---

## 2. `DATA` Tab `WorkshopsList` Status (`PLACEHOLDER`)

- `WorkshopsList` on the Pip-Boy `DATA` page (`CollectQuestAndStatsMainThread` in `sfse/FO4SFPipboyMenu/src/main.cpp`) is an explicit **static placeholder** (`"Sanctuary Hills (Placeholder)"` when `FO4SFWorkshop.esm` is loaded) so the ActionScript `Workshops` sub-tab renders without undefined-member errors; it does **not** read live settlement population, happiness, or resource counts yet.
