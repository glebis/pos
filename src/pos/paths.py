from pathlib import Path


def resolve_path(spec: str, base: str) -> Path:
    """Resolve a project path: absolute as-is, ~ expanded, else joined to base."""
    if spec.startswith("/"):
        return Path(spec)
    if spec.startswith("~"):
        return Path(spec).expanduser()
    return Path(base).expanduser() / spec
