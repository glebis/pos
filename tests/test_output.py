from pos.output import resolve_mode


def test_explicit_json_flag_forces_json_even_on_a_tty():
    assert resolve_mode(["--json"], isatty=True) == "json"


def test_explicit_human_flag_forces_human_even_when_piped():
    assert resolve_mode(["--human"], isatty=False) == "human"


def test_default_on_a_tty_is_human():
    assert resolve_mode([], isatty=True) == "human"


def test_default_when_piped_is_json():
    assert resolve_mode([], isatty=False) == "json"


def test_json_takes_precedence_over_human_when_both_given():
    assert resolve_mode(["--human", "--json"], isatty=True) == "json"
