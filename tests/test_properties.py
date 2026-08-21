"""Property-based tests for identity, normalization, and diff counts."""

from hypothesis import given, settings
from hypothesis import strategies as st

from crawlsync.diff import _norm, diff_crawls, entity_key

_SAFE_CHARS = st.characters(
    whitelist_categories=("L", "N", "P", "S", "Zs"),
    blacklist_characters="\x00",
)

jsonish = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**12), max_value=10**12),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(_SAFE_CHARS, max_size=40),
)

field_names = st.text(_SAFE_CHARS, min_size=1, max_size=16).filter(
    lambda s: s.strip() != ""
)

records = st.dictionaries(field_names, jsonish, max_size=8)

identity_free_names = field_names.filter(
    lambda s: s not in {"id", "sku", "url", "product_id", "asin", "title", "name"}
)
hash_records = st.dictionaries(identity_free_names, jsonish, max_size=6)


@given(st.text(_SAFE_CHARS, max_size=80), st.none())
@settings(max_examples=80)
def test_norm_none_is_empty_and_text_is_str(s, n):
    assert _norm(n) == ""
    out = _norm(s)
    assert isinstance(out, str)
    assert out == out.strip()
    assert _norm(out) == out


@given(st.text(_SAFE_CHARS, max_size=80))
@settings(max_examples=80)
def test_norm_is_idempotent_on_text(s):
    assert _norm(_norm(s)) == _norm(s)


@given(st.text(_SAFE_CHARS, max_size=80))
@settings(max_examples=80)
def test_norm_lowercases_and_collapses_ascii_space(s):
    assert "\n" not in _norm(s)
    assert "\t" not in _norm(s)
    assert "  " not in _norm(s)
    assert _norm(s) == _norm(s.lower())


@given(records)
@settings(max_examples=80)
def test_entity_key_is_deterministic(record):
    assert entity_key(record) == entity_key(dict(record))
    assert isinstance(entity_key(record), str)
    assert entity_key(record) != ""


@given(hash_records)
@settings(max_examples=60)
def test_hash_key_independent_of_insertion_order(record):
    items = list(record.items())
    reversed_rec = dict(reversed(items))
    assert entity_key(record) == entity_key(reversed_rec)
    if record:
        assert entity_key(record).startswith("hash:")


@given(st.text(_SAFE_CHARS, min_size=1, max_size=40).filter(lambda s: _norm(s) != ""))
@settings(max_examples=80)
def test_entity_key_strips_and_lowercases_sku(s):
    assert entity_key({"sku": s}) == entity_key({"sku": s.lower()})
    assert entity_key({"sku": s}) == entity_key({"sku": f"  {s}  "})
    assert entity_key({"sku": s}).startswith("sku:")


@given(st.lists(records, max_size=25))
@settings(max_examples=50)
def test_diff_against_self_has_only_unchanged(rows):
    d = diff_crawls(rows, list(rows))
    assert d.added == []
    assert d.removed == []
    assert d.changed == []
    unique = {entity_key(r) for r in rows}
    assert d.unchanged == len(unique)


@given(st.lists(records, max_size=20), st.lists(records, max_size=20))
@settings(max_examples=50)
def test_added_and_removed_swap_when_snapshots_swap(old, new):
    d1 = diff_crawls(old, new)
    d2 = diff_crawls(new, old)
    assert d1.added == d2.removed
    assert d1.removed == d2.added
    assert {row["key"] for row in d1.changed} == {row["key"] for row in d2.changed}
    assert d1.unchanged == d2.unchanged


@given(st.lists(records, max_size=20), st.lists(records, max_size=20))
@settings(max_examples=50)
def test_counts_partition_the_key_union(old, new):
    d = diff_crawls(old, new)
    old_keys = {entity_key(r) for r in old}
    new_keys = {entity_key(r) for r in new}
    assert len(d.added) + len(d.removed) + len(d.changed) + d.unchanged == len(
        old_keys | new_keys
    )
    assert len(d.added) == len(new_keys - old_keys)
    assert len(d.removed) == len(old_keys - new_keys)
    assert len(d.changed) + d.unchanged == len(old_keys & new_keys)


@given(st.lists(records, max_size=15), st.lists(field_names, max_size=4))
@settings(max_examples=40)
def test_ignore_fields_never_appear_in_changes(rows, ignored):
    # Mutate a copy so ignored fields differ; they must not show up as changes
    # unless some other field also differs.
    new = []
    for row in rows:
        copy = dict(row)
        for name in ignored:
            copy[name] = "changed-ignored"
        new.append(copy)
    d = diff_crawls(rows, new, ignore_fields=ignored)
    for row in d.changed:
        changed_names = {c["field"] for c in row["changes"]}
        assert changed_names.isdisjoint(set(ignored))
