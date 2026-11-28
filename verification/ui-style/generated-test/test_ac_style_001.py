# hotdocs-criterion: sha256:36574fecbf61f5b36b26eff69996b85a77784922d64a1762571200f0248bc743
from pathlib import Path

import ui_style


def _asset_path():
    return Path(ui_style.__file__).parent / "static" / "style.css"


def _asset_text():
    return _asset_path().read_bytes().decode("utf-8")


def test_declared_asset_exists():
    assert _asset_path().is_file()


def test_stylesheet_equals_asset_text_read_as_utf8():
    expected = _asset_text()
    result = ui_style.stylesheet()
    assert isinstance(result, str)
    assert result == expected
    # Read at each call, unchanged: a second call returns the same text.
    assert ui_style.stylesheet() == expected


def test_style_element_wraps_stylesheet_exactly():
    sheet = ui_style.stylesheet()
    element = ui_style.style_element()
    assert isinstance(element, str)
    assert element == "<style>\n" + sheet + "</style>"
    assert element == "<style>\n" + _asset_text() + "</style>"


def test_stylesheet_contains_no_closing_style_tag():
    assert "</style" not in ui_style.stylesheet()
    assert "</style" not in _asset_text()