"""Codex handover, entirely synthetic: never invoke installed Codex or the watchdog entrypoint.

PowerShell discovery is replaced with fixture PATH records and LOCALAPPDATA is temporary.
Native tests compile a tiny fixture executable outside the repository (no inference, network or game).
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/game/codex_handover.ps1"
WATCHDOG = ROOT / "scripts/game/watchdog.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_ps(script, env=None):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=45,
    )
    if result.returncode:
        raise AssertionError((result.stdout + result.stderr)[-3000:])
    return result.stdout.strip()


class FixtureEnvironment:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex fixture spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, LOCALAPPDATA=str(self.root / "local app data"))

    def bundle(self, folder, complete=True):
        folder.mkdir(parents=True)
        exe = folder / "codex.exe"
        exe.write_bytes(b"synthetic executable placeholder; do not execute")
        if complete:
            for name in ("codex-code-mode-host.exe", "codex-command-runner.exe"):
                (folder / name).write_bytes(b"fixture companion")
        return exe

    def prelude(self, paths=()):
        # Never allow automatic discovery to inspect the real machine's applications.
        items = ",".join(ps_literal(p) for p in paths)
        return f"""$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
. {ps_literal(HELPER)}
function Get-Command {{
  param($Name, $CommandType, [switch]$All, $ErrorAction)
  if ($Name -ne 'codex.exe') {{ throw 'unexpected discovery' }}
  foreach ($path in @({items})) {{ [pscustomobject]@{{ Source = $path }} }}
}}
"""

    def resolve(self, configured="$null", paths=()):
        return run_ps(self.prelude(paths) + f"""
try {{ $exe = Resolve-CodexBundle {configured}; @{{exe=$exe; error=$null}} | ConvertTo-Json -Compress }}
catch {{ @{{exe=$null; error="$($_.Exception.Message)"}} | ConvertTo-Json -Compress }}
""", self.env)

    def process_stub(self, exe, probe_hook="", exec_hook=""):
        # Hypatia's exact adversarial shape: fake help can create the final report, exec writes its -o path.
        return f"""
$script:fixtureCalls = @()
function Invoke-CodexProcess {{
  param($Executable, $Arguments, $Workspace, $InputText = '', $TimeoutMilliseconds = 600000)
  if ($Executable -ne {ps_literal(exe)}) {{ throw 'MUST NOT EXECUTE ACTUAL CLI' }}
  $script:fixtureCalls += ($Arguments -join ' ')
  if ($Arguments.Count -eq 1 -and $Arguments[0] -eq '--version') {{
    return [pscustomobject]@{{ExitCode=0;Stdout='codex-cli 0.162.0';Stderr='';TimedOut=$false;InputError=$null}}
  }}
  if ($Arguments.Count -eq 2 -and $Arguments[1] -eq '--help') {{
    {probe_hook}
    return [pscustomobject]@{{ExitCode=0;Stdout='--sandbox --config --cd --output-last-message --skip-git-repo-check';Stderr='';TimedOut=$false;InputError=$null}}
  }}
  if ($Arguments[0] -ne 'exec' -or $Arguments[-1] -ne '-') {{ throw 'unexpected fixture invocation' }}
  [IO.File]::WriteAllText($Arguments[-2], 'replacement synthetic report')
  {exec_hook}
  return [pscustomobject]@{{ExitCode=0;Stdout='fixture exec';Stderr='';TimedOut=$false;InputError=$null}}
}}
"""


@unittest.skipUnless(POWERSHELL, "PowerShell unavailable")
class DiscoveryTests(FixtureEnvironment, unittest.TestCase):
    def test_stale_copied_path_skipped_for_complete_path_bundle(self):
        copied = self.bundle(self.root / ".sandbox-bin", complete=False)
        installed = self.bundle(self.root / "installed bundle with spaces")
        result = json.loads(self.resolve(paths=(copied, installed)))
        self.assertEqual(result["exe"], str(installed))
        self.assertIsNone(result["error"])

    def test_installed_bundle_discovered_without_pinning_hash(self):
        root = Path(self.env["LOCALAPPDATA"]) / "OpenAI/Codex/bin"
        older = self.bundle(root / "arbitrary-old")
        newer = self.bundle(root / "arbitrary-new")
        self.bundle(root / "incomplete-newest", complete=False)
        os.utime(older.parent, (1000, 1000))
        os.utime(newer.parent, (2000, 2000))
        copied = self.bundle(self.root / "copied", complete=False)
        result = json.loads(self.resolve(paths=(copied,)))
        self.assertEqual(result["exe"], str(newer))

    def test_path_precedes_other_installed_bundle(self):
        path = self.bundle(self.root / "on PATH")
        self.bundle(Path(self.env["LOCALAPPDATA"]) / "OpenAI/Codex/bin/other-version")
        self.assertEqual(json.loads(self.resolve(paths=(path,)))["exe"], str(path))

    def test_explicit_valid_executable_precedes_path(self):
        explicit = self.bundle(self.root / "configured [literal] bundle")
        alternative = self.bundle(self.root / "alternative")
        result = json.loads(self.resolve(ps_literal(explicit), (alternative,)))
        self.assertEqual(result["exe"], str(explicit))

    def test_explicit_invalid_never_falls_back(self):
        alternative = self.bundle(self.root / "valid alternative")
        copied = self.bundle(self.root / "old copied", complete=False)
        for configured in (ps_literal(copied), ps_literal(self.root / "missing.exe"), "''", "'codex.exe'", "42"):
            with self.subTest(configured=configured):
                result = json.loads(self.resolve(configured, (alternative,)))
                self.assertIsNone(result["exe"])
                self.assertIn("no fallback", result["error"])

    def test_missing_command_runner_also_refuses(self):
        exe = self.bundle(self.root / "missing runner")
        (exe.parent / "codex-command-runner.exe").unlink()
        self.assertIsNone(json.loads(self.resolve(ps_literal(exe)))["exe"])

    def test_no_bundle_refuses_without_launch(self):
        result = json.loads(self.resolve())
        self.assertIsNone(result["exe"])
        self.assertIn("no complete Codex bundle", result["error"])

    def test_invalid_configuration_appends_refusal_and_starts_no_process(self):
        log = self.root / "watchdog.log"
        log.write_text("existing log\n", encoding="utf-8")
        script = self.prelude() + f"""
function Invoke-CodexProcess {{ throw 'MUST NOT START' }}
$ok = Invoke-CodexHandover -ConfiguredExe '' -Workspace {ps_literal(self.root)} -Prompt 'fixture' `
  -OutputPath {ps_literal(self.root / 'new.md')} -LogPath {ps_literal(log)}
$ok | ConvertTo-Json -Compress
"""
        self.assertFalse(json.loads(run_ps(script, self.env)))
        text = log.read_text(encoding="utf-8-sig")
        self.assertIn("existing log", text)
        self.assertIn("refused/failed", text)
        self.assertIn("no fallback", text)
        self.assertNotIn("MUST NOT START", text)

    def test_output_outside_workspace_refuses_before_process_or_directory_creation(self):
        log = self.root / "watchdog.log"
        outside = self.root / "uncreated directory" / "report.md"
        script = self.prelude() + f"""
function Invoke-CodexProcess {{ throw 'MUST NOT START' }}
$ok = Invoke-CodexHandover -Workspace {ps_literal(self.root)} -Prompt 'fixture' `
  -OutputPath {ps_literal(outside)} -LogPath {ps_literal(log)}
$ok | ConvertTo-Json -Compress
"""
        self.assertFalse(json.loads(run_ps(script, self.env)))
        self.assertFalse(outside.parent.exists())
        self.assertIn("existing workspace directory", log.read_text(encoding="utf-8-sig"))
        self.assertNotIn("MUST NOT START", log.read_text(encoding="utf-8-sig"))


@unittest.skipUnless(POWERSHELL, "PowerShell unavailable")
class ReportPublicationTests(FixtureEnvironment, unittest.TestCase):
    def test_report_created_during_probe_is_never_overwritten(self):
        self.assert_publication_refuses("probe")

    def test_report_created_during_exec_is_never_overwritten(self):
        self.assert_publication_refuses("exec")

    def assert_publication_refuses(self, when):
        exe = self.bundle(self.root / "fake complete bundle")
        output = self.root / "report.md"
        log = self.root / "watchdog.log"
        creation = f"[IO.File]::WriteAllText({ps_literal(output)}, 'KEEP concurrent synthetic report')"
        stub = self.process_stub(exe, probe_hook=creation if when == "probe" else "",
                                 exec_hook=creation if when == "exec" else "")
        result = json.loads(run_ps(self.prelude((exe,)) + stub + f"""
$ok = Invoke-CodexHandover -ConfiguredExe {ps_literal(exe)} -Workspace {ps_literal(self.root)} `
  -Prompt 'synthetic reporting fixture' -OutputPath {ps_literal(output)} -LogPath {ps_literal(log)}
@{{ok=$ok;calls=@($script:fixtureCalls)}} | ConvertTo-Json -Compress
""", self.env))
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(output.read_text(), "KEEP concurrent synthetic report")
        pending = list(self.root.glob(".codex_handover_*.pending.md"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].read_text(), "replacement synthetic report")
        diagnostic = log.read_text(encoding="utf-8-sig")
        self.assertIn(str(pending[0]), diagnostic)
        self.assertNotIn("hand-over completed", diagnostic)


@unittest.skipUnless(POWERSHELL, "PowerShell unavailable")
class ConfigRefusalTests(FixtureEnvironment, unittest.TestCase):
    def config_handover(self, content, unreadable=False):
        exe = self.root / "fake complete bundle" / "codex.exe"
        if not exe.exists():
            exe = self.bundle(exe.parent)
        config = self.root / "fixture-config.json"
        if content is not None:
            config.write_text(content, encoding="utf-8")
        # Only copy the two AST-selected functions into a fixture script. Never execute the watchdog entrypoint.
        # Its helper is a source copy with a synthetic process stub, so the pre-fix bad-config fallback also runs safely.
        helper_fixture = self.root / "codex_handover.ps1"
        helper_fixture.write_text(HELPER.read_text(encoding="utf-8") + self.process_stub(exe), encoding="utf-8")
        denied_read = """
function Get-Content { param($LiteralPath, [switch]$Raw, $ErrorAction); throw 'synthetic config read denied' }
""" if unreadable else ""
        return json.loads(run_ps(self.prelude((exe,)) + f"""
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile({ps_literal(WATCHDOG)}, [ref]$null, [ref]$errors)
if ($errors.Count) {{ throw 'watchdog AST parse failed' }}
$definitions = foreach ($name in @('Cfg', 'CodexHandOver')) {{
  $functions = @($ast.FindAll({{param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
  }}, $true))
  if ($functions.Count -ne 1) {{ throw 'fixture function must be unique' }}
  $functions[0].Extent.Text
}}
$fixtureScript = {ps_literal(self.root / 'watchdog-functions-fixture.ps1')}
[IO.File]::WriteAllText($fixtureScript, ($definitions -join "`n"))
. $fixtureScript
$script:fixtureCalls = @()
$script:fixtureNotes = @()
function Note($m) {{ $script:fixtureNotes += $m }}
$Config = {ps_literal(config)}
$repo = {ps_literal(ROOT)}
$wt = $repo
$tq = {ps_literal(self.root)}
$log = {ps_literal(self.root / 'watchdog.log')}
{denied_read}
$cfg = Cfg
$ok = CodexHandOver $cfg 4
@{{ok=$ok;invalid=$cfg.codex_config_invalid;calls=@($script:fixtureCalls);notes=@($script:fixtureNotes);
  threshold=$cfg.threshold_hours;check=$cfg.check_minutes;every=$cfg.codex_every_hours}} | ConvertTo-Json -Compress
""", self.env))

    def test_malformed_and_nonobject_config_refuse_discovery_probes_and_exec(self):
        for content in ('{ "codex_exe": ', 'null', '[]', '[{}]', '[{"threshold_hours":0}]', 'true', '42', '"text"'):
            with self.subTest(content=content):
                result = self.config_handover(content)
                self.assertFalse(result["ok"])
                self.assertTrue(result["invalid"])
                self.assertEqual(result["calls"], [])
                self.assertIn("watchdog config invalid", " ".join(result["notes"]))
                self.assertEqual((result["threshold"], result["check"], result["every"]), (3, 10, 6))

    def test_present_unreadable_config_refuses_handover_only(self):
        result = self.config_handover('{}', unreadable=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["invalid"])
        self.assertEqual(result["calls"], [])
        self.assertIn("synthetic config read denied", " ".join(result["notes"]))
        self.assertEqual((result["threshold"], result["check"], result["every"]), (3, 10, 6))

    def test_absent_config_keeps_discovery_and_chain_defaults(self):
        result = self.config_handover(None)
        self.assertFalse(result["invalid"])
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual((result["threshold"], result["check"], result["every"]), (3, 10, 6))

    def test_valid_object_keeps_configured_chain_policy(self):
        result = self.config_handover('{"threshold_hours":9,"check_minutes":11,"codex_every_hours":12}')
        self.assertFalse(result["invalid"])
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual((result["threshold"], result["check"], result["every"]), (9, 11, 12))


FIXTURE_SOURCE = r'''
using System;
using System.IO;
using System.Text;
using System.Threading;
public class CodexFixture {
    public static int Main(string[] args) {
        Console.OutputEncoding = new UTF8Encoding(false);
        string mode = Environment.GetEnvironmentVariable("FO4SF_CODEX_FIXTURE_MODE");
        if (args.Length == 1 && args[0] == "--version") {
            Console.WriteLine(mode == "bad-version" ? "not a Codex version" : "codex-cli 0.162.0-alpha.17.2");
            if (mode == "version-timeout") { Console.Error.WriteLine("fixture timed-out probe"); Thread.Sleep(5000); }
            if (mode == "version") { Console.Error.WriteLine("fixture version failure"); return 17; }
            return 0;
        }
        if (args.Length == 2 && args[0] == "exec" && args[1] == "--help") {
            Console.WriteLine(mode == "bad-help" ? "old help" :
                "--sandbox --config --cd --output-last-message --skip-git-repo-check PROMPT - (stdin)");
            if (mode == "probe") { Console.Error.WriteLine("fixture probe failure"); return 18; }
            return 0;
        }
        if (args.Length > 0 && args[0] == "sleep-fixture") { Thread.Sleep(5000); return 0; }
        if (mode == "early-child") { Console.Error.WriteLine("fixture early failure"); return 24; }
        if (mode == "exec-no-read") { Console.Error.WriteLine("fixture not reading stdin"); Thread.Sleep(5000); return 0; }
        foreach (string arg in args) Console.WriteLine("ARG:" + Convert.ToBase64String(Encoding.UTF8.GetBytes(arg)));
        Console.WriteLine("INPUT:" + Convert.ToBase64String(Encoding.UTF8.GetBytes(Console.In.ReadToEnd())));
        if (args.Length > 0 && args[0] == "exec") {
            Console.Error.WriteLine("fixture child diagnostics");
            // Force concurrent drain of both pipes: sequential reads/waits would hang here.
            Console.WriteLine(new string('x', 100000));
            Console.Error.WriteLine(new string('y', 100000));
            for (int i = 0; i + 1 < args.Length; i++) {
                if (args[i] == "-o" && mode != "no-report")
                    File.WriteAllText(args[i + 1], mode == "empty-report" ? "" : "fixture report", new UTF8Encoding(false));
            }
            if (mode == "child") { Console.Error.WriteLine("fixture child failure"); return 23; }
            if (mode == "exec-timeout") { Console.Error.WriteLine("fixture hung after report"); Thread.Sleep(5000); }
        }
        return 0;
    }
}
'''


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell required for native fixture")
class NativeProcessTests(FixtureEnvironment, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiled_temp = tempfile.TemporaryDirectory(prefix="synthetic codex compiler ")
        cls.addClassCleanup(cls.compiled_temp.cleanup)
        cls.fixture = Path(cls.compiled_temp.name) / "codex.exe"
        run_ps(f"""
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition {ps_literal(FIXTURE_SOURCE)} -Language CSharp `
  -OutputAssembly {ps_literal(cls.fixture)} -OutputType ConsoleApplication
""")

    def native_bundle(self, folder):
        exe = self.bundle(folder)
        shutil.copyfile(self.fixture, exe)
        return exe

    def handover(self, exe, mode="", paths=(), prompt=None, extra_script="", exec_timeout=None):
        self.env["FO4SF_CODEX_FIXTURE_MODE"] = mode
        self.output = self.root / "new report [literal].md"
        self.log = self.root / "watchdog.log"
        self.prompt = prompt or "fixture prompt\nquotes: \" hello \"; $(); &; unicode: café\n"
        # Large stdin is constructed in the fixture process rather than passed on the OS command line.
        prompt_expr = ps_literal(self.prompt) if len(self.prompt) < 10000 else f"('p' * {len(self.prompt)})"
        timeout_arg = "" if exec_timeout is None else f" -ExecTimeoutMilliseconds {exec_timeout}"
        result = run_ps(self.prelude(paths) + extra_script + f"""
$ok = Invoke-CodexHandover -ConfiguredExe {ps_literal(exe)} -Workspace {ps_literal(self.root)} `
  -Prompt {prompt_expr} -OutputPath {ps_literal(self.output)} -LogPath {ps_literal(self.log)}{timeout_arg}
$ok | ConvertTo-Json -Compress
""", self.env)
        return json.loads(result)

    def diagnostics(self):
        return self.log.read_text(encoding="utf-8-sig")

    def retained_report(self):
        pending = list(self.root.glob(".codex_handover_*.pending.md"))
        self.assertEqual(len(pending), 1)
        self.assertIn(str(pending[0]), self.diagnostics())
        self.assertFalse(self.output.exists())
        return pending[0]

    def test_real_drive_relative_bundle_is_refused_without_fallback(self):
        exe = self.native_bundle(self.root / "drive relative bundle")
        alternative = self.native_bundle(self.root / "valid absolute alternative")
        relative = self.root.drive + "drive relative bundle\\codex.exe"
        log = self.root / "watchdog.log"
        result = json.loads(run_ps(self.prelude((alternative,)) + f"""
Set-Location -LiteralPath {ps_literal(self.root)}
$relative = {ps_literal(relative)}
$resolved = (Resolve-Path -LiteralPath $relative).ProviderPath
$rooted = [IO.Path]::IsPathRooted($relative)
$complete = Test-CodexBundle $relative
function Invoke-CodexProcess {{ throw 'MUST NOT START' }}
$ok = Invoke-CodexHandover -ConfiguredExe $relative -Workspace {ps_literal(self.root)} -Prompt 'fixture' `
  -OutputPath {ps_literal(self.root / 'new.md')} -LogPath {ps_literal(log)}
@{{ok=$ok; rooted=$rooted; complete=$complete; resolved=$resolved}} | ConvertTo-Json -Compress
""", self.env))
        self.assertTrue(result["rooted"], "fixture must reproduce IsPathRooted accepting drive-relative paths")
        self.assertTrue(result["complete"], "drive-relative path must point to a complete fake bundle")
        self.assertEqual(result["resolved"], str(exe))
        self.assertFalse(result["ok"])
        diagnostic = log.read_text(encoding="utf-8-sig")
        self.assertIn("absolute executable path", diagnostic)
        self.assertIn("no fallback", diagnostic)
        self.assertNotIn("MUST NOT START", diagnostic)
        self.assertNotIn(str(alternative), diagnostic)

    def test_success_uses_stdin_scope_and_exact_arguments_with_spaces(self):
        exe = self.native_bundle(self.root / "installed [literal] spaces")
        for suffix in (".log", ".err"):
            (self.root / ("new report [literal].md" + suffix)).write_text("preserved diagnostics\n", encoding="utf-8")
        self.assertTrue(self.handover(exe))
        lines = Path(str(self.output) + ".log").read_text(encoding="utf-8-sig").splitlines()
        arguments = [base64.b64decode(line[4:]).decode("utf-8") for line in lines if line.startswith("ARG:")]
        pending = Path(arguments[-2])
        self.assertEqual(pending.parent, self.root)
        self.assertTrue(pending.name.startswith(".codex_handover_"))
        self.assertTrue(pending.name.endswith(".pending.md"))
        self.assertFalse(pending.exists(), "successful publication must move the temporary report")
        self.assertEqual(self.output.read_text(), "fixture report")
        self.assertEqual(arguments, [
            "exec", "--skip-git-repo-check", "-C", str(self.root), "--sandbox", "workspace-write",
            "-c", "sandbox_workspace_write.network_access=true", "-o", str(pending), "-",
        ])
        input_line = next(line for line in lines if line.startswith("INPUT:"))
        self.assertEqual(base64.b64decode(input_line[6:]).decode("utf-8"), self.prompt)
        self.assertIn("preserved diagnostics", lines)
        self.assertIn("hand-over completed", self.diagnostics())
        self.assertIn("fixture child diagnostics", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))
        self.assertFalse((self.root / "codex_prompt.txt").exists())

    def test_child_failure_never_marks_success_even_with_report(self):
        exe = self.native_bundle(self.root / "failing child")
        self.assertFalse(self.handover(exe, "child"))
        self.assertEqual(self.retained_report().read_text(), "fixture report")
        self.assertIn("child failed (exit 23)", self.diagnostics())
        self.assertNotIn("hand-over completed", self.diagnostics())
        self.assertIn("fixture child failure", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))

    def test_failed_version_never_hands_over_or_falls_back(self):
        exe = self.native_bundle(self.root / "failing version")
        alternative = self.native_bundle(self.root / "valid alternative")
        self.assertFalse(self.handover(exe, "version", (alternative,)))
        self.assertFalse(self.output.exists())
        self.assertIn("exit 17", self.diagnostics())
        self.assertIn("fixture version failure", self.diagnostics())
        self.assertNotIn("hand-over started", self.diagnostics())
        self.assertNotIn(str(alternative), self.diagnostics())

    def test_early_child_failure_retains_exit_and_stderr_when_stdin_breaks(self):
        exe = self.native_bundle(self.root / "early failing child")
        self.assertFalse(self.handover(exe, "early-child", prompt="p" * 200000))
        self.assertIn("exit 24", self.diagnostics())
        self.assertIn("fixture early failure", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_failed_help_probe_never_hands_over(self):
        exe = self.native_bundle(self.root / "failing help")
        self.assertFalse(self.handover(exe, "probe"))
        self.assertFalse(self.output.exists())
        self.assertIn("exit 18", self.diagnostics())
        self.assertNotIn("hand-over started", self.diagnostics())

    def test_exec_timeout_refuses_even_after_report_is_written(self):
        exe = self.native_bundle(self.root / "hung reporting fixture")
        started = time.monotonic()
        self.assertFalse(self.handover(exe, "exec-timeout", exec_timeout=800))
        self.assertLess(time.monotonic() - started, 4.5)
        self.assertEqual(self.retained_report().read_text(), "fixture report")
        self.assertIn("child timed out after 800 ms", self.diagnostics())
        self.assertIn("fixture hung after report", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_exec_timeout_also_bounds_blocked_stdin_delivery(self):
        exe = self.native_bundle(self.root / "not reading stdin fixture")
        started = time.monotonic()
        self.assertFalse(self.handover(exe, "exec-no-read", prompt="p" * 200000, exec_timeout=800))
        self.assertLess(time.monotonic() - started, 4.5)
        self.assertIn("child timed out after 800 ms", self.diagnostics())
        self.assertIn("fixture not reading stdin", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_explicit_timed_out_flag_refuses_even_with_zero_exit_and_report(self):
        exe = self.native_bundle(self.root / "timeout flag fixture")
        wrapper = """
$script:fixtureProcess = ${function:Invoke-CodexProcess}
function Invoke-CodexProcess {
  param($Executable, $Arguments, $Workspace, $InputText = '', $TimeoutMilliseconds = 600000)
  if ($Arguments[-1] -eq '-') {
    [IO.File]::WriteAllText($Arguments[-2], 'synthetic report')
    return [pscustomobject]@{ ExitCode=0; Stdout=''; Stderr='synthetic timeout'; TimedOut=$true; InputError=$null }
  }
  & $script:fixtureProcess @PSBoundParameters
}
"""
        self.assertFalse(self.handover(exe, extra_script=wrapper))
        self.assertEqual(self.retained_report().read_text(), "synthetic report")
        self.assertIn("child timed out after 600000 ms", self.diagnostics())
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_bad_version_help_or_missing_report_refuses(self):
        exe = self.native_bundle(self.root / "bad response")
        for mode in ("bad-version", "bad-help", "no-report", "empty-report"):
            with self.subTest(mode=mode):
                if hasattr(self, "output") and self.output.exists():
                    self.output.unlink()
                self.assertFalse(self.handover(exe, mode))
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_stale_report_refuses_before_probes(self):
        exe = self.native_bundle(self.root / "complete fixture")
        output = self.root / "new report [literal].md"
        output.write_text("preserve previous report", encoding="utf-8")
        self.assertFalse(self.handover(exe))
        self.assertEqual(output.read_text(), "preserve previous report")
        self.assertIn("report already exists", self.diagnostics())
        self.assertFalse(Path(str(output) + ".log").exists())

    def test_unlaunchable_executable_refuses_and_logs(self):
        exe = self.bundle(self.root / "invalid executable")
        self.assertFalse(self.handover(exe))
        self.assertIn("refused/failed", self.diagnostics())
        self.assertNotIn("hand-over completed", self.diagnostics())

    def test_windows_argument_round_trip(self):
        exe = self.native_bundle(self.root / "quote fixture")
        args = ["dump-fixture", "", "two words", 'a"b', 'a\\"b', "trailing slash\\", "\\\\", "$() & literal"]
        encoded_args = ",".join(ps_literal(value) for value in args)
        result = run_ps(self.prelude() + f"""
$result = Invoke-CodexProcess -Executable {ps_literal(exe)} -Workspace {ps_literal(self.root)} -Arguments @({encoded_args})
$result | ConvertTo-Json -Compress
""", self.env)
        parsed = json.loads(result)
        actual = [base64.b64decode(line[4:]).decode("utf-8") for line in parsed["Stdout"].splitlines() if line.startswith("ARG:")]
        self.assertEqual(parsed["ExitCode"], 0)
        self.assertEqual(actual, args)

    def test_probe_timeout_kills_fixture_and_returns_refusal(self):
        exe = self.native_bundle(self.root / "timeout fixture")
        # Shorten only the synthetic probe's timeout; production remains 15 seconds.
        wrapper = """
$script:fixtureProcess = ${function:Invoke-CodexProcess}
function Invoke-CodexProcess {
  param($Executable, $Arguments, $Workspace, $InputText = '', $TimeoutMilliseconds = -1)
  $PSBoundParameters['TimeoutMilliseconds'] = 200
  & $script:fixtureProcess @PSBoundParameters
}
"""
        self.assertFalse(self.handover(exe, "version-timeout", extra_script=wrapper))
        self.assertIn("timed out", self.diagnostics())
        self.assertNotIn("hand-over started", self.diagnostics())
        self.assertIn("fixture timed-out probe", Path(str(self.output) + ".err").read_text(encoding="utf-8-sig"))


class SourceContractTests(unittest.TestCase):
    def test_headless_launch_and_read_only_reporting_contract(self):
        helper = HELPER.read_text(encoding="utf-8")
        for setting in ("$info.UseShellExecute = $false", "$info.CreateNoWindow = $true", "::Hidden"):
            self.assertIn(setting, helper)
        runbook = (ROOT / "docs/ai/codex-runbook.md").read_text(encoding="utf-8")
        self.assertNotIn("testqueue.py status --queue", runbook)
        self.assertNotIn("... testqueue.py report --queue", runbook)
        for required in ("Never run", "rescoring", "runner exit **4**", "Claude retains the live controller",
                         "protected config replacement", "Do not restart a running watchdog"):
            self.assertIn(required, runbook)

    @unittest.skipUnless(POWERSHELL, "PowerShell unavailable")
    def test_watchdog_only_records_completed_handover_without_executing_it(self):
        # Inspect the AST only. Never dot-source or run the watchdog, not even -Once.
        result = run_ps(f"""
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile({ps_literal(WATCHDOG)}, [ref]$null, [ref]$errors)
if ($errors.Count) {{ throw ($errors | Out-String) }}
$guard = $ast.FindAll({{ param($node)
  $node -is [Management.Automation.Language.IfStatementAst] -and
  $node.Clauses[0].Item1.Extent.Text -eq 'CodexHandOver $cfg $idleH'
}}, $true)
@($guard | ForEach-Object {{ $_.Clauses[0].Item2.Extent.Text }}) | ConvertTo-Json -Compress
""")
        body = json.loads(result)
        if isinstance(body, list):
            self.assertEqual(len(body), 1)
            body = body[0]
        self.assertIn("SaveState @{ last_codex = (Get-Date).ToString('s')", body)


if __name__ == "__main__":
    unittest.main()
