from pathlib import Path

from pos.paths import resolve_path


def test_absolute_path_unchanged():
    assert resolve_path("/tmp/x", base="/base") == Path("/tmp/x")


def test_tilde_expands(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/test")
    assert resolve_path("~/proj", base="/base") == Path("/Users/test/proj")


def test_relative_joins_base():
    assert resolve_path("cenno", base="/Users/test/ai_projects") == Path(
        "/Users/test/ai_projects/cenno"
    )
