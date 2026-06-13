import subprocess

YARD_SESSION = "yard"


def _ensure_session_argv() -> list:
    return ["tmux", "new-session", "-d", "-s", YARD_SESSION]


def run_argv(name: str, command: str) -> list:
    return ["tmux", "new-window", "-t", YARD_SESSION, "-n", name, command]


def attach_argv(name: str) -> list:
    return ["tmux", "attach", "-t", f"{YARD_SESSION}:{name}"]


def list_argv() -> list:
    return ["tmux", "list-windows", "-t", YARD_SESSION]


def kill_argv(name: str) -> list:
    return ["tmux", "kill-window", "-t", f"{YARD_SESSION}:{name}"]


def run(name: str, command: str) -> None:
    # ensure the detached session exists, then add the job window
    subprocess.run(_ensure_session_argv(), capture_output=True, text=True)
    subprocess.run(run_argv(name, command), capture_output=True, text=True)
