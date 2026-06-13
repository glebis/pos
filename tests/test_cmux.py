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
