"""Output-mode resolution: agents get JSON, humans get pretty text — no flags.

The rule is TTY auto-detect: when stdout is a real terminal (a human is
reading), render human-friendly text; when piped or captured (which is exactly
how an agent invokes `pos`), render JSON. Explicit --json / --human override the
detection in either direction; --json wins if both are passed.
"""

import sys


def resolve_mode(args: list, isatty: bool | None = None) -> str:
    """Return "json" or "human" for this invocation.

    isatty defaults to the real stdout TTY state; pass it explicitly in tests.
    """
    if "--json" in args:
        return "json"
    if "--human" in args:
        return "human"
    if isatty is None:
        isatty = sys.stdout.isatty()
    return "human" if isatty else "json"
