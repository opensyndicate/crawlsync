# CrawlSync: Semantic Diff for Web Crawl Outputs (SKU and Product Change Tracker)

**Keywords:** crawl diff, compare scrape results, product catalog diff, SKU change detection, web scraping diff, price change tracker, JSON product comparison, ecommerce catalog sync, semantic diff python, detect added removed products

> Diff two crawl dumps by SKU, URL, or title. Get added, removed, and field-level changes instead of a raw JSON dump.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/pandeyvishwas51-oss/crawlsync/actions/workflows/ci.yml/badge.svg)](https://github.com/pandeyvishwas51-oss/crawlsync/actions/workflows/ci.yml)

---

## What is CrawlSync?

CrawlSync is a zero-dependency Python library that compares two lists of crawled records (usually products) and reports what appeared, disappeared, or changed field by field. Identity is not array index. A record is matched by `id`, `sku`, `url`, `product_id`, or `asin`, then by `title` or `name`.

| Piece | Role |
|-------|------|
| `entity_key` | Stable identity from the first non-empty key field |
| `diff_crawls` | Set difference plus per-field compare |
| `CrawlDiff` | `added`, `removed`, `changed`, `unchanged` count, `summary()` |
| CLI | Diff two JSON files, or `--demo` |

It does not crawl the web. You already have yesterday's dump and today's dump. This package diffs them.

### Direct answer

**How do I compare two web crawls and see which products changed?**
Load both crawls as lists of dicts and call `diff_crawls(old, new)`. Records match by SKU (or url, id, title), not by list position. The result lists new products, missing products, and per-field old/new values for products that stayed but changed.

**Why not git-diff the JSON files?**
Git compares lines. If the scraper reorders products, pretty-prints differently, or writes a new `fetched_at` on every row, the whole file looks changed. CrawlSync compares entities and ignores `_scraped_at` and `fetched_at` by default.

**Can I track price changes by SKU?**
Yes. Two records with the same SKU and a different `price` land in `changed` as `{"field": "price", "old": ..., "new": ...}`. That is the main use: catalog monitoring after each crawl.

---

## Why CrawlSync?

| Approach | What you get | Tradeoff |
|----------|--------------|----------|
| `git diff` on JSON | Line delta | Breaks when array order, key order, or scrape timestamps change. No SKU identity. |
| DeepDiff / jsondiff | Tree delta | Matches by path or index unless you configure it. Heavier, and still not a catalog tool. |
| pandas merge | Join on a key | Extra dependency. You still write the added/removed/changed logic. |
| **CrawlSync** | Entity-keyed add / remove / field changes | In-memory, top-level fields, no runtime deps. Not a database and not a crawler. |

Use git when you care about the file. Use CrawlSync when you care about the catalog.

---

## How it works

Each record gets an identity string from `entity_key`:

1. Try `id`, `sku`, `url`, `product_id`, `asin` in that order (override with `key_fields`).
2. If none are present, use `title`, then `name`.
3. Last resort: a SHA-1 of the normalized field set (stable across processes). Values are stripped, lowercased, and whitespace-collapsed, so `"A1"` and `"a1"` are the same product.

Then `diff_crawls` builds an old map and a new map:

```
old records ── entity_key ──► old_map
new records ── entity_key ──► new_map

new keys - old keys  ► added
old keys - new keys  ► removed
intersection         ► compare fields (skip _scraped_at, fetched_at)
                       changed if any field differs, else unchanged += 1
```

Field compare uses the same normalization. `10` and `"10"` count as equal. `10` and `10.0` do not (`"10"` vs `"10.0"`). Nested objects are compared as `str()`, which detects a change but does not report a nested path. Duplicate keys in one snapshot: the last record with that key wins.

Changed entries look like this:

```json
{
  "key": "sku:a1",
  "changes": [{"field": "price", "old": 10, "new": 12}],
  "record": {"sku": "A1", "title": "Widget", "price": 12}
}
```

The `key` is lowercased because identity is normalized. `record` is the new snapshot's row.

```
src/crawlsync/
  __init__.py    CrawlDiff, diff_crawls, entity_key
  diff.py        identity + compare
  cli.py         crawlsync command
examples/        yesterday.json, today.json
tests/
```

---

## Installation

Python 3.11+. No third-party runtime packages.

```bash
git clone https://github.com/pandeyvishwas51-oss/crawlsync.git
cd crawlsync
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Quick start

```python
from crawlsync import diff_crawls

yesterday = [
    {"sku": "A1", "title": "Widget", "price": 10},
    {"sku": "B2", "title": "Gadget", "price": 20},
]
today = [
    {"sku": "A1", "title": "Widget", "price": 12},
    {"sku": "C3", "title": "New Thing", "price": 5},
]

d = diff_crawls(yesterday, today)
print(d.summary())
# +1 added, -1 removed, ~1 changed, =0 unchanged

for row in d.changed:
    print(row["key"], row["changes"])
# sku:a1 [{'field': 'price', 'old': 10, 'new': 12}]
```

Custom identity and ignored fields:

```python
d = diff_crawls(
    yesterday,
    today,
    key_fields=["url", "sku"],
    ignore_fields=["_scraped_at", "fetched_at", "rank"],
)
```

### CLI

```bash
# Built-in example
crawlsync --demo --json

# Real files (each a JSON array of objects)
crawlsync examples/yesterday.json examples/today.json
crawlsync examples/yesterday.json examples/today.json --json
crawlsync examples/yesterday.json examples/today.json --key-fields sku,url
```

`examples/yesterday.json` vs `examples/today.json` is: A1 price 10 to 12, B2 removed, C3 added, D4 unchanged (only `_scraped_at` moved). Expected summary:

```
+1 added, -1 removed, ~1 changed, =1 unchanged
```

Same thing as a module:

```bash
python -m crawlsync --demo
```

---

## FAQ

### Does CrawlSync crawl websites?
No. It diffs datasets you already have (Scrapy exports, sitemap dumps, marketplace APIs). Pair it with your crawler. It is the compare step, not the fetch step.

### Which field is used as the product identity?
The first non-empty of `id`, `sku`, `url`, `product_id`, `asin`. If those are missing, `title`, then `name`, then a content hash. Pass `key_fields` when your catalog uses something else (`gtin`, `mpn`, `handle`).

### Why did a price of 10 vs 10.0 show up as a change?
Values are compared as normalized strings. `10` becomes `"10"` and `10.0` becomes `"10.0"`. Cast numbers to a single type before calling `diff_crawls` if you want those to match.

### What if two rows share the same SKU?
The last row with that key in the list wins. Deduplicate before you diff if duplicates are a data-quality issue.

### Are scrape timestamps treated as product changes?
Not by default. `_scraped_at` and `fetched_at` are ignored. Override with `ignore_fields` if your crawler uses other clock columns.

### Can it diff nested JSON (variants, images, specs)?
It compares top-level fields. A nested dict or list is one value. You will see that `images` changed, not which URL at which index. Flatten or pre-process nested structures if you need path-level output.

### What Python versions are supported?
Python 3.11 and newer.

### Is there a test suite?
Yes. `pytest tests/ -v` (mocked-nothing, no network). GitHub Actions runs the same on 3.11 and 3.12.

---

## License

[MIT](LICENSE). Free for commercial and personal use.
