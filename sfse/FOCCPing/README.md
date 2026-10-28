# FOCCPing: the B0 bridge spike for SFSE

The plugin half of B0 (`docs/combined-core-cpp-port.md`, section 4; runbook `docs/spikes/combined-core-probes.md`,
section B0): can a quest script call our SFSE plugin and read its answer on Starfield 1.16.244? One Papyrus native,
`FOCC.Ping(int v)`, answers `v + 1`. The kit side (`scripts/combined_probes/FOCC.psc`, the declaration, and
`FOCC_B0.psc`, the console commands) is in the probe stage since #568. It is the owner's stack A (28 Oct 2026):
CommonLibSF as it is, the Address Library as a dependency, fixed where 1.16.244 breaks it; the plugin keeps no state
and is not the combined core's real plugin.

Nothing of Bethesda's, of SFSE's or of CommonLibSF's is in this folder. CommonLibSF (GPL-3.0 with its modding and
linking exceptions, `COPYING` and `EXCEPTIONS` in its repository) is built and installed on the PC from its own
clone at `9caec20`; this plugin links the installed library and includes its headers at build time only. The licence
review named in section 4 is owed before anything built on it ships; a spike dll ships nowhere.

## Files

| File | Role |
|---|---|
| `src/main.cpp` | the plugin: version data (Address Library, layout dependent, runtime 1.16.244), load, the Papyrus callback that binds `FOCC.Ping` |
| `src/Plugin.h` | name, author, version |
| `CMakeLists.txt` | the shared library against `CommonLibSF::CommonLibSF`; dynamic CRT to match the library's triplet |
| `build.ps1` | PC build: cmake + ninja in the loaded MSVC environment into a new staging folder; `build.json` with every sha256 |

`tests/test_sfse_ping_plugin.py` pins the contract between this folder, `FOCC.psc` and the runbook as text (no
compiler here).

## What it stands on (checked offline against CommonLibSF `9caec20`)

- `SFSE::Init` loads the Address Library before anything else: `Data\SFSE\Plugins\versionlib-1-16-244-0.bin` on
  Steam (`src/REL/ID.cpp`: `versionlib-<version with dashes>`, no platform suffix for Steam). A missing file stops
  the game with a message box naming the path. v22 of the Address Library for SFSE Plugins (Nexus 3256) covers
  1.16.244; the archive is on the PC (Install's state note, 24 Oct) and the file is installed by hand. One check
  before the launch: CommonLibSF `9caec20` reads address library format 2 only (`src/REL/ID.cpp`, `kDatabaseVersion`
  in `include/REL/ID.h`; another first word stops the game with "Unsupported address library format"), and SFSE's
  own `PluginAPI.h` names two libraries, "Address Library v1 (Nexus 3256)" and an "Address Library for 1.15.216+"
  (`kAddressIndependence_AddressLibraryV2`). So the `.bin`'s first four bytes must read `02 00 00 00`
  (`Format-Hex <path> | Select-Object -First 1` in Windows PowerShell 5.1, the first 16-byte row; `-Count` exists only
  from PowerShell 6.2); anything else is the other generation, a library finding before the hook is even reached, and
  goes on the card as such.
- `SFSE::SetPapyrusCallback` hooks the call inside `GameVM::GameVM` that binds everything to the script VM
  (`REL::ID(169912) + 0x514`, a trampoline call hook). The callback runs there with the VM and binds the native:
  `BindNativeMethod("FOCC", "Ping", &Ping, true, false)` (callable from tasklets, not latent). A global native takes
  `std::monostate` in the self slot (`RE/B/BSScriptUtil.h`).
- The library's `Version.h` ends at runtime 1.14.74; whether the id resolves and the offset holds on 1.16.244 is
  what the first launch tells. An id the library lacks is a message box; a wrong offset is a crash. Either is stack
  A's finding, and per the owner the fix goes into the library before stack B comes in.
- Log: `Documents\My Games\Starfield\SFSE\Logs\FOCCPing.log` (CommonLibSF's logger; the file is named after the
  plugin). Lines: `loaded on runtime ...`, `papyrus callback set`, `bound FOCC.Ping`, then one `ping N -> N+1` per call.

## Building on the owner's PC (runbook section B0, job B0-2)

Prerequisites: the portable MSVC (`D:\Modding\tools\msvc_env.ps1`, with cmake and ninja), CommonLibSF `9caec20`
built from its configured tree and installed (on the PC since 28 Oct: preset `release-msvc-ninja`, prefix
`D:\Modding\tools\CommonLibSF-install`), and the library's `vcpkg_installed\x64-windows-static-md-release` folder (spdlog,
fmt; on the PC `D:\Modding\tools\CommonLibSF\build\release-msvc-ninja\vcpkg_installed\x64-windows-static-md-release`).

```powershell
powershell -File sfse\FOCCPing\build.ps1 -Out D:\Modding\staging\focc_ping_<date> `
  -CommonLibSF D:\Modding\tools\CommonLibSF-install `
  -Vcpkg D:\Modding\tools\CommonLibSF\build\release-msvc-ninja\vcpkg_installed\x64-windows-static-md-release `
  -Env D:\Modding\tools\msvc_env.ps1
```

Writes `FOCCPing.dll` and `FOCCPing.pdb` (`/Zi` and `/DEBUG`, so a crash dump names our frames), `cmake_output.txt`,
`build.cmd`, `build.json`. It refuses an `-Out` that already
holds a dll, a non-x64 compiler, a prefix without `CommonLibSFConfig.cmake` and a triplet folder without spdlog.
Compile errors on the first build are expected and cheap: this source has never met the installed library.

## Install and run (the owner's line; game closed for the copies)

1. The Address Library's `.bin` into `<Starfield>\Data\SFSE\Plugins\` (its own name; `versionlib-1-16-244-0.bin` is
   what the library opens), after the format check above (the first row of
   `Format-Hex <path> | Select-Object -First 1` opens with `02 00 00 00`).
2. `FOCCPing.dll` into the same folder.
3. Launch through `sfse_loader.exe`. The kit's rule: a dll that keeps the game from the main menu is deleted at once.
4. Runbook job B0-2: `cgf "FOCC_B0.Ping" 41`, `save focc_b0_a`, load it, `cgf "FOCC_B0.Ping" 43`,
   `cgf "FOCC_B0.Gmst"`; expect `b0 pong sent=41 got=42` and `got=44`. Collect `focc.0.log`, `FOCCPing.log` (as
   `sfse\FOCCPing.log`), the loader's output and, on `got=0`, `Papyrus.0.log`; judge
   `python -m fo4sf.combined.probes b0 <folder>`.
5. Uninstall (game closed): delete `FOCCPing.dll` before any other experiment. The Address Library file can stay; it
   does nothing on its own.
