import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# tier sort order — mirrors My Focus.md (revenue first)
TIER_ORDER = {"revenue": 0, "rnd": 1, "life": 2, "health": 3, "base": 4}


@dataclass
class Focus:
    name: str
    emoji: str = ""
    glyph: str = ""
    tier: str = "base"
    home: str = "~"


@dataclass
class Project:
    name: str
    focus: str
    path: str


@dataclass
class Manifest:
    focuses: dict = field(default_factory=dict)
    projects: dict = field(default_factory=dict)
    presets: dict = field(default_factory=dict)
    projects_base: str = "~/ai_projects"


def load_manifest(path: Path) -> Manifest:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    focuses = {
        name: Focus(
            name=name,
            emoji=f.get("emoji", ""),
            glyph=f.get("glyph", ""),
            tier=f.get("tier", "base"),
            home=f.get("home", "~"),
        )
        for name, f in data.get("focuses", {}).items()
    }
    projects = {
        name: Project(name=name, focus=p["focus"], path=p["path"])
        for name, p in data.get("projects", {}).items()
    }
    for p in projects.values():
        if p.focus not in focuses:
            raise ValueError(
                f"project {p.name!r} references unknown focus {p.focus!r}"
            )
    presets = {
        name: list(p.get("members", []))
        for name, p in data.get("presets", {}).items()
    }
    base = data.get("settings", {}).get("projects_base", "~/ai_projects")
    return Manifest(focuses=focuses, projects=projects, presets=presets, projects_base=base)


def resolve_preset(m: Manifest, args: list) -> list:
    """Resolve `pos load` args into a member list.

    A single arg that names a preset expands to its members; otherwise all args
    are treated as ad-hoc members (focus or project names).
    """
    if len(args) == 1 and args[0] in m.presets:
        return list(m.presets[args[0]])
    return list(args)


def focus_order(m: Manifest) -> list:
    return sorted(m.focuses, key=lambda n: (TIER_ORDER.get(m.focuses[n].tier, 99), n))


def projects_by_focus(m: Manifest) -> dict:
    out = {name: [] for name in focus_order(m)}
    for p in m.projects.values():
        out.setdefault(p.focus, []).append(p.name)
    for k in out:
        out[k].sort()
    return out


def expand_focus_members(m: Manifest, members: list) -> list:
    """Replace any focus name in `members` with that focus's project names.

    Project names and unknowns pass through unchanged. Order is preserved and
    duplicates collapsed. A focus with no projects falls back to itself (so
    `pos load <empty-focus>` still opens the focus's home tab rather than nothing).
    """
    grouped = projects_by_focus(m)
    expanded = []
    for x in members:
        if x in m.focuses:
            projs = grouped.get(x, [])
            expanded.extend(projs if projs else [x])
        else:
            expanded.append(x)
    seen, out = set(), []
    for x in expanded:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
