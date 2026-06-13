from pos.migrate import is_running, ws_title


def test_running_flag():
    assert is_running({"running": True}) is True


def test_running_glyph_in_title():
    assert is_running({"processTitle": "✳ Claude Code"}) is True


def test_status_entry_needs_input():
    assert is_running({"statusEntries": [{"state": "needs_input"}]}) is True


def test_idle_workspace_not_running():
    assert is_running({"title": "glebkalinin@Mac:~/ai_projects/cull"}) is False


def test_ws_title_prefers_custom():
    assert ws_title({"customTitle": "cenno app", "title": "x"}) == "cenno app"
