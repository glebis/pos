from pos import tmuxify as T


def test_tmux_session_extraction():
    assert T.tmux_session_of("tmux attach -t 1") == "1"
    assert T.tmux_session_of("tmux new-session -A -s unknowing-community") == "unknowing-community"
    assert T.tmux_session_of("~/ai_projects/cenno") is None


def test_classify():
    assert T.classify("tmux attach -t life") == "tmux"
    assert T.classify("glebkalinin@Mac:~/Brains/brain") == "shell"
    assert T.classify("…/pos/src/pos") == "shell"
    assert T.classify("/Users/x/proj") == "shell"
    assert T.classify("cenno app") == "other"
    assert T.classify("devops") == "other"


def test_selected_surface_prefers_selected():
    surfaces = [{"ref": "s1", "title": "a", "selected": False},
                {"ref": "s2", "title": "b", "selected": True}]
    assert T.selected_surface(surfaces)["ref"] == "s2"
    assert T.selected_surface([])  == {}


def test_audit_workspace_backed():
    a = T.audit_workspace("◆ cenno", [{"ref": "s8", "title": "tmux attach -t 1", "selected": True}])
    assert a["backed"] and a["session"] == "1" and a["kind"] == "tmux"


def test_audit_workspace_shell():
    a = T.audit_workspace("◆ business", [{"ref": "s1", "title": "glebkalinin@Mac:~/Brains/brain", "selected": True}])
    assert not a["backed"] and a["kind"] == "shell"


def test_build_plan_splits_and_protects_current():
    audits = [
        T.audit_workspace("◆ cenno", [{"ref": "s", "title": "tmux attach -t 1", "selected": True}]),
        T.audit_workspace("◆ business", [{"ref": "s", "title": "user@host:~/x", "selected": True}]),
        T.audit_workspace("devops", [{"ref": "s", "title": "devops", "selected": True}]),
        T.audit_workspace("Exploration", [{"ref": "s", "title": "…/pos/src", "selected": True}]),
    ]
    plan = T.build_plan(audits, current_title="Exploration")
    titles = lambda xs: {T.strip_glyph(a["title"]) for a in xs}
    assert titles(plan["backed"]) == {"cenno"}
    assert titles(plan["convert"]) == {"business"}          # Exploration is current -> skipped
    assert titles(plan["skipped"]) == {"devops", "Exploration"}


def test_convert_command_uses_pwd_and_session_name():
    cmd = T.convert_command("◆ business")
    assert cmd == 'exec tmux new-session -A -s business -c "$PWD"'


def test_apply_sends_exec_and_refreshes(monkeypatch):
    calls = []
    monkeypatch.setattr(T.cmux, "run", lambda argv: calls.append(argv))
    n = T.apply([{"title": "◆ business", "ref": "workspace:29", "selected_ref": "surface:1"}])
    assert n == 1
    sent = [a for a in calls if "send" in a and "exec tmux new-session" in " ".join(a)]
    assert sent and "surface:1" in sent[0]
    # tab is renamed to the clean session name (not the 'exec tmux …' command)
    renamed = [a for a in calls if "rename-tab" in a]
    assert renamed and "business" in renamed[0] and "surface:1" in renamed[0]
    assert any("refresh-surfaces" in a for a in calls)


def test_tmux_without_session_is_not_backed_and_skipped():
    # selected surface title is bare "tmux" (no -t/-s) -> running tmux but unknown session
    a = T.audit_workspace("agent-sdk-lab", [{"ref": "s", "title": "tmux", "selected": True}])
    assert a["kind"] == "tmux" and a["session"] is None and a["backed"] is False
    plan = T.build_plan([a], current_title="other")
    assert plan["backed"] == [] and len(plan["skipped"]) == 1
    assert "session name unknown" in plan["skipped"][0]["reason"]
