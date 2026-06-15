import types
from pos import projects as P


def _res(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_create_delegates_to_open_and_label(monkeypatch):
    seen = {}
    monkeypatch.setattr(P.cmux, "open_and_label", lambda cwd, label: seen.update(cwd=cwd, label=label) or "workspace:9")
    assert P.create("brain", "/x/y", glyph="∴") == "workspace:9"
    assert seen["label"] == "∴ brain" and seen["cwd"] == "/x/y"


def test_rename_finds_and_renames(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [{"ref": "workspace:3", "title": "◆ cenno"}])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: "workspace:3" if label == "cenno" else None)
    calls = []
    monkeypatch.setattr(P.cmux, "run", lambda a: (calls.append(a), _res())[1])
    assert P.rename("cenno", "cenno-2") == "workspace:3"
    assert any("rename-workspace" in a and "cenno-2" in a for a in calls)
    assert any("rename-tab" in a and "cenno-2" in a for a in calls)


def test_rename_missing_returns_none(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: None)
    assert P.rename("nope", "x") is None


def test_backing_session_reads_selected_surface(monkeypatch):
    monkeypatch.setattr(P.tmuxify, "_surfaces",
                        lambda ref: [{"ref": "s", "title": "tmux attach -t brain", "selected": True}])
    assert P.backing_session("workspace:43") == "brain"


def test_remove_refuses_unbacked_without_force(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [{"ref": "workspace:5", "title": "business"}])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: "workspace:5")
    monkeypatch.setattr(P, "is_backed", lambda ref: False)   # no live backing session
    monkeypatch.setattr(P.cmux, "run", lambda a: _res())
    ref, status = P.remove("business", force=False)
    assert status == "unbacked"          # not forced -> refused


def test_remove_closes_backed(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [{"ref": "workspace:43", "title": "brain"}])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: "workspace:43")
    monkeypatch.setattr(P, "is_backed", lambda ref: True)
    calls = []
    monkeypatch.setattr(P.cmux, "run", lambda a: (calls.append(a), _res())[1])
    ref, status = P.remove("brain", force=False)
    assert status == "closed"
    assert any("close-workspace" in a and "workspace:43" in a for a in calls)


def test_remove_force_closes_unbacked(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [{"ref": "workspace:5", "title": "business"}])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: "workspace:5")
    monkeypatch.setattr(P, "is_backed", lambda ref: False)
    calls = []
    monkeypatch.setattr(P.cmux, "run", lambda a: (calls.append(a), _res())[1])
    ref, status = P.remove("business", force=True)
    assert status == "closed"
    assert any("close-workspace" in a for a in calls)


def test_remove_not_found(monkeypatch):
    monkeypatch.setattr(P.cmux, "live_workspaces", lambda: [])
    monkeypatch.setattr(P.cmux, "find_workspace_ref", lambda ws, label: None)
    assert P.remove("ghost")[1] == "not-found"
