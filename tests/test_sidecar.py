import json

from pos.cmux import parse_new_surface_ref, parse_surfaces, sidecar_argv, unique_sidecar_name


def test_sidecar_argv_targets_workspace_when_known():
    assert sidecar_argv(url=None, ws_ref="workspace:3")[-2:] == ["--workspace", "workspace:3"]
    assert "--workspace" not in sidecar_argv(url=None)


def test_parse_new_surface_ref():
    assert parse_new_surface_ref("OK surface:132 pane:101 workspace:3") == "surface:132"
    assert parse_new_surface_ref("Error: nope") is None
    assert parse_new_surface_ref("") is None


def test_explicit_name_is_used_verbatim():
    assert unique_sidecar_name("pos", ["pos"], explicit="logs") == "logs"


def test_default_is_the_folder_name():
    assert unique_sidecar_name("pos", []) == "pos"


def test_collision_appends_next_free_number():
    assert unique_sidecar_name("pos", ["pos"]) == "pos 2"
    assert unique_sidecar_name("pos", ["pos", "pos 2"]) == "pos 3"


def test_collision_skips_gaps_to_first_free_slot():
    # 'pos 2' taken but 'pos 3' free → fill the gap is not required; first free wins.
    assert unique_sidecar_name("pos", ["pos", "pos 2", "pos 4"]) == "pos 3"


def test_empty_folder_falls_back_to_sidecar():
    assert unique_sidecar_name("", []) == "sidecar"


def test_parse_surfaces_extracts_ref_and_title():
    payload = json.dumps(
        {"surfaces": [
            {"ref": "surface:8", "title": "◆ cenno", "type": "terminal"},
            {"ref": "surface:11", "title": "tmux", "type": "terminal"},
        ]}
    )
    surfaces = parse_surfaces(payload)
    assert surfaces == [
        {"ref": "surface:8", "title": "◆ cenno"},
        {"ref": "surface:11", "title": "tmux"},
    ]


def test_parse_surfaces_tolerates_garbage():
    assert parse_surfaces("not json") == []
    assert parse_surfaces("") == []
