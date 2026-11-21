# hotdocs-criterion: sha256:5e8ce97bd3b54b4d801a522c53f6bdbe9ed4f2629763a47c033f93f17a02af19
from pathlib import Path

import kind_javascript


CLEAN_TEXT = (
    "// import x from 'y'; fetch(\n"
    "const s = \"require('fs') and new WebSocket(u)\";\n"
    "export function f(a) { return a + 1; }\n"
)

FORBIDDEN_TEXT = (
    "import x from './x.js';\n"
    "export function g(u) { fetch(u); require (u); return new XMLHttpRequest(); }\n"
    "export const h = () => import('./y.js') && new WebSocket('ws://a');\n"
)


def test_ac_kjs_002_forbidden_words_only_outside_strings_and_comments(tmp_path):
    clean = tmp_path / "app.js"
    clean.write_text(CLEAN_TEXT, encoding="utf-8")

    result = kind_javascript.layout_errors(clean)
    assert list(result) == []

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    bad = other_dir / "app.js"
    bad.write_text(FORBIDDEN_TEXT, encoding="utf-8")

    result2 = kind_javascript.layout_errors(bad)
    assert list(result2) == [
        "forbidden: import",
        "forbidden: fetch(",
        "forbidden: require(",
        "forbidden: XMLHttpRequest",
        "forbidden: import",
        "forbidden: WebSocket",
    ]