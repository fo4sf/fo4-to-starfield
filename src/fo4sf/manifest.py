"""Simple manifest reader for conversion status (WP-01).

Manifest is a JSON list or object under staging/work dir. Synthetic only in tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    pass


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Load manifest.json. Accepts a list of records or {"items": [...]}."""
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"invalid JSON in {p}: {e}") from e

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    raise ManifestError("manifest must be a list or an object with an 'items' list")


def summarize_manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Return simple counts for a coverage table."""
    total = len(items)
    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for it in items:
        typ = str(it.get("type") or it.get("record_type") or "unknown")
        by_type[typ] = by_type.get(typ, 0) + 1
        tier = str(it.get("fidelity_tier") or it.get("tier") or "T?")
        by_tier[tier] = by_tier.get(tier, 0) + 1
    return {"total": total, "by_type": by_type, "by_tier": by_tier}
