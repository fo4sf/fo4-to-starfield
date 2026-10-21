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

## New lead: the mission script moves actors exactly where the crashes happen
**Verified from source** (scripts/mission/FO4SF_Min00Quest.psc, Relocate, KeepCodsworth, MoveOver):
- FO4SFMission's start-game-enabled quest checks every second (Codsworth every 2 s, and still after stage 200) and
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

## Ranked suspects and cheap tests
1. Mission actor moves (FO4SFMission). Test A, read only: the fo4sf_mission.*.log of the 15:44:33 and 16:38 sessions;
   look for `world`/`moved` lines in the 30 s before each crash. Test B, no build: plugin_toggle.py holds FO4SFMission off,
   repeat the Vault111Cryo to Red Rocket move three times, wait 60 s each. Stable means the mission; then split
   Codsworth (`write --no-codsworth`) from Preston and the raiders.
2. Name the faulting object. `minidump_read.py --exe <Starfield.exe>` (this PR) prints the code bytes and function start
   at the fault, which stack entries follow a call, and the C++ class (RTTI) of every object a register or stack slot
   points at, when the dump holds it. An Actor, a Character or an animation-graph class there supports suspect 1; a
   geometry or skin class supports suspect 3.
3. Counter and safe door rigs (v6h, the bisect's next step): costs a resumed build; run after A and B.
4. Load-door VMAD targets and teleports near Red Rocket (BACUP's dangling-teleport note): a cell-load crash would come
   at the load, not 15 s later, so low.
5. NVIDIA Streamline (DLSS or frame generation) on that thread: a general Starfield crash source, but the fault is in
   Starfield.exe at the same offset every time, so low; one run with frame generation off is the owner's call.
