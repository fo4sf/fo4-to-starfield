"""Every doc comment and string literal in the repo's Papyrus sources stays well under 4 KB.

newgame_v11 crashed Starfield while the game loaded its data files, before the main menu, on every launch (29 to 31 Oct
2026), and newgame_v10 did not. The crash dump's register held the bytes 4,096 to 4,103 of FO4SF_NewGameQuest.psc's
doc comment ("ell for ", from "load the cell for"), which v11 had grown to 4,196 bytes (v10's: 2,745). So Starfield's
script loader copies a doc comment into a 4 KB buffer, and the bytes past it overwrite what follows (supported
hypothesis, from that dump: docs/newgame/vault111-start.md section 13a). The compiler keeps doc comments ({...}) and
string literals in the .pex; ";" comments it leaves out, so long notes go there.

LIMIT leaves a quarter of the buffer free: a Windows checkout may turn each line end into two bytes (counted here), and a
terminator may follow. The longest doc comment that has loaded in game is 2,745 bytes (v10's header).
"""
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 3072
BUFFER = 4096                       # where the bytes in the 31 Oct crash dump came from
SKIP_DIRS = {".git", "__pycache__", ".venv", "bin", "obj", ".vs", "node_modules", ".claude"}


def papyrus_texts(src):
    """[(kind, line, text)] of every doc comment ("doc", the text between { and }) and string literal ("string", the
    text between the quotes, escapes as written) in a Papyrus source, in file order. ";" line comments and ";/ ... /;"
    block comments are skipped, so braces or quotes inside them count for nothing; so are braces inside a string."""
    out = []
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c == ";":
            if src.startswith(";/", i):
                end = src.find("/;", i + 2)
                end = n if end < 0 else end + 2
            else:
                end = src.find("\n", i)
                end = n if end < 0 else end
            line += src.count("\n", i, end)
            i = end
        elif c == "{":
            end = src.find("}", i + 1)
            end = n if end < 0 else end
            out.append(("doc", line, src[i + 1:end]))
            line += src.count("\n", i, end)
            i = end + 1
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"' and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(("string", line, src[i + 1:min(j, n)]))
            i = j + 1
        else:
            i += 1
    return out


def size(text):
    """Bytes as stored with Windows line ends: UTF-8, each line end counted as two."""
    return len(text.encode("utf-8")) + text.count("\n")


def sources(root=ROOT):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower().endswith(".psc"):
                yield os.path.join(dirpath, fn)


def too_long(root=ROOT):
    """["path:line kind of N bytes"] for every doc comment and string literal over LIMIT in the .psc files under root,
    sorted by path."""
    out = []
    for path in sorted(sources(root)):
        with open(path, encoding="utf-8") as f:
            for kind, line, text in papyrus_texts(f.read()):
                if size(text) > LIMIT:
                    out.append(f"{os.path.relpath(path, root).replace(os.sep, '/')}:{line} {kind} of {size(text)} bytes")
    return out


class PapyrusStringsTest(unittest.TestCase):
    def test_every_doc_comment_and_string_is_short(self):
        self.assertGreaterEqual(len(list(sources())), 21)    # the repo's scripts were found (21 on 31 Oct 2026)
        self.assertEqual(too_long(), [], f"over {LIMIT} bytes (Starfield's script loader crashed on one of 4,196): "
                                         "shorten it, and move long notes into ';' comments")

    def test_the_scan_finds_a_long_doc_and_a_long_string_in_any_file(self):
        """The repo-wide scan itself, on a made-up folder: at the limit passes, one byte over fails, for a doc comment
        and a string, in a second file and a subfolder too; folders in SKIP_DIRS are left out."""
        at_limit = "x" * LIMIT
        over = "y" * (LIMIT + 1)
        files = {
            "A.psc": f'Scriptname A extends Quest\n{{{at_limit}}}\nstring Property S = "{at_limit}" Auto Const\n',
            "sub/B.psc": f"Scriptname B extends Quest\n{{{over}}}\n",
            "sub/C.psc": f'Scriptname C extends Quest\n\nstring Property S = "{over}" Auto Const\n',
            "obj/D.psc": f"Scriptname D extends Quest\n{{{over}}}\n",
        }
        with tempfile.TemporaryDirectory() as root:
            for rel, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                with open(os.path.join(root, rel), "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            self.assertEqual(len(list(sources(root))), 3)
            self.assertEqual(too_long(root), [f"sub/B.psc:2 doc of {LIMIT + 1} bytes",
                                              f"sub/C.psc:3 string of {LIMIT + 1} bytes"])

    def test_the_quest_script_header_is_the_short_one(self):
        """The doc comment that crashed the game is short now, its stage contract kept (the stage contract test reads
        it), and the notes it carried are ";" comments after it."""
        with open(os.path.join(ROOT, "scripts", "newgame", "FO4SF_NewGameQuest.psc"), encoding="utf-8") as f:
            src = f.read()
        texts = papyrus_texts(src)
        kind, line, header = texts[0]
        self.assertEqual((kind, line), ("doc", 2))
        self.assertLessEqual(size(header), LIMIT)
        self.assertIn("Stages are the published contract", header)
        self.assertNotIn("load the cell for", header)      # the crash dump's bytes are in a ";" note now
        notes = src[src.index("}") + 1:src.index("GlobalVariable Property GameDaysPassed")]
        self.assertTrue(all(not ln.strip() or ln.startswith(";") for ln in notes.strip("\n").split("\n")))
        self.assertIn("tests/test_papyrus_strings.py", notes)
        self.assertIn("load the cell for (Debug.CenterOnCell)", notes)

    def test_the_limit_leaves_room_in_the_buffer(self):
        self.assertLessEqual(LIMIT, BUFFER * 3 // 4)
        self.assertGreater(LIMIT, 2745 + 2745 // 10)         # v10's header, which loaded, fits with room for line ends

    def test_doc_comments_and_strings_are_found(self):
        src = ('Scriptname X extends Quest\n{Line one\n line two}\n'
               'string Property P = "a {not a doc} b" Auto Const\n'
               '; a comment with { and " in it\n'
               ';/ a block comment\n with { braces } and "quotes"\n/;\n'
               'Function F()\n    Trace("say \\"hi\\" {x}") ; trailing { comment\nEndFunction\n'
               'int Property Q Auto\n{Q\'s doc}\n')
        self.assertEqual(papyrus_texts(src), [
            ("doc", 2, "Line one\n line two"),
            ("string", 4, "a {not a doc} b"),
            ("string", 10, 'say \\"hi\\" {x}'),
            ("doc", 13, "Q's doc"),
        ])

    def test_size_counts_windows_line_ends(self):
        self.assertEqual(size("ab\ncd"), 6)
        self.assertEqual(size("é"), 2)
        self.assertEqual(size(""), 0)

    def test_the_crashing_header_would_fail(self):
        """A doc comment as long as v11's (4,196 bytes, its line ends as LF) is over the limit; v10's length is not."""
        long_doc = "Scriptname X extends Quest\n{" + ("x" * 99 + "\n") * 41 + "x" * 96 + "}\n"
        (kind, _, text), = papyrus_texts(long_doc)
        self.assertEqual((kind, len(text.encode())), ("doc", 4196))
        self.assertGreater(size(text), LIMIT)
        self.assertLessEqual(size("x" * 2745), LIMIT)


if __name__ == "__main__":
    unittest.main()
