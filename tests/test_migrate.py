from pos.migrate import is_running, ws_title


def test_running_flag():
    assert is_running({"running": True}) is True


def test_running_glyph_in_title():
    assert is_running({"processTitle": "✳ Claude Code"}) is True


def test_status_entry_needs_input():
    assert is_running({"statusEntries": [{"state": "needs_input"}]}) is True


def test_idle_workspace_not_running():
    assert is_running({"title": "user@host:~/ai_projects/cull"}) is False


def test_ws_title_prefers_custom():
    assert ws_title({"customTitle": "cenno app", "title": "x"}) == "cenno app"


from pos.manifest import load_manifest
from pos.migrate import classify, paths_from_title, project_index
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "focus.toml"


def test_paths_from_title_extracts_path():
    assert paths_from_title("user@host:~/ai_projects/cenno") == ["~/ai_projects/cenno"]
    assert paths_from_title("cenno app") == []


def test_project_index_maps_resolved_paths():
    m = load_manifest(FIX)
    idx = project_index(m)
    assert any(p.endswith("/ai_projects/cenno") for p in idx)


def test_classify_single_project(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/test")
    m = load_manifest(FIX)
    r = classify(["~/ai_projects/cenno"], m)
    assert r["kind"] == "project"
    assert r["projects"] == ["cenno"]
    assert r["target_focus"] == "business"


def test_classify_grab_bag(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/test")
    m = load_manifest(FIX)
    r = classify(["~/ai_projects/cenno", "~/ai_projects/generative-sequencer"], m)
    assert r["kind"] == "grab-bag"
    assert set(r["projects"]) == {"cenno", "generative-sequencer"}


def test_classify_unmatched(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/test")
    m = load_manifest(FIX)
    assert classify(["~/random/place"], m)["kind"] == "unmatched"
