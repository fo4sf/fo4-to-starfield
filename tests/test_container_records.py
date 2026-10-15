"""Synthetic serialized records for the independent container output auditor."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "testing"))
import container_records as cr  # noqa: E402


def sub(sig, payload):
    return sig.encode() + struct.pack("<H", len(payload)) + payload


def record(sig, fid, fields, flags=0):
    payload = b"".join(sub(k, v) for k, v in fields)
    return struct.pack("<4sIII8x", sig.encode(), len(payload), flags, fid) + payload


def group(kind, label, payload):
    return struct.pack("<4sIIi8x", b"GRUP", 24 + len(payload), label, kind) + payload


class ContainerRecordTests(unittest.TestCase):
    def setUp(self):
        self.src = "123456:Fallout4.esm"
        self.objects = {"world": "FixtureWorld", "refs": [{"src": "654321:Fallout4.esm"}], "containers": [
            {"src": self.src, "edid": "FixtureContainer", "name": "First Aid Kit", "model": "fixture/kit.nif",
             "cell": [0, 0], "pos": [10., 20., 1.], "rot": [0., 0., .5], "scale": 2.,
             "items": [{"form": "Starfield.esm:00000F", "count": 25}, {"form": "Starfield.esm:00000A", "count": 1}]}]}
        self.ids = {"plugin": "Fixture.esm", "world": "FixtureWorld", "bases": {"FixtureStatic": "000802"},
                    "refs": {"654321:Fallout4.esm": "000805"}, "containers": {self.src: {"base": "000803", "ref": "000804"}}}
        self.baseline = {"plugin": "Fixture.esm", "world": "FixtureWorld", "bases": {"FixtureStatic": "000802"},
                         "refs": {"654321:Fallout4.esm": "000805", self.src: "000804"}}
        self.base_fields = [("EDID", b"FixtureContainer\0"), ("FULL", b"First Aid Kit\0"), ("MODL", b"fixture/kit.nif\0"),
                            ("CNTO", struct.pack("<Ii", 15, 25)), ("CNTO", struct.pack("<Ii", 10, 1))]
        self.ref_fields = [("NAME", struct.pack("<I", 0x01000803)), ("DATA", struct.pack("<6f", 10, 20, 1, 0, 0, .5)),
                           ("XSCL", struct.pack("<f", 2))]

    def blob(self, *, base=None, ref=None, grid=(0, 0), world="FixtureWorld", kind=9, flags=0, extra=b""):
        header = record("TES4", 0, [("MAST", b"Starfield.esm\0"), ("DATA", bytes(8))])
        cont = record("CONT", 0x01000803, self.base_fields if base is None else base)
        placed = record("REFR", 0x01000804, self.ref_fields if ref is None else ref, flags)
        cell = record("CELL", 0x01000801, [("XCLC", struct.pack("<ii", *grid))])
        children = group(6, 0x01000801, group(kind, 0x01000801, placed + extra))
        wrld = record("WRLD", 0x01000800, [("EDID", world.encode() + b"\0")])
        return header + group(0, int.from_bytes(b"CONT", "little"), cont) + group(0, int.from_bytes(b"WRLD", "little"), wrld + group(1, 0x01000800, cell + children))

    def audit(self, blob=None):
        return cr.audit(self.blob() if blob is None else blob, self.objects, self.ids, plugin_name="Fixture.esm", baseline=self.baseline)

    def test_valid_pair_and_declared_baseline_pass_offline_only(self):
        report = self.audit()
        self.assertTrue(report["offline_passed"], report)
        self.assertFalse(report["runtime_accepted"])
        self.assertEqual(report["containers_checked"], 1)
        self.assertEqual(report["refs_ids_changed"], 0)

    def test_count_preserving_container_corruptions_fail(self):
        cases = {
            "model": ([(k, b"wrong.nif\0" if k == "MODL" else v) for k, v in self.base_fields], None),
            "name": ([(k, b"Wrong name\0" if k == "FULL" else v) for k, v in self.base_fields], None),
            "inventory": ([(k, v) for k, v in self.base_fields if k != "CNTO"], None),
            "item_count": ([(k, struct.pack("<Ii", 15, 250) if k == "CNTO" else v) for k, v in self.base_fields], None),
            "base": (None, [(k, struct.pack("<I", 0x01000802) if k == "NAME" else v) for k, v in self.ref_fields]),
            "xyz": (None, [(k, struct.pack("<6f", 1000, 1000, 1000, 0, 0, .5) if k == "DATA" else v) for k, v in self.ref_fields]),
            "rotation": (None, [(k, struct.pack("<6f", 10, 20, 1, 0, 0, 2) if k == "DATA" else v) for k, v in self.ref_fields]),
            "scale": (None, [(k, struct.pack("<f", 12) if k == "XSCL" else v) for k, v in self.ref_fields]),
            "nan": (None, [(k, struct.pack("<6f", float("nan"), 20, 1, 0, 0, .5) if k == "DATA" else v) for k, v in self.ref_fields]),
        }
        for name, (base, ref) in cases.items():
            with self.subTest(name=name):
                report = self.audit(self.blob(base=base, ref=ref))
                self.assertFalse(report["offline_passed"], report)

    def test_world_cell_state_and_duplicate_placement_fail(self):
        extra = record("REFR", 0x01000806, self.ref_fields)
        for kwargs in ({"grid": (1, 0)}, {"world": "OtherWorld"}, {"kind": 8}, {"flags": 0x800}, {"flags": 0x400}, {"extra": extra}):
            with self.subTest(kwargs=kwargs.keys()):
                self.assertFalse(self.audit(self.blob(**kwargs))["offline_passed"])

    def test_shifted_or_removed_unrelated_ids_fail_declared_baseline(self):
        for category in ("bases", "refs"):
            with self.subTest(category=category):
                key = next(iter(self.ids[category]))
                old = self.ids[category][key]
                self.ids[category][key] = "000809"
                self.assertFalse(self.audit()["offline_passed"])
                del self.ids[category][key]
                self.assertFalse(self.audit()["offline_passed"])
                self.ids[category][key] = old

    def test_missing_aliased_or_duplicated_metadata_cannot_pass(self):
        original = deepcopy(self.ids)
        for key in ("base", "ref"):
            self.ids["containers"][self.src][key] = "000809"
            self.assertFalse(self.audit()["offline_passed"])
            self.ids = deepcopy(original)
        self.ids["containers"][self.src]["ref"] = self.ids["containers"][self.src]["base"]
        self.assertFalse(self.audit()["offline_passed"])
        self.ids = original
        self.objects["containers"].append(deepcopy(self.objects["containers"][0]))
        self.assertFalse(self.audit()["offline_passed"])

    def test_empty_malformed_and_truncated_evidence_cannot_pass(self):
        for blob in (b"", self.blob()[:-1], self.blob() + group(9, 0, b"")[:-1]):
            self.assertFalse(self.audit(blob)["offline_passed"])
        self.objects["containers"] = []
        self.assertFalse(self.audit()["offline_passed"])

    def test_current_writer_cp1252_names_and_models_pass(self):
        c = self.objects["containers"][0]
        c["name"], c["model"] = "Caf\u00e9 bo\u00eete", "fixture/caf\u00e9/bo\u00eete.nif"
        fields = [(k, c["name"].encode("cp1252") + b"\0" if k == "FULL" else
                   c["model"].encode("cp1252") + b"\0" if k == "MODL" else v) for k, v in self.base_fields]
        self.assertTrue(self.audit(self.blob(base=fields))["offline_passed"])

    def test_physical_world_must_match_cell_definition_world(self):
        header = record("TES4", 0, [("MAST", b"Starfield.esm\0")])
        cont = group(0, int.from_bytes(b"CONT", "little"), record("CONT", 0x01000803, self.base_fields))
        world_a = record("WRLD", 0x01000800, [("EDID", b"FixtureWorld\0")])
        cell_a = record("CELL", 0x01000801, [("XCLC", struct.pack("<ii", 0, 0))])
        world_b = record("WRLD", 0x01000810, [("EDID", b"OtherWorld\0")])
        cell_b = record("CELL", 0x01000811, [("XCLC", struct.pack("<ii", 0, 0))])
        misplaced = group(6, 0x01000801, group(9, 0x01000801, record("REFR", 0x01000804, self.ref_fields)))
        worlds = world_a + group(1, 0x01000800, cell_a) + world_b + group(1, 0x01000810, cell_b + misplaced)
        self.assertFalse(self.audit(header + cont + group(0, int.from_bytes(b"WRLD", "little"), worlds))["offline_passed"])

    def test_unknown_subrecord_cannot_overrun_its_record(self):
        blob = self.blob()
        start = 24 + struct.unpack_from("<I", blob, 4)[0]
        end = start + struct.unpack_from("<I", blob, start + 4)[0]
        cont = bytearray(record("CONT", 0x01000803, self.base_fields) + b"QBAD" + struct.pack("<H", 16) + b"xx")
        struct.pack_into("<I", cont, 4, len(cont) - 24)
        corrupt = blob[:start] + group(0, int.from_bytes(b"CONT", "little"), cont) + blob[end:]
        self.assertFalse(self.audit(corrupt)["offline_passed"])
        self.assertEqual(cr._fields(sub("XXXX", struct.pack("<I", 8)) + sub("QBIG", b"12345678")), [(b"QBIG", b"12345678")])
        with self.assertRaises(ValueError):
            cr._fields(sub("XXXX", struct.pack("<I", 8)))

    def test_wrong_metadata_types_return_failure_evidence(self):
        self.ids["plugin"] = None
        self.assertFalse(self.audit()["offline_passed"])
        self.ids["plugin"] = "Fixture.esm"
        self.objects["containers"][0]["model"] = None
        self.assertFalse(self.audit()["offline_passed"])

    def test_cli_pins_inputs_and_never_overwrites_an_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "Fixture.esm"
            plugin.write_bytes(self.blob())
            objects, ids, out = (root / n for n in ("objects.json", "formids.json", "report.json"))
            objects.write_text(json.dumps(self.objects))
            ids.write_text(json.dumps(self.ids))
            args = ["container_records", "--plugin", str(plugin), "--objects", str(objects), "--ids", str(ids), "--out", str(out)]
            with patch.object(sys, "argv", args):
                self.assertEqual(cr.main(), 0)
                self.assertEqual(cr.main(), 2)
            report = json.loads(out.read_text())
            self.assertTrue(report["offline_passed"])
            self.assertFalse(report["baseline_maps_checked"])
            self.assertEqual(len(report["input_sha256"]), 3)
            before = plugin.read_bytes()
            with patch.object(sys, "argv", args[:-1] + [str(plugin)]):
                self.assertEqual(cr.main(), 2)
            self.assertEqual(plugin.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
