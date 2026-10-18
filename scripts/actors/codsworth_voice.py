"""Codsworth's FO4 voice files -> .wav (ffmpeg) -> Starfield .wem (Wwise 2021.1.10 WwiseConsole). PC only.

    probe:   python scripts/actors/codsworth_voice.py probe --sf-voices "<Starfield Data>\\Starfield - Voices02.ba2"
             prints the RIFF fmt chunk (codec tag, channels, rate) of the vanilla RobotMiniBotA .wem files, so ours match.
    extract: python scripts/actors/codsworth_voice.py extract --voices "<depot_377164>\\Data\\Fallout4 - Voices.ba2"
                 --lines <codsworth_lines.tsv> --count 20 --out <dir> [--rate 44100]
             first N rows of the suggested batch (or --infos 0001A2B3,...) -> <dir>\\fuz, <dir>\\wav, <dir>\\lines.tsv.
    wem:     python scripts/actors/codsworth_voice.py wem --wwise-console <WwiseConsole.exe> --out <dir> [--conversion <name>]
             a scratch Wwise project in <dir>\\wwise, then convert-external-source on every <dir>\\wav file -> <dir>\\wem.

.fuz layout (UESP "FUZ file"; checked by this script on each file): "FUZE", u32 version, u32 lip size, lip data, then
an xWMA RIFF. The xWMA is handed to ffmpeg (its xwma demuxer) and written as 16-bit mono PCM. Lip data is not used: the
mini bot body has no face. Which codec and rate Starfield's voice .wem files use is what `probe` is for; until it has
run on the PC that is unresolved.
"""
import argparse
import csv
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf.ba2 import Ba2  # noqa: E402

SF_VOICE_DIR = "sound\\voice\\starfield.esm\\robotminibota\\"
FIRST_BATCH = ("HELO", "GREE", "IDAT", "IDLE", "HIT_", "ASNC", "AGRE")


def riff_fmt(data: bytes) -> dict:
    if data[:4] != b"RIFF":
        return {"error": f"not RIFF: {data[:4]!r}"}
    p = 12
    while p + 8 <= len(data):
        cid, size = data[p:p + 4], struct.unpack_from("<I", data, p + 4)[0]
        if cid == b"fmt ":
            tag, ch, rate, avg = struct.unpack_from("<HHII", data, p + 8)
            return {"form": data[8:12].decode("latin-1"), "codec_tag": f"{tag:#06x}", "channels": ch, "rate": rate,
                    "avg_bytes_per_s": avg, "fmt_size": size}
        p += 8 + size + (size & 1)
    return {"error": "no fmt chunk"}


def split_fuz(data: bytes):
    """(lip bytes, xWMA bytes) of a .fuz."""
    if data[:4] != b"FUZE":
        raise ValueError(f"not a .fuz: {data[:4]!r}")
    _version, lip = struct.unpack_from("<II", data, 4)
    audio = data[12 + lip:]
    if audio[:4] != b"RIFF":
        raise ValueError(f".fuz audio is not RIFF: {audio[:4]!r}")
    return data[12:12 + lip], audio


def pick(rows, count, infos):
    if infos:
        want = {i.upper() for i in infos}
        return [r for r in rows if r["info"].upper() in want]
    batch = sorted((r for r in rows if r["subtype"] in FIRST_BATCH and r["text"]),
                   key=lambda r: (FIRST_BATCH.index(r["subtype"]), len(r["text"])))
    return batch[:count]


def cmd_probe(a):
    arch = Ba2(a.sf_voices)
    hits = [e.name for e in arch.entries if e.name.lower().replace("/", "\\").startswith(SF_VOICE_DIR)]
    for name in hits[:5]:
        print(name, riff_fmt(arch.read(name)[:4096]))
    print(f"{len(hits)} files in {SF_VOICE_DIR}")
    return 0


def cmd_extract(a):
    with open(a.lines, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    chosen = pick(rows, a.count, a.infos.split(",") if a.infos else None)
    arch = Ba2(a.voices)
    for sub in ("fuz", "wav"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    out_rows = []
    for r in chosen:
        stem = f"{r['info'].lower()}_{r['response']}"
        _lip, xwma = split_fuz(arch.read(r["voice"]))
        xpath = os.path.join(a.out, "fuz", stem + ".xwm")
        with open(xpath, "wb") as f:
            f.write(xwma)
        wav = os.path.join(a.out, "wav", stem + ".wav")
        subprocess.run([a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", xpath, "-ac", "1", "-ar", str(a.rate),
                        "-c:a", "pcm_s16le", wav], check=True)
        out_rows.append({**r, "wav": wav, "wav_bytes": os.path.getsize(wav)})
        print(f"{stem} {os.path.getsize(wav)} B  {r['subtype']} {r['quest']}: {r['text'][:80]}")
    with open(os.path.join(a.out, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]) if out_rows else ["info"], delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(out_rows)} lines -> {os.path.join(a.out, 'wav')}")
    return 0


def cmd_wem(a):
    proj_dir = os.path.join(a.out, "wwise")
    proj = os.path.join(proj_dir, "CodsworthVoice.wproj")
    if not os.path.exists(proj):
        subprocess.run([a.wwise_console, "create-new-project", proj, "--platform", "Windows", "--quiet"], check=True)
    wav_dir = os.path.abspath(os.path.join(a.out, "wav"))
    sources = os.path.join(a.out, "codsworth.wsources")
    with open(sources, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<ExternalSourcesList SchemaVersion="1" Root="{wav_dir}">\n')
        for fn in sorted(os.listdir(wav_dir)):
            if fn.lower().endswith(".wav"):
                f.write(f'  <Source Path="{fn}" Conversion="{a.conversion}"/>\n')
        f.write("</ExternalSourcesList>\n")
    wem_dir = os.path.abspath(os.path.join(a.out, "wem"))
    subprocess.run([a.wwise_console, "convert-external-source", proj, "--platform", "Windows", "--source-file", sources,
                    "--output", wem_dir, "--quiet"], check=True)
    made = []
    for dp, _d, fns in os.walk(wem_dir):
        made += [os.path.join(dp, fn) for fn in fns if fn.lower().endswith(".wem")]
    for p in sorted(made)[:5]:
        with open(p, "rb") as f:
            print(os.path.relpath(p, wem_dir), os.path.getsize(p), riff_fmt(f.read(4096)))
    print(f"{len(made)} .wem files in {wem_dir}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("probe")
    p.add_argument("--sf-voices", required=True)
    p = sp.add_parser("extract")
    p.add_argument("--voices", required=True)
    p.add_argument("--lines", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--infos", help="comma-separated INFO ids instead of the suggested batch")
    p.add_argument("--rate", type=int, default=44100)   # vanilla RobotMiniBotA .wem: Vorbis, mono, 44100 Hz (probe, PC 2026-10-18)
    p.add_argument("--ffmpeg", default="ffmpeg")
    p = sp.add_parser("wem")
    p.add_argument("--wwise-console", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--conversion", default="Vorbis Quality High", help="conversion ShareSet name in the scratch project")
    a = ap.parse_args(argv)
    return {"probe": cmd_probe, "extract": cmd_extract, "wem": cmd_wem}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
