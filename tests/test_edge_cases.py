"""Empty, missing, wrong-type, unicode, and boundary cases for the core API."""

import math
from copy import deepcopy

import pytest

from crawlsync.diff import CrawlDiff, _norm, diff_crawls, entity_key


def test_norm_none_and_empty():
    assert _norm(None) == ""
    assert _norm("") == ""
    assert _norm("   ") == ""
    assert _norm("\t\n\r") == ""


def test_norm_collapses_whitespace_and_lowercases():
    assert _norm("  Foo\tBAR\n") == "foo bar"
    assert _norm(0) == "0"
    assert _norm(-1) == "-1"
    assert _norm(True) == "true"
    assert _norm(False) == "false"


def test_norm_nested_and_list_use_str():
    assert _norm([1, 2]) == str([1, 2]).strip().lower()
    assert _norm({"a": 1}).startswith("{")


def test_entity_key_rejects_non_dict():
    with pytest.raises(TypeError, match="record must be a dict"):
        entity_key(None)
    with pytest.raises(TypeError, match="record must be a dict"):
        entity_key("identity-sku")
    with pytest.raises(TypeError, match="record must be a dict"):
        entity_key(["sku", "A1"])
    with pytest.raises(TypeError, match="record must be a dict"):
        entity_key(1)


def test_entity_key_rejects_string_key_fields():
    with pytest.raises(TypeError, match="key_fields must be a list"):
        entity_key({"sku": "A1"}, key_fields="sku")


def test_entity_key_rejects_non_str_key_field_items():
    with pytest.raises(TypeError, match="key_fields\\[0\\] must be a str"):
        entity_key({"sku": "A1"}, key_fields=[1])
    with pytest.raises(TypeError, match="key_fields\\[1\\] must be a str"):
        entity_key({"sku": "A1"}, key_fields=["sku", None])


def test_entity_key_empty_key_fields_falls_through_to_title():
    assert entity_key({"sku": "X", "title": "Widget"}, key_fields=[]) == "title:widget"


def test_entity_key_skips_blank_identity_values():
    assert entity_key({"sku": None, "title": "Widget"}) == "title:widget"
    assert entity_key({"sku": "", "title": "Widget"}) == "title:widget"
    assert entity_key({"sku": "   ", "title": "Widget"}) == "title:widget"
    assert entity_key({"sku": "\t", "id": "9"}) == "id:9"


def test_entity_key_skips_blank_title_and_name():
    assert entity_key({"title": "", "name": "Gadget"}).startswith("name:")
    assert entity_key({"title": None, "name": "Gadget"}) == "name:gadget"
    assert entity_key({"title": "  ", "name": "Gadget"}) == "name:gadget"
    key = entity_key({"title": "", "name": "", "color": "red"})
    assert key.startswith("hash:")
    assert key == entity_key({"title": None, "name": None, "color": "red"})


def test_entity_key_blank_title_does_not_collide_with_other_blank_titles():
    a = entity_key({"title": "", "color": "red"})
    b = entity_key({"title": "", "color": "blue"})
    assert a != b
    assert a.startswith("hash:")


def test_entity_key_empty_record_is_stable_hash():
    assert entity_key({}) == entity_key({})
    assert entity_key({}).startswith("hash:")


def test_entity_key_unicode_emoji_and_controls():
    assert entity_key({"sku": "价格"}) == "sku:价格"
    assert entity_key({"sku": "Café"}) == entity_key({"sku": "café"})
    assert entity_key({"sku": "🔥"}).startswith("sku:")
    assert entity_key({"title": "naïve"}) == "title:naïve"
    # NUL is not whitespace; it stays in the identity
    assert "\x00" in entity_key({"sku": "A\x00B"})
    # tab/newline collapse like other whitespace
    assert entity_key({"sku": "A\tB"}) == entity_key({"sku": "A B"})


def test_entity_key_prefers_id_over_sku():
    assert entity_key({"id": "1", "sku": "X"}).startswith("id:")


def test_diff_crawls_empty_snapshots():
    d = diff_crawls([], [])
    assert d.added == []
    assert d.removed == []
    assert d.changed == []
    assert d.unchanged == 0
    assert d.summary() == "+0 added, -0 removed, ~0 changed, =0 unchanged"


def test_diff_crawls_none_and_wrong_container_types():
    with pytest.raises(TypeError, match="old must be a list of dicts"):
        diff_crawls(None, [])
    with pytest.raises(TypeError, match="new must be a list of dicts"):
        diff_crawls([], None)
    with pytest.raises(TypeError, match="old must be a list of dicts"):
        diff_crawls({"sku": "1"}, [{"sku": "1"}])
    with pytest.raises(TypeError, match="old must be a list of dicts"):
        diff_crawls("[]", [])
    with pytest.raises(TypeError, match="old must be a list of dicts"):
        diff_crawls(1, [])


def test_diff_crawls_rejects_non_dict_rows():
    with pytest.raises(TypeError, match=r"old\[0\] must be a dict"):
        diff_crawls([None], [])
    with pytest.raises(TypeError, match=r"new\[1\] must be a dict"):
        diff_crawls([], [{}, "row"])
    with pytest.raises(TypeError, match=r"old\[0\] must be a dict"):
        diff_crawls(["identity"], ["identity"])


def test_diff_crawls_accepts_tuple_of_dicts():
    d = diff_crawls(({"sku": "1", "p": 1},), ({"sku": "1", "p": 2},))
    assert len(d.changed) == 1


def test_diff_crawls_empty_ignore_fields_ignores_nothing():
    old = [{"sku": "1", "price": 10, "_scraped_at": "t0"}]
    new = [{"sku": "1", "price": 10, "_scraped_at": "t1"}]
    d = diff_crawls(old, new, ignore_fields=[])
    assert d.unchanged == 0
    assert len(d.changed) == 1
    assert d.changed[0]["changes"][0]["field"] == "_scraped_at"


def test_diff_crawls_rejects_string_ignore_fields():
    with pytest.raises(TypeError, match="ignore_fields must be a list"):
        diff_crawls([{"sku": "1"}], [{"sku": "1"}], ignore_fields="rank")


def test_diff_crawls_rejects_string_key_fields():
    with pytest.raises(TypeError, match="key_fields must be a list"):
        diff_crawls([{"sku": "1"}], [{"sku": "1"}], key_fields="sku")


def test_diff_missing_and_extra_fields():
    old = [{"sku": "1", "color": "red"}]
    new = [{"sku": "1", "size": "M"}]
    d = diff_crawls(old, new)
    fields = {c["field"] for c in d.changed[0]["changes"]}
    assert fields == {"color", "size"}
    by_field = {c["field"]: c for c in d.changed[0]["changes"]}
    assert by_field["color"]["old"] == "red"
    assert by_field["color"]["new"] is None
    assert by_field["size"]["old"] is None
    assert by_field["size"]["new"] == "M"


def test_diff_none_vs_missing_and_empty_string_are_equal():
    assert diff_crawls([{"sku": "1", "x": None}], [{"sku": "1"}]).unchanged == 1
    assert diff_crawls([{"sku": "1", "x": None}], [{"sku": "1", "x": ""}]).unchanged == 1
    assert diff_crawls([{"sku": "1", "x": "  "}], [{"sku": "1", "x": None}]).unchanged == 1


def test_diff_boundary_numbers():
    old = [{"sku": "1", "n": 0, "neg": -1, "big": 10**18}]
    new = [{"sku": "1", "n": 0, "neg": -1, "big": 10**18}]
    assert diff_crawls(old, new).unchanged == 1
    huge = diff_crawls([{"sku": "1", "n": 10**100}], [{"sku": "1", "n": 10**100}])
    assert huge.unchanged == 1
    # Documented: numbers compare as strings, so 0 and 0.0 differ.
    d = diff_crawls([{"sku": "1", "n": 0}], [{"sku": "1", "n": 0.0}])
    assert len(d.changed) == 1
    assert _norm(0) == "0"
    assert _norm(0.0) == "0.0"
    assert _norm(-0.0) == "-0.0"


def test_diff_nan_and_inf_stringify():
    d = diff_crawls(
        [{"sku": "1", "n": float("nan")}],
        [{"sku": "1", "n": float("nan")}],
    )
    assert d.unchanged == 1
    d = diff_crawls(
        [{"sku": "1", "n": float("inf")}],
        [{"sku": "1", "n": float("-inf")}],
    )
    assert len(d.changed) == 1
    assert math.isinf(d.changed[0]["changes"][0]["old"])


def test_diff_bool_not_equal_to_int():
    d = diff_crawls([{"sku": "1", "x": True}], [{"sku": "1", "x": 1}])
    assert len(d.changed) == 1


def test_diff_does_not_mutate_inputs():
    old = [{"sku": "1", "price": 10, "tags": ["a"]}]
    new = [{"sku": "1", "price": 12, "tags": ["a"]}]
    old_copy, new_copy = deepcopy(old), deepcopy(new)
    diff_crawls(old, new)
    assert old == old_copy
    assert new == new_copy


def test_as_dict_list_copy_does_not_alias_top_level():
    d = diff_crawls([], [{"sku": "1"}])
    payload = d.as_dict()
    payload["added"].clear()
    assert len(d.added) == 1


def test_changed_fields_are_sorted():
    d = diff_crawls(
        [{"sku": "1", "z": 1, "a": 1, "m": 1}],
        [{"sku": "1", "z": 2, "a": 2, "m": 2}],
    )
    assert [c["field"] for c in d.changed[0]["changes"]] == ["a", "m", "z"]


def test_duplicate_keys_last_row_wins():
    old = [{"sku": "1", "price": 1}, {"sku": "1", "price": 9}]
    new = [{"sku": "1", "price": 9}]
    d = diff_crawls(old, new)
    assert d.unchanged == 1
    assert d.added == []
    assert d.removed == []


def test_unicode_field_values_round_trip_in_as_dict():
    old = [{"sku": "Å1", "title": "🔥 widget"}]
    new = [{"sku": "å1", "title": "🔥 widget", "note": "ok"}]
    d = diff_crawls(old, new)
    assert d.changed[0]["key"] == "sku:å1"
    payload = d.as_dict()
    assert payload["changed"][0]["record"]["note"] == "ok"


def test_nested_dict_change_is_detected_as_one_field():
    old = [{"sku": "1", "meta": {"a": 1}}]
    new = [{"sku": "1", "meta": {"a": 2}}]
    d = diff_crawls(old, new)
    assert len(d.changed) == 1
    assert d.changed[0]["changes"][0]["field"] == "meta"


def test_crawl_diff_defaults_and_summary():
    empty = CrawlDiff()
    assert empty.summary() == "+0 added, -0 removed, ~0 changed, =0 unchanged"
    assert empty.as_dict()["unchanged"] == 0
