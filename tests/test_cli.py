import json

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
