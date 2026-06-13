"""Typographic focus glyphs prefixed to workspace titles."""

# Known marks we recognise as a leading focus glyph (so re-labeling is idempotent).
# Superset of Set A plus a few alternates, in case the manifest uses others.
GLYPHS = {"◆", "◇", "+", "∴", "⌂", "●", "▲", "■", "○", "▸", "◦", "~", "·"}


def strip_glyph(title: str) -> str:
    """Remove a leading known glyph (and its following space) from a title."""
    t = title.lstrip()
    if t[:1] in GLYPHS:
        return t[1:].lstrip()
    return t


def glyphed_title(glyph: str, title: str) -> str:
    """Return title prefixed with glyph, idempotently (strips any existing mark).

    An empty glyph yields the clean, unprefixed title.
    """
    clean = strip_glyph(title)
    if not glyph:
        return clean
    return f"{glyph} {clean}"
