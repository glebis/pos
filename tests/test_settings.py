import types
from pos import settings, spread
from pos import cli


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    assert settings.load() == {"window_manager": "aerospace", "tile_layout": "tiles"}


def test_set_and_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    ok, msg = settings.set_value("window_manager", "none")
    assert ok and settings.load()["window_manager"] == "none"
    # other keys keep defaults
    assert settings.load()["tile_layout"] == "tiles"


def test_validate_rejects_unknown_key_and_value(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    assert settings.set_value("bogus", "x")[0] is False
    ok, msg = settings.set_value("window_manager", "i3")
    assert ok is False and "one of" in msg


def test_load_ignores_unknown_keys_in_file(tmp_path, monkeypatch):
    f = tmp_path / "s.toml"
    f.write_text('window_manager = "none"\nbogus = "1"\n')
    monkeypatch.setenv("POS_SETTINGS", str(f))
    cfg = settings.load()
    assert cfg == {"window_manager": "none", "tile_layout": "tiles"}


def test_tile_respects_window_manager_none(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    settings.set_value("window_manager", "none")
    monkeypatch.setattr(spread, "spread", lambda: 4)
    aero_called = []
    monkeypatch.setattr(spread, "aerospace_running", lambda: aero_called.append(1) or True)
    monkeypatch.setattr(spread.cmux, "run", lambda a: None)
    n = spread.tile()
    assert n == 4
    assert not aero_called                    # never even checks aerospace when disabled
    assert "spread only" in capsys.readouterr().out


def test_config_interactive_uses_input_fn(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    answers = iter(["none", ""])              # set window_manager=none, keep tile_layout
    rc = cli._cmd_config(None, [], input_fn=lambda prompt: next(answers))
    assert rc == 0
    assert settings.load()["window_manager"] == "none"
    assert settings.load()["tile_layout"] == "tiles"


def test_config_show_and_direct_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_SETTINGS", str(tmp_path / "s.toml"))
    assert cli._cmd_config(None, ["window_manager", "none"]) == 0
    cli._cmd_config(None, ["show"])
    assert "window_manager = none" in capsys.readouterr().out
    assert cli._cmd_config(None, ["window_manager", "i3"]) == 1   # invalid
