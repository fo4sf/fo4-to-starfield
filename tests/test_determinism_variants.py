"""Determinism under process variations (framework B5): the same synthetic inputs give the same bytes whatever the
string-hash seed, the locale or numpy's CPU code paths. Each variant runs in a fresh interpreter, since those settings
are fixed at start. Covers a static mesh conversion and the launcher driver's step fingerprint; no game files."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHILD = r'''
import hashlib, json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "src"))
sys.path.insert(0, os.path.join(root, "tests"))
from fo4sf import convert_static
from fo4sf.launcher import driver
from test_sf_pipeline import fake_fo4_nif
raw, _, _ = fake_fo4_nif(6)
files = convert_static.convert_static(raw, "fo4port/test/quad")
out = {"files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())}}
step = {"argv": ["python", "x.py", "--b", "--a"], "cwd": root, "inputs": [], "code": [], "id": "s"}
out["fingerprint"] = driver.fingerprint(step, root)
print(json.dumps(out, sort_keys=True))
'''

VARIANTS = {
    "hashseed 0": {"PYTHONHASHSEED": "0"},
    "hashseed 1": {"PYTHONHASHSEED": "1"},
    "hashseed 4242, German locale": {"PYTHONHASHSEED": "4242", "LC_ALL": "de_DE.UTF-8", "LANG": "de_DE.UTF-8"},
    "numpy without AVX2 and AVX512": {"PYTHONHASHSEED": "7", "NPY_DISABLE_CPU_FEATURES": "AVX2 AVX512F"},
}


class DeterminismVariantTests(unittest.TestCase):
    def run_variant(self, env_extra, script):
        env = dict(os.environ)
        env.pop("PYTHONHASHSEED", None)
        env.update(env_extra)
        r = subprocess.run([sys.executable, "-I", script, ROOT], capture_output=True, text=True, env=env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_same_bytes_under_every_variant(self):
        with tempfile.TemporaryDirectory() as t:
            script = os.path.join(t, "child.py")
            with open(script, "w") as f:
                f.write(CHILD)
            results = {name: self.run_variant(env, script) for name, env in VARIANTS.items()}
        first_name, first = next(iter(results.items()))
        self.assertTrue(first["files"])
        for name, got in results.items():
            with self.subTest(variant=name):
                self.assertEqual(got, first, f"{name} differs from {first_name}")
        digest = hashlib.sha256(json.dumps(first["files"], sort_keys=True).encode()).hexdigest()
        self.assertRegex(digest, "^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
