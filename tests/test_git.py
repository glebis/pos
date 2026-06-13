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
