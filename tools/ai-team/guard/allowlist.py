"""The unattended Lead's shell guard: a command runs only if it matches an exact argument list below.

OpenCode's bash rules match a command as text, one pattern at a time, and some shapes get past any list of patterns:
git reads a file outside the repo with no flag once a path lies outside the worktree, a $(...) is built after the
check, and a workdir can point anywhere. This guard reads a command the way bash and PowerShell read it, refuses every
shell metacharacter and expansion, and accepts only the argument lists below. Anything else is refused.

The OpenCode plugin .opencode/plugin/fo4-guard.js runs this before each shell call and each file write. It passes one
JSON object on stdin, for a shell call:
  {"root": "<worktree root>", "directory": "<the session's folder>", "command": "<the command text>",
   "workdir": "<optional directory>", "owner_present": false}
and for a file write (edit, write, multiedit, patch, apply_patch), the paths the tool would write:
  {"root": "<worktree root>", "write": ["<path>", ...]}
owner_present is true only in the owner's terminal (terminal.ps1), never in an unattended run: it adds the implementation
agent's branch and commit wrapper (agent_git.py). Allowed is exit 0 with {"allowed": true} on stdout; the plugin needs
both, so a wrong program that only exits 0 refuses too. Refused is exit 1 with {"allowed": false, "reason": "..."}.
Anything unreadable is a refusal too. Run it by hand (PowerShell):  Get-Content call.json | python -I tools/ai-team/guard/allowlist.py
"""
import ast
import json
import os
import re
import sys
import unicodedata
import warnings


class Refused(Exception):
    pass


# Shell syntax outside quotes: separators, redirects, expansions, globs, comments, escapes, history expansion. The comma
# is here too: PowerShell splits an unquoted a,b into two arguments, so a value with a comma must be quoted.
BAD_BARE = set(";&|<>$`(){}[]*?%@#!\\,")
# What bash or PowerShell expands inside double quotes, quote characters that Windows argument passing mangles, and what
# cmd.exe would read as syntax if a program on the list ever resolved to a .bat or .cmd shim; refused in any quoted
# argument, to keep one rule.
BAD_QUOTED = set("$`\\!'\"&|^%<>")
# PowerShell turns a bare argument that reads as a number into that number, then passes its own text of it: 0x10 reaches
# the program as 16, 1kb as 1024, .5 as 0.5. Only plain digits pass through unchanged.
PS_NUMBER = re.compile(r"(?:0x[0-9a-f]+|0b[01]+|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?)"
                       r"(?:[lduysn]|ul|us|uy|un)?(?:kb|mb|gb|tb|pb)?", re.IGNORECASE)

WORD = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/,+=-]{0,199}")
DIGITS = re.compile(r"[0-9]{1,4}")
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_/.-]*(?:[~^][0-9]*)*")
PATH = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*")


def tokenize(command):
    """Split a command into arguments the way bash and PowerShell do for the forms allowed here. Anything the two shells
    could read differently (a quote in the middle of an argument, an unclosed quote, a character outside printable ASCII)
    is refused rather than guessed at."""
    if any(c != " " and not " " < c <= "~" for c in command):
        raise Refused("only printable ASCII and spaces are allowed")
    tokens, word, i = [], None, 0          # word: the characters of the argument being read, None between arguments
    while i < len(command):
        c = command[i]
        if c == " ":
            if word is not None:
                tokens.append(bare_word(word))
                word = None
            i += 1
        elif c in "'\"":
            if word is not None:
                raise Refused("a quote must start an argument")
            end = command.find(c, i + 1)
            if end < 0:
                raise Refused("unterminated quote")
            body = command[i + 1:end]
            if any(x in BAD_QUOTED or x == "\n" for x in body):
                raise Refused("a quoted argument may not contain a quote mark, $, a backtick, a backslash, !, &, |, ^, %, "
                              "< or >")
            tokens.append(body)
            i = end + 1
            if i < len(command) and command[i] != " ":
                raise Refused("a quote must end its argument")
        elif c in "~^":
            if word is None:
                raise Refused(f"{c} is not allowed at the start of an argument")
            if c == "~" and ("=" in word or ":" in word):     # bash expands x=~ and x=a:~ to the home folder
                raise Refused("~ is not allowed after = or :")
            word.append(c)
            i += 1
        elif c in BAD_BARE:
            raise Refused(f"shell syntax is not allowed: {c}")
        else:
            if word is None:
                word = []
            word.append(c)
            i += 1
    if word is not None:
        tokens.append(bare_word(word))
    if not tokens:
        raise Refused("empty command")
    return tokens


def bare_word(word):
    """Close a bare argument: one PowerShell would pass on as a different number is refused."""
    text = "".join(word)
    core = text[1:] if text[:1] in "+-" else text
    if PS_NUMBER.fullmatch(core) and not (core.isdigit() and text[:1] != "+"):
        raise Refused(f"PowerShell would pass {text!r} on as a number: write plain digits, or quote it")
    return text


def digits(value):
    return DIGITS.fullmatch(value) is not None


def word(value):
    return WORD.fullmatch(value) is not None


def one_of(*allowed):
    return lambda value: value in allowed


def revision(token):
    """A git revision or a range (A..B, A...B) written without a path or a drive: no ':', no leading '.', no '..' segment
    that could climb out of the repo."""
    parts = re.split(r"\.\.\.?", token)
    return len(parts) <= 2 and all(p and REVISION.fullmatch(p) for p in parts)


def path(token):
    return PATH.fullmatch(token) is not None and all(seg not in (".", "..") for seg in token.rstrip("/").split("/"))


def take_options(tokens, spec):
    """Split tokens into (positional, option names). spec maps an option to None (a switch) or to a value check. A value
    option takes its value from the same token (--name=value) or from the next one. Any other option is refused."""
    positional, names, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-") or tok == "-":
            positional.append(tok)
            i += 1
            continue
        name, eq, value = tok.partition("=")
        if name not in spec:
            raise Refused(f"option not allowed: {name}")
        check = spec[name]
        if check is None:
            if eq:
                raise Refused(f"{name} takes no value")
            i += 1
        else:
            if eq:
                i += 1
            else:
                if i + 1 >= len(tokens):
                    raise Refused(f"{name} needs a value")
                value = tokens[i + 1]
                i += 2
            if not check(value):
                raise Refused(f"{name} value not allowed: {value!r}")
        names.append(name)
    return positional, names


def split_paths(tokens):
    """Everything before a bare '--' is options and revisions; everything after it is paths."""
    if "--" not in tokens:
        return tokens, []
    k = tokens.index("--")
    return tokens[:k], tokens[k + 1:]


# ---- gh: the Lead reads issues and PRs, and comments on #32 only -------------------------------------------------------

LIST_OPTS = {"--state": one_of("open", "closed", "all"), "--limit": digits, "--label": word, "--json": word}
VIEW_OPTS = {"--comments": None, "--json": word}
DIFF_OPTS = {"--name-only": None}


# Characters that read as the letters of "for Claude": digits and marks, a capital I (lowercased first), and the
# Cyrillic and Greek look-alikes of those letters.
LOOKALIKES = str.maketrans("01|!i\u0131\u0456\u04cf\u0430\u0435\u043e\u0441\u0501\u03bf\u03b1\u03f2\u03c5",
                           "olllllllaeocdoacu")


def is_handoff(text):
    """A comment that reads as a handoff to Claude however it is marked up: with markup a reader does not see taken out
    (a link's target, an HTML tag or comment, an entity) and look-alikes read as the letters they look like, its letters
    alone, lowercased, start with leadlocalforclaude (so **for Claude:**, for-Claude, F O R Claude, [](x)for Claude and
    for CIaude all count)."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"<!--.*?(?:-->|$)|<[^>]*>|&#?\w+;|\]\([^)]*\)", "", text, flags=re.S)
    return re.sub(r"[^a-z]", "", text.lower().translate(LOOKALIKES)).startswith("leadlocalforclaude")


def gh(argv, owner_present=False):
    head = argv[1:3]
    if head in (["issue", "list"], ["pr", "list"]):
        positional, _ = take_options(argv[3:], LIST_OPTS)
        if positional:
            raise Refused("gh list takes no positional argument")
        return
    if head in (["issue", "view"], ["pr", "view"]):
        positional, _ = take_options(argv[3:], VIEW_OPTS)
        if len(positional) != 1 or not digits(positional[0]):
            raise Refused("gh view takes one issue or PR number")
        return
    if head == ["pr", "diff"]:
        positional, _ = take_options(argv[3:], DIFF_OPTS)
        if len(positional) != 1 or not digits(positional[0]):
            raise Refused("gh pr diff takes one PR number")
        return
    if head == ["pr", "checks"]:
        if len(argv) != 4 or not digits(argv[3]):
            raise Refused("gh pr checks takes one PR number")
        return
    if argv[1:5] == ["issue", "comment", "32", "--body"] and len(argv) == 6:
        text = argv[5]
        if not text.startswith("Lead (local): ") or len(text) > 1500:
            raise Refused("the Lead's comment on #32 starts with 'Lead (local): ' and is at most 1500 characters")
        # Claude reads a "for Claude" comment as a handoff the owner started (/handoff), so only their terminal posts one.
        if is_handoff(text) and not owner_present:
            raise Refused("a handoff to Claude (Lead (local): for Claude: ...) is posted from the owner's terminal only")
        return
    raise Refused("this gh command is not on the list")


# ---- git: read-only, inside the repo -----------------------------------------------------------------------------------

STATUS_OPTS = {"--short": None, "-s": None, "--branch": None, "-b": None, "--porcelain": None}
LOG_OPTS = {"-n": digits, "--max-count": digits, "--oneline": None, "--stat": None, "--no-color": None,
            "--graph": None, "--name-only": None, "--name-status": None}
DIFF_SWITCHES = {"--stat": None, "--name-only": None, "--name-status": None, "--no-color": None,
                 "--cached": None, "--staged": None}
SHOW_SWITCHES = {"--stat": None, "--name-only": None, "--oneline": None, "--no-color": None, "-s": None,
                 "--no-patch": None}
REV_PARSE = (["HEAD"], ["--short", "HEAD"], ["--abbrev-ref", "HEAD"], ["--show-toplevel"], ["--absolute-git-dir"])


def git_revs_and_paths(rest, spec, max_revs=None):
    before, after = split_paths(rest)
    positional, _ = take_options(before, spec)
    if (max_revs is not None and len(positional) > max_revs) or not all(revision(r) for r in positional):
        raise Refused("expected revisions before -- and paths after it")
    if not all(path(p) for p in after):
        raise Refused("a path must be relative, inside the repo, with no '..' segment")


def git(argv):
    sub, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if sub == "status":
        positional, _ = take_options(rest, STATUS_OPTS)
        if positional:
            raise Refused("git status takes switches only")
    elif sub == "log":
        expanded = []
        for tok in rest:                          # git's -5 is -n 5
            if re.fullmatch(r"-[0-9]{1,4}", tok):
                expanded += ["-n", tok[1:]]
            else:
                expanded.append(tok)
        git_revs_and_paths(expanded, LOG_OPTS)
    elif sub == "diff":
        git_revs_and_paths(rest, DIFF_SWITCHES)
    elif sub == "show":
        git_revs_and_paths(rest, SHOW_SWITCHES, max_revs=1)
    elif sub == "worktree" and rest in (["list"], ["list", "--porcelain"]):
        return
    elif sub == "branch" and rest in ([], ["--show-current"], ["--list"]):
        return
    elif sub == "rev-parse" and rest in REV_PARSE:
        return
    else:
        raise Refused(f"git {sub or '(nothing)'} is not on the list")


# ---- python: the team's own scripts, the unit tests and the repo guard -------------------------------------------------

TEAM_SCRIPTS = (
    ["tools/ai-team/guardian/guardian.py", "status"],
    ["tools/ai-team/guardian/guardian.py", "report"],
    ["tools/ai-team/team.py", "board"],
    ["tools/ai-team/team.py", "status"],
    ["tools/ai-team/models.py", "list"],
    ["tools/ai-team/wake_agent.py", "status"],
    ["scripts/guard.py"],
)
# The Codex and Grok wakes are refused: wake_agent.py codex|grok starts an agent with approvals on a brief, which the
# unattended Lead may not do. The owner decides whether it may. `wake_agent.py status` only reads idle times.
# A test by name: a module that exists as tests/test_<name>.py, optionally one TestCase class in it and one test method
# of that class. unittest calls whatever a longer dotted name ends on (tests.test_x.some_module.main would run main(),
# and a plain class would be instantiated), so a class must be a TestCase defined in that file (test_case_classes) and a
# method one defined in its body; nothing else is allowed after the module name. Discovery imports test files only.
# Unittest never runs with -I: that drops the repo folder from sys.path, so `tests` could be a package from elsewhere.
TEST_NAME = re.compile(r"tests\.(test_[a-z0-9_]+)(?:\.([A-Za-z_][A-Za-z0-9_]*)(?:\.(test[A-Za-z0-9_]*))?)?")


def bound_names(node):
    """The names a top-level statement binds directly (a def, a class, an import, an assignment's targets)."""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return [node.name]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
    return [n.id for t in targets if t is not None for n in ast.walk(t) if isinstance(n, ast.Name)]


def scope_bindings(body, tree=None):
    """How many times each name is bound in one scope (a module, or a class body), counting every binding and not only
    the top-level statements: names stored or deleted anywhere in the scope's statements (inside if, try, with, for,
    while and match blocks, comprehensions and walrus targets too), except-as and match-capture names, imports, and the
    names of defs and classes, and `global` declarations. Function, lambda and class bodies are scopes of their own and
    are not entered, but for a module (tree given) a `global` anywhere in the file counts as a binding. A star import
    binds an unknown set of names: it counts as the name '*'. Counting too much only refuses a name, never allows one.
    This reads syntax only: setattr, globals(), exec and the like are not seen, so it trusts the repo's own test files
    not to rebind their names at run time."""
    counts = {}

    def add(name):
        counts[name] = counts.get(name, 0) + 1

    def outside(node):                              # what a def, lambda or class evaluates in the enclosing scope
        args = getattr(node, "args", None)
        found = list(getattr(node, "decorator_list", [])) + list(getattr(node, "bases", [])) + \
            [k.value for k in getattr(node, "keywords", [])]
        if args is not None:
            found += list(args.defaults) + [d for d in args.kw_defaults if d is not None]
            found += [a.annotation for a in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
                      if a is not None and a.annotation is not None]
        if getattr(node, "returns", None) is not None:
            found.append(node.returns)
        return found

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            if not isinstance(node, ast.Lambda):
                add(node.name)
            for child in outside(node):
                visit(child)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                add("*" if a.name == "*" else (a.asname or a.name).split(".")[0])
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            add(node.rest)
        elif isinstance(node, ast.Global):          # in a class body: the def that follows binds the module's name
            for n in node.names:
                add(n)
        for child in ast.iter_child_nodes(node):
            visit(child)
    for stmt in body:
        visit(stmt)
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for n in node.names:
                    add(n)
    return counts


def test_case_classes(source):
    """{class name: method names} for the TestCase classes of a test file, read from its syntax, not imported. A class
    counts if the file binds its name once, one of its bases is unittest.TestCase (or TestCase imported from unittest,
    or such a class of the same file defined above it), its other bases are plain mixin classes of the same file
    defined above it, it takes no keywords and no __init_subclass__, and its only decorators are unittest's own marks.
    A method counts if the class body binds its name once (a class-body global counts), with a def whose only
    decorators are those marks, and with none at all if the class body binds `unittest` itself. Anything else could be
    a callable unittest would call. Methods a class inherits are not counted: run them through the class or the
    module. Syntax only: see scope_bindings."""
    with warnings.catch_warnings():                # a test file's own odd escapes are its business, not the guard's
        warnings.simplefilter("ignore")
        tree = ast.parse(source)
    counts = scope_bindings(tree.body, tree)
    if "*" in counts:                              # a star import could rebind any name
        return {}
    bound = {}
    for node in tree.body:
        for n in bound_names(node):
            bound.setdefault(n, []).append(node)
    one = {n: nodes[0] for n, nodes in bound.items() if len(nodes) == 1 and counts.get(n) == 1}
    case_import = one.get("TestCase")
    imported_case = isinstance(case_import, ast.ImportFrom) and case_import.module == "unittest" \
        and case_import.level == 0 and any(a.name == "TestCase" for a in case_import.names
                                           if (a.asname or a.name) == "TestCase")
    # `import unittest` and `import unittest.mock` both bind the name unittest to the unittest package, so a file may
    # have both; any other binding of the name (an `as unittest`, an assignment, one inside a block) makes it something
    # else.
    unittest_module = 0 < len(bound.get("unittest", [])) == counts.get("unittest") and all(
        isinstance(node, ast.Import) and all(a.asname is None and a.name.split(".")[0] == "unittest"
                                             for a in node.names if (a.asname or a.name).split(".")[0] == "unittest")
        for node in bound["unittest"])

    def unittest_attr(node, names):
        return unittest_module and isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "unittest" and node.attr in names

    def skip_mark(d):
        # unittest's marks as they are written: skip, skipIf and skipUnless called with their reason, expectedFailure
        # bare (expectedFailure(x) returns x, so x would be the real decorator)
        if isinstance(d, ast.Call):
            return unittest_attr(d.func, ("skip", "skipIf", "skipUnless"))
        return unittest_attr(d, ("expectedFailure",))

    def skip_marks_only(node):
        return all(skip_mark(d) for d in node.decorator_list)

    def plain_body(node):
        # a docstring, pass, and plain defs with ordinary names: no class attributes or decorators, and no dunder hook
        # (__init_subclass__ could rewrite a test method of the class that uses the mixin)
        for i, item in enumerate(node.body):
            if i == 0 and isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) \
                    and isinstance(item.value.value, str):
                continue
            if isinstance(item, ast.Pass) or (isinstance(item, ast.FunctionDef) and not item.decorator_list
                                              and not (item.name.startswith("__") and item.name.endswith("__"))):
                continue
            return False
        return True

    def above(base, node):
        # a same-file base is the class only once its statement has run: one defined below is still a builtin of that
        # name (class C(Warning) above class Warning(...)) when this class is made
        found = one.get(base.id) if isinstance(base, ast.Name) else None
        return isinstance(found, ast.ClassDef) and found.lineno < node.lineno

    def is_mixin(name, seen=()):
        # A plain class of the same file that only adds methods: no bases but other such classes (or object), no
        # keywords (so no metaclass), no decorators, a plain body.
        node = one.get(name)
        if not isinstance(node, ast.ClassDef) or name in seen or node.keywords or node.decorator_list \
                or not plain_body(node):
            return False
        return all(isinstance(b, ast.Name) and ((b.id == "object" and "object" not in counts)
                                                or (above(b, node) and is_mixin(b.id, seen + (name,))))
                   for b in node.bases)

    def is_case(name, seen=()):
        node = one.get(name)
        if not isinstance(node, ast.ClassDef) or name in seen or not node.bases or node.keywords:
            return False
        if not skip_marks_only(node) or "__init_subclass__" in scope_bindings(node.body):
            return False
        cases = [b for b in node.bases if unittest_attr(b, ("TestCase",)) or (isinstance(b, ast.Name) and (
            (b.id == "TestCase" and imported_case) or (above(b, node) and is_case(b.id, seen + (name,)))))]
        return bool(cases) and all(b in cases or (above(b, node) and is_mixin(b.id)) for b in node.bases)

    out = {}
    for name, node in one.items():
        if is_case(name):
            times = scope_bindings(node.body)
            # a method's decorators look names up in the class body first, so `unittest = ...` there would make
            # @unittest.skip(...) something else
            marks_ok = "unittest" not in times
            out[name] = {item.name for item in node.body if isinstance(item, ast.FunctionDef)
                         and times.get(item.name) == 1 and (not item.decorator_list or marks_ok and skip_marks_only(item))}
    return out


def test_name_ok(name, root):
    m = TEST_NAME.fullmatch(name)
    if not m or not isinstance(root, str):
        return False
    module, cls, method = m.groups()
    file = os.path.join(root, "tests", module + ".py")
    if not os.path.isfile(file):
        return False
    if cls is None:
        return True
    try:
        with open(file, "rb") as f:
            cases = test_case_classes(f.read())
    except (OSError, SyntaxError, ValueError):
        return False
    return cls in cases and (method is None or method in cases[cls])


AGENT_BRANCH = re.compile(r"ai/[a-z0-9][a-z0-9-]{0,79}")


def agent_git(rest, isolated, owner_present, root):
    """The implementation agent's branch and commit, in the owner's terminal only (agent_git.py runs git without hooks
    and checks the branch and paths itself)."""
    if not owner_present:
        raise Refused("agent_git runs only in the owner's terminal")
    if not isolated:
        raise Refused("agent_git runs as: python -I tools/ai-team/agent_git.py ...")
    if len(rest) == 3 and rest[1] == "branch" and AGENT_BRANCH.fullmatch(rest[2]):
        return
    if len(rest) >= 4 and rest[1] == "commit":
        message, paths = rest[2], rest[3:]
        if message.startswith("-") or not message.strip() or len(message) > 500:
            raise Refused("agent_git commit takes one message that does not start with -, then paths")
        if not all(path(p) for p in paths):
            raise Refused("a path must be relative, inside the repo, with no '..' segment")
        check_write(root, paths)                    # each a file the agents may write, never a folder
        return
    raise Refused('agent_git takes: branch ai/<name>, or commit "<message>" <paths>')


def python(argv, root=None, owner_present=False):
    rest = argv[1:]
    isolated = rest[:1] == ["-I"]
    if isolated:
        rest = rest[1:]
    if rest[:1] == ["tools/ai-team/agent_git.py"]:
        return agent_git(rest, isolated, owner_present, root)
    if rest[:1] == ["tools/ai-team/lead_commit.py"]:
        if not isolated:
            raise Refused('lead_commit runs as: python -I tools/ai-team/lead_commit.py "<what changed>"')
        if len(rest) != 2 or rest[1].startswith("-") or not rest[1].strip():
            raise Refused("lead_commit takes one message that does not start with -")
        if len(rest[1]) > 500:
            raise Refused("the lead_commit message is at most 500 characters")
        return
    if rest in [list(s) for s in TEAM_SCRIPTS]:
        return
    if rest[:2] == ["tools/ai-team/guardian/guardian.py", "report"] and len(rest) == 4 and rest[2] == "--hours" \
            and digits(rest[3]):
        return
    if rest[:2] == ["-m", "unittest"]:
        if isolated:                              # -I drops the repo folder from sys.path, so tests.* would load elsewhere
            raise Refused("unittest runs without -I: python -m unittest tests.test_<name>, or discover -s tests")
        args = [a for a in rest[2:] if a not in ("-v", "-q")]
        if args[:1] == ["discover"]:
            if args != ["discover", "-s", "tests"]:
                raise Refused("unittest discovery runs only as: discover -s tests")
            return
        if not args or not all(test_name_ok(a, root) for a in args):
            raise Refused("unittest takes tests.test_<name> modules that exist (or one TestCase class or test method in "
                          "one), or discover -s tests")
        return
    raise Refused("this python command is not on the list")


def dispatch(argv, root=None, owner_present=False):
    exe = argv[0].lower()
    if exe == "gh":
        return gh(argv, owner_present)
    if exe == "git":
        return git(argv)
    if exe in ("python", "python3"):
        return python(argv, root, owner_present)
    raise Refused(f"command is not on the list: {exe}")


# ---- file writes: never the team's own rules, tools or instructions, and never outside the repo ------------------------

PROTECTED = (".opencode/", ".claude/", ".agents/", ".git/", ".github/", "tools/ai-team/", "scripts/guard.py",
             "agents.md", "contributing.md", "docs/codex-handoff.md")
# OpenCode reads opencode.json and opencode.jsonc (and tui.json) and a .opencode folder as config in the folder it
# starts in and each one above it, and an AGENTS.md, CLAUDE.md or CONTEXT.md in ANY folder as instructions for files
# read below it, so those names are refused wherever they are, as are the other tools' config folders and git's own.
ROOT_CONFIG = re.compile(r"(?:opencode|tui)\.jsonc?")
INSTRUCTION_NAMES = ("agents.md", "claude.md", "context.md")
CONFIG_FOLDERS = (".opencode", ".claude", ".agents", ".git", ".github")
# Each part of a written path must be a name NTFS reads the way this check does. A ':' names a stream (AGENTS.md::$DATA
# writes AGENTS.md itself), a trailing dot or space is dropped (opencode.jsonc. is opencode.jsonc), and realpath keeps a
# file that does not exist yet exactly as typed. So only the characters the repo's own file names use are taken: letters,
# digits and ._@+=,- , not starting or ending with a dot (no hidden files either).
SAFE_NAME = re.compile(r"[A-Za-z0-9_@+=,-](?:[A-Za-z0-9._@+=,-]*[A-Za-z0-9_@+=,-])?")
# Python puts the script's own folder first on sys.path (python scripts/guard.py: scripts/), and python -m puts the
# working folder there (the repo root), so a file or folder there named like a standard module (scripts/re.py,
# json/__init__.py) would run in place of it. Those names are refused in both folders, as are the two startup hooks.
SHADOW_NAMES = frozenset(n.lower() for n in sys.stdlib_module_names) | {"sitecustomize", "usercustomize"}


def check_write(root, paths):
    """Refuse a write to the guard, the agents' rules, the launchers and skills, CI, git's own files, or outside the
    repo. OpenCode's edit rules say the same per agent; this holds even where a rule pattern misses a spelling."""
    if not isinstance(root, str) or not root:
        raise Refused("a write needs the repo root")
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
        raise Refused("a write names no file")
    real_root = os.path.realpath(root)
    for p in paths:
        target = os.path.realpath(os.path.join(real_root, p))
        try:
            rel = os.path.relpath(target, real_root).replace(os.path.sep, "/")
        except ValueError:                          # on Windows, a path on another drive
            raise Refused(f"writes stay inside the repo: {p}")
        if rel == "." or rel == ".." or rel.startswith("../") or os.path.isabs(rel):
            raise Refused(f"writes stay inside the repo: {p}")
        if not all(SAFE_NAME.fullmatch(part) for part in rel.split("/")):
            raise Refused("a written file's path takes letters, digits and ._@+=,- only, with no part that starts or ends "
                          f"with a dot: {rel!r}")
        low = rel.lower()                           # Windows paths ignore case
        parts = low.split("/")
        if any(low == x.rstrip("/") or (x.endswith("/") and low.startswith(x)) for x in PROTECTED) \
                or ROOT_CONFIG.fullmatch(parts[-1]) or parts[-1] in INSTRUCTION_NAMES \
                or any(part in CONFIG_FOLDERS for part in parts):
            raise Refused(f"the team's own rules, tools and instructions are not written by an agent: {rel}")
        searched = parts[:2] if parts[0] == "scripts" else parts[:1]     # the entry in the root, or in scripts/
        if any(name.split(".")[0] in SHADOW_NAMES for name in searched):
            raise Refused(f"a file or folder named like a standard Python module, in a folder Python searches first: "
                          f"{rel}")
        if os.path.isdir(target):
            raise Refused(f"name each file, not a folder: {rel}")


def check(call):
    if not isinstance(call, dict):
        raise Refused("no call")
    root = call.get("root")
    # Commands run from the repo root only. A subfolder is refused too: the agents can write files under docs/ai/, and
    # relative script paths, git's repo discovery, gh's choice of repo and unittest's discovery all follow the working
    # directory, so a planted folder there could change what an allowed command runs. OpenCode runs a call in the
    # session's folder (directory), or in its workdir resolved against that folder, so both must be the root itself.
    # A write's relative path is resolved against the session's folder too, so writes need the same root session.
    if not isinstance(root, str) or not root:
        raise Refused("no repo root")
    directory, workdir = call.get("directory"), call.get("workdir")
    if directory is not None and not same_folder(directory, root):
        raise Refused("the session runs in a subfolder or elsewhere: start OpenCode at the repo root")
    if "write" in call:
        return check_write(root, call.get("write"))
    command = call.get("command")
    if not isinstance(command, str):
        raise Refused("no command text")
    # OpenCode treats an empty workdir as none, and resolves a relative one against the session's folder (the root).
    if workdir not in (None, "") and not same_folder(workdir, root) and not here(workdir):
        raise Refused("commands run from the repo root only")
    dispatch(tokenize(command), root, call.get("owner_present") is True)


def here(workdir):
    """A relative spelling of the session's own folder: '.', './', '.\\' (no '..' segment, nothing else)."""
    return isinstance(workdir, str) and set(workdir) <= set("./\\") and ".." not in workdir and workdir.startswith(".")


def same_folder(path, root):
    """The exact root, written as an absolute path (separators, a trailing slash and, on Windows, case may differ). No
    '..' segment and no other spelling: OpenCode maps /d/ and /mnt/d/ to D:\\ on Windows, which a resolve here would not."""
    if not isinstance(path, str) or not os.path.isabs(path) or ".." in path.replace("\\", "/").split("/"):
        return False
    return os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(root))


def refused_writes(root, paths):
    """The reason check_write gives for each path it refuses (terminal.ps1's start check, agent_git.py's switch back)."""
    out = []
    for p in paths:
        try:
            check_write(root, [p])
        except Refused as why:
            out.append(str(why))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        # allowlist.py --refused-writes <root>, paths on stdin one per line (UTF-8): prints the reason for each path an
        # agent may not write and exits 0; any other exit means the paths were not checked.
        if len(argv) != 2 or argv[0] != "--refused-writes" or not os.path.isdir(argv[1]):
            print("usage: allowlist.py --refused-writes <repo root> < paths", file=sys.stderr)
            return 2
        lines = sys.stdin.buffer.read().decode("utf-8").split("\n")
        for reason in refused_writes(argv[1], [p[:-1] if p.endswith("\r") else p for p in lines if p not in ("", "\r")]):
            print(reason)
        return 0
    try:
        check(json.loads(sys.stdin.buffer.read().decode("utf-8")))
    except Refused as why:
        print(json.dumps({"allowed": False, "reason": str(why)}))
        return 1
    except Exception as err:                       # unreadable input fails closed
        print(json.dumps({"allowed": False, "reason": f"guard error ({type(err).__name__})"}))
        return 1
    print(json.dumps({"allowed": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
