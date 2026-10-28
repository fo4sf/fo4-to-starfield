"""FOCCSidecar's PC scripts (sfse/FOCCSidecar): the compiler route contract. check_toolchain.ps1 and build.ps1 take a
loaded MSVC environment (cl.exe on PATH with INCLUDE and LIB set, the PC's portable toolchain under D:\\Modding\\tools
since 28 Oct 2026) before they look for Visual Studio with vswhere, and the runbook passes it with -Env."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FOCCSidecar"


class CompilerRouteTests(unittest.TestCase):
    check = (PLUGIN / "check_toolchain.ps1").read_text(encoding="utf-8")
    build = (PLUGIN / "build.ps1").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "spikes" / "combined-core-probes.md").read_text(encoding="utf-8")

    def test_both_scripts_take_the_environment_script_and_dot_source_it(self):
        for text in (self.check, self.build):
            self.assertIn("[string]$Env = ''", text)
            self.assertIn("if ($Env) {\n  if (-not (Test-Path $Env)) { \"-Env $Env not found\"; exit 1 }\n  . $Env\n}", text)

    def test_a_loaded_environment_comes_before_vswhere(self):
        for text in (self.check, self.build):
            env = text.index("Get-Command cl.exe -ErrorAction SilentlyContinue")
            self.assertIn("$clOnPath -and $env:INCLUDE -and $env:LIB", text)
            self.assertLess(env, text.index("vswhere.exe"))

    def test_the_check_reports_which_toolchain_it_found(self):
        self.assertIn("$r.toolchain = 'environment'", self.check)
        self.assertIn("$r.toolchain = 'visual-studio'", self.check)
        # the environment route needs no vcvars64; Visual Studio's does
        self.assertIn("($r.toolchain -eq 'environment' -or $r.vcvars64)", self.check)
        # the portable SDK is registered nowhere: INCLUDE is read first, the registry second
        self.assertLess(self.check.index("Join-Path $_ 'windows.h'"), self.check.index("HKLM:\\SOFTWARE\\Microsoft\\Windows Kits"))

    def test_the_build_calls_vcvars64_only_on_the_visual_studio_route(self):
        self.assertIn("$enter = if ($vcvars) { @(\"call `\"$vcvars`\" >nul || exit /b 90\") } else { @() }", self.build)
        self.assertIn("toolchain = $toolchain", self.build)
        # the compiler line itself is unchanged
        self.assertIn("cl.exe /nologo /std:c++20 /EHsc /O2 /W4 /DUNICODE /D_UNICODE /LD", self.build)
        # the script still never deletes or overwrites
        self.assertNotIn("Remove-Item", self.build)
        self.assertIn("this script never overwrites", self.build)

    def test_the_runbook_and_readme_pass_the_environment(self):
        self.assertEqual(self.runbook.count("-Env D:\\Modding\\tools\\msvc_env.ps1"), 2)
        self.assertIn("-Env D:\\Modding\\tools\\msvc_env.ps1", self.readme)


if __name__ == "__main__":
    unittest.main()
