"""Packed output evidence uses synthetic BA2s, never installed game resources."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

from ba2_fixture import general_archive

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_packed_experiment import verify_archive  # noqa: E402


class PackedExperimentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "synthetic.ba2"
        self.resources = {"Terrain/World.btd": b"synthetic terrain", "textures/mask.dds": b"synthetic mask"}
        self.inputs = {"Data/" + name: hashlib.sha256(data).hexdigest()
                       for name, data in self.resources.items()}
        self.inputs["plugin/Experiment.esm"] = hashlib.sha256(b"plugin").hexdigest()

    def verify(self, entries=None, **kwargs):
        self.path.write_bytes(general_archive(self.resources if entries is None else entries, **kwargs))
        verify_archive(str(self.path), self.inputs)

    def test_stored_general_layouts_preserve_terrain_and_mask(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                self.verify(version=version)
        self.verify({name.upper().replace("/", "\\"): data for name, data in self.resources.items()})

    def test_missing_or_unexpected_resources_are_rejected(self):
        for entries in ({}, {"other.btd": b"x", "textures/mask.dds": b"synthetic mask"},
                        dict(self.resources, extra=b"unexpected")):
            with self.subTest(entries=list(entries)):
                with self.assertRaises(ValueError):
                    self.verify(entries)

    def test_compressed_resources_are_rejected_even_when_bytes_would_match(self):
        with self.assertRaisesRegex(ValueError, "uncompressed"):
            self.verify(compressed=True)

    def test_duplicate_names_cannot_hide_missing_resource(self):
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.verify([("Terrain/World.btd", b"synthetic terrain"), ("TERRAIN\\WORLD.BTD", b"synthetic terrain")])

    def test_changed_bytes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify(dict(self.resources, **{"Terrain/World.btd": b"wrong terrain"}))

    def test_truncated_or_wrong_layout_is_rejected(self):
        valid = general_archive(self.resources)
        for blob in (b"BTDX", valid[:32], valid[:8] + b"DX10" + valid[12:], valid[:-7]):
            with self.subTest(size=len(blob)):
                self.path.write_bytes(blob)
                with self.assertRaises(ValueError):
                    verify_archive(str(self.path), self.inputs)

    def test_case_colliding_inputs_are_rejected(self):
        self.inputs["Data/TERRAIN/WORLD.BTD"] = self.inputs["Data/Terrain/World.btd"]
        self.path.write_bytes(general_archive(self.resources))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify_archive(str(self.path), self.inputs)
