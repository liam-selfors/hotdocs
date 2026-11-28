# hotdocs-criterion: sha256:b6b1ad2a785c773411dacd0a37aad0954c410805549fdf341eafebb7376c234c
from pathlib import Path

import ui_style


def _asset_path():
    return Path(ui_style.__file__).parent / "static" / "style.css"


def _asset_text():
    return _asset_path().read_bytes().decode("utf-8")


def test_ac_style_001_stylesheet_and_style_element():
    asset = _asset_path()
    assert asset.is_file()

    expected = _asset_text()

    sheet = ui_style.stylesheet()
    assert isinstance(sheet, str)
    assert sheet == expected

    element = ui_style.style_element()
    assert isinstance(element, str)
    assert element == "<style>\n" + ui_style.stylesheet() + "</style>"
    assert element == "<style>\n" + expected + "</style>"

    assert "</style" not in sheet
    assert "</style" not in expected


def test_ac_style_001_repeated_calls_are_stable():
    expected = _asset_text()
    first = ui_style.stylesheet()
    second = ui_style.stylesheet()
    assert first == expected
    assert second == expected
    assert ui_style.style_element() == ui_style.style_element()
    assert ui_style.style_element() == "<style>\n" + expected + "</style>"