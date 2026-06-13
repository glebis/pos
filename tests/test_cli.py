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


def test_day_dry_run(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.day.read_daily", lambda d: "work on cenno today")
    rc = cli.main(["day", "--date", "20260613", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hybrid pin plan" in out
    assert "cenno" in out
    assert "dry-run" in out


def test_load_dry_run_preset(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◆ cenno", "pinned": True},
        {"ref": "w2", "title": "◆ devops", "pinned": False},
    ])
    rc = cli.main(["load", "revenue-sprint"])  # members: business, cenno
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    assert "business" in out and "cenno" in out
    assert "devops" in out  # devops should be listed to close


def test_load_unknown_member_errors(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["load", "nonexistent-thing"])
    assert rc == 1


def test_load_bare_lists_presets(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["load"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "revenue-sprint" in out


def test_load_force_ignores_running_overlay(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◇ Voice", "pinned": False},
        {"ref": "w2", "title": "◆ cenno", "pinned": False},
    ])
    # session JSON would mark Voice running, but --force skips that overlay
    monkeypatch.setattr("pos.cli._running_titles", lambda: {"Voice"})
    # without force: Voice protected (skip running)
    cli.main(["load", "cenno"])
    out_noforce = capsys.readouterr().out
    assert "Voice" in out_noforce and "skip (running)" in out_noforce
    # with force: Voice is closeable
    cli.main(["load", "cenno", "--force"])
    out_force = capsys.readouterr().out
    assert "skip (running)" not in out_force
    assert "Voice" in out_force  # now in close list
