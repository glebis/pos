from pathlib import Path

from pos.day import active_projects_from_text, build_pin_plan
from pos.manifest import load_manifest

FIX = Path(__file__).parent / "fixtures" / "focus.toml"

DAILY = """\
## do
- [ ] ship the cenno release notes
- [ ] poke at generative-sequencer timing

## log
- worked on unrelated stuff
"""


def test_active_projects_matches_manifest_names():
    m = load_manifest(FIX)
    found = active_projects_from_text(DAILY, m)
    assert set(found) == {"cenno", "generative-sequencer"}


def test_active_projects_ignores_unlisted_words():
    m = load_manifest(FIX)
    assert active_projects_from_text("just rambling about coffee", m) == []


def test_active_projects_dedupes_and_orders():
    m = load_manifest(FIX)
    txt = "cenno cenno and cenno again, plus generative-sequencer"
    assert active_projects_from_text(txt, m) == ["cenno", "generative-sequencer"]


def test_build_pin_plan_hybrid():
    m = load_manifest(FIX)
    plan = build_pin_plan(m, DAILY)
    # stable spine: every focus context
    assert set(plan["focuses"]) == {"business", "play"}
    # dynamic: today's active projects
    assert set(plan["projects"]) == {"cenno", "generative-sequencer"}


def test_build_pin_plan_empty_daily_still_pins_focuses():
    m = load_manifest(FIX)
    plan = build_pin_plan(m, "")
    assert set(plan["focuses"]) == {"business", "play"}
    assert plan["projects"] == []


def test_unpin_all_only_targets_pinned(monkeypatch):
    import pos.day as day
    calls = []
    monkeypatch.setattr(day, "run", lambda argv: calls.append(argv))
    ws = [
        {"ref": "w1", "title": "◆ cenno", "pinned": True},
        {"ref": "w2", "title": "◇ Voice", "pinned": False},
        {"ref": "w3", "title": "∴ brain", "pinned": True},
    ]
    unpinned = day._unpin_all(ws)
    assert unpinned == ["◆ cenno", "∴ brain"]
    # every call is an unpin action targeting a pinned ref
    assert all("unpin" in c for c in calls)
    assert {c[c.index("--workspace") + 1] for c in calls} == {"w1", "w3"}
