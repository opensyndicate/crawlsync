"""Large-input checks: stay correct and finish in a short time."""

import time

from crawlsync.diff import diff_crawls, entity_key


def test_thousands_of_unchanged_records():
    n = 4000
    old = [{"sku": f"S{i:05d}", "title": f"Item {i}", "price": i} for i in range(n)]
    new = [{"sku": f"S{i:05d}", "title": f"Item {i}", "price": i} for i in range(n)]
    started = time.perf_counter()
    d = diff_crawls(old, new)
    elapsed = time.perf_counter() - started
    assert d.unchanged == n
    assert d.added == []
    assert d.removed == []
    assert d.changed == []
    assert elapsed < 5.0


def test_thousands_with_one_change_and_one_add_remove():
    n = 3000
    old = [{"sku": f"S{i:05d}", "price": i} for i in range(n)]
    new = [{"sku": f"S{i:05d}", "price": i} for i in range(n)]
    new[0] = {"sku": "S00000", "price": 999}
    new[-1] = {"sku": "NEW", "price": 0}
    # last old sku is missing from new; NEW is added; first price changed
    started = time.perf_counter()
    d = diff_crawls(old, new)
    elapsed = time.perf_counter() - started
    assert len(d.added) == 1
    assert d.added[0]["sku"] == "NEW"
    assert len(d.removed) == 1
    assert d.removed[0]["sku"] == f"S{n - 1:05d}"
    assert len(d.changed) == 1
    assert d.changed[0]["key"] == "sku:s00000"
    assert d.unchanged == n - 2
    assert elapsed < 5.0


def test_all_new_catalog_is_added():
    old = [{"sku": f"OLD{i}", "price": 1} for i in range(1500)]
    new = [{"sku": f"NEW{i}", "price": 1} for i in range(1500)]
    d = diff_crawls(old, new)
    assert len(d.added) == 1500
    assert len(d.removed) == 1500
    assert d.changed == []
    assert d.unchanged == 0


def test_very_long_string_fields():
    blob = "x" * 200_000
    old = [{"sku": "1", "desc": blob}]
    new = [{"sku": "1", "desc": blob}]
    d = diff_crawls(old, new)
    assert d.unchanged == 1
    new2 = [{"sku": "1", "desc": blob + "y"}]
    d2 = diff_crawls(old, new2)
    assert len(d2.changed) == 1
    assert d2.changed[0]["changes"][0]["field"] == "desc"


def test_very_long_identity_value():
    sku = "K" * 50_000
    key = entity_key({"sku": sku})
    assert key.startswith("sku:")
    assert len(key) == 4 + 50_000
    d = diff_crawls([{"sku": sku, "p": 1}], [{"sku": sku, "p": 2}])
    assert len(d.changed) == 1


def test_wide_records_many_fields():
    fields = {f"f{i}": i for i in range(500)}
    old = [{"sku": "1", **fields}]
    new_fields = dict(fields)
    new_fields["f0"] = 999
    new = [{"sku": "1", **new_fields}]
    d = diff_crawls(old, new)
    assert len(d.changed) == 1
    assert d.changed[0]["changes"][0]["field"] == "f0"


def test_duplicate_heavy_snapshot_last_wins():
    old = [{"sku": "DUP", "n": i} for i in range(2000)]
    new = [{"sku": "DUP", "n": 1999}]
    d = diff_crawls(old, new)
    assert d.unchanged == 1
    assert d.summary() == "+0 added, -0 removed, ~0 changed, =1 unchanged"
