"""Entity-aware crawl diff."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _norm(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def entity_key(record: Dict[str, Any], key_fields: Optional[List[str]] = None) -> str:
    key_fields = key_fields or ["id", "sku", "url", "product_id", "asin"]
    for k in key_fields:
        if k in record and record[k] not in (None, ""):
            return f"{k}:{_norm(record[k])}"
    # fallback: title
    if "title" in record:
        return f"title:{_norm(record['title'])}"
    if "name" in record:
        return f"name:{_norm(record['name'])}"
    return f"hash:{hash(frozenset((k, _norm(v)) for k, v in record.items()))}"


@dataclass
class FieldChange:
    field: str
    old: Any
    new: Any


@dataclass
class CrawlDiff:
    added: List[Dict[str, Any]] = field(default_factory=list)
    removed: List[Dict[str, Any]] = field(default_factory=list)
    changed: List[Dict[str, Any]] = field(default_factory=list)  # {key, changes: [...]}
    unchanged: int = 0

    def summary(self) -> str:
        return (
            f"+{len(self.added)} added, -{len(self.removed)} removed, "
            f"~{len(self.changed)} changed, ={self.unchanged} unchanged"
        )


def diff_crawls(
    old: List[Dict[str, Any]],
    new: List[Dict[str, Any]],
    key_fields: Optional[List[str]] = None,
    ignore_fields: Optional[List[str]] = None,
) -> CrawlDiff:
    ignore = set(ignore_fields or ["_scraped_at", "fetched_at"])
    old_map = {entity_key(r, key_fields): r for r in old}
    new_map = {entity_key(r, key_fields): r for r in new}

    result = CrawlDiff()
    old_keys = set(old_map)
    new_keys = set(new_map)

    for k in sorted(new_keys - old_keys):
        result.added.append(new_map[k])
    for k in sorted(old_keys - new_keys):
        result.removed.append(old_map[k])

    for k in sorted(old_keys & new_keys):
        a, b = old_map[k], new_map[k]
        changes = []
        fields = set(a) | set(b)
        for f in fields:
            if f in ignore:
                continue
            if _norm(a.get(f)) != _norm(b.get(f)):
                changes.append({"field": f, "old": a.get(f), "new": b.get(f)})
        if changes:
            result.changed.append({"key": k, "changes": changes, "record": b})
        else:
            result.unchanged += 1

    return result
