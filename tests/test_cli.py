import json
from pathlib import Path

from pos import cli

FIX = str(Path(__file__).parent / "fixtures" / "focus.toml")


def test_status_json(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.status.git_state", lambda p: {"branch": "main", "dirty": False})
    rc = cli.main(["status", "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 0
    assert any(r["project"] == "cenno" for r in data)


def test_bare_lists_focuses(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main([])
    out = capsys.readouterr().out
    assert "business" in out and "play" in out
    assert rc == 0


def test_p_lists_projects_grouped(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["p"])
    out = capsys.readouterr().out
    assert "cenno" in out and "generative-sequencer" in out
    assert rc == 0


def test_unknown_command_returns_1(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["frobnicate"])
    assert rc == 1


def test_yard_run_valid(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    calls = []
    monkeypatch.setattr("pos.yard.run", lambda name, command: calls.append((name, command)))
    rc = cli.main(["yard", "run", "crawl", "--", "firecrawl", "go"])
    assert rc == 0
    assert calls == [("crawl", "firecrawl go")]


def test_yard_run_missing_name_before_dashdash(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.yard.run", lambda *a: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = cli.main(["yard", "run", "--", "ls"])
    assert rc == 1


def test_yard_run_empty_command_after_dashdash(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.yard.run", lambda *a: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = cli.main(["yard", "run", "task", "--"])
    assert rc == 1
