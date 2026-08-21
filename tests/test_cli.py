import json

import pytest

from crawlsync.cli import main


def test_demo_prints_summary(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "+1 added, -1 removed, ~1 changed, =0 unchanged" in out


def test_file_diff_json(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps([{"sku": "A1", "price": 10}]), encoding="utf-8")
    new.write_text(json.dumps([{"sku": "A1", "price": 12}]), encoding="utf-8")
    assert main([str(old), str(new), "--json"]) == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured.split("\n", 1)[1])
    assert payload["changed"][0]["changes"][0]["field"] == "price"


def test_no_args_prints_demo_on_stderr(capsys):
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "demo mode" in captured.err
    assert "added" in captured.out


def test_one_file_is_an_error():
    with pytest.raises(SystemExit):
        main(["only.json"])


def test_missing_file_is_a_clear_error(tmp_path):
    missing = tmp_path / "nope.json"
    present = tmp_path / "ok.json"
    present.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(missing), str(present)])
    assert "file not found" in str(ei.value)


def test_directory_path_is_a_clear_error(tmp_path):
    folder = tmp_path / "dir"
    folder.mkdir()
    other = tmp_path / "ok.json"
    other.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(folder), str(other)])
    msg = str(ei.value).lower()
    assert "directory" in msg or "permission denied" in msg or "is a directory" in msg


def test_empty_file_is_a_clear_error(tmp_path):
    empty = tmp_path / "empty.json"
    other = tmp_path / "ok.json"
    empty.write_text("", encoding="utf-8")
    other.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(empty), str(other)])
    assert "empty file" in str(ei.value)


def test_broken_json_is_a_clear_error(tmp_path):
    bad = tmp_path / "bad.json"
    ok = tmp_path / "ok.json"
    bad.write_text('[{"sku": "A1"', encoding="utf-8")
    ok.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(bad), str(ok)])
    assert "invalid JSON" in str(ei.value)


def test_trailing_comma_json_is_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    ok = tmp_path / "ok.json"
    bad.write_text('[{"sku": "A1"},]', encoding="utf-8")
    ok.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(bad), str(ok)])
    assert "invalid JSON" in str(ei.value)


def test_json_object_root_is_rejected(tmp_path):
    obj = tmp_path / "obj.json"
    ok = tmp_path / "ok.json"
    obj.write_text('{"sku": "A1"}', encoding="utf-8")
    ok.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(obj), str(ok)])
    assert "expected a JSON array" in str(ei.value)
    assert "dict" in str(ei.value)


def test_json_null_and_number_roots_are_rejected(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text("[]", encoding="utf-8")
    for raw, kind in (("null", "NoneType"), ("1", "int"), ('"x"', "str"), ("true", "bool")):
        path = tmp_path / f"root-{kind}.json"
        path.write_text(raw, encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            main([str(path), str(ok)])
        assert "expected a JSON array" in str(ei.value)
        assert kind in str(ei.value)


def test_non_object_array_item_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    ok = tmp_path / "ok.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    ok.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(bad), str(ok)])
    assert "item 0 is not an object" in str(ei.value)


def test_utf8_bom_is_accepted(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    payload = json.dumps([{"sku": "A1", "price": 10}])
    old.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    new.write_text(json.dumps([{"sku": "A1", "price": 10}]), encoding="utf-8")
    assert main([str(old), str(new)]) == 0
    assert "unchanged" in capsys.readouterr().out


def test_invalid_utf8_is_a_clear_error(tmp_path):
    bad = tmp_path / "bad.json"
    ok = tmp_path / "ok.json"
    bad.write_bytes(b'[{"sku": "\xff"}]')
    ok.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        main([str(bad), str(ok)])
    assert "UTF-8" in str(ei.value)


def test_duplicate_json_object_keys_last_wins(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    # Standard json.loads keeps the last value for a repeated key.
    old.write_text('[{"sku": "A", "sku": "B", "price": 1}]', encoding="utf-8")
    new.write_text('[{"sku": "B", "price": 1}]', encoding="utf-8")
    assert main([str(old), str(new)]) == 0
    assert "=1 unchanged" in capsys.readouterr().out


def test_unicode_records_via_cli(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(
        json.dumps([{"sku": "价格", "title": "Café 🔥"}], ensure_ascii=False),
        encoding="utf-8",
    )
    new.write_text(
        json.dumps([{"sku": "价格", "title": "Café 🔥", "price": 3}], ensure_ascii=False),
        encoding="utf-8",
    )
    assert main([str(old), str(new), "--json"]) == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured.split("\n", 1)[1])
    assert payload["changed"][0]["key"] == "sku:价格"


def test_empty_arrays_via_cli(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text("[]", encoding="utf-8")
    new.write_text("[]", encoding="utf-8")
    assert main([str(old), str(new)]) == 0
    assert "+0 added" in capsys.readouterr().out


def test_ignore_fields_empty_means_ignore_nothing(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(
        json.dumps([{"sku": "A1", "price": 10, "_scraped_at": "t0"}]),
        encoding="utf-8",
    )
    new.write_text(
        json.dumps([{"sku": "A1", "price": 10, "_scraped_at": "t1"}]),
        encoding="utf-8",
    )
    assert main([str(old), str(new), "--ignore-fields", ""]) == 0
    assert "~1 changed" in capsys.readouterr().out


def test_key_fields_flag(tmp_path, capsys):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(
        json.dumps([{"url": "https://ex/a", "title": "Old"}]),
        encoding="utf-8",
    )
    new.write_text(
        json.dumps([{"url": "https://ex/a", "title": "New"}]),
        encoding="utf-8",
    )
    assert main([str(old), str(new), "--key-fields", "url"]) == 0
    out = capsys.readouterr().out
    assert "url:https://ex/a" in out


def test_examples_yesterday_vs_today(capsys):
    assert main(["examples/yesterday.json", "examples/today.json"]) == 0
    out = capsys.readouterr().out
    assert "+1 added, -1 removed, ~1 changed, =1 unchanged" in out


def test_demo_json_is_valid(capsys):
    assert main(["--demo", "--json"]) == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured.split("\n", 1)[1])
    assert payload["summary"].startswith("+1 added")
    assert len(payload["added"]) == 1
    assert len(payload["removed"]) == 1
    assert len(payload["changed"]) == 1
