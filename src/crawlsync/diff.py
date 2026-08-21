"""Entity-aware crawl diff."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


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
    return hashlib.sha1(blob.encode("utf-8", errors="surrogatepass")).hexdigest()[:16]


def _require_str_sequence(value: Any, name: str) -> List[str]:
    """Return a list of strings, or raise TypeError."""
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a list of strings, got {type(value).__name__}")
    try:
        items = list(value)
    except TypeError as exc:
        raise TypeError(
            f"{name} must be a list of strings, got {type(value).__name__}"
        ) from exc
    out: List[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, str):
            raise TypeError(f"{name}[{i}] must be a str, got {type(item).__name__}")
        out.append(item)
    return out


def _require_records(rows: Any, name: str) -> Sequence[Dict[str, Any]]:
    """Reject None, mappings, and strings so callers get a clear TypeError."""
    if rows is None or isinstance(rows, (str, bytes, Mapping)):
        raise TypeError(f"{name} must be a list of dicts, got {type(rows).__name__}")
    if not isinstance(rows, Iterable):
        raise TypeError(f"{name} must be a list of dicts, got {type(rows).__name__}")
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"{name}[{i}] must be a dict, got {type(row).__name__}")
        out.append(row)
    return out


def entity_key(record: Dict[str, Any], key_fields: Optional[List[str]] = None) -> str:
    """Return a stable identity string for one crawled record.

    Tries ``key_fields`` in order (default: ``id``, ``sku``, ``url``,
    ``product_id``, ``asin``). ``None`` uses that default. An empty list skips
    those fields and falls through to ``title``, then ``name``, then hash.

    The first field that is present and non-blank after normalization wins.
    Blank means None, empty, or whitespace-only. ``title`` and ``name`` use
    the same rule. If none match, a SHA-1 of the normalized field set is
    used so the same record hashes the same across processes.

    Values are normalized (strip, lowercase, collapsed whitespace) before
    they become part of the key, so ``SKU: "A1"`` and ``sku: "a1"`` match.
    """
    if not isinstance(record, dict):
        raise TypeError(f"record must be a dict, got {type(record).__name__}")
    if key_fields is None:
        fields = ["id", "sku", "url", "product_id", "asin"]
    else:
        fields = _require_str_sequence(key_fields, "key_fields")
    for k in fields:
        if k in record:
            val = _norm(record[k])
            if val:
                return f"{k}:{val}"
    if "title" in record:
        val = _norm(record["title"])
        if val:
            return f"title:{val}"
    if "name" in record:
        val = _norm(record["name"])
        if val:
            return f"name:{val}"
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
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
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
    scrape timestamps do not look like product changes. Pass an empty list to
    ignore nothing. A string is rejected; pass a list of field names.

    Values are compared after whitespace-normalized lowercase
    stringification, so ``10`` and ``"10"`` count as equal. ``10`` and
    ``10.0`` do not (``"10"`` vs ``"10.0"``). Duplicate keys in a snapshot:
    the last record with that key wins. Nested objects are compared as
    their ``str()`` form, which is good enough to detect a change, not to
    point at a nested path.
    """
    if ignore_fields is None:
        ignore: set[Any] = {"_scraped_at", "fetched_at"}
    else:
        ignore = set(_require_str_sequence(ignore_fields, "ignore_fields"))
    if key_fields is not None:
        key_fields = _require_str_sequence(key_fields, "key_fields")

    old_rows = _require_records(old, "old")
    new_rows = _require_records(new, "new")
    old_map = {entity_key(r, key_fields): r for r in old_rows}
    new_map = {entity_key(r, key_fields): r for r in new_rows}

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
        for f in sorted(fields, key=str):
            if f in ignore:
                continue
            if _norm(a.get(f)) != _norm(b.get(f)):
                changes.append({"field": f, "old": a.get(f), "new": b.get(f)})
        if changes:
            result.changed.append({"key": k, "changes": changes, "record": b})
        else:
            result.unchanged += 1

    return result
