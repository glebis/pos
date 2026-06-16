import json
from pathlib import Path

from pos import cli

FIX = str(Path(__file__).parent / "fixtures" / "focus.toml")


def test_status_json(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.status.git_state", lambda p: {"branch": "main", "dirty": False})
    rc = cli.main(["status", "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 0
    assert any(r["project"] == "cenno" for r in data)


def test_bare_lists_focuses(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main([])
    out = capsys.readouterr().out
    assert "business" in out and "play" in out
    assert rc == 0


def test_status_is_json_when_piped_without_a_flag(capsys, monkeypatch):
    # No --json, but capsys is not a TTY → agent-facing JSON by default.
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.status.git_state", lambda p: {"branch": "main", "dirty": False})
    rc = cli.main(["status"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0 and any(r["project"] == "cenno" for r in data)


def test_status_human_flag_overrides_pipe(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.status.git_state", lambda p: {"branch": "main", "dirty": False})
    rc = cli.main(["status", "--human"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "·" in out  # human row separator, not JSON


def test_bare_is_json_when_piped(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main([])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    names = {f["name"] for f in data}
    assert {"business", "play"} <= names


def test_help_json_returns_command_table(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["help", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0 and any(c["name"] == "status" for c in data)


def test_help_agents_prints_guide(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["help", "agents"])
    out = capsys.readouterr().out
    assert rc == 0 and "MENTAL MODEL" in out


def test_p_lists_projects_grouped(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["p"])
    out = capsys.readouterr().out
    assert "cenno" in out and "generative-sequencer" in out
    assert rc == 0


def _fake_sidecar(monkeypatch, existing):
    """Wire cmux so _cmd_sidecar runs offline; return the recorded run() argvs.
    The create call reports a fresh surface ref via stdout, as real cmux does."""
    import subprocess

    from pos import cmux

    monkeypatch.setattr(cmux, "current_workspace_ref", lambda: "workspace:1")
    monkeypatch.setattr(cmux, "workspace_surfaces", lambda ws: existing)
    recorded = []

    def fake_run(argv):
        recorded.append(argv)
        stdout = "OK surface:99 pane:1 workspace:1" if ("new-pane" in argv or "new-surface" in argv) else ""
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(cmux, "run", fake_run)
    return recorded


def test_sidecar_names_new_tab_after_folder(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("POS_MANIFEST", FIX)
    folder = Path.cwd().name
    recorded = _fake_sidecar(monkeypatch, [{"ref": "surface:1", "title": "shell"}])
    rc = cli.main(["sidecar"])
    assert rc == 0
    rename = [a for a in recorded if "rename-tab" in a]
    assert rename, "expected a rename-tab call"
    assert rename[-1][-1] == folder
    assert "surface:99" in rename[-1]  # renamed the surface cmux reported


def test_sidecar_numbers_a_colliding_folder_name(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("POS_MANIFEST", FIX)
    folder = Path.cwd().name
    recorded = _fake_sidecar(monkeypatch, [{"ref": "surface:1", "title": folder}])
    rc = cli.main(["sidecar"])
    assert rc == 0
    rename = [a for a in recorded if "rename-tab" in a]
    assert rename[-1][-1] == f"{folder} 2"


def test_sidecar_explicit_name_overrides_folder(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    recorded = _fake_sidecar(monkeypatch, [{"ref": "surface:1", "title": "shell"}])
    rc = cli.main(["sidecar", "logs"])
    assert rc == 0
    rename = [a for a in recorded if "rename-tab" in a]
    assert rename[-1][-1] == "logs"


def test_sidecar_browser_targets_workspace(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    recorded = _fake_sidecar(monkeypatch, [])
    rc = cli.main(["sidecar", "https://example.com"])
    assert rc == 0
    create = next(a for a in recorded if "new-surface" in a)
    assert "https://example.com" in create
    assert create[create.index("--workspace") + 1] == "workspace:1"


def test_sidecar_no_workspace_returns_1(monkeypatch, capsys):
    from pos import cmux

    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr(cmux, "current_workspace_ref", lambda: None)
    rc = cli.main(["sidecar"])
    assert rc == 1
    assert "no current workspace" in capsys.readouterr().err


def test_unknown_command_returns_1(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["frobnicate"])
    assert rc == 1


def test_yard_run_valid(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    calls = []
    monkeypatch.setattr("pos.yard.run", lambda name, command: calls.append((name, command)))
    rc = cli.main(["yard", "run", "crawl", "--", "firecrawl", "go"])
    assert rc == 0
    assert calls == [("crawl", "firecrawl go")]


def test_yard_run_missing_name_before_dashdash(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.yard.run", lambda *a: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = cli.main(["yard", "run", "--", "ls"])
    assert rc == 1


def test_yard_run_empty_command_after_dashdash(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.yard.run", lambda *a: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = cli.main(["yard", "run", "task", "--"])
    assert rc == 1


def test_day_dry_run(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.day.read_daily", lambda d: "work on cenno today")
    rc = cli.main(["day", "--date", "20260613", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hybrid pin plan" in out
    assert "cenno" in out
    assert "dry-run" in out


def _stub_protection(monkeypatch):
    """Neutralize the live-protection shell-outs so load tests stay hermetic."""
    monkeypatch.setattr("pos.cmux.live_busy_sessions", lambda: set())
    monkeypatch.setattr("pos.cmux.current_workspace_refs", lambda: set())
    monkeypatch.setattr("pos.cmux.current_tmux_session", lambda: None)


def test_load_dry_run_preset(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    _stub_protection(monkeypatch)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◆ cenno", "pinned": True},
        {"ref": "w2", "title": "◆ devops", "pinned": False},
    ])
    rc = cli.main(["load", "revenue-sprint"])  # members: business, cenno
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    assert "business" in out and "cenno" in out
    assert "devops" in out  # devops should be listed to close


def test_load_unknown_member_errors(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["load", "nonexistent-thing"])
    assert rc == 1


def test_load_bare_lists_presets(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["load"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "revenue-sprint" in out


def test_load_force_ignores_running_overlay(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    _stub_protection(monkeypatch)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◇ Voice", "pinned": False},
        {"ref": "w2", "title": "◆ cenno", "pinned": False},
    ])
    # session JSON would mark Voice running, but --force skips that overlay
    monkeypatch.setattr("pos.cli._running_titles", lambda: {"Voice"})
    # without force: Voice protected (skip running)
    cli.main(["load", "cenno"])
    out_noforce = capsys.readouterr().out
    assert "Voice" in out_noforce and "skip (running)" in out_noforce
    # with force: Voice is closeable
    cli.main(["load", "cenno", "--force"])
    out_force = capsys.readouterr().out
    assert "skip (running)" not in out_force
    assert "Voice" in out_force  # now in close list


def test_load_focus_expands_to_projects(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    _stub_protection(monkeypatch)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [])
    # business focus -> its projects (cenno), NOT the bare focus name
    rc = cli.main(["load", "business"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "cenno" in out
    # focus should have been expanded away (members line is projects, not "business")
    assert "open+pin: cenno" in out


def test_bare_focus_verb_routes_to_load(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    _stub_protection(monkeypatch)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [])
    # `pos business` should behave like `pos load business` (dry-run plan)
    rc = cli.main(["business"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    assert "cenno" in out


def test_load_never_closes_launching_tab(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cmux.live_busy_sessions", lambda: set())
    monkeypatch.setattr("pos.cli._running_titles", lambda: set())
    # the operation is launched from the 'devops' tab (focused per identify)
    monkeypatch.setattr("pos.cmux.current_workspace_refs", lambda: {"w2"})
    monkeypatch.setattr("pos.cmux.current_tmux_session", lambda: None)
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◆ cenno", "pinned": False},
        {"ref": "w2", "title": "◆ devops", "pinned": False},  # launching tab
    ])
    cli.main(["load", "cenno"])
    out = capsys.readouterr().out
    # devops is not wanted and idle, but it's the launching tab -> never closed
    assert "skip (running): ◆ devops" in out or "devops" not in out.split("close:")[1].split("\n")[0]


def test_load_guards_current_tmux_session(capsys, monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cmux.live_busy_sessions", lambda: set())
    monkeypatch.setattr("pos.cli._running_titles", lambda: set())
    monkeypatch.setattr("pos.cmux.current_workspace_refs", lambda: set())
    # pos is running inside the 'Exploration' tmux session
    monkeypatch.setattr("pos.cmux.current_tmux_session", lambda: "Exploration")
    monkeypatch.setattr("pos.cmux.live_workspaces", lambda: [
        {"ref": "w1", "title": "◆ cenno", "pinned": False},
        {"ref": "w2", "title": "tmux attach-session -t Exploration", "pinned": False},
    ])
    cli.main(["load", "cenno"])
    out = capsys.readouterr().out
    close_line = [l for l in out.splitlines() if l.startswith("  close:")][0]
    assert "Exploration" not in close_line  # current session tab guarded


def test_cc_opens_focus_workspace(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    calls = []

    def fake_open(focus, cwd, glyph):
        calls.append((focus, cwd, glyph))
        return "workspace:7"

    monkeypatch.setattr("pos.cc.open_cc", fake_open)
    rc = cli.main(["cc", "business"])
    assert rc == 0
    assert len(calls) == 1 and calls[0][0] == "business"


def test_cc_returns_1_when_open_fails(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    monkeypatch.setattr("pos.cc.open_cc", lambda focus, cwd, glyph: None)
    assert cli.main(["cc", "business"]) == 1


def test_cc_unknown_focus_returns_1(monkeypatch, capsys):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["cc", "frobnicate"])
    assert rc == 1
    assert "unknown focus" in capsys.readouterr().err


def test_cc_no_arg_returns_1(monkeypatch):
    monkeypatch.setenv("POS_MANIFEST", FIX)
    rc = cli.main(["cc"])
    assert rc == 1
