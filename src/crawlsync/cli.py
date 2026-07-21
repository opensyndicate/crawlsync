from __future__ import annotations

import json

from src.crawlsync.diff import diff_crawls


def main():
    old = [
        {"sku": "A1", "title": "Widget", "price": 10},
        {"sku": "B2", "title": "Gadget", "price": 20},
    ]
    new = [
        {"sku": "A1", "title": "Widget", "price": 12},  # price change
        {"sku": "C3", "title": "New Thing", "price": 5},  # added
        # B2 removed
    ]
    d = diff_crawls(old, new)
    print(d.summary())
    print(json.dumps({"added": d.added, "removed": d.removed, "changed": d.changed}, indent=2))


if __name__ == "__main__":
    main()
