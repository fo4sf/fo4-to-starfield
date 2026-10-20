"""Synthetic tests for Ba2.largest_entries and by_extension."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class LargestEntriesTests(unittest.TestCase):
    def test_orders_by_unpacked_size(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            top = a.largest_entries(2)
            self.assertEqual(len(top), 2)
            self.assertEqual(top[0]["name"], "large.dat")
            self.assertEqual(top[0]["unpacked"], 1000)
            self.assertGreater(top[0]["packed"], 0)  # compressed
            self.assertEqual(top[1]["name"], "medium.bin")
            self.assertEqual(top[1]["unpacked"], 100)

    def test_empty_and_n_limit(self):
        data = general_archive({"only.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(len(a.largest_entries(5)), 1)
            self.assertEqual(a.largest_entries(0), [])

    def test_by_extension_counts(self):
        entries = {
            "meshes/chair.nif": b"nifdata",
            "meshes/table.NIF": b"more",
            "textures/stone.dds": b"ddsdata",
            "materials/iron.bgsm": b"mat",
            "readme.txt": b"text",
            "noext": b"raw",
        }
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mix.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            counts = a.by_extension()
            self.assertEqual(counts.get("nif"), 2)
            self.assertEqual(counts.get("dds"), 1)
            self.assertEqual(counts.get("bgsm"), 1)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get(""), 1)
            self.assertEqual(sum(counts.values()), 6)

    def test_dotted_directory_is_not_a_filename_extension(self):
        for name in ["textures.v1/README", "textures.v1\\README", "parent.v2/sub.dir/README"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "dotted.ba2")
                data = general_archive({name: b"synthetic"})
                with open(path, "wb") as f:
                    f.write(data)
                archive = Ba2(path)
                self.assertEqual(archive.by_extension(), {"": 1})
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), data)

    def test_mixed_separator_paths_and_multidot_leaf_keep_real_extensions(self):
        entries = {"parent.v2/sub.dir/file.part.NIF": b"one",
                   "parent.v2\\sub.dir/file.DDS": b"two",
                   "parent.v2/sub.dir\\file.BGSM": b"three",
                   "parent.v2/README": b"four"}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mixed.ba2")
            with open(path, "wb") as f:
                f.write(general_archive(entries, compressed=True))
            archive = Ba2(path)
            self.assertEqual(archive.by_extension(), {"nif": 1, "dds": 1, "bgsm": 1, "": 1})
            for name, expected in entries.items():
                self.assertEqual(archive.read(name.replace("/", "\\")), expected)


if __name__ == "__main__":
    unittest.main()
