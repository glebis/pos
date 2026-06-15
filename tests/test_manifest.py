import os
import tempfile
from pathlib import Path

import pytest

from pos.manifest import focus_order, load_manifest, projects_by_focus

FIX = Path(__file__).parent / "fixtures" / "focus.toml"


def test_loads_focuses_and_projects():
    m = load_manifest(FIX)
    assert set(m.focuses) == {"business", "play"}
    assert m.projects["cenno"].focus == "business"
    assert m.focuses["business"].emoji == "🟢"


def test_projects_by_focus_groups():
    m = load_manifest(FIX)
    grouped = projects_by_focus(m)
    assert grouped["business"] == ["cenno"]
    assert grouped["play"] == ["generative-sequencer"]


def test_focus_order_revenue_first():
    m = load_manifest(FIX)
    assert focus_order(m)[0] == "business"


def test_missing_focus_ref_raises():
    bad = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
    bad.write('[projects.x]\nfocus="nope"\npath="~/x"\n')
    bad.close()
    with pytest.raises(ValueError, match="unknown focus"):
        load_manifest(Path(bad.name))
    os.unlink(bad.name)


def test_loads_presets():
    m = load_manifest(FIX)
    assert m.presets["revenue-sprint"] == ["business", "cenno"]


def test_presets_default_empty(tmp_path):
    p = tmp_path / "f.toml"
    p.write_text('[focuses.x]\nemoji="x"\n')
    assert load_manifest(p).presets == {}


from pos.manifest import expand_focus_members


def test_expand_focus_members_replaces_focus_with_projects():
    m = load_manifest(FIX)
    # business -> its projects (cenno); play -> generative-sequencer
    assert expand_focus_members(m, ["business"]) == ["cenno"]
    assert expand_focus_members(m, ["play"]) == ["generative-sequencer"]


def test_expand_focus_members_passes_projects_through_and_dedupes():
    m = load_manifest(FIX)
    # cenno is a project (passthrough); business expands to cenno -> deduped
    assert expand_focus_members(m, ["cenno", "business"]) == ["cenno"]


def test_expand_focus_members_keeps_unknowns():
    m = load_manifest(FIX)
    assert expand_focus_members(m, ["whatever"]) == ["whatever"]
