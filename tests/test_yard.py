from pos.yard import YARD_SESSION, attach_argv, kill_argv, list_argv, run_argv


def test_run_creates_named_window():
    argv = run_argv(name="crawl", command="firecrawl run")
    assert argv[:2] == ["tmux", "new-window"]
    assert "-t" in argv and YARD_SESSION in argv
    assert "-n" in argv and "crawl" in argv
    assert "firecrawl run" in argv


def test_attach_targets_window():
    assert attach_argv("crawl") == ["tmux", "attach", "-t", f"{YARD_SESSION}:crawl"]


def test_list_argv():
    assert list_argv()[:2] == ["tmux", "list-windows"]


def test_kill_argv():
    assert kill_argv("crawl") == ["tmux", "kill-window", "-t", f"{YARD_SESSION}:crawl"]
