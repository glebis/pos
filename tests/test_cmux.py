from pos.cmux import CMUX_BIN, open_workspace_argv, sidecar_argv


def test_open_workspace_argv():
    argv = open_workspace_argv(title="business", cwd="/Users/test/Brains/brain")
    assert argv[0] == CMUX_BIN
    assert "new-workspace" in argv
    assert "--command" in argv
    cmd = argv[argv.index("--command") + 1]
    assert "/Users/test/Brains/brain" in cmd


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
