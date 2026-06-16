from pathlib import Path

from pos.manifest import load_manifest
from pos.status import build_status

FIX = Path(__file__).parent / "fixtures" / "focus.toml"


def fake_git(path):
    return {"branch": "main", "dirty": "cenno" in str(path)}


def test_build_status_groups_and_orders():
    m = load_manifest(FIX)
    rows = build_status(m, git_fn=fake_git)
    focuses = [r["focus"] for r in rows]
    assert focuses.index("business") < focuses.index("play")
    cenno = next(r for r in rows if r["project"] == "cenno")
    assert cenno["branch"] == "main"
    assert cenno["dirty"] is True


def test_build_status_runs_git_concurrently():
    # A barrier that only releases once every project's git_fn is in flight:
    # a serial implementation blocks on the first call forever and times out
    # (BrokenBarrierError), so this fails RED until the loop fans out.
    import threading

    m = load_manifest(FIX)
    n = len(m.projects)
    barrier = threading.Barrier(n, timeout=5)

    def git_fn(path):
        barrier.wait()
        return {"branch": "main", "dirty": False}

    rows = build_status(m, git_fn=git_fn)
    assert len(rows) == n


def test_build_status_maps_each_result_to_its_own_project():
    # Guards parallelization against cross-wiring: each row must carry the git
    # result for ITS path, not another project's.
    m = load_manifest(FIX)
    rows = build_status(m, git_fn=lambda path: {"branch": str(path), "dirty": False})
    assert all(r["branch"] == r["path"] for r in rows)


def test_build_status_default_git_fn_is_patchable(monkeypatch):
    # monkeypatching the module-level git_state must take effect when no
    # git_fn is injected (guards against def-time default binding).
    m = load_manifest(FIX)
    monkeypatch.setattr("pos.status.git_state", lambda p: {"branch": "PATCHED", "dirty": False})
    rows = build_status(m)
    assert all(r["branch"] == "PATCHED" for r in rows)
