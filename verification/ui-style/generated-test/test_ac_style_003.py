# hotdocs-criterion: sha256:aab6a1545c48ad865bcbe70b7e8cc179213d6a7b3a879b8056030a9872c3a72a
import pytest

import ui_style


EXPECTED_DARK = [
    ("--color-bg", "#0d1117"),
    ("--color-surface", "#151b23"),
    ("--color-text", "#f0f6fc"),
    ("--color-text-muted", "#9198a1"),
    ("--color-border", "#3d444d"),
    ("--color-accent", "#4493f8"),
    ("--color-focus", "#4493f8"),
    ("--color-ok", "#3fb950"),
    ("--color-warn", "#d29922"),
    ("--color-fail", "#f85149"),
    ("--color-neutral", "#8b949e"),
    ("--color-edge-depends-on", "#4493f8"),
    ("--color-edge-realizes", "#3fb950"),
    ("--color-edge-other", "#db6d28"),
]

BACKGROUNDS = ["--color-bg", "--color-surface"]

TEXT_TOKENS = ["--color-text", "--color-text-muted", "--color-accent"]

NON_TEXT_TOKENS = [
    "--color-focus",
    "--color-ok",
    "--color-warn",
    "--color-fail",
    "--color-neutral",
    "--color-edge-depends-on",
    "--color-edge-realizes",
    "--color-edge-other",
]


@pytest.fixture
def run(asset_runner):
    return asset_runner("static/style.css")


def test_dark_tokens_equal_table_in_order(run):
    tokens = run("tokens", ["dark"])
    assert isinstance(tokens, dict)
    assert tokens == dict(EXPECTED_DARK)
    assert list(tokens.keys()) == [name for name, _ in EXPECTED_DARK]


@pytest.mark.parametrize("bg", BACKGROUNDS)
@pytest.mark.parametrize("fg", TEXT_TOKENS)
def test_text_pairs_contrast_at_least_4_5(run, fg, bg):
    light = run("contrast", [fg, bg])
    dark = run("contrast", [fg, bg, "dark"])
    assert float(light) >= 4.5, (fg, bg, "light", light)
    assert float(dark) >= 4.5, (fg, bg, "dark", dark)


@pytest.mark.parametrize("bg", BACKGROUNDS)
@pytest.mark.parametrize("fg", NON_TEXT_TOKENS)
def test_non_text_pairs_contrast_at_least_3(run, fg, bg):
    light = run("contrast", [fg, bg])
    dark = run("contrast", [fg, bg, "dark"])
    assert float(light) >= 3, (fg, bg, "light", light)
    assert float(dark) >= 3, (fg, bg, "dark", dark)