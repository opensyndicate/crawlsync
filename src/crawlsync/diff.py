"""Entity-aware crawl diff."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _norm(s: Any) -> str:
    """Lowercase, trim, and collapse whitespace. None becomes an empty string."""
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _stable_hash(record: Dict[str, Any]) -> str:
    items = sorted((str(k), _norm(v)) for k, v in record.items())
    blob = "|".join(f"{k}={v}" for k, v in items)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def entity_key(record: Dict[str, Any], key_fields: Optional[List[str]] = None) -> str:
    """Return a stable identity string for one crawled record.

    Tries ``key_fields`` in order (default: ``id``, ``sku``, ``url``,
    ``product_id``, ``asin``). The first field that is present and non-empty
    wins. If none match, falls back to ``title``, then ``name``, then a SHA-1
    of the normalized field set so the same record hashes the same across
    processes.

    Values are normalized (strip, lowercase, collapsed whitespace) before
    they become part of the key, so ``SKU: "A1"`` and ``sku: "a1"`` match.
    """
    key_fields = key_fields or ["id", "sku", "url", "product_id", "asin"]
    for k in key_fields:
        if k in record and record[k] not in (None, ""):
            return f"{k}:{_norm(record[k])}"
    if "title" in record:
        return f"title:{_norm(record['title'])}"
    if "name" in record:
        return f"name:{_norm(record['name'])}"
    return f"hash:{_stable_hash(record)}"


@dataclass
class CrawlDiff:
    """Result of comparing two crawl snapshots.

    ``added`` / ``removed`` hold full records. ``changed`` holds dicts of
    ``{key, changes, record}`` where ``record`` is the new snapshot's row
    and ``changes`` is a list of ``{field, old, new}``. ``unchanged`` is a
    count, not a list of records.
    """

    added: List[Dict[str, Any]] = field(default_factory=list)
    removed: List[Dict[str, Any]] = field(default_factory=list)
    changed: List[Dict[str, Any]] = field(default_factory=list)
    unchanged: int = 0

    def summary(self) -> str:
        """One-line count: added, removed, changed, unchanged."""
        return (
            f"+{len(self.added)} added, -{len(self.removed)} removed, "
            f"~{len(self.changed)} changed, ={self.unchanged} unchanged"
        )

    def as_dict(self) -> Dict[str, Any]:
        """JSON-serializable copy of the diff, including the summary string."""
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "summary": self.summary(),
        }


def diff_crawls(
    old: List[Dict[str, Any]],
    new: List[Dict[str, Any]],
    key_fields: Optional[List[str]] = None,
    ignore_fields: Optional[List[str]] = None,
) -> CrawlDiff:
    """Compare two crawl snapshots and return added, removed, and changed records.

    Records are matched by :func:`entity_key`, not by list position. Fields in
    ``ignore_fields`` (default ``_scraped_at``, ``fetched_at``) are skipped so
    scrape timestamps do not look like product changes.

    Values are compared after whitespace-normalized lowercase
    stringification, so ``10`` and ``"10"`` count as equal. ``10`` and
    ``10.0`` do not (``"10"`` vs ``"10.0"``). Duplicate keys in a snapshot:
    the last record with that key wins. Nested objects are compared as
    their ``str()`` form, which is good enough to detect a change, not to
    point at a nested path.
    """
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
