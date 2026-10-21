# Red Rocket crash: outside research and a new lead (2026-10-21)

Author: Claude-cloud. Companion to red-rocket-crash-bisect.md (the Bugs thread owns the bisect). Labels as in
docs/ai/research-log.md.

## Public sources
- No public report, crash-log table or Address Library entry names Starfield.exe+0x2bf016b in 1.16.244. Crash Logger
  for Starfield (github.com/0xra0/sf-crash-logger) gives Address Library ids, not function names, and keeps no address
  table. Searches of Nexus, Steam and GitHub found only generic Starfield crash threads. **Verified** (searched
  2026-10-21; absence of evidence, not evidence).
- BACUP (github.com/Bryant-21/bacup) still lists only fo76, fnv/fo3 and skyrimse to fo4 as wired pairs. Its fo4 to
  Starfield pair is record-only: no meshes, collision, door rigs or actors, and no in-game evidence (bacup-comparison.md,
  re-read 2026-10-21). Its one crash note is "a dangling teleport can crash cell loading". BACUP did not meet this crash.
  **Verified.**

## What the dump itself says (C:\Modding\scratch\dumps_v6e_154433.json, read only)
- The faulting thread's stack is shallow: the thread-start frames (kernel32+0x2dda7, ntdll+0xc9c5c) sit 0xe98 to 0xec8
  above rsp. So it is a worker thread, not the main thread. Its slots also hold stale D3D12Core, nvwgf2umx and
  sl.interposer (NVIDIA Streamline) pointers, so the thread has done GPU submission work (**supported hypothesis**: a
  render or job thread).
- The read target 0x19a87db9280 is a heap-range address that is not mapped, next to the float 0.02 in rcx. A pointer
  read from memory that was freed or reused fits that better than a bad value in a file (**supported hypothesis**).

## The faulting instruction (--exe read on the PC, 2026-10-21, minidump_read at 3a28329)
Disassembled here from the 96 code bytes the PC returned (capstone), **verified**:
```
+0x2bf0161  mov rcx, rax
+0x2bf0164  mov rax, [rsi+0x340]        ; a table of pointers, held in a stack-local struct (rsi = rsp+0x4e0)
+0x2bf016b  mov rdx, [rax+rcx*8]        ; FAULT: rcx = 0x3ca3d70a
+0x2bf016f  mov rax, [rdi]
+0x2bf0172  cmp rdx, rax
            ...
+0x2bf0181  lock xadd [rdx+0x10], eax    ; take a reference on the entry
```
- The read target is exactly table + index * 8: 0x198a2bcda30 + 0x3ca3d70a * 8 = 0x19a87db9280. So the table pointer
  is good; the **index** is the float 0.02's bit pattern. The function looks up a ref-counted entry by index and stores it
  in the smart pointer at [rdi] (fault function starts at +0x2bf00f0; caller +0x2bda63c in +0x2bd9dd0).
- This revises the read above: a float stored where a 32-bit index is expected (a field-layout mismatch, or a struct whose
  memory was reused) rather than a stale table. Where the index came from is before the window; `--code-before -1`
  prints the whole function from +0x2bf00f0. Object types need a full dump (-ma, owner's call).

## The whole fault function (--code-before -1 on the PC, minidump_read at ccec077)
Disassembled here, **verified** (Starfield.exe+0x2bf00f0, 123 bytes before the fault):
```
mov rdi, rdx ; mov rsi, rcx              ; rsi = a load context (a stack object of the caller), rdi = the out pointer
mov rbx, [rcx+0x358]                     ; the context's stream
mov r8d, 4 ; lea rdx, [rsp+0x30] ; mov rcx, rbx ; call [vtable+0x28]   ; read 4 bytes
add [rbx+8], rax                         ; advance the stream position
mov eax, [rsp+0x30] ; cmp eax, -1 ; jne  ; -1: clear the out pointer, return
mov rcx, rax ; mov rax, [rsi+0x340] ; mov rdx, [rax+rcx*8]   ; FAULT: objects[index]
... lock xadd [rdx+0x10], eax            ; take a reference, store in the out pointer
```
This is a link-id reader: read a 4-byte object index from a stream (-1 = none) and resolve it against the table of
objects already read, the way a NIF stream resolves block references. **Supported hypothesis:** a file the game is
loading on a worker thread (models load on background threads as cells stream in) has the float 0.02 where the reader
expects a reference, i.e. its layout differs from what the engine reads by at least one field. That moves a converted
file (most likely a NIF) to the top, ahead of the mission's actor moves. One converted value is exactly 0.02 by
construction: `convert_static` clamps a door leaf's box-collision half-extent to `max(0.02, ...)`, so a thin leaf (the
counter door's flap, a safe door) gets 0.02 in its bhkPhysicsSystem blob. Whether the game reads that blob through this
reader is not known.

`scripts/game/nif_float_scan.py` (this PR) lists every NIF and block holding 0x3ca3d70a, and flags box half-extents.

## Scan result (PC, 2026-10-21, nif_float_scan at 0bf3ea0, read only; reported by Install through the coordinator)
- 6 of 11,768 converted NIFs hold 0x3ca3d70a, every one a door leaf's box-collision half-extent in bhkPhysicsSystem
  (the 0.02 clamp): bldgmetalgaragedoorcoma, bldcounterdoor01, switchdoorexsmlatch01 and 02, safedoor01,
  fancycuriodoors01. Within 250 m of Red Rocket and of the museum door, only **bldcounterdoor01**, in both areas.
- v6h's counter door still has a 0.02 half-extent (block 9 +544, hx); v6e had it in blocks 7 and 11.
- **Supported hypothesis:** a clamped (thin) box, not door boxes in general, is the trigger: thick leaves would give
  other rcx values, and every dump has exactly 0.02. Next: raise the clamp floor, gate the build on 0 scan hits, then
  the Red Rocket arrival test; Card D (mission off) as the control.

## Earlier lead: the mission script moves actors exactly where the crashes happen
**Verified from source** (scripts/mission/FO4SF_Min00Quest.psc, Relocate, KeepCodsworth, MoveOver):
- FO4SFMission's start-game-enabled quest checks every second (Codsworth every CodsworthCheck = 5 s, and still after stage 200) and
  MoveTo's Preston, the raiders and Codsworth from their unmerged local spot into the merged world when the player is
  within RelocateRadius 800 m of the actor's merged spot.
- Red Rocket's cell (-17, 19) centre is 237 m from Codsworth's spot and 207 m from Preston's (core-local coordinates,
  same offset), so arriving at Red Rocket triggers those moves within a few seconds. The museum crashes (7 s after
  stage 30, 21 s after completion, and after the fight on v6c) are at the same actors.
- The Oct 15 Red Rocket to Sanctuary walk PASS (core64d) predates the mission plugin (Oct 18).
- Actors already snap back to their editor spot as cells reload (Preston 5 times, Codsworth twice, when-freedom-calls.md),
  so the engine is holding persistent actors across the base world and its runtime merged instance.
- **Supported hypothesis, not tested:** moving persistent actors between the base world and the runtime merged world
  (or the Garden Mini Bot body, or the raider fight) leaves an object freed while a worker thread still uses it.

## Ranked suspects and cheap tests (revised after the function read)
1. A converted NIF with the float 0.02 where a reference is read. Test, read only and offline: `nif_float_scan.py` over
   the v6e core's converted meshes, with `--names` from near_redrocket.jsonl's models and again for the museum's
   cells. A model on both lists, or a door rig with a 0.02 half-extent, is the prime suspect. Then v6h (no rig on the
   counter and safe doors) tests it in game; if a box half-extent is the hit, raising the clamp is a cheaper variant.
2. Mission actor moves (FO4SFMission): Card D, mission off, three Red Rocket arrivals. Still worth running: if the game
   stays up with the mission off, the stream is not a mesh after all (a save or reference-handle stream).
3. A full dump (-ma, about 18 GB, owner's call) on the next crash: the stream object at [rsi+0x358] names the file.
4. Load-door VMAD targets and teleports (BACUP's note): low.
5. NVIDIA Streamline: low.
