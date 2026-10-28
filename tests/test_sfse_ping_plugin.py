"""FOCCPing (sfse/FOCCPing), the B0 bridge spike's SFSE plugin, as text: its one native matches the declaration in
scripts/combined_probes/FOCC.psc, its version data names the Address Library and runtime 1.16.244, its build takes the
loaded MSVC environment and the installed CommonLibSF, and the runbook's B0-2 card names its log. No compiler or
CommonLibSF here (docs/combined-core-cpp-port.md section 4; docs/spikes/combined-core-probes.md section B0)."""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FOCCPing"


class PingPluginTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    header = (PLUGIN / "src" / "Plugin.h").read_text(encoding="utf-8")
    cmake = (PLUGIN / "CMakeLists.txt").read_text(encoding="utf-8")
    build = (PLUGIN / "build.ps1").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    psc = (ROOT / "scripts" / "combined_probes" / "FOCC.psc").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")

    def test_the_native_matches_the_papyrus_declaration(self):
        self.assertIn("\nint Function Ping(int v) global native\n", self.psc)             # the script side
        self.assertIn("Scriptname FOCC Hidden Native", self.psc)
        # a global native: std::monostate in the self slot, int in and out, answers v + 1
        self.assertIn("std::int32_t Ping(std::monostate, std::int32_t a_v)", self.main)
        self.assertIn("return a_v + 1;", self.main)
        self.assertIn('BindNativeMethod("FOCC"sv, "Ping"sv, &Ping, true, false)', self.main)
        self.assertEqual(self.main.count("BindNativeMethod("), 1)

    def test_version_data_names_the_address_library_and_the_runtime(self):
        self.assertIn("SFSEPluginVersion = []() noexcept {", self.main)
        for line in ("data.UsesAddressLibrary(true);", "data.IsLayoutDependent(true);",
                     "data.CompatibleVersions({ REL::Version{ 1, 16, 244, 0 } });",
                     "data.PluginName(Plugin::NAME);", "data.PluginVersion(Plugin::VERSION);"):
            self.assertIn(line, self.main, line)
        self.assertIn('inline constexpr auto         NAME{ "FOCCPing"sv };', self.header)
        self.assertIn("inline constexpr REL::Version VERSION{ 0, 1, 0, 0 };", self.header)

    def test_load_inits_before_the_papyrus_callback_and_keeps_no_state(self):
        load = self.main[self.main.index("SFSEPluginLoad("):]
        self.assertIn("SFSEPluginLoad(const SFSE::LoadInterface* a_sfse)", load)
        self.assertLess(load.index("SFSE::Init(a_sfse);"), load.index("SFSE::SetPapyrusCallback(&OnPapyrusInit);"))
        self.assertIn("return true;", load)
        self.assertIn("if (!a_vm || !*a_vm) {", self.main)                              # no VM, no bind, no crash
        code = "\n".join(l for l in self.main.splitlines() if not l.lstrip().startswith("//"))   # the comments cite the hook
        for banned in ("static ", "new ", "malloc", "WriteProcessMemory", "REL::Relocation", "REL::ID("):
            self.assertNotIn(banned, code, banned)                                       # no state, no address of its own
        # the log is the plugin's own file, named after it (CommonLibSF's logger)
        self.assertIn("FOCCPing.log", self.readme)
        self.assertIn("FOCCPing.log", self.runbook)

    def test_cmake_links_the_installed_library_with_a_matching_runtime(self):
        self.assertIn("find_package(CommonLibSF CONFIG REQUIRED)", self.cmake)
        self.assertIn("target_link_libraries(FOCCPing PRIVATE CommonLibSF::CommonLibSF)", self.cmake)
        self.assertIn('set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")', self.cmake)
        self.assertIn("set(CMAKE_CXX_STANDARD 23)", self.cmake)
        self.assertIn("add_library(FOCCPing SHARED src/main.cpp src/Plugin.h)", self.cmake)
        self.assertNotIn("vcpkg", self.cmake.lower().replace("no\n# vcpkg run", "").split("add_library")[1])   # no toolchain file of its own
        # nothing of CommonLibSF, SFSE or the game is in the folder
        files = sorted(os.path.relpath(os.path.join(d, f), PLUGIN) for d, _, fs in os.walk(PLUGIN) for f in fs)
        self.assertEqual(files, ["CMakeLists.txt", "README.md", "build.ps1", os.path.join("src", "Plugin.h"), os.path.join("src", "main.cpp")])

    def test_the_build_takes_the_environment_and_the_two_prefixes_and_never_overwrites(self):
        self.assertIn("[Parameter(Mandatory)][string]$CommonLibSF, [Parameter(Mandatory)][string]$Vcpkg, [string]$Env = ''", self.build)
        self.assertIn("if ($Env) {\n  if (-not (Test-Path $Env)) { \"-Env $Env not found\"; exit 1 }\n  . $Env\n}", self.build)
        self.assertIn("(& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''", self.build)      # x64 only, as FOCCSidecar
        self.assertIn("if ($banner -notmatch '\\bx64\\b')", self.build)
        self.assertIn("lib\\cmake\\CommonLibSF\\CommonLibSFConfig.cmake", self.build)
        self.assertIn("share\\spdlog\\spdlogConfig.cmake", self.build)
        self.assertIn('`"-DCMAKE_PREFIX_PATH=$prefix`"', self.build)                   # quoted inside the batch line
        self.assertIn("-G Ninja -DCMAKE_BUILD_TYPE=Release", self.build)
        self.assertIn("2>&1 || exit /b 90", self.build)                                 # stderr merged inside cmd.exe
        self.assertIn("this script never overwrites", self.build)
        self.assertNotIn("Remove-Item", self.build)
        self.assertNotIn("Data\\SFSE\\Plugins\\'", self.build)                            # it installs nothing
        for text in (self.readme, self.runbook):                                        # the PC's paths, Install 28 Oct
            self.assertIn("-CommonLibSF D:\\Modding\\tools\\CommonLibSF-install", text)
            self.assertIn("-Vcpkg", text)
            self.assertIn("D:\\Modding\\tools\\CommonLibSF\\build\\release-msvc-ninja\\vcpkg_installed\\x64-windows-static-md-release", text)
            self.assertIn("Format-Hex <", text)                                        # the address library format check
            self.assertIn("| Select-Object -First 1", text)                            # runs on Windows PowerShell 5.1
            self.assertNotIn("-Count 4", text)                                         # Format-Hex -Count is PowerShell 6.2+
            self.assertIn("02 00 00 00", text)


if __name__ == "__main__":
    unittest.main()
