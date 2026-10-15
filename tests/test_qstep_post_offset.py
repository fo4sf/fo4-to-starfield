"""Evaluate the actual diagnostic call with a stub; never run qstep or game input."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import unittest


SHELL = shutil.which('powershell') or shutil.which('pwsh')
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/game/qstep.ps1'


@unittest.skipUnless(SHELL, 'PowerShell is required to evaluate the native call')
class PostOffsetTests(unittest.TestCase):
    def evaluate(self, offset, drop_z, merged_drop_z):
        fixture = {'script': str(SCRIPT), 'offset': offset, 'drop': merged_drop_z,
                   'spec': {'beyond': {'x': -638.1714, 'y': 1499.4286}, 'drop_z': drop_z}}
        data = base64.b64encode(json.dumps(fixture).encode()).decode()
        program = r'''
$ErrorActionPreference = 'Stop'
$fixture = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('FIXTURE')) | ConvertFrom-Json
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($fixture.script, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'qstep has parser errors' }
$calls = @($ast.FindAll({param($node)
    $node -is [Management.Automation.Language.CommandAst] -and
    $node.GetCommandName() -eq 'Teleport' -and $node.Extent.Text.Contains('$t.beyond')
}, $true))
if ($calls.Count -ne 1) { throw 'expected one diagnostic call' }
function Teleport($pos, $heading, $pitch) {
    [pscustomobject]@{position=@($pos);heading=$heading;pitch=$pitch} | ConvertTo-Json -Compress
}
$t = $fixture.spec
$ox = [double]$fixture.offset[0]; $oy = [double]$fixture.offset[1]; $oz = [double]$fixture.offset[2]
$dropz = [double]$fixture.drop
# Only this parsed call executes; Teleport is the harmless JSON stub above.
Invoke-Expression $calls[0].Extent.Text
'''.replace('FIXTURE', data)
        encoded = base64.b64encode(program.encode('utf-16le')).decode()
        completed = subprocess.run([SHELL, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                   capture_output=True, text=True, check=True, timeout=20)
        return json.loads(completed.stdout)

    def check_position(self, offset, drop_z, merged_drop_z):
        result = self.evaluate(offset, drop_z, merged_drop_z)
        expected = [-638.1714 + offset[0], 1499.4286 + offset[1], merged_drop_z]
        self.assertEqual(len(result['position']), 3)
        for actual, target in zip(result['position'], expected):
            self.assertAlmostEqual(actual, target, places=6)
        self.assertEqual(result['heading'], 90)
        self.assertEqual(result['pitch'], 5)

    def test_nonzero_xyz_merge_offset_applies_to_actual_diagnostic_call(self):
        self.check_position([-1200.0029, -2700.0043, 17.5], 160, 177.5)

    def test_zero_offset_retains_local_diagnostic(self):
        self.check_position([0, 0, 0], 160, 160)

    def test_diagnostic_reuses_computed_drop_above_spawn_height(self):
        self.check_position([3000, -3500, -12], 160, 245.13)


if __name__ == '__main__':
    unittest.main()
