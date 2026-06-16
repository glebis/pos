import subprocess
from pathlib import Path

from pos.git import git_state


def _init(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def test_clean_repo(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True)
    st = git_state(tmp_path)
    assert st["branch"] == "main"
    assert st["dirty"] is False


def test_dirty_repo(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.txt").write_text("x")  # untracked => dirty
    st = git_state(tmp_path)
    assert st["dirty"] is True


def test_non_repo(tmp_path):
    assert git_state(tmp_path) == {"branch": None, "dirty": False}


def test_unborn_branch_reports_name_and_dirtiness(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.txt").write_text("x")  # untracked on an unborn branch
    st = git_state(tmp_path)
    assert st["branch"] == "main"
    assert st["dirty"] is True


def test_detached_head_has_no_branch(tmp_path):
    _init(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "--detach"], cwd=tmp_path, check=True, capture_output=True)
    st = git_state(tmp_path)
    assert st["branch"] is None
    assert st["dirty"] is False


def test_git_state_issues_a_single_subprocess(tmp_path, monkeypatch):
    _init(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True)
    import pos.git as g

    real_run = g.subprocess.run
    calls = []

    def counting(*args, **kwargs):
        calls.append(args)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(g.subprocess, "run", counting)
    git_state(tmp_path)
    assert len(calls) == 1
