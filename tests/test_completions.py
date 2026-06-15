from pathlib import Path
from pos import cli, completions

FIX = str(Path(__file__).parent / "fixtures" / "focus.toml")


def test_scripts_exist_for_all_shells():
    for sh in ("zsh", "bash", "fish"):
        assert completions.script(sh)
    assert completions.script("powershell") is None


def test_commands_list_covers_key_verbs():
    for v in ("cc", "tile", "config", "spread", "gather", "solo", "completions"):
        assert v in completions.COMMANDS


def test_completions_cmd_prints_zsh_by_default(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    assert cli.main(["completions"]) == 0
    out = capsys.readouterr().out
    assert "#compdef pos" in out and "pos __list commands" in out


def test_completions_unknown_shell_errors(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    assert cli.main(["completions", "powershell"]) == 1


def test_list_commands(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    cli.main(["__list", "commands"])
    out = capsys.readouterr().out.split()
    assert "cc" in out and "tile" in out


def test_list_focuses_and_projects(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    cli.main(["__list", "focuses"]); foc = capsys.readouterr().out
    assert "business" in foc
    cli.main(["__list", "projects"]); proj = capsys.readouterr().out
    assert "cenno" in proj


def test_list_settings(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    cli.main(["__list", "settings"])
    out = capsys.readouterr().out
    assert "window_manager" in out and "tile_layout" in out


def test_list_workspaces_uses_live_cmux(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [{"title": "◆ cenno"}, {"title": "brain"}])
    cli.main(["__list", "workspaces"])
    out = capsys.readouterr().out.split()
    assert "cenno" in out and "brain" in out


def test_list_unknown_kind_returns_1(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    assert cli.main(["__list", "bogus"]) == 1
