"""Unit tests for src/fo4sf/bsa.py (BSA v104 read-only archive reader)."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.bsa import (  # noqa: E402
    BSA_MAGIC,
    BSA_VERSION_104,
    FILE_COMPRESS_TOGGLE,
    FLAG_COMPRESSED_BY_DEFAULT,
    FLAG_EMBED_FILE_NAMES,
    FLAG_INCLUDE_DIRECTORY_NAMES,
    FLAG_INCLUDE_FILE_NAMES,
    Bsa,
    BsaError,
    main,
)


def build_synthetic_bsa(
    entries,
    default_compressed=False,
    embed_names=False,
    toggle_names=(),
    version=BSA_VERSION_104,
    magic=BSA_MAGIC,
):
    """Build a valid synthetic v104 BSA from {full_path: raw_bytes}."""
    toggle_set = {n.replace("/", "\\").lower().lstrip("\\") for n in toggle_names}
    grouped = {}
    for full_path, data in entries.items():
        norm = full_path.replace("/", "\\").lstrip("\\")
        if "\\" in norm:
            folder, fname = norm.rsplit("\\", 1)
        else:
            folder, fname = "", norm
        grouped.setdefault(folder, []).append((norm, fname, data))

    archive_flags = FLAG_INCLUDE_DIRECTORY_NAMES | FLAG_INCLUDE_FILE_NAMES
    if default_compressed:
        archive_flags |= FLAG_COMPRESSED_BY_DEFAULT
    if embed_names:
        archive_flags |= FLAG_EMBED_FILE_NAMES

    folder_items = list(grouped.items())
    folder_count = len(folder_items)
    file_count = sum(len(v) for _, v in folder_items)

    # Calculate folder name & file name table sizes
    total_folder_name_len = sum(len(folder.encode("latin-1")) + 1 for folder, _ in folder_items)
    file_name_bytes = b"".join(fname.encode("latin-1") + b"\x00" for _, files in folder_items for _, fname, _ in files)
    total_file_name_len = len(file_name_bytes)

    # Offsets
    folder_table_off = 36
    file_blocks_off = folder_table_off + folder_count * 16
    file_blocks_len = sum(1 + (len(folder.encode("latin-1")) + 1) + len(files) * 16 for folder, files in folder_items)
    name_table_off = file_blocks_off + file_blocks_len
    data_start_off = name_table_off + total_file_name_len

    folder_records = []
    file_blocks = []
    payloads = []
    cur_block_off = file_blocks_off
    cur_data_off = data_start_off

    for f_idx, (folder, files) in enumerate(folder_items):
        f_bytes = folder.encode("latin-1") + b"\x00"
        # v104 stores folder_record.offset = actual_block_offset + total_file_name_len
        folder_records.append(struct.pack("<QII", f_idx + 1, len(files), cur_block_off + total_file_name_len))
        block = [struct.pack("<B", len(f_bytes)) + f_bytes]
        for e_idx, (norm, fname, raw_data) in enumerate(files):
            toggled = norm.lower() in toggle_set
            is_comp = bool(default_compressed) ^ toggled
            prefix = b""
            if embed_names:
                emb = norm.encode("latin-1")
                prefix = struct.pack("<B", len(emb)) + emb
            if is_comp:
                body = struct.pack("<I", len(raw_data)) + zlib.compress(raw_data)
            else:
                body = raw_data
            blob = prefix + body
            size_field = len(blob) | (FILE_COMPRESS_TOGGLE if toggled else 0)
            block.append(struct.pack("<QII", (f_idx + 1) * 100 + e_idx, size_field, cur_data_off))
            payloads.append(blob)
            cur_data_off += len(blob)
        block_bytes = b"".join(block)
        file_blocks.append(block_bytes)
        cur_block_off += len(block_bytes)

    assert cur_block_off == name_table_off
    header = struct.pack(
        "<4s8I",
        magic,
        version,
        folder_table_off,
        archive_flags,
        folder_count,
        file_count,
        total_folder_name_len,
        total_file_name_len,
        0,
    )
    return header + b"".join(folder_records) + b"".join(file_blocks) + file_name_bytes + b"".join(payloads)


class BsaReaderTests(unittest.TestCase):
    def _write_temp(self, blob: bytes) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".bsa", delete=False)
        tmp.write(blob)
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return tmp.name

    def test_uncompressed_and_default_compressed_and_lookup(self):
        files = {
            r"meshes\clutter\fan01.nif": b"Gamebryo-NIF-" * 40,
            r"meshes\clutter\plate01.nif": b"Gamebryo-PLATE-" * 25,
            r"menus\main\hud.xml": b"<menu><rect/></menu>",
        }
        for comp in (False, True):
            with self.subTest(default_compressed=comp):
                path = self._write_temp(build_synthetic_bsa(files, default_compressed=comp))
                a = Bsa(path)
                self.assertEqual(a.version, 104)
                self.assertEqual(len(a.entries), 3)
                self.assertEqual(a.find("MESHES/CLUTTER/FAN01.NIF"), 0)
                self.assertEqual(a.find(r"\menus\main\hud.xml"), 2)
                self.assertIsNone(a.find("meshes/missing.nif"))
                for k, want in files.items():
                    self.assertEqual(a.read(k), want)
                s = a.summary()
                self.assertEqual(s["compressed"], 3 if comp else 0)
                self.assertEqual(s["uncompressed"], 0 if comp else 3)

    def test_per_entry_compression_toggle_bit(self):
        files = {
            r"sound\fx\beep.wav": b"RIFF-UNCOMPRESSED-WAVE" * 10,
            r"meshes\props\crate.nif": b"NIF-COMPRESSED-BODY" * 50,
        }
        # Archive default compressed=True, but sound\fx\beep.wav toggled to uncompressed
        p1 = self._write_temp(
            build_synthetic_bsa(files, default_compressed=True, toggle_names=[r"sound\fx\beep.wav"])
        )
        a1 = Bsa(p1)
        self.assertFalse(a1.entries[a1.find("sound/fx/beep.wav")].compressed)
        self.assertTrue(a1.entries[a1.find("meshes/props/crate.nif")].compressed)
        self.assertEqual(a1.read("sound/fx/beep.wav"), files[r"sound\fx\beep.wav"])
        self.assertEqual(a1.read("meshes/props/crate.nif"), files[r"meshes\props\crate.nif"])

        # Archive default compressed=False, but meshes\props\crate.nif toggled to compressed
        p2 = self._write_temp(
            build_synthetic_bsa(files, default_compressed=False, toggle_names=[r"meshes\props\crate.nif"])
        )
        a2 = Bsa(p2)
        self.assertFalse(a2.entries[a2.find("sound/fx/beep.wav")].compressed)
        self.assertTrue(a2.entries[a2.find("meshes/props/crate.nif")].compressed)
        self.assertEqual(a2.read("sound/fx/beep.wav"), files[r"sound\fx\beep.wav"])
        self.assertEqual(a2.read("meshes/props/crate.nif"), files[r"meshes\props\crate.nif"])

    def test_embedded_filename_flag_0x0100_compressed_and_uncompressed(self):
        files = {
            r"textures\clutter\deskfan_d.dds": b"DDS " + b"\x55" * 256,
            r"textures\clutter\deskfan_n.dds": b"DDS " + b"\xAA" * 256,
        }
        for comp in (True, False):
            with self.subTest(default_compressed=comp):
                p = self._write_temp(
                    build_synthetic_bsa(files, default_compressed=comp, embed_names=True)
                )
                a = Bsa(p)
                self.assertTrue(a.archive_flags & FLAG_EMBED_FILE_NAMES)
                for k, want in files.items():
                    self.assertEqual(a.read(k), want)

    def test_extract_all_subset_cli_and_path_traversal_refusal(self):
        files = {
            r"meshes\a\one.nif": b"ONE",
            r"textures\b\two.dds": b"TWO",
        }
        bsa_path = self._write_temp(build_synthetic_bsa(files, default_compressed=True, embed_names=True))
        with tempfile.TemporaryDirectory(prefix="bsa-extract-") as out_dir:
            a = Bsa(bsa_path)
            sub_out = os.path.join(out_dir, "subset")
            written = a.extract_all(sub_out, names=["textures/b/two.dds"])
            self.assertEqual(len(written), 1)
            self.assertEqual(Path(sub_out, "textures", "b", "two.dds").read_bytes(), b"TWO")
            self.assertFalse(Path(sub_out, "meshes", "a", "one.nif").exists())

            full_out = os.path.join(out_dir, "full")
            self.assertEqual(main(["list", bsa_path, "--limit", "1"]), 0)
            self.assertEqual(main(["extract", bsa_path, "--out", full_out]), 0)
            self.assertEqual(Path(full_out, "meshes", "a", "one.nif").read_bytes(), b"ONE")
            self.assertEqual(Path(full_out, "textures", "b", "two.dds").read_bytes(), b"TWO")

            # Mutate entry name in memory to test traversal guards directly
            drive_colon = "X" + ":" + "evil.dll"
            for bad_name in (r"..\..\evil.dll", r"meshes\..\..\evil.dll", drive_colon, r"\abs\evil.dll"):
                a.entries[0].name = bad_name
                with self.assertRaises(BsaError):
                    a.extract_all(os.path.join(out_dir, "blocked"))

    def test_invalid_magic_version_truncation_and_corrupt_zlib_refused(self):
        files = {r"meshes\x.nif": b"DATA" * 30}
        with self.assertRaises(BsaError):
            Bsa(self._write_temp(build_synthetic_bsa(files, magic=b"BTDX")))

        for bad_ver in (103, 105, 1):
            with self.assertRaises(BsaError):
                Bsa(self._write_temp(build_synthetic_bsa(files, version=bad_ver)))

        with self.assertRaises(BsaError):
            Bsa(self._write_temp(b"BSA\x00\x68"))

        corrupt = bytearray(build_synthetic_bsa(files, default_compressed=True))
        corrupt[-4] ^= 0xFF
        corrupt[-3] ^= 0xFF
        a = Bsa(self._write_temp(bytes(corrupt)))
        with self.assertRaises(BsaError):
            a.read(0)


if __name__ == "__main__":
    unittest.main()
