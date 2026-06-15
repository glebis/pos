import types
from pos import cmux, spread


def _res(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_parse_windows():
    text = (
        "* 0: WIN-A selected_workspace=WS-1 workspaces=11\n"
        "  1: WIN-B selected_workspace=WS-2 workspaces=1\n"
    )
    ws = cmux.parse_windows(text)
    assert len(ws) == 2
    assert ws[0] == {"id": "WIN-A", "selected_workspace": "WS-1", "count": 11, "selected": True}
    assert ws[1]["id"] == "WIN-B" and ws[1]["selected"] is False


def test_spread_gives_each_nonselected_its_own_window(monkeypatch):
    monkeypatch.setattr(spread.cmux, "current_window_id", lambda: "home")
    monkeypatch.setattr(spread.cmux, "window_workspaces", lambda: {"window_id": "home", "workspaces": [
        {"ref": "ws:1", "title": "◆ cenno", "selected": True},
        {"ref": "ws:2", "title": "brain", "selected": False},
        {"ref": "ws:3", "title": "health", "selected": False},
    ]})
    monkeypatch.setattr(spread.cmux, "list_windows", lambda: [
        {"id": "home", "selected_workspace": "ws:1", "count": 3, "selected": True},
        {"id": "NEWWIN", "selected_workspace": "DEFAULT", "count": 1, "selected": False},
    ])
    calls = []

    def run(argv):
        calls.append(argv)
        if "new-window" in argv:
            return _res(out="OK NEWWIN")
        return _res()

    monkeypatch.setattr(spread.cmux, "run", run)
    n = spread.spread()
    assert n == 2                                        # cenno (selected) stays home
    assert sum("new-window" in a for a in calls) == 2     # one window per target
    moves = [a for a in calls if "move-workspace-to-window" in a]
    assert {a[a.index("--workspace") + 1] for a in moves} == {"ws:2", "ws:3"}
    assert any("close-workspace" in a and "DEFAULT" in a for a in calls)  # default disposed


def test_spread_noop_single_workspace(monkeypatch, capsys):
    monkeypatch.setattr(spread.cmux, "current_window_id", lambda: "home")
    monkeypatch.setattr(spread.cmux, "window_workspaces", lambda: {"window_id": "home",
        "workspaces": [{"ref": "ws:1", "selected": True}]})
    monkeypatch.setattr(spread.cmux, "run", lambda a: _res())
    assert spread.spread() == 0
    assert "nothing to fan out" in capsys.readouterr().out


def test_gather_merges_other_windows(monkeypatch):
    monkeypatch.setattr(spread.cmux, "current_window_id", lambda: "home")
    monkeypatch.setattr(spread.cmux, "list_windows", lambda: [
        {"id": "home", "selected_workspace": "ws:1", "count": 1, "selected": True},
        {"id": "W2", "selected_workspace": "ws:2", "count": 1, "selected": False},
        {"id": "W3", "selected_workspace": "ws:3", "count": 1, "selected": False},
    ])
    # each focused other window reports its single workspace
    seq = iter([
        {"window_id": "W2", "workspaces": [{"ref": "ws:2", "selected": True}]},
        {"window_id": "W3", "workspaces": [{"ref": "ws:3", "selected": True}]},
    ])
    monkeypatch.setattr(spread.cmux, "window_workspaces", lambda: next(seq))
    monkeypatch.setattr(spread.cmux, "reorder_pinned_first", lambda: 0)  # covered separately
    calls = []
    monkeypatch.setattr(spread.cmux, "run", lambda a: (calls.append(a), _res())[1])
    n = spread.gather()
    assert n == 2
    moves = [a for a in calls if "move-workspace-to-window" in a]
    assert all("home" in a for a in moves)
    assert sum("close-window" in a for a in calls) == 2   # both other windows closed


def test_gather_noop_single_window(monkeypatch, capsys):
    monkeypatch.setattr(spread.cmux, "current_window_id", lambda: "home")
    monkeypatch.setattr(spread.cmux, "list_windows", lambda: [
        {"id": "home", "selected_workspace": "ws:1", "count": 5, "selected": True}])
    monkeypatch.setattr(spread.cmux, "run", lambda a: _res())
    assert spread.gather() == 0
    assert "already a single window" in capsys.readouterr().out


def test_pinned_first_order_groups_pinned_then_rest_stable():
    ws = [
        {"ref": "a", "pinned": False},
        {"ref": "b", "pinned": True},
        {"ref": "c", "pinned": False},
        {"ref": "d", "pinned": True},
    ]
    assert cmux.pinned_first_order(ws) == ["b", "d", "a", "c"]


def test_reorder_pinned_first_noop_when_already_ordered(monkeypatch):
    monkeypatch.setattr(cmux, "window_workspaces", lambda: {"workspaces": [
        {"ref": "b", "pinned": True}, {"ref": "a", "pinned": False}]})
    calls = []
    monkeypatch.setattr(cmux, "run", lambda a: calls.append(a))
    assert cmux.reorder_pinned_first() == 0
    assert not any("reorder-workspace" in a for a in calls)


def test_reorder_pinned_first_moves_when_unordered(monkeypatch):
    monkeypatch.setattr(cmux, "window_workspaces", lambda: {"workspaces": [
        {"ref": "a", "pinned": False}, {"ref": "b", "pinned": True}]})
    calls = []
    monkeypatch.setattr(cmux, "run", lambda a: calls.append(a))
    n = cmux.reorder_pinned_first()
    assert n == 2
    reorders = [a for a in calls if "reorder-workspace" in a]
    # pinned 'b' goes to index 0, 'a' to index 1
    assert reorders[0][reorders[0].index("--workspace") + 1] == "b"
    assert reorders[0][-1] == "0"


def test_tile_spreads_then_calls_aerospace(monkeypatch):
    monkeypatch.setattr(spread, "spread", lambda: 10)
    monkeypatch.setattr(spread, "aerospace_running", lambda: True)
    monkeypatch.setattr(spread.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(spread.cmux, "run", lambda a: calls.append(a))
    assert spread.tile() == 10
    assert any(a[:2] == [spread.AEROSPACE, "flatten-workspace-tree"] for a in calls)
    assert any(a[:2] == [spread.AEROSPACE, "layout"] and "tiles" in a for a in calls)


def test_tile_falls_back_without_aerospace(monkeypatch, capsys):
    monkeypatch.setattr(spread, "spread", lambda: 3)
    monkeypatch.setattr(spread, "aerospace_running", lambda: False)
    calls = []
    monkeypatch.setattr(spread.cmux, "run", lambda a: calls.append(a))
    assert spread.tile() == 3
    assert not any("layout" in a for a in calls)        # no tiling attempted
    assert "not running" in capsys.readouterr().out
