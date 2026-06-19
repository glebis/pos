from pathlib import Path

from pos import tui
from pos.manifest import load_manifest

FIX = str(Path(__file__).parent / "fixtures" / "focus.toml")


def _m():
    return load_manifest(Path(FIX))


def test_build_view_groups_projects_with_git_and_live():
    m = _m()
    status_rows = [
        {"focus": "business", "project": "cenno", "branch": "main", "dirty": True, "path": "/x"},
        {"focus": "play", "project": "generative-sequencer", "branch": "dev", "dirty": False, "path": "/y"},
    ]
    workspaces = [{"title": "◆ cenno"}]  # cenno is live (◆ = a focus glyph, stripped)
    view = tui.build_view(m, workspaces, status_rows)

    assert [f.name for f in view.focuses] == ["business", "play"]
    cenno = view.projects["business"][0]
    assert cenno.name == "cenno" and cenno.dirty is True and cenno.live is True
    gs = view.projects["play"][0]
    assert gs.branch == "dev" and gs.dirty is False and gs.live is False
    assert "cenno" in view.live


def test_resolve_action_focus_pane():
    a = tui.resolve_action("focus", "\n", focus="business")
    assert a.cmd == "load" and a.rest == ["business", "--apply"] and a.confirm is True
    assert tui.resolve_action("focus", "c", focus="business").cmd == "cc"
    assert tui.resolve_action("focus", "n", focus="business").prompt == ["name"]
    assert tui.resolve_action("focus", "x", focus="business") is None
    assert tui.resolve_action("focus", "\n", focus=None) is None


def test_resolve_action_project_pane():
    assert tui.resolve_action("project", "\n", project="cenno").cmd == "p"
    rm = tui.resolve_action("project", "r", project="cenno")
    assert rm.cmd == "rm" and rm.rest == ["cenno"] and rm.confirm is True
    cc = tui.resolve_action("project", "c", project="cenno", project_focus="business")
    assert cc.cmd == "cc" and cc.rest == ["business"]
    ld = tui.resolve_action("project", "l", project="cenno")
    assert ld.cmd == "load" and ld.confirm is True


def test_filter_palette():
    items = tui.palette_items()
    assert any(c["name"] == "status" for c in items)
    only = tui.filter_palette(items, "STAT")
    assert only and all("stat" in c["name"].lower() or "stat" in c["synopsis"].lower() for c in only)
    assert tui.filter_palette(items, "") == items
