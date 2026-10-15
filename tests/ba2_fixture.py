"""Small synthetic General BA2s using the record layout read by fo4sf.ba2."""
import struct
import zlib


def general_archive(entries, compressed=False, version=2):
    entries = list(entries.items()) if isinstance(entries, dict) else list(entries)
    extra = {1: b"", 2: bytes(8), 3: bytes(12)}[version]
    offset = 24 + len(extra) + 36 * len(entries)
    records, payloads, names = [], [], []
    for name, data in entries:
        payload = zlib.compress(data) if compressed else data
        extension = name.rsplit(".", 1)[-1].upper().encode("ascii")[:4].ljust(4, b"\0")
        records.append(struct.pack("<I4sIIQIII", 0, extension, 0, 0, offset,
                                   len(payload) if compressed else 0, len(data), 0))
        payloads.append(payload)
        encoded = name.encode("utf-8")
        names.append(struct.pack("<H", len(encoded)) + encoded)
        offset += len(payload)
    return (struct.pack("<4sI4sIQ", b"BTDX", version, b"GNRL", len(entries), offset) + extra
            + b"".join(records) + b"".join(payloads) + b"".join(names))


def archive_from_tree(root):
    return general_archive({p.relative_to(root).as_posix(): p.read_bytes()
                            for p in sorted(root.rglob("*")) if p.is_file()})
