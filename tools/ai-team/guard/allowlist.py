"""The unattended Lead's shell guard: a command runs only if it matches an exact argument list below.

OpenCode's bash rules match a command as text, one pattern at a time, and some shapes get past any list of patterns:
git reads a file outside the repo with no flag once a path lies outside the worktree, a $(...) is built after the
check, and a workdir can point anywhere. This guard reads a command the way bash and PowerShell read it, refuses every
shell metacharacter and expansion, and accepts only the argument lists below. Anything else is refused.

The OpenCode plugin .opencode/plugin/fo4-guard.js runs this before each shell call. It passes one JSON object on stdin:
  {"root": "<worktree root>", "directory": "<the session's folder>", "command": "<the command text>",
   "workdir": "<optional directory>"}
Exit 0 means allowed. Exit 1 means refused, with {"allowed": false, "reason": "..."} on stdout. Anything unreadable is a
refusal too. Run it by hand (PowerShell):  Get-Content call.json | python -I tools/ai-team/guard/allowlist.py
"""
import json
import os
import re
import sys


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


def gh(argv):
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
    if argv[1:5] == ["issue", "comment", "32", "--body"] and len(argv) == 6:
        text = argv[5]
        if not text.startswith("Lead (local): ") or len(text) > 1500:
            raise Refused("the Lead's comment on #32 starts with 'Lead (local): ' and is at most 1500 characters")
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
    ["tools/ai-team/wake_agent.py", "status"],
    ["scripts/guard.py"],
)
# The Codex and Grok wakes are refused: wake_agent.py codex|grok starts an agent with approvals on a brief, which the
# unattended Lead may not do. The owner decides whether it may. `wake_agent.py status` only reads idle times.
# A test module by name, and only one that exists as tests/test_<name>.py: unittest calls whatever a longer dotted name
# ends on (tests.test_x.some_module.main would run main()), so nothing after the module name is allowed.
TEST_MODULE = re.compile(r"tests\.(test_[a-z0-9_]+)")


def python(argv, root=None):
    rest = argv[1:]
    isolated = rest[:1] == ["-I"]
    if isolated:
        rest = rest[1:]
    if rest[:1] == ["tools/ai-team/lead_commit.py"]:
        if not isolated:
            raise Refused('lead_commit runs as: python -I tools/ai-team/lead_commit.py "<what changed>"')
        if len(rest) != 2 or rest[1].startswith("-") or not rest[1].strip() or len(rest[1]) > 500:
            raise Refused("lead_commit takes one message that does not start with -")
        return
    if rest in [list(s) for s in TEAM_SCRIPTS]:
        return
    if rest[:2] == ["tools/ai-team/guardian/guardian.py", "report"] and len(rest) == 4 and rest[2] == "--hours" \
            and digits(rest[3]):
        return
    if rest[:2] == ["-m", "unittest"]:
        args = [a for a in rest[2:] if a not in ("-v", "-q")]
        if args[:1] == ["discover"]:
            if args != ["discover", "-s", "tests"]:
                raise Refused("unittest discovery runs only as: discover -s tests")
            return
        names = [TEST_MODULE.fullmatch(a) for a in args]
        if not args or not all(names) or not isinstance(root, str) or not all(
                os.path.isfile(os.path.join(root, "tests", m.group(1) + ".py")) for m in names):
            raise Refused("unittest takes test modules named tests.test_<name> that exist, or discover -s tests")
        return
    raise Refused("this python command is not on the list")


def dispatch(argv, root=None):
    exe = argv[0].lower()
    if exe == "gh":
        return gh(argv)
    if exe == "git":
        return git(argv)
    if exe in ("python", "python3"):
        return python(argv, root)
    raise Refused(f"command is not on the list: {exe}")


def check(call):
    if not isinstance(call, dict):
        raise Refused("no call")
    command = call.get("command")
    if not isinstance(command, str):
        raise Refused("no command text")
    root = call.get("root")
    # Commands run from the repo root only. A subfolder is refused too: the agents can write files under docs/ai/, and
    # relative script paths, git's repo discovery, gh's choice of repo and unittest's discovery all follow the working
    # directory, so a planted folder there could change what an allowed command runs. OpenCode runs a call in the
    # session's folder (directory), or in its workdir resolved against that folder, so both must be the root itself.
    if not isinstance(root, str) or not root:
        raise Refused("no repo root")
    directory, workdir = call.get("directory"), call.get("workdir")
    if directory is not None and not same_folder(directory, root):
        raise Refused("the session runs in a subfolder or elsewhere: start OpenCode at the repo root")
    if workdir is not None and workdir != "." and not same_folder(workdir, root):
        raise Refused("commands run from the repo root only")
    dispatch(tokenize(command), root)


def same_folder(path, root):
    """The exact root, written as an absolute path (separators, a trailing slash and, on Windows, case may differ). No
    '..' segment and no other spelling: OpenCode maps /d/ and /mnt/d/ to D:\\ on Windows, which a resolve here would not."""
    if not isinstance(path, str) or not os.path.isabs(path) or ".." in path.replace("\\", "/").split("/"):
        return False
    return os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(root))


def main():
    try:
        check(json.loads(sys.stdin.buffer.read().decode("utf-8")))
    except Refused as why:
        print(json.dumps({"allowed": False, "reason": str(why)}))
        return 1
    except Exception as err:                       # unreadable input fails closed
        print(json.dumps({"allowed": False, "reason": f"guard error ({type(err).__name__})"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
