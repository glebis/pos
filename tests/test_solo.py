import json
import types

from pos import solo


def _res(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


WS = [
    {"id": "uuid-business", "ref": "workspace:29", "title": "◆ business", "selected": False},
    {"id": "uuid-cenno", "ref": "workspace:3", "title": "◆ cenno", "selected": True},
    {"id": "uuid-life", "ref": "workspace:47", "title": "life", "selected": False},
]


def test_park_targets_excludes_selected():
    assert solo.park_targets(WS) == ["uuid-business", "uuid-life"]


def test_park_targets_excludes_explicit_keep():
    # when a workspace is named, keep THAT one (not the selected one)
    assert solo.park_targets(WS, keep_id="uuid-life") == ["uuid-business", "uuid-cenno"]


def test_selected_id():
    assert solo.selected_id(WS) == "uuid-cenno"
    assert solo.selected_id([{"id": "x", "selected": False}]) is None


def test_find_by_name_matches_glyph_stripped_title():
    assert solo.find_by_name(WS, "business")["id"] == "uuid-business"
    assert solo.find_by_name(WS, "life")["id"] == "uuid-life"
    assert solo.find_by_name(WS, "nope") is None


def test_engage_by_name_keeps_named_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_STATE", str(tmp_path / "solo.json"))
    monkeypatch.setattr(solo.cmux, "window_workspaces", lambda: {"window_id": "win-home", "workspaces": WS})
    calls = []

    def run(argv):
        calls.append(argv)
        if "new-window" in argv:
            return _res(out="OK win-parked")
        return _res()

    monkeypatch.setattr(solo.cmux, "run", run)
    rc = solo.engage("life")
    assert rc == 0
    state = json.loads((tmp_path / "solo.json").read_text())
    # keep "life"; park business + the currently-selected cenno
    assert state["parked"] == ["uuid-business", "uuid-cenno"]
    moves = [a for a in calls if "move-workspace-to-window" in a]
    assert all("uuid-life" not in a for a in moves)
    assert any("select-workspace" in a and "uuid-life" in a for a in calls)


def test_engage_by_name_unknown_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_STATE", str(tmp_path / "solo.json"))
    monkeypatch.setattr(solo.cmux, "window_workspaces", lambda: {"window_id": "win-home", "workspaces": WS})
    monkeypatch.setattr(solo.cmux, "run", lambda argv: _res())
    assert solo.engage("ghost") == 1
    assert not (tmp_path / "solo.json").exists()
    out = capsys.readouterr().out
    assert "ghost" in out and "business" in out  # lists available names


def test_engage_parks_others_and_writes_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_STATE", str(tmp_path / "solo.json"))
    monkeypatch.setattr(solo.cmux, "window_workspaces", lambda: {"window_id": "win-home", "workspaces": WS})
    calls = []

    def run(argv):
        calls.append(argv)
        if "new-window" in argv:
            return _res(out="OK win-parked")
        return _res()

    monkeypatch.setattr(solo.cmux, "run", run)
    rc = solo.engage()
    assert rc == 0
    state = json.loads((tmp_path / "solo.json").read_text())
    assert state["home_window"] == "win-home"
    assert state["parked_window"] == "win-parked"
    assert state["parked"] == ["uuid-business", "uuid-life"]
    # the selected workspace must NOT be parked, and we re-select it
    moves = [a for a in calls if "move-workspace-to-window" in a]
    assert all("uuid-cenno" not in a for a in moves)
    assert any("select-workspace" in a and "uuid-cenno" in a for a in calls)
    # never rename-window (it corrupts a workspace title); always refresh surfaces
    assert not any("rename-window" in a for a in calls)
    assert any("refresh-surfaces" in a for a in calls)
    assert "hid 2" in capsys.readouterr().out


def test_engage_noop_when_only_one_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POS_STATE", str(tmp_path / "solo.json"))
    only = [{"id": "uuid-cenno", "title": "◆ cenno", "selected": True}]
    monkeypatch.setattr(solo.cmux, "window_workspaces", lambda: {"window_id": "win-home", "workspaces": only})
    monkeypatch.setattr(solo.cmux, "run", lambda argv: _res())
    assert solo.engage() == 0
    assert not (tmp_path / "solo.json").exists()
    assert "nothing to hide" in capsys.readouterr().out


def test_restore_moves_back_and_clears_state(tmp_path, monkeypatch, capsys):
    sp = tmp_path / "solo.json"
    sp.write_text(json.dumps({"home_window": "win-home", "parked_window": "win-parked",
                              "parked": ["uuid-business", "uuid-life"]}))
    monkeypatch.setenv("POS_STATE", str(sp))
    calls = []
    monkeypatch.setattr(solo.cmux, "run", lambda argv: (calls.append(argv), _res())[1])
    rc = solo.restore()
    assert rc == 0
    assert not sp.exists()
    moves = [a for a in calls if "move-workspace-to-window" in a]
    assert len(moves) == 2 and all("win-home" in a for a in moves)
    assert any("close-window" in a and "win-parked" in a for a in calls)
    assert any("refresh-surfaces" in a for a in calls)
    assert "restored 2" in capsys.readouterr().out


def test_toggle_dispatches_on_state(tmp_path, monkeypatch):
    sp = tmp_path / "solo.json"
    monkeypatch.setenv("POS_STATE", str(sp))
    monkeypatch.setattr(solo, "engage", lambda name=None: 11)
    monkeypatch.setattr(solo, "restore", lambda: 22)
    assert solo.toggle() == 11          # no state -> engage
    sp.write_text("{}")
    assert solo.toggle() == 22          # state -> restore
