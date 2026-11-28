# hotdocs-criterion: sha256:25d5e647f50e0d7370b4deef00c70067a810822c7e7b104e95d491049eb0dd95
import ui_style  # noqa: F401


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
    ("--color-edge-depends-on", "#0969da"),
    ("--color-edge-realizes", "#1a7f37"),
    ("--color-edge-other", "#bc4c00"),
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

    # tokens equals the table, in the table's order
    assert dict(tokens) == expected
    assert list(dict(tokens).items()) == EXPECTED_TOKENS

    # :root rule equals the tokens plus color-scheme, which is last
    expected_root = list(EXPECTED_TOKENS) + [("color-scheme", "light dark")]
    assert dict(root) == dict(expected_root)
    assert list(dict(root).items()) == expected_root
    assert list(dict(root).keys())[-1] == "color-scheme"