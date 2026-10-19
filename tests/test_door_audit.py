"""scripts/terrain/door_audit.py: each scripted load door's two sides, read-only, on synthetic folders."""
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door_audit  # noqa: E402
from test_vmad_patch import OWN, core_folder, door_entry, tiny_plugin  # noqa: E402


class AuditTests(unittest.TestCase):
    def test_interior_base_and_exterior_flags_per_door(self):
        with tempfile.TemporaryDirectory() as d:
            core, port = os.path.join(d, "core"), os.path.join(d, "port")
            core_folder(core, [door_entry(), door_entry(src="0EE662:Fallout4.esm", ref="000899")])
            os.makedirs(port)
            with open(os.path.join(port, "FO4Port.esm"), "wb") as f:
                f.write(tiny_plugin())
            manifest = os.path.join(d, "manifest.json")
            with open(manifest, "w") as f:
                json.dump({"items": [{"model": "FO4CORE\\d.nif", "door_not_opening": "open animation not ported: passable",
                                      "collision_report": {"source": "passable-door"}}]}, f)
            rows = door_audit.audit(core, port, [manifest])
        self.assertEqual(rows[0]["interior_base_sig"], "STAT")             # a STAT nobody can activate
        self.assertEqual(rows[0]["interior_base_edid"], "FO4Port_door02")
        self.assertEqual(rows[0]["interior_base"], f"{OWN | 0x800:08X}")
        self.assertFalse(rows[0]["interior_vmad"])
        self.assertEqual(rows[0]["exterior"], {"door_not_opening": "open animation not ported: passable",
                                               "collision": "passable-door"})
        self.assertEqual(rows[1]["interior_ref"], f"{OWN | 0x899:08X} missing")


if __name__ == "__main__":
    unittest.main()
