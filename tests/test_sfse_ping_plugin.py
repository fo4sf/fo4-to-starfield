"""FOCCPing (sfse/FOCCPing), the B0 bridge spike's SFSE plugin, as text: its one native matches the declaration in
scripts/combined_probes/FOCC.psc, it binds the native on SFSE's PostDataLoad message through the GameVM singleton (no
hook), its xmake project takes the libxse CommonLibSF checkout through the library's own plugin rule, its build script
drives xmake in the loaded MSVC environment, and the README and the runbook's B0-2 card name the format-5 Address
Library and the libxse commits. No compiler or library here (docs/combined-core-cpp-port.md section 4;
docs/spikes/combined-core-probes.md section B0)."""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FOCCPing"
LIBXSE = "9d090c4"
SHARED = "9fbb74d"


class PingPluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    pch = (PLUGIN / "src" / "pch.h").read_text(encoding="utf-8")
    xmake = (PLUGIN / "xmake.lua").read_text(encoding="utf-8")
    build = (PLUGIN / "build.ps1").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    psc = (ROOT / "scripts" / "combined_probes" / "FOCC.psc").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")
    port = (ROOT / "docs" / "combined-core-cpp-port.md").read_text(encoding="utf-8")

    def test_the_native_matches_the_papyrus_declaration(self):
        self.assertIn("\nint Function Ping(int v) global native\n", self.psc)             # the script side
        self.assertIn("Scriptname FOCC Hidden Native", self.psc)
        # a global native: std::monostate in the self slot, int in and out, answers v + 1
        self.assertIn("std::int32_t Ping(std::monostate, std::int32_t a_v)", self.main)
        self.assertIn("return a_v + 1;", self.main)
        self.assertIn('vm->BindNativeMethod("FOCC"sv, "Ping"sv, &Ping, true, false);', self.main)
        self.assertEqual(self.main.count("BindNativeMethod("), 1)

    def test_the_native_is_bound_on_post_data_load_through_the_singleton_without_a_hook(self):
        self.assertIn("SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)", self.main)
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD("):]
        self.assertIn("SFSE::Init(a_sfse, { .trampoline = false, .hook = false });", load)
        self.assertLess(load.index("SFSE::Init("), load.index("RegisterListener(&OnMessage)"))
        self.assertIn("if (a_msg && a_msg->type == SFSE::MessagingInterface::kPostDataLoad) {", self.main)
        self.assertIn("const auto game = RE::GameVM::GetSingleton();", self.main)
        self.assertIn("const auto vm = game ? game->GetVM() : nullptr;", self.main)
        self.assertIn("if (!vm) {", self.main)                                           # no VM, no bind, no crash
        self.assertEqual(load.count("return true;"), 2)                                   # loaded either way, the log tells
        code = "\n".join(l for l in self.main.splitlines() if not l.lstrip().startswith("//"))   # the comments cite the old hook
        for banned in ("static ", "new ", "malloc", "WriteProcessMemory", "REL::Relocation", "REL::ID(", "THook",
                       "SetPapyrusCallback", "SFSEPluginVersion", "SFSE_PLUGIN_VERSION", "write_call"):
            self.assertNotIn(banned, code, banned)                                       # no state, no address, no hook, no version data of its own
        self.assertIn('#include "pch.h"', self.main)
        self.assertEqual(self.pch.count("#include"), 2)
        for inc in ('#include "RE/Starfield.h"', '#include "SFSE/SFSE.h"'):
            self.assertIn(inc, self.pch)
        # the log lines the runbook's card reads
        for line in ("FOCCPing loaded on runtime {}", "listening for PostDataLoad; FOCC.Ping binds then", "bound FOCC.Ping",
                     "no script VM at PostDataLoad: FOCC.Ping not bound", "ping {} -> {}"):
            self.assertIn(line, self.main, line)
        self.assertIn("FOCCPing.log", self.readme)
        self.assertIn("FOCCPing.log", self.runbook)

    def test_the_xmake_project_follows_the_libxse_template_and_installs_nothing(self):
        self.assertIn('includes("lib/commonlibsf")', self.xmake)
        self.assertIn('set_project("FOCCPing")', self.xmake)
        self.assertIn('set_languages("c++23")', self.xmake)
        self.assertIn('add_rules("commonlibsf.plugin", {', self.xmake)                  # the rule writes the SFSE version data
        self.assertIn('name = "FOCCPing",', self.xmake)
        self.assertIn('set_values("commonlib.plugin.install", false)', self.xmake)
        self.assertIn('set_pcxxheader("src/pch.h")', self.xmake)
        for banned in ("XSE_SF_GAME_PATH\")", "add_requires(", "Data/SFSE", "SFSE/Plugins"):
            self.assertNotIn(banned, self.xmake.replace("-- the rule's after_build would copy the dll into a game or mods folder named by XSE_SF_GAME_PATH or", ""))
        # nothing of CommonLibSF, SFSE or the game is in the folder
        files = sorted(os.path.relpath(os.path.join(d, f), PLUGIN) for d, _, fs in os.walk(PLUGIN) for f in fs)
        self.assertEqual(files, ["README.md", "build.ps1", os.path.join("src", "main.cpp"), os.path.join("src", "pch.h"), "xmake.lua"])

    def test_the_build_drives_xmake_against_the_pinned_checkout_and_never_overwrites(self):
        self.assertIn("[Parameter(Mandatory)][string]$Out, [string]$Lib = 'D:\\Modding\\tools\\libxse-commonlibsf', [string]$Env = '', [string]$Sdk = ''", self.build)
        self.assertIn("if ($Env) {\n  if (-not (Test-Path $Env)) { \"-Env $Env not found\"; exit 1 }\n  . $Env\n}", self.build)
        self.assertIn("$PinnedLib = '9d090c4c521f4f2c1aa00bb05923c380d47ae596'", self.build)
        self.assertIn("$PinnedShared = '9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d'", self.build)
        self.assertIn("if ([int]$Matches[1] -lt 3)", self.build)                        # libxse's set_xmakever("3.0.0")
        self.assertIn("(& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''", self.build)      # x64 only, as FOCCSidecar
        self.assertIn("if ($banner -notmatch '\\bx64\\b')", self.build)
        self.assertIn("'lib\\commonlib-shared\\src\\REL\\IDDB.cpp'", self.build)         # the submodule is there (the format-5 reader)
        # xmake's MSVC root from the PC's environment: VC and Windows Kits junctions in the staging folder
        self.assertIn("$vcRoot = Split-Path (Split-Path (Split-Path $env:VCToolsInstallDir.TrimEnd('\\', '/')))", self.build)
        self.assertIn("$kits = Split-Path $env:WindowsSdkDir.TrimEnd('\\', '/')", self.build)
        self.assertIn("New-Item -ItemType Junction -Path (Join-Path $Sdk 'Windows Kits') -Target $kits", self.build)
        self.assertIn("New-Item -ItemType Junction -Path (Join-Path $proj 'lib\\commonlibsf') -Target (Resolve-Path $Lib).Path", self.build)
        self.assertIn("Remove-Item Env:XSE_SF_MODS_PATH -ErrorAction SilentlyContinue", self.build)
        self.assertIn("Remove-Item Env:XSE_SF_GAME_PATH -ErrorAction SilentlyContinue", self.build)
        self.assertIn('"xmake.exe f -y -p windows -a x64 -m releasedbg --toolchain=msvc$sdkArg 2>&1 || exit /b 90",', self.build)
        self.assertIn('"xmake.exe build -y FOCCPing 2>&1 || exit /b 91",', self.build)   # stderr merged inside cmd.exe
        self.assertIn("'build\\windows\\x64\\releasedbg\\FOCCPing.dll'", self.build)
        self.assertIn("this script never overwrites", self.build)
        self.assertNotIn("Remove-Item $", self.build)
        self.assertNotIn("Data\\SFSE\\Plugins\\'", self.build)                            # it installs nothing
        for text in (self.readme, self.runbook):                                        # the PC's setup, Install 28 Oct
            self.assertIn("libxse", text)
            self.assertIn(LIBXSE, text)
            self.assertIn(SHARED, text)
            self.assertIn("D:\\Modding\\tools\\libxse-commonlibsf", text)
            self.assertIn("-Env D:\\Modding\\tools\\msvc_env.ps1", text)
            self.assertNotIn("CommonLibSF-install -Vcpkg", text)                         # the morning's cmake line is gone
            self.assertIn("Format-Hex <", text)                                        # the address library format check
            self.assertIn("| Select-Object -First 1", text)                            # runs on Windows PowerShell 5.1
            self.assertNotIn("-Count 4", text)                                         # Format-Hex -Count is PowerShell 6.2+
            self.assertIn("05 00 00 00", text)                                         # format 5, the file on the PC
        self.assertIn("libxse/commonlibsf", self.port)
        self.assertIn("Unsupported address library format: 5", self.port)


if __name__ == "__main__":
    unittest.main()
