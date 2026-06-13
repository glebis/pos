from pos.label import GLYPHS, glyphed_title, strip_glyph


def test_prefixes_glyph():
    assert glyphed_title("◆", "cenno") == "◆ cenno"


def test_strips_existing_glyph_before_reprefixing():
    # idempotent: applying twice doesn't stack glyphs
    once = glyphed_title("◆", "cenno")
    twice = glyphed_title("◆", once)
    assert twice == "◆ cenno"


def test_reprefix_with_different_glyph_replaces():
    assert glyphed_title("◇", "◆ cenno") == "◇ cenno"


def test_strip_glyph_removes_any_known_mark():
    assert strip_glyph("∴ Brain 01") == "Brain 01"
    assert strip_glyph("plain title") == "plain title"


def test_empty_glyph_returns_clean_title():
    assert glyphed_title("", "◆ cenno") == "cenno"


def test_glyphs_constant_covers_set_a():
    # the known marks we strip include Set A
    for g in ["◆", "◇", "+", "∴", "⌂"]:
        assert g in GLYPHS
