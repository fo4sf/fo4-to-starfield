# FO4SFCombat (`FO4SFCombat.dll`)

Minimal SFSE sidecar for `FO4SFCombat.esm` (`docs/combat/combat-core.md`).

Watches two configurable virtual keys (`VatsKey=0x56` `V` and `AmmoKey=0x4E` `N` in `FO4SFCombat.ini`) while Starfield is the foreground window and queues zero-argument static calls on the main thread via `IVirtualMachine::DispatchStaticCall` (slot `0x2F`):

- `FO4SF_CombatInput.OnVatsKey()`
- `FO4SF_CombatInput.OnAmmoKey()`

Checks runtime `1.16.244.0`, PE32+ image bounds, `versionlib-1-16-244-0.bin` (`format 5`), `GameVM` and `VirtualMachine` RTTI, and `IVirtualMachine` vtable slots `0x00..0x2F` before any call into the game.
