from src.crawlsync.diff import diff_crawls, entity_key


def test_entity_key_prefers_sku():
    assert entity_key({"sku": "X", "title": "T"}).startswith("sku:")


def test_diff_add_remove_change():
    old = [{"sku": "1", "price": 10}, {"sku": "2", "price": 20}]
    new = [{"sku": "1", "price": 11}, {"sku": "3", "price": 30}]
    d = diff_crawls(old, new)
    assert len(d.added) == 1
    assert len(d.removed) == 1
    assert len(d.changed) == 1
    assert d.changed[0]["changes"][0]["field"] == "price"
