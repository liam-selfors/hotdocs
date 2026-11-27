# hotdocs-criterion: sha256:ba7ac82d4537a6e51627e2adaed1003f5621460fd2840f577aca0db6647dad11
import pytest

import ui_style


ROWS = [
    (
        "body",
        [
            ("margin", "0"),
            ("padding", "var(--space-5)"),
            ("background", "var(--color-bg)"),
            ("color", "var(--color-text)"),
            ("font-family", "var(--font-body)"),
            ("font-size", "var(--text-base)"),
            ("line-height", "1.5"),
        ],
    ),
    (
        "a",
        [
            ("color", "var(--color-accent)"),
        ],
    ),
    (
        "code, pre",
        [
            ("font-family", "var(--font-mono)"),
            ("font-size", "var(--text-sm)"),
        ],
    ),
    (
        "h1",
        [
            ("font-size", "var(--text-xl)"),
            ("margin", "0 0 var(--space-4)"),
        ],
    ),
    (
        "h2",
        [
            ("font-size", "var(--text-lg)"),
            ("margin", "var(--space-5) 0 var(--space-3)"),
        ],
    ),
    (
        ".node",
        [
            ("padding", "var(--space-2) var(--space-3)"),
            ("border", "1px solid var(--color-border)"),
            ("border-radius", "var(--radius)"),
            ("background", "var(--color-surface)"),
        ],
    ),
    (
        ".tone-ok",
        [
            ("border-left", "4px solid var(--color-ok)"),
        ],
    ),
    (
        ".tone-warn",
        [
            ("border-left", "4px solid var(--color-warn)"),
        ],
    ),
    (
        ".tone-fail",
        [
            ("border-left", "4px solid var(--color-fail)"),
        ],
    ),
    (
        ".tone-neutral",
        [
            ("border-left", "4px solid var(--color-neutral)"),
        ],
    ),
    (
        ".muted",
        [
            ("color", "var(--color-text-muted)"),
        ],
    ),
    (
        ":focus-visible",
        [
            ("outline", "2px solid var(--color-focus)"),
            ("outline-offset", "2px"),
        ],
    ),
]


@pytest.mark.parametrize("selector,declarations", ROWS, ids=[r[0] for r in ROWS])
def test_ac_style_004_rule_declarations(asset_runner, selector, declarations):
    run = asset_runner("static/style.css")
    result = run("rule", [selector])
    expected = dict(declarations)
    assert isinstance(result, dict)
    assert result == expected
    assert list(result.keys()) == [prop for prop, _ in declarations]
    assert list(result.items()) == declarations