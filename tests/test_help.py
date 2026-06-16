from pos import cli, help as poshelp


def test_registry_entries_have_name_synopsis_and_example():
    cmds = poshelp.render_json()
    assert isinstance(cmds, list) and cmds
    for c in cmds:
        assert c["name"]
        assert c["synopsis"]
        assert "example" in c


def test_registry_covers_core_commands():
    names = {c["name"] for c in poshelp.render_json()}
    assert {"status", "load", "new", "cc", "p"} <= names


def test_every_registry_command_is_dispatchable():
    # Guard against documenting a command `main` doesn't handle. Every registry
    # name must appear as a dispatch arm in cli.main's source.
    import inspect

    src = inspect.getsource(cli.main)
    for c in poshelp.render_json():
        assert f'"{c["name"]}"' in src, f"{c['name']} not dispatched in main()"


def test_every_registry_command_appears_in_human_usage():
    # USAGE (the human view) and the registry (the agent view) must not drift.
    for c in poshelp.render_json():
        assert f"pos {c['name']}" in cli.USAGE, f"{c['name']} missing from USAGE"


def test_agents_doc_mentions_focus_model_and_json():
    doc = poshelp.agents_doc()
    assert "focus" in doc.lower()
    assert "--json" in doc or "json" in doc.lower()
