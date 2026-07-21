# CrawlSync

**Git-like semantic diff for crawl outputs.**

Compare two crawls and get: products added, removed, and field-level changes — with entity identity (`sku` / `url` / `title`), not blind JSON dumps.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
python -m src.crawlsync.cli
```

## Usage

```python
from src.crawlsync.diff import diff_crawls

d = diff_crawls(yesterday_products, today_products)
print(d.summary())
# +3 added, -1 removed, ~12 changed, =984 unchanged
for c in d.changed:
    print(c["key"], c["changes"])
```

## License

MIT
