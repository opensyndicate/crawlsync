"""Command-line entry for CrawlSync.

Pass two JSON files (each a list of objects) to diff real crawls. With no
arguments, or with ``--demo``, prints a built-in catalog example.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from crawlsync.diff import diff_crawls


def _demo_payload() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old = [
        {"sku": "A1", "title": "Widget", "price": 10},
        {"sku": "B2", "title": "Gadget", "price": 20},
    ]
    new = [
        {"sku": "A1", "title": "Widget", "price": 12},
        {"sku": "C3", "title": "New Thing", "price": 5},
    ]
    return old, new


def _load_records(path: str) -> List[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise SystemExit(f"{path}: expected a JSON array of objects, got {type(data).__name__}")
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise SystemExit(f"{path}: item {i} is not an object")
    return data


def _split_fields(raw: Optional[str]) -> Optional[List[str]]:
    if raw is None:
        return None
    fields = [part.strip() for part in raw.split(",") if part.strip()]
    return fields or None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crawlsync",
        description="Semantic diff for web crawl datasets (added, removed, field changes).",
    )
    parser.add_argument("old", nargs="?", help="Old crawl JSON (array of objects)")
    parser.add_argument("new", nargs="?", help="New crawl JSON (array of objects)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in Widget/Gadget example instead of reading files",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="as_json",
        action="store_true",
        help="Print the full diff as JSON",
    )
    parser.add_argument(
        "--key-fields",
        metavar="FIELDS",
        help="Comma-separated identity fields (default: id,sku,url,product_id,asin)",
    )
    parser.add_argument(
        "--ignore-fields",
        metavar="FIELDS",
        help="Comma-separated fields to skip (default: _scraped_at,fetched_at)",
    )
    args = parser.parse_args(argv)

    if args.demo or (args.old is None and args.new is None):
        old, new = _demo_payload()
        if not args.demo and args.old is None:
            print("demo mode (pass two JSON files to diff real crawls)", file=sys.stderr)
    elif args.old is not None and args.new is not None:
        old, new = _load_records(args.old), _load_records(args.new)
    else:
        parser.error("provide both OLD and NEW JSON files, or pass --demo")

    d = diff_crawls(
        old,
        new,
        key_fields=_split_fields(args.key_fields),
        ignore_fields=_split_fields(args.ignore_fields),
    )
    print(d.summary())
    if args.as_json:
        print(json.dumps(d.as_dict(), indent=2))
    elif not args.demo and args.old is not None:
        for row in d.changed:
            print(row["key"], row["changes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
