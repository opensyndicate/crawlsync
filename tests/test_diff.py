from crawlsync.diff import diff_crawls, entity_key


def test_entity_key_prefers_sku():
    assert entity_key({"sku": "X", "title": "T"}).startswith("sku:")


def test_entity_key_falls_back_to_title():
    assert entity_key({"title": "Widget"}) == "title:widget"


def test_entity_key_normalizes_case_and_space():
    assert entity_key({"sku": " A1 "}) == entity_key({"sku": "a1"})


def test_entity_key_hash_is_stable_and_order_independent():
    a = entity_key({"color": "Red", "size": "M"})
    b = entity_key({"size": "M", "color": "Red"})
    assert a == b
    assert a.startswith("hash:")
    assert a == entity_key({"color": "Red", "size": "M"})


def test_diff_add_remove_change():
    old = [{"sku": "1", "price": 10}, {"sku": "2", "price": 20}]
    new = [{"sku": "1", "price": 11}, {"sku": "3", "price": 30}]
    d = diff_crawls(old, new)
    assert len(d.added) == 1
    assert len(d.removed) == 1
    assert len(d.changed) == 1
    assert d.changed[0]["changes"][0]["field"] == "price"
    assert d.summary() == "+1 added, -1 removed, ~1 changed, =0 unchanged"


def test_ignore_scraped_at_by_default():
    old = [{"sku": "1", "price": 10, "_scraped_at": "t0"}]
    new = [{"sku": "1", "price": 10, "_scraped_at": "t1"}]
    d = diff_crawls(old, new)
    assert d.unchanged == 1
    assert d.changed == []


def test_string_and_int_values_compare_equal():
    old = [{"sku": "1", "price": 10}]
    new = [{"sku": "1", "price": "10"}]
    d = diff_crawls(old, new)
    assert d.unchanged == 1


def test_custom_key_fields():
    old = [{"url": "https://ex/a", "title": "Old"}]
    new = [{"url": "https://ex/a", "title": "New"}]
    d = diff_crawls(old, new, key_fields=["url"])
    assert len(d.changed) == 1
    assert d.changed[0]["key"].startswith("url:")


def test_as_dict_includes_summary():
    d = diff_crawls([], [{"sku": "1"}])
    payload = d.as_dict()
    assert payload["summary"].startswith("+1 added")
    assert payload["unchanged"] == 0
