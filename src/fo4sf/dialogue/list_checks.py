"""Silent-player list conversation contract, prefix tags, deterministic NV-style checks, and bug-ledger validator.

Sits beside PR #792's 4-option wheel (`Interface/FO4SF_DialogueWheel.swf`):
- Keeps Starfield's native `DialogueMenu` class, `DialogueListData.aChoices` shuttle, and `DialogueMenu.swf` intact
  (never packs or replaces `Interface/DialogueMenu.swf`).
- Formats and parses `[Skill N]`, `[SPECIAL N]`, `[Background]`, and `[Trait]` prefix tags.
- Evaluates checks deterministically (`value >= threshold` or `has_perk == True`, New Vegas rule — zero RNG `%` roll).
- Validates per-quest / per-conversation known-bug ledgers under the clean-room rule (`docs/plan/core-and-assets-plan.md`).
"""
from __future__ import annotations

import re
from typing import Iterable

HOST_MENU = "DialogueMenu"
FORBIDDEN_HOST_MOVIE = "Interface/DialogueMenu.swf"
WHEEL_OVERLAY_MOVIE = "Interface/FO4SF_DialogueWheel.swf"
LIST_PROVIDER = "DialogueListData"
CHOICES_KEY = "aChoices"
SELECT_EVENT = "DialogueMenu_OnDialogueSelect"
SELECT_KEY = "selectedIndex"

NV_SKILLS = frozenset({
    "Barter", "Energy Weapons", "Explosives", "Guns", "Lockpick", "Medicine",
    "Melee Weapons", "Repair", "Science", "Sneak", "Speech", "Survival", "Unarmed",
})

SPECIAL_ATTRIBUTES = frozenset({
    "Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck",
})

TAG_RE = re.compile(r"^\[(?P<inner>[^\]]+)\]\s*(?P<body>.*)$")
THRESHOLD_INNER_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z ]*?)\s+(?P<num>\d+)\+?$")
VALID_BUG_DISPOSITIONS = frozenset({"fixed", "studied_clean_room", "left"})
FORBIDDEN_MOD_FILE_RE = re.compile(r"\.(?:esp|esm|esl|ba2|bsa|pex|psc)\b", re.I)


class ListDialogueError(ValueError):
    pass


def format_prefix_tag(kind: str, label: str, threshold: int | None = None) -> str:
    """Format a deterministic dialogue prefix tag: `[Speech 50]`, `[Strength 7]`, `[Vault Dweller]`, `[Good Natured]`."""
    clean_label = label.strip()
    if not clean_label:
        raise ListDialogueError("tag label must not be empty")
    kind_low = kind.lower()
    if kind_low == "skill":
        if clean_label not in NV_SKILLS:
            raise ListDialogueError(f"unknown Fallout skill {clean_label!r}")
        if threshold is None or threshold < 1 or threshold > 100:
            raise ListDialogueError(f"skill threshold must be in 1..100, got {threshold!r}")
        return f"[{clean_label} {threshold}]"
    if kind_low == "special":
        if clean_label not in SPECIAL_ATTRIBUTES:
            raise ListDialogueError(f"unknown SPECIAL attribute {clean_label!r}")
        if threshold is None or threshold < 1 or threshold > 15:
            raise ListDialogueError(f"SPECIAL threshold must be in 1..15, got {threshold!r}")
        return f"[{clean_label} {threshold}]"
    if kind_low in ("background", "trait"):
        if threshold is not None:
            raise ListDialogueError(f"{kind_low} tag does not take a numeric threshold")
        return f"[{clean_label}]"
    raise ListDialogueError(f"unknown check kind {kind!r}; expected skill, special, background, or trait")


def format_prompt(kind: str, label: str, text: str, threshold: int | None = None) -> str:
    body = text.strip()
    if not body:
        raise ListDialogueError("choice prompt body must not be empty")
    if kind.lower() == "plain":
        return body
    return f"{format_prefix_tag(kind, label, threshold)} {body}"


def parse_prefix_tag(prompt: str, known_backgrounds: set[str] | None = None, known_traits: set[str] | None = None) -> dict | None:
    """Parse a leading `[...]` tag from a player choice prompt, returning `{kind, label, threshold, body}` or None."""
    m = TAG_RE.match(prompt.strip())
    if not m:
        return None
    inner = m.group("inner").strip()
    body = m.group("body").strip()
    tm = THRESHOLD_INNER_RE.match(inner)
    if tm:
        name = tm.group("name").strip()
        num = int(tm.group("num"))
        if name in NV_SKILLS:
            return {"kind": "skill", "label": name, "threshold": num, "body": body}
        if name in SPECIAL_ATTRIBUTES:
            return {"kind": "special", "label": name, "threshold": num, "body": body}
        raise ListDialogueError(f"unrecognized thresholded tag [{inner}]")
    bgs = known_backgrounds or set()
    traits = known_traits or set()
    if inner in traits and inner not in bgs:
        return {"kind": "trait", "label": inner, "threshold": None, "body": body}
    if inner in bgs:
        return {"kind": "background", "label": inner, "threshold": None, "body": body}
    return {"kind": "background_or_trait", "label": inner, "threshold": None, "body": body}


def evaluate_check(
    kind: str,
    label: str,
    threshold: int | None = None,
    *,
    skills: dict[str, float] | None = None,
    special: dict[str, float] | None = None,
    backgrounds: set[str] | None = None,
    traits: set[str] | None = None,
) -> bool:
    """Deterministic New Vegas-style check evaluator (no RNG percentage roll)."""
    k = kind.lower()
    if k == "plain":
        return True
    if k == "skill":
        if threshold is None:
            raise ListDialogueError("skill check requires threshold")
        return float((skills or {}).get(label, 0.0)) >= float(threshold)
    if k == "special":
        if threshold is None:
            raise ListDialogueError("special check requires threshold")
        return float((special or {}).get(label, 0.0)) >= float(threshold)
    if k == "background":
        return label in (backgrounds or set())
    if k == "trait":
        return label in (traits or set())
    raise ListDialogueError(f"unsupported check kind {kind!r}")


def build_shuttle_choices(
    options: Iterable[dict],
    *,
    skills: dict[str, float] | None = None,
    special: dict[str, float] | None = None,
    backgrounds: set[str] | None = None,
    traits: set[str] | None = None,
) -> dict:
    """Filter and build a Starfield `DialogueListData` shuttle payload for the active player sheet.

    Each option dict carries `{entry_id, kind, label, threshold, variant ('pass'|'fail'|'only'), text, already_said}`.
    - For `skill` and `special`: deterministic NV dual-branching selects the `pass` row when `val >= threshold`
      and the `fail` row when `val < threshold` (or hides `only` rows when unmet).
    - For `background` and `trait`: `only` rows appear iff the player holds that `PERK`.
    """
    rows = []
    for opt in options:
        kind = opt.get("kind", "plain").lower()
        label = opt.get("label", "")
        threshold = opt.get("threshold")
        variant = opt.get("variant", "only")
        passed = evaluate_check(
            kind, label, threshold,
            skills=skills, special=special, backgrounds=backgrounds, traits=traits,
        )
        if variant == "pass" and not passed:
            continue
        if variant == "fail" and passed:
            continue
        if variant == "only" and not passed:
            continue
        prompt = format_prompt(kind, label, opt["text"], threshold)
        rows.append({
            "sChoiceText": prompt,
            "bCanBeChosen": True,
            "bWasAlreadySaid": bool(opt.get("already_said", False)),
            "uEntryID": int(opt["entry_id"]),
            "checkPassed": passed,
        })
    return {LIST_PROVIDER: {CHOICES_KEY: rows}}


def select_dialogue_mode(choice_texts: list[str], *, is_fo4_wheel_scene: bool = False) -> str:
    """Coexistence rule beside #792: 4-slot untagged FO4 wheel scenes use `wheel_4`; all list/tagged/5+ use `list_host`."""
    has_prefix_tag = any(TAG_RE.match(t.strip()) for t in choice_texts)
    if is_fo4_wheel_scene and len(choice_texts) == 4 and not has_prefix_tag:
        return "wheel_4"
    return "list_host"


def validate_no_host_movie_override(staged_paths: Iterable[str]) -> None:
    """Refuse any stage that tries to replace Starfield's host `Interface/DialogueMenu.swf` (killed in #792)."""
    for rel in staged_paths:
        norm = rel.replace("\\", "/").lstrip("/")
        if norm.lower() == FORBIDDEN_HOST_MOVIE.lower() or norm.lower().endswith("/dialoguemenu.swf"):
            raise ListDialogueError(f"staging {FORBIDDEN_HOST_MOVIE} is forbidden: keep Starfield's native DialogueMenu")


def validate_bug_ledger(entries: Iterable[dict]) -> list[dict]:
    """Validate a converted quest/dialogue known-bug ledger per the clean-room rule (`core-and-assets-plan.md`)."""
    cleaned = []
    for idx, item in enumerate(entries):
        for key in ("bug_id", "summary", "disposition", "reproduction"):
            val = str(item.get(key, "")).strip()
            if not val:
                raise ListDialogueError(f"bug ledger entry {idx} missing non-empty {key!r}")
        disp = str(item["disposition"]).strip()
        if disp not in VALID_BUG_DISPOSITIONS:
            raise ListDialogueError(f"bug ledger entry {item['bug_id']!r} has invalid disposition {disp!r}")
        combined = f"{item['summary']} {item['reproduction']}"
        if FORBIDDEN_MOD_FILE_RE.search(combined):
            raise ListDialogueError(f"bug ledger entry {item['bug_id']!r} references a plugin/archive/script filename; use plain functional descriptions only")
        cleaned.append({
            "bug_id": str(item["bug_id"]).strip(),
            "summary": str(item["summary"]).strip(),
            "disposition": disp,
            "reproduction": str(item["reproduction"]).strip(),
        })
    return cleaned
