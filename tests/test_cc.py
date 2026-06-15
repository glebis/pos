from pathlib import Path

from pos import cc
from pos.cmux import CMUX_BIN


def test_encode_project_dir_slashes_to_dashes():
    # Claude names its session dir by replacing every '/' with '-'
    # (a leading '/' therefore yields a leading '-').
    assert cc.encode_project_dir("/Users/glebkalinin/Brains/brain") == "-Users-glebkalinin-Brains-brain"


def test_has_prior_session_true_when_jsonl_present(tmp_path):
    cwd = "/Users/test/proj"
    proj = tmp_path / "projects" / cc.encode_project_dir(cwd)
    proj.mkdir(parents=True)
    (proj / "abc.jsonl").write_text("{}")
    assert cc.has_prior_session(cwd, claude_home=str(tmp_path)) is True


def test_has_prior_session_false_when_empty(tmp_path):
    cwd = "/Users/test/proj"
    (tmp_path / "projects" / cc.encode_project_dir(cwd)).mkdir(parents=True)
    assert cc.has_prior_session(cwd, claude_home=str(tmp_path)) is False


def test_has_prior_session_false_when_missing(tmp_path):
    assert cc.has_prior_session("/nope/nowhere", claude_home=str(tmp_path)) is False


def test_cc_session_name_is_stable_and_prefixed():
    assert cc.cc_session_name("brain") == "cc-brain"
    assert cc.cc_session_name("unknowing.community") == "cc-unknowing-community"


def test_cc_launch_command_is_tmux_backed_and_runs_wrapper():
    cmd = cc.cc_launch_command("brain", "/Users/test/Brains/brain")
    # attach-or-create a stable session, started in cwd, running the resume-aware wrapper
    assert "tmux new-session -A -s cc-brain" in cmd
    assert "/Users/test/Brains/brain" in cmd
    # MUST launch via the wrapper (NOT bare `claude`) so restore resumes the conversation
    assert cmd.rstrip().endswith("pos-cc")
    assert "claude" not in cmd  # bare claude would defeat resume-on-restore


def test_cc_open_argv_uses_new_workspace_command():
    argv = cc.cc_open_argv("brain", "/Users/test/Brains/brain")
    assert argv[0] == CMUX_BIN
    assert "new-workspace" in argv and "--command" in argv
    cmd = argv[argv.index("--command") + 1]
    assert "tmux new-session -A -s cc-brain" in cmd


def test_claude_argv_fresh_when_no_session(tmp_path):
    assert cc.claude_argv("/x/y", claude_home=str(tmp_path)) == ["claude"]


def test_claude_argv_continue_when_session_exists(tmp_path):
    cwd = "/x/y"
    proj = tmp_path / "projects" / cc.encode_project_dir(cwd)
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text("{}")
    assert cc.claude_argv(cwd, claude_home=str(tmp_path)) == ["claude", "--continue"]


def test_claude_argv_passes_through_extra_args(tmp_path):
    argv = cc.claude_argv("/x/y", claude_home=str(tmp_path), extra=["--model", "opus"])
    assert argv == ["claude", "--model", "opus"]


# ── audit fixes: liveness, collision, failure propagation ────────────────
import types


def _fake_run(mapping):
    """Return a `run` stub: maps argv-substring -> SimpleNamespace(returncode,stdout,stderr)."""
    def run(argv):
        key = " ".join(argv)
        for needle, result in mapping.items():
            if needle in key:
                return result
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def _res(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_tmux_session_alive(monkeypatch):
    monkeypatch.setattr(cc, "run", _fake_run({"has-session": _res(rc=0)}))
    assert cc.tmux_session_alive("cc-brain") is True
    monkeypatch.setattr(cc, "run", _fake_run({"has-session": _res(rc=1)}))
    assert cc.tmux_session_alive("cc-brain") is False


def test_cwd_collision_detects_other_cc_session(monkeypatch):
    panes = "cc-health\t/Users/x/Brains/brain\ncc-brain\t/Users/x/Brains/brain\nscratch\t/tmp\n"
    monkeypatch.setattr(cc, "run", _fake_run({"list-panes": _res(out=panes)}))
    # opening cc-brain finds cc-health sharing the cwd
    assert cc.cwd_collision("cc-brain", "/Users/x/Brains/brain") == "cc-health"


def test_cwd_collision_none_when_unique(monkeypatch):
    panes = "cc-brain\t/Users/x/Brains/brain\nscratch\t/tmp\n"
    monkeypatch.setattr(cc, "run", _fake_run({"list-panes": _res(out=panes)}))
    assert cc.cwd_collision("cc-brain", "/Users/x/Brains/brain") is None


def test_open_cc_returns_none_when_new_workspace_fails(monkeypatch):
    monkeypatch.setattr(cc, "live_workspaces", lambda: [])
    monkeypatch.setattr(cc, "find_workspace_ref", lambda ws, label: None)
    monkeypatch.setattr(cc, "run", _fake_run({
        "list-panes": _res(out=""),
        "new-workspace": _res(rc=1, err="socket unreachable"),
    }))
    assert cc.open_cc("brain", "/tmp/x", "∴") is None


def test_open_cc_recreates_stale_husk(monkeypatch):
    # cmux workspace exists but its tmux session is DEAD -> close + recreate
    monkeypatch.setattr(cc, "live_workspaces", lambda: [{"ref": "workspace:9", "title": "∴ cc-brain"}])
    monkeypatch.setattr(cc, "find_workspace_ref", lambda ws, label: "workspace:9")
    seen = []

    def run(argv):
        seen.append(" ".join(argv))
        key = " ".join(argv)
        if "has-session" in key:
            return _res(rc=1)            # tmux session dead
        if "new-workspace" in key:
            return _res(out="OK new-ref-uuid")
        if "list-panes" in key:
            return _res(out="")
        return _res()

    monkeypatch.setattr(cc, "run", run)
    ref = cc.open_cc("brain", "/tmp/x", "∴")
    assert ref == "new-ref-uuid"
    assert any("close-workspace" in c for c in seen)   # husk closed
    assert any("new-workspace" in c for c in seen)     # fresh created
