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
