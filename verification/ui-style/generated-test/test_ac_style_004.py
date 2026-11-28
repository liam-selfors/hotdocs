# hotdocs-criterion: sha256:6823d56dc57ed1a9c7f36af0428329efdc1b5ae3d99ceef12bf647e998606d99
"""AC-STYLE-004: each rule of R-STYLE-004's table has exactly its declarations, in order."""

import pytest

import ui_style  # noqa: F401  (module under test; the asset is read through asset_runner)


RULES = [
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
    ("a", [("color", "var(--color-accent)")]),
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
    (".tone-ok", [("border-left", "4px solid var(--color-ok)")]),
    (".tone-warn", [("border-left", "4px solid var(--color-warn)")]),
    (".tone-fail", [("border-left", "4px solid var(--color-fail)")]),
    (".tone-neutral", [("border-left", "4px solid var(--color-neutral)")]),
    (".edge-depends-on", [("stroke", "var(--color-edge-depends-on)")]),
    (".edge-realizes", [("stroke", "var(--color-edge-realizes)")]),
    (".edge-other", [("stroke", "var(--color-edge-other)")]),
    (".muted", [("color", "var(--color-text-muted)")]),
    (
        ":focus-visible",
        [
            ("outline", "2px solid var(--color-focus)"),
            ("outline-offset", "2px"),
        ],
    ),
]


@pytest.mark.parametrize(
    "selector,declarations", RULES, ids=[selector for selector, _ in RULES]
)
def test_rule_declarations_match_table_in_order(asset_runner, selector, declarations):
    run = asset_runner("static/style.css")
    result = run("rule", [selector])

    expected = dict(declarations)

    assert isinstance(result, dict)
    assert result == expected
    assert list(result.keys()) == [prop for prop, _ in declarations]