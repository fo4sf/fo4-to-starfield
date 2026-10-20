"""Copy Starfield's door animation graphs (.agx, XML) out of its BA2s and summarise them (framework question A1:
what a *_Load graph adds over SimpleOpenClose01). Read-only on the game; the output is game data and stays on the PC
(never in Git), so the output folder must be new and outside the repository.

  python scripts/door_bridge/extract_door_graphs.py --starfield-data <Starfield\\Data> --out <new folder>

Takes every graph under meshes\\animtextdata\\tables\\graphs whose name matches --pattern (door families by default),
then every .agx those graphs name (their base graphs), until nothing new is named. Writes the files as stored, plus
summary.json: per graph its root attributes, node types with counts, the .agx files it names, and the distinct short
identifier strings it holds (event and variable names such as Open, Close, AnimSpeed), so two graphs can be diffed
without opening them.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.ba2 import Ba2  # noqa: E402

GRAPHS = "meshes\\animtextdata\\tables\\graphs\\"
DEFAULT_PATTERN = r"openclose|_load|airlock|elevator|door"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_ .:-]{0,47}$")
_AGX = re.compile(r"[A-Za-z0-9_\\/ .-]+\.agx", re.I)


def summarise(data):
    """{"root": attrs, "node_types": {type: n}, "graphs": [.agx names], "strings": [...]} of one .agx (XML)."""
    out = {"root": {}, "node_types": {}, "graphs": [], "strings": []}
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        out["error"] = f"not XML: {e}"
        return out
    out["root"] = dict(root.attrib)
    strings, graphs = set(), set()
    for el in root.iter():
        texts = list(el.attrib.values()) + ([el.text.strip()] if el.text and el.text.strip() else [])
        if el.tag == "node_type" and el.text:
            out["node_types"][el.text.strip()] = out["node_types"].get(el.text.strip(), 0) + 1
        for v in texts:
            graphs.update(m.group(0).strip() for m in _AGX.finditer(v))
            if _IDENT.match(v) and not re.fullmatch(r"[0-9a-fA-F-]{8,}", v):
                strings.add(v)
    out["graphs"] = sorted(graphs)
    out["strings"] = sorted(strings)
    return out


def _graph_name(ref):
    """The archive key of a graph a graph names: a full path, a path from AnimTextData, or a bare file name."""
    name = ref.replace("/", "\\").lower().lstrip("\\")
    if name.startswith("meshes\\"):
        return name
    if name.startswith("animtextdata\\"):
        return "meshes\\" + name
    return GRAPHS + name.rpartition("\\")[2]


def extract(archives, out_dir, pattern=DEFAULT_PATTERN):
    """archives: opened Ba2 objects. Returns the summary dict; writes the graphs and summary.json into out_dir."""
    index = {}
    for a in archives:
        for i, n in enumerate(a.names):
            key = n.replace("/", "\\").lower()
            if key.endswith(".agx") and key not in index:
                index[key] = (a, i, n)
    rx = re.compile(pattern, re.I)
    todo = sorted(k for k in index if k.startswith(GRAPHS) and rx.search(k.rpartition("\\")[2]))
    done, summary, missing = set(), {}, set()
    while todo:
        key = todo.pop(0)
        if key in done:
            continue
        done.add(key)
        a, i, stored = index[key]
        data = a.read(i)
        path = os.path.join(out_dir, *stored.replace("\\", "/").split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        s = summarise(data)
        s["bytes"], s["sha256"] = len(data), hashlib.sha256(data).hexdigest()
        summary[stored] = s
        # graphs named with ".agx", and bare names equal to another graph's file name (a base graph named by Name only)
        refs = s["graphs"] + [v + ".agx" for v in s["strings"] if GRAPHS + v.lower() + ".agx" in index]
        for ref in refs:
            k = _graph_name(ref)
            if k in index:
                if k not in done:
                    todo.append(k)
            else:
                missing.add(ref)
    result = {"graphs": summary, "named_but_not_found": sorted(missing)}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    return result


def _inside(path, root):
    """True if path is root or under it. Case-insensitive on Windows; a path on another drive is outside (commonpath
    raises ValueError there)."""
    path, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--starfield-data", required=True)
    ap.add_argument("--out", required=True, help="a new folder outside the repository")
    ap.add_argument("--pattern", default=DEFAULT_PATTERN, help="regex over graph file names")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        raise SystemExit(f"refusing to write into existing {out}: give a new folder")
    if _inside(out, ROOT):
        raise SystemExit("refusing to write game data inside the repository")
    paths = sorted(glob.glob(os.path.join(a.starfield_data, "Starfield - Animations*.ba2")))
    if not paths:
        raise SystemExit(f"no 'Starfield - Animations*.ba2' under {a.starfield_data}")
    os.makedirs(out)
    result = extract([Ba2(p) for p in paths], out, a.pattern)
    print(f"{len(result['graphs'])} graphs from {len(paths)} archives into {out}; "
          f"{len(result['named_but_not_found'])} named graphs not found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
