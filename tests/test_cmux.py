from pos.cmux import CMUX_BIN, open_workspace_argv, sidecar_argv


def test_open_workspace_argv_is_tmux_backed():
    argv = open_workspace_argv(title="business", cwd="/Users/test/Brains/brain")
    assert argv[0] == CMUX_BIN
    assert "new-workspace" in argv
    assert "--command" in argv
    cmd = argv[argv.index("--command") + 1]
    # durable: attach-or-create a named tmux session, started in cwd
    assert "tmux new-session -A -s" in cmd
    assert "business" in cmd
    assert "/Users/test/Brains/brain" in cmd


def test_session_name_sanitizes():
    from pos.cmux import session_name
    assert session_name("◆ business") == "business"
    assert session_name("unknowing.community") == "unknowing-community"
    assert session_name("CC Lab 04") == "CC-Lab-04"
    assert session_name("cenno") == "cenno"


def test_sidecar_browser_argv():
    argv = sidecar_argv(url="https://localhost:3000")
    assert "new-surface" in argv
    assert "--type" in argv and "browser" in argv
    assert "https://localhost:3000" in argv


def test_sidecar_terminal_argv():
    argv = sidecar_argv(url=None)
    assert "new-pane" in argv
    assert "--type" in argv and "terminal" in argv


from pos.cmux import parse_new_workspace_ref, rename_workspace_argv


def test_parse_new_workspace_ref():
    assert parse_new_workspace_ref("OK 8E8D4F0C-9434-4930-B873-8321197934BE") == "8E8D4F0C-9434-4930-B873-8321197934BE"
    assert parse_new_workspace_ref("  OK abc \n") == "abc"
    assert parse_new_workspace_ref("") is None
    assert parse_new_workspace_ref("ERROR nope") is None


def test_rename_argv_with_ref_targets_workspace():
    argv = rename_workspace_argv("◆ business", ref="uuid-1")
    assert "--workspace" in argv and "uuid-1" in argv
    assert argv[-1] == "◆ business"


def test_rename_argv_without_ref_omits_flag():
    argv = rename_workspace_argv("x")
    assert "--workspace" not in argv


from pos.cmux import find_workspace_ref, reconcile_plan, is_running_ws

WS = [
    {"ref": "w1", "title": "◆ cenno", "pinned": True},
    {"ref": "w2", "title": "◇ Voice", "pinned": False, "processTitle": "✳ Claude Code"},
    {"ref": "w3", "title": "scratch", "pinned": False},
    {"ref": "w4", "title": "◆ devops", "pinned": False},
    {"ref": "w5", "title": "+ genome-toolkit", "pinned": False},
]


def test_find_workspace_ref_matches_glyph_stripped():
    assert find_workspace_ref(WS, "cenno") == "w1"
    assert find_workspace_ref(WS, "genome-toolkit") == "w5"
    assert find_workspace_ref(WS, "nonexistent") is None


def test_is_running_ws_detects_glyph():
    assert is_running_ws(WS[1]) is True   # ✳ Voice
    assert is_running_ws(WS[0]) is False


def test_reconcile_plan_converges():
    # want only cenno + genome-toolkit
    plan = reconcile_plan(WS, wanted={"cenno", "genome-toolkit"}, protect={"scratch"})
    assert set(plan["keep"]) == {"w1", "w5"}          # wanted + present
    # devops is not wanted, not running, not protected -> close
    assert "w4" in plan["close"]
    # Voice is running -> never close (protected)
    assert "w2" not in plan["close"]
    assert "w2" in plan["skip_running"]
    # scratch protected -> not closed
    assert "w3" not in plan["close"]
    # cenno already present and wanted -> not in 'open'
    assert "cenno" not in plan["open"]


def test_reconcile_plan_opens_missing():
    plan = reconcile_plan(WS, wanted={"cenno", "claude-code-lab"}, protect=set())
    assert "claude-code-lab" in plan["open"]   # not present -> open
    assert "cenno" not in plan["open"]


from pos.cmux import mark_running


def test_mark_running_overlays_session_state():
    ws = [
        {"ref": "w1", "title": "◇ Voice", "pinned": False},   # socket: no running info
        {"ref": "w2", "title": "◆ cenno", "pinned": False},
    ]
    marked = mark_running(ws, running_titles={"Voice"})
    assert marked[0]["running"] is True
    assert marked[1].get("running") is not True
    # and reconcile now protects it from closing
    plan = reconcile_plan(marked, wanted={"cenno"}, protect=set())
    assert "w1" in plan["skip_running"]
    assert "w1" not in plan["close"]


from pos.cmux import (
    tmux_session_for_title,
    busy_sessions_from_panes,
    mark_running_tmux,
    mark_running_refs,
)


def test_tmux_session_for_title_parses_attach_command():
    assert tmux_session_for_title("tmux attach-session -t Exploration") == "Exploration"
    assert tmux_session_for_title("tmux attach -t 6") == "6"
    assert tmux_session_for_title("tmux new-session -A -s brain -c /x") == "brain"


def test_tmux_session_for_title_maps_glyphed_label():
    assert tmux_session_for_title("∴ brain") == "brain"
    assert tmux_session_for_title("◆ unknowing.community") == "unknowing-community"
    assert tmux_session_for_title("scratch") == "scratch"


def test_busy_sessions_from_panes_flags_nonshell():
    lines = [
        "Exploration 2.1.177",   # claude/node-ish -> busy
        "brain zsh",             # idle shell
        "play zsh",
        "scratch zsh",
        "0 vim",                 # busy
        "  ",                    # blank -> ignored
        "weird",                 # no cmd -> ignored
    ]
    assert busy_sessions_from_panes(lines) == {"Exploration", "0"}


def test_mark_running_tmux_overlays_busy_sessions():
    ws = [
        {"ref": "w1", "title": "tmux attach-session -t Exploration"},
        {"ref": "w2", "title": "◆ cenno"},
        {"ref": "w3", "title": "∴ brain"},
    ]
    marked = mark_running_tmux(ws, busy_sessions={"Exploration", "brain"})
    by_ref = {w["ref"]: w for w in marked}
    assert by_ref["w1"]["running"] is True
    assert by_ref["w2"].get("running") is not True
    assert by_ref["w3"]["running"] is True


def test_mark_running_refs_overlays_given_refs():
    ws = [{"ref": "w1", "title": "a"}, {"ref": "w2", "title": "b"}]
    marked = mark_running_refs(ws, refs={"w2"})
    by_ref = {w["ref"]: w for w in marked}
    assert by_ref["w2"]["running"] is True
    assert by_ref["w1"].get("running") is not True


from pos import cmux as _cmux
from pos.cmux import rename_tab_argv


def test_rename_tab_argv_targets_workspace():
    argv = rename_tab_argv("cenno", ref="w9")
    assert "rename-tab" in argv
    assert "--workspace" in argv and "w9" in argv
    assert argv[-1] == "cenno"


def test_open_and_label_names_both_workspace_and_tab(monkeypatch):
    calls = []
    monkeypatch.setattr(_cmux, "live_workspaces", lambda: [])  # nothing existing
    monkeypatch.setattr(_cmux, "run", lambda argv: calls.append(argv) or _Res("OK new-uuid"))
    ref = _cmux.open_and_label(cwd="/x", label="cenno")
    assert ref == "new-uuid"
    flat = [" ".join(c) for c in calls]
    assert any("rename-workspace" in c and "new-uuid" in c and c.endswith("cenno") for c in flat)
    assert any("rename-tab" in c and "new-uuid" in c and c.endswith("cenno") for c in flat)


class _Res:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0
