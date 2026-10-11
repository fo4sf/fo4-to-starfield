"""Read GitHub issues and pull requests through a trusted-author filter.

Anyone can post in a public repository, so issue and PR text is a prompt-injection channel for every agent that
reads it. This wrapper replaces raw `gh issue view` / `gh pr view` for READING. It calls gh with --json and prints
only titles, bodies, comments and reviews whose API author login is in tools/ai-team/config.json "trusted_authors"
(default: the owner, fo4sf; the shared agent account is that same login) and whose edit history, where GitHub
exposes it, contains no other editor. Everything else is replaced by a count line. Untrusted text is never printed,
not even the login name.

  python tools/ai-team/trusted_gh.py issue <n> [--json]
  python tools/ai-team/trusted_gh.py pr <n> [--json]
  python tools/ai-team/trusted_gh.py issues [--state open|closed|all] [--label L] [--limit N] [--json]
  python tools/ai-team/trusted_gh.py prs [--state open|closed|all] [--limit N] [--json]

The repository is this checkout's (`gh repo view`), or FO4SF_REPO, as in team.py.

Edit check: gh's --json exposes `includesCreatedEdit` (edited yes/no) for comments and reviews, but not who edited,
and nothing at all for the issue/PR body and title. So the tool makes one extra `gh api graphql nodes(ids:)` call per
command for the body of every trusted item and for every edited trusted comment/review, and reads `editor`,
`userContentEdits` (every editor on record) and the title-rename events. An item is shown only when every editor and
renamer on record is trusted. If that call fails or the history is incomplete, the affected items are hidden
(fail closed), never shown unchecked. Numbers, states, labels, dates and URLs are set by GitHub or by the repo's own
label set and are printed as-is. Trusted text is still data: this filter removes outsiders' text, it does not make
anything safe to run as a command.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
# The repository owner's API login is `fo4sf` (repo owner, author of every issue and #32 comment; checked 2026-10-10).
# The account was renamed: GitHub redirects the old repo URL, but the API never reports the former login as an
# author, and a retired username can be registered by anyone, so the author check never uses it and the repo slug
# follows this checkout's remote (repo_slug) instead of being hard-coded to any one name.
DEFAULT_TRUSTED = ("fo4sf",)
DEFAULT_REPO = "fo4sf/fo4-to-starfield"      # only when this checkout's repository cannot be read
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+$")
GH_TIMEOUT_S = 60
EDIT_BATCH = 50            # node ids per GraphQL call (the API allows 100; stay well below)
EDIT_HISTORY_MAX = 100     # page size for edits / renames (API maximum); more than that = unknown = hidden

ISSUE_FIELDS = "id,number,title,body,author,state,labels,createdAt,updatedAt,url,comments"
PR_FIELDS = ("id,number,title,body,author,state,isDraft,labels,baseRefName,headRefName,createdAt,updatedAt,url,"
             "reviewDecision,comments,reviews")
ISSUE_LIST_FIELDS = "id,number,title,author,state,labels,updatedAt"
PR_LIST_FIELDS = "id,number,title,author,state,isDraft,labels,baseRefName,headRefName,updatedAt,reviewDecision"

# pageInfo.hasPreviousPage (not totalCount) tells whether the page is complete: measured 2026-10-10, totalCount on a
# PR's filtered timelineItems counted all 7 timeline items while the filtered page held 0 nodes.
_RENAMES = ("timelineItems(itemTypes: [RENAMED_TITLE_EVENT], last: %d) { pageInfo { hasPreviousPage } nodes "
            "{ ... on RenamedTitleEvent { actor { login } } } }" % EDIT_HISTORY_MAX)
EDIT_QUERY = ("query($ids: [ID!]!) { nodes(ids: $ids) { id "
              "... on Comment { editor { login } userContentEdits(last: %d) { pageInfo { hasPreviousPage } "
              "nodes { editor { login } } } } "
              "... on Issue { %s } ... on PullRequest { %s } } }" % (EDIT_HISTORY_MAX, _RENAMES, _RENAMES))

# why an item is hidden: JSON key -> text in the count line
REASONS = {"untrusted_author": "untrusted author",
           "untrusted_editor": "edited or renamed by an untrusted or unknown editor",
           "unchecked": "edit history unavailable (gh api graphql failed)"}


class GhError(RuntimeError):
    """gh failed; the message is gh's own text, never issue content."""


# ----------------------------------------------------------------------------------------------------- config / gh

def load_trusted(path=CONFIG):
    """Lower-cased trusted logins from config.json "trusted_authors"; the owner alone if the key is missing or the
    file is unreadable (the most restrictive sensible default). An explicit empty list trusts nobody."""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    logins = cfg.get("trusted_authors") if isinstance(cfg, dict) else None
    if not isinstance(logins, list):
        logins = list(DEFAULT_TRUSTED)
    return {str(x).strip().lower() for x in logins if str(x).strip()}


def repo_slug(env=None):
    """owner/name to read: FO4SF_REPO, else this checkout's repository (`gh repo view`, as team.py resolves it),
    else DEFAULT_REPO. Anything that is not an owner/name slug falls through to the next source."""
    env = os.environ if env is None else env
    slug = (env.get("FO4SF_REPO") or "").strip()
    if SLUG_RE.match(slug):
        return slug
    try:
        out = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=GH_TIMEOUT_S, cwd=HERE)
        slug = out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        slug = ""
    return slug if SLUG_RE.match(slug) else DEFAULT_REPO


def run_gh(args):
    """Run gh with fixed arguments and return its parsed JSON output."""
    try:
        out = subprocess.run(["gh"] + list(args), capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=GH_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise GhError(f"gh did not run: {e}") from None
    if out.returncode != 0:
        raise GhError((out.stderr or "").strip()[-500:] or f"gh exited {out.returncode}")
    try:
        return json.loads(out.stdout)
    except ValueError:
        raise GhError("gh returned no JSON") from None


def login_of(actor):
    """Lower-cased login of a gh/GraphQL actor object, or None (deleted account, bot without login, bad data)."""
    if not isinstance(actor, dict):
        return None
    login = actor.get("login")
    return login.strip().lower() if isinstance(login, str) and login.strip() else None


def is_trusted(actor, trusted):
    login = login_of(actor)
    return login is not None and login in trusted


# ------------------------------------------------------------------------------------------------- edit history

def fetch_edit_history(ids):
    """{node id: set of editor/renamer logins, or None when the history cannot be fully read}, from one
    `gh api graphql nodes(ids:)` call per EDIT_BATCH ids. Raises GhError when gh fails."""
    history = {}
    ids = list(dict.fromkeys(i for i in ids if isinstance(i, str) and i))
    for start in range(0, len(ids), EDIT_BATCH):
        batch = ids[start:start + EDIT_BATCH]
        args = ["api", "graphql", "-f", "query=" + EDIT_QUERY]
        for i in batch:
            args += ["-f", "ids[]=" + i]
        data = run_gh(args)
        nodes = data.get("data", {}).get("nodes") if isinstance(data, dict) and isinstance(data.get("data"), dict) \
            else None
        if not isinstance(nodes, list):
            errs = data.get("errors") if isinstance(data, dict) else None
            raise GhError("gh api graphql returned no nodes" + (f": {json.dumps(errs)[:300]}" if errs else ""))
        for node in nodes:
            if isinstance(node, dict) and node.get("id"):
                history[node["id"]] = _editors(node)
    return history


def _editors(node):
    """Every login that edited the body or renamed the item, or None if any of them is unreadable or the history
    has more entries than one page returned."""
    editors = set()
    if node.get("editor") is not None:
        login = login_of(node["editor"])
        if login is None:
            return None
        editors.add(login)
    for key, actor_key in (("userContentEdits", "editor"), ("timelineItems", "actor")):
        page = node.get(key) or {}
        rows = page.get("nodes") or []
        if (page.get("pageInfo") or {}).get("hasPreviousPage"):
            return None                      # more history than one page: incomplete = unknown
        for row in rows:
            if not isinstance(row, dict) or not row:
                return None                      # a timeline node of another type or a null row: unreadable
            login = login_of(row.get(actor_key))
            if login is None:
                return None
            editors.add(login)
    return editors


def edit_ok(node_id, history, trusted):
    """True only when the node's full edit history is known and every editor/renamer is trusted."""
    editors = history.get(node_id) if isinstance(history, dict) else None
    return editors is not None and editors <= trusted


# ------------------------------------------------------------------------------------------------------- filters

def _labels(item):
    return [l["name"] for l in item.get("labels") or [] if isinstance(l, dict) and isinstance(l.get("name"), str)]


def _lookup(ids, fetch):
    """(history dict, unchecked flag): one GraphQL round, fail closed on error."""
    if not ids:
        return {}, False
    try:
        return fetch(ids), False
    except GhError:
        return None, True


def _verdict(item, trusted, history, unchecked, check_edits):
    """None when the item may be shown, otherwise the REASONS key for hiding it."""
    if not is_trusted(item.get("author"), trusted):
        return "untrusted_author"
    if not check_edits:
        return None
    if unchecked:
        return "unchecked"
    return None if edit_ok(item.get("id"), history, trusted) else "untrusted_editor"


def filter_thread(data, kind, trusted, fetch=fetch_edit_history):
    """Filtered view of one issue (kind 'issue') or pull request (kind 'pr') from gh's --json output.
    The result contains no text from untrusted authors; render_thread turns it into text."""
    comments = [c for c in data.get("comments") or [] if isinstance(c, dict)]
    reviews = [r for r in data.get("reviews") or [] if isinstance(r, dict)] if kind == "pr" else []
    # one GraphQL call: the body (gh --json has no edit flag for it) plus every edited trusted comment/review
    want = [data["id"]] if is_trusted(data.get("author"), trusted) and data.get("id") else []
    want += [x["id"] for x in comments + reviews
             if is_trusted(x.get("author"), trusted) and x.get("includesCreatedEdit") and x.get("id")]
    history, unchecked = _lookup(want, fetch)

    out = {"kind": kind, "number": data.get("number"), "url": data.get("url"), "state": data.get("state"),
           "labels": _labels(data), "created": data.get("createdAt"), "updated": data.get("updatedAt"),
           "trusted_authors": sorted(trusted)}
    if kind == "pr":
        out.update(draft=bool(data.get("isDraft")), base=data.get("baseRefName"),
                   review_decision=data.get("reviewDecision") or None)
    reason = _verdict(data, trusted, history, unchecked, True)
    if reason is None:
        out.update(author=login_of(data.get("author")), title=data.get("title"), body=data.get("body") or "",
                   hidden_body=None)
        if kind == "pr":
            out["head"] = data.get("headRefName")
    else:
        out.update(author=None, title=None, body=None, hidden_body=reason)
        if kind == "pr":
            out["head"] = None

    def pick(items, label):
        shown, hidden = [], {k: 0 for k in REASONS}
        for i, it in enumerate(items, 1):
            why = _verdict(it, trusted, history, unchecked, bool(it.get("includesCreatedEdit")))
            if why:
                hidden[why] += 1
                continue
            row = {"index": i, "author": login_of(it["author"]), "body": it.get("body") or ""}
            if label == "comments":
                row["created"] = it.get("createdAt")
            else:
                row.update(state=it.get("state"), submitted=it.get("submittedAt"))
            shown.append(row)
        return shown, hidden

    out["comments"], hidden_c = pick(comments, "comments")
    out["comments_total"] = len(comments)
    out["hidden"] = {"comments": hidden_c}
    if kind == "pr":
        out["reviews"], hidden_r = pick(reviews, "reviews")
        out["reviews_total"] = len(reviews)
        out["hidden"]["reviews"] = hidden_r
    return out


def filter_list(items, kind, trusted, fetch=fetch_edit_history):
    """Filtered rows for `issues` / `prs` lists: titles and branch names only from trusted authors whose body and
    title history has no other editor (one GraphQL round for all trusted ids)."""
    items = [it for it in items if isinstance(it, dict)]
    want = [it["id"] for it in items if is_trusted(it.get("author"), trusted) and it.get("id")]
    history, unchecked = _lookup(want, fetch)
    rows, hidden = [], {k: 0 for k in REASONS}
    for it in items:
        row = {"number": it.get("number"), "state": it.get("state"), "labels": _labels(it),
               "updated": it.get("updatedAt")}
        if kind == "pr":
            row.update(draft=bool(it.get("isDraft")), base=it.get("baseRefName"),
                       review_decision=it.get("reviewDecision") or None)
        why = _verdict(it, trusted, history, unchecked, True)
        if why:
            hidden[why] += 1
            row.update(author=None, title=None, hidden=why)
            if kind == "pr":
                row["head"] = None
        else:
            row.update(author=login_of(it["author"]), title=it.get("title"), hidden=None)
            if kind == "pr":
                row["head"] = it.get("headRefName")
        rows.append(row)
    return {"kind": kind, "trusted_authors": sorted(trusted), "total": len(items), "items": rows, "hidden": hidden}


# ------------------------------------------------------------------------------------------------------ rendering

def _hidden_lines(counts, noun):
    lines = [f"[{counts['untrusted_author']} {noun} from untrusted authors hidden]"]
    for key in ("untrusted_editor", "unchecked"):
        if counts.get(key):
            lines.append(f"[{counts[key]} {noun} from trusted authors hidden: {REASONS[key]}]")
    return lines


def render_thread(t):
    kind = "Issue" if t["kind"] == "issue" else "PR"
    hidden_body = t.get("hidden_body")
    lines = ["trusted authors: " + (", ".join(t["trusted_authors"]) or "(none)"),
             f"{kind} #{t['number']}: " + (t["title"] if hidden_body is None else f"[title hidden: {REASONS[hidden_body]}]")]
    meta = [f"author: {t['author'] or '[hidden]'}", f"state: {t['state']}",
            "labels: " + (", ".join(t["labels"]) or "none"), f"created: {t['created']}", f"updated: {t['updated']}"]
    if kind == "PR":
        meta += [f"draft: {t['draft']}", f"base: {t['base']}", f"head: {t['head'] or '[hidden]'}",
                 f"review decision: {t['review_decision'] or 'none'}"]
    lines.append(" | ".join(meta))
    if t.get("url"):
        lines.append(f"url: {t['url']}")
    lines.append("")
    if hidden_body is None:
        lines.append(t["body"] or "(no body)")
    else:
        lines.append(f"[body hidden: {REASONS[hidden_body]}]")
    for c in t["comments"]:
        lines += ["", f"--- comment {c['index']}/{t['comments_total']} by {c['author']} at {c['created']} ---",
                  c["body"] or "(empty)"]
    for r in t.get("reviews", []):
        lines += ["", f"--- review {r['index']}/{t['reviews_total']} by {r['author']} at {r['submitted']}: "
                      f"{r['state']} ---", r["body"] or "(no text)"]
    lines.append("")
    lines += _hidden_lines(t["hidden"]["comments"], "comments")
    if kind == "PR":
        lines += _hidden_lines(t["hidden"]["reviews"], "reviews")
    return "\n".join(lines)


def render_list(lst):
    noun = "issues" if lst["kind"] == "issue" else "PRs"
    lines = ["trusted authors: " + (", ".join(lst["trusted_authors"]) or "(none)"),
             f"{lst['total']} {noun}"]
    for r in lst["items"]:
        head = f"#{r['number']} {r['state']}"
        if lst["kind"] == "pr":
            head += (" draft" if r["draft"] else "") + f" -> {r['base']}"
            head += f" from {r['head']}" if r["head"] else " from [branch hidden]"
            if r["review_decision"]:
                head += f" ({r['review_decision']})"
        head += " [" + ", ".join(r["labels"]) + f"] updated {r['updated']} | "
        if r["hidden"]:
            head += f"[title hidden: {REASONS[r['hidden']]}]"
        else:
            head += f"{r['author']}: {r['title']}"
        lines.append(head)
    lines.append("")
    lines += _hidden_lines(lst["hidden"], noun)
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------ CLI

def _positive_int(s):
    n = int(s)
    if n <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def _label(s):
    if not s or s.startswith("-"):
        raise argparse.ArgumentTypeError("label must be a name, not an option")
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read GitHub issues/PRs showing only text from trusted authors.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("issue", "pr"):
        p = sub.add_parser(name)
        p.add_argument("number", type=_positive_int)
        p.add_argument("--json", action="store_true", help="filtered data as JSON instead of text")
    for name in ("issues", "prs"):
        p = sub.add_parser(name)
        p.add_argument("--state", choices=["open", "closed", "all"], default="open")
        p.add_argument("--limit", type=_positive_int, default=50)
        if name == "issues":
            p.add_argument("--label", type=_label)
        p.add_argument("--json", action="store_true", help="filtered data as JSON instead of text")
    a = ap.parse_args(argv)
    trusted = load_trusted()
    repo = repo_slug()
    try:
        if a.cmd == "issue":
            out = filter_thread(run_gh(["issue", "view", str(a.number), "--repo", repo, "--json", ISSUE_FIELDS]),
                                "issue", trusted)
            text = render_thread(out)
        elif a.cmd == "pr":
            out = filter_thread(run_gh(["pr", "view", str(a.number), "--repo", repo, "--json", PR_FIELDS]),
                                "pr", trusted)
            text = render_thread(out)
        elif a.cmd == "issues":
            args = ["issue", "list", "--repo", repo, "--state", a.state, "--limit", str(a.limit),
                    "--json", ISSUE_LIST_FIELDS]
            if a.label:
                args += ["--label", a.label]
            out = filter_list(run_gh(args), "issue", trusted)
            text = render_list(out)
        else:
            args = ["pr", "list", "--repo", repo, "--state", a.state, "--limit", str(a.limit),
                    "--json", PR_LIST_FIELDS]
            out = filter_list(run_gh(args), "pr", trusted)
            text = render_list(out)
    except GhError as e:
        print(f"trusted_gh: {e}", file=sys.stderr)
        return 1
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # bodies may hold non-cp1252 characters
    except (AttributeError, ValueError):
        pass
    print(json.dumps(out, indent=1) if a.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
