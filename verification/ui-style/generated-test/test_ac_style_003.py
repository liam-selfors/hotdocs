# hotdocs-criterion: sha256:364c391283acb98b977de7a07553df9ea1e51419fe5abffbf4d9543bd3bcd118
import pytest

import ui_style


DARK_TOKENS = {
    "--color-bg": "#0d1117",
    "--color-surface": "#151b23",
    "--color-text": "#f0f6fc",
    "--color-text-muted": "#9198a1",
    "--color-border": "#3d444d",
    "--color-accent": "#4493f8",
    "--color-focus": "#4493f8",
    "--color-ok": "#3fb950",
    "--color-warn": "#d29922",
    "--color-fail": "#f85149",
    "--color-neutral": "#8b949e",
}

BACKGROUNDS = ["--color-bg", "--color-surface"]
TEXT_TOKENS = ["--color-text", "--color-text-muted", "--color-accent"]
NON_TEXT_TOKENS = [
    "--color-focus",
    "--color-ok",
    "--color-warn",
    "--color-fail",
    "--color-neutral",
]


@pytest.fixture
def run(asset_runner):
    return asset_runner("static/style.css")


def test_dark_tokens_equal_table_in_order(run):
    result = run("tokens", ["dark"])
    assert dict(result) == DARK_TOKENS
    assert list(result.keys()) == list(DARK_TOKENS.keys())


@pytest.mark.parametrize("bg", BACKGROUNDS)
@pytest.mark.parametrize("fg", TEXT_TOKENS)
def test_text_pairs_contrast_at_least_4_5(run, fg, bg):
    light = run("contrast", [fg, bg])
    dark = run("contrast", [fg, bg, "dark"])
    assert float(light) >= 4.5, (fg, bg, light)
    assert float(dark) >= 4.5, (fg, bg, dark)


@pytest.mark.parametrize("bg", BACKGROUNDS)
@pytest.mark.parametrize("fg", NON_TEXT_TOKENS)
def test_non_text_pairs_contrast_at_least_3(run, fg, bg):
    light = run("contrast", [fg, bg])
    dark = run("contrast", [fg, bg, "dark"])
    assert float(light) >= 3, (fg, bg, light)
    assert float(dark) >= 3, (fg, bg, dark)