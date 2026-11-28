# hotdocs-criterion: sha256:c0cf8b75c0bcc102733ef874da069148150053a7df145edfdf74ed80bd5cd4db
"""AC-STYLE-002: the :root rule declares exactly R-STYLE-002's tokens, in
order, then color-scheme: light dark."""

import ui_style  # noqa: F401  (module under test)


EXPECTED_TOKENS = [
    ("--color-bg", "#ffffff"),
    ("--color-surface", "#f6f8fa"),
    ("--color-text", "#1f2328"),
    ("--color-text-muted", "#59636e"),
    ("--color-border", "#d1d9e0"),
    ("--color-accent", "#0969da"),
    ("--color-focus", "#0969da"),
    ("--color-ok", "#1a7f37"),
    ("--color-warn", "#9a6700"),
    ("--color-fail", "#d1242f"),
    ("--color-neutral", "#6e7781"),
    ("--font-body", 'system-ui, -apple-system, "Segoe UI", sans-serif'),
    ("--font-mono", "ui-monospace, Menlo, Consolas, monospace"),
    ("--text-sm", "0.875rem"),
    ("--text-base", "1rem"),
    ("--text-lg", "1.25rem"),
    ("--text-xl", "1.5rem"),
    ("--space-1", "4px"),
    ("--space-2", "8px"),
    ("--space-3", "12px"),
    ("--space-4", "16px"),
    ("--space-5", "24px"),
    ("--radius", "6px"),
]


def test_ac_style_002_root_tokens_and_color_scheme(asset_runner):
    run = asset_runner("static/style.css")

    tokens = run("tokens", [])
    root = run("rule", [":root"])

    expected = dict(EXPECTED_TOKENS)

    # tokens equals the table as a dict, keys in the table's order
    assert dict(tokens) == expected
    assert list(dict(tokens).items()) == EXPECTED_TOKENS
    assert list(dict(tokens).keys()) == [k for k, _ in EXPECTED_TOKENS]

    # :root rule equals that dict plus color-scheme, which comes last
    expected_root = dict(EXPECTED_TOKENS)
    expected_root["color-scheme"] = "light dark"
    root_dict = dict(root)
    assert root_dict == expected_root
    assert list(root_dict.items()) == EXPECTED_TOKENS + [("color-scheme", "light dark")]
    assert list(root_dict.keys())[-1] == "color-scheme"