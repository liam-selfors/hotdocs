# hotdocs-criterion: sha256:85a147474b7adb6514e029fa050a8b712ada7b06c46b97870178988a8f1886c7
import kind_javascript


def test_forbidden_words_inside_comment_and_string_are_not_reported(tmp_path):
    path = tmp_path / "app.js"
    text = (
        "// import x from 'y'; fetch(\n"
        "const s = \"require('fs') and new WebSocket(u)\";\n"
        "export function f(a) { return a + 1; }\n"
    )
    path.write_text(text, encoding="utf-8")

    result = kind_javascript.layout_errors(path)

    assert result == []


def test_forbidden_tokens_reported_once_per_occurrence_in_text_order(tmp_path):
    clean = tmp_path / "app.js"
    clean.write_text(
        "// import x from 'y'; fetch(\n"
        "const s = \"require('fs') and new WebSocket(u)\";\n"
        "export function f(a) { return a + 1; }\n",
        encoding="utf-8",
    )
    assert kind_javascript.layout_errors(clean) == []

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    path = other_dir / "app.js"
    text = (
        "import x from './x.js';\n"
        "export function g(u) { fetch(u); require (u); return new XMLHttpRequest(); }\n"
        "export const h = () => import('./y.js') && new WebSocket('ws://a');\n"
    )
    path.write_text(text, encoding="utf-8")

    result = kind_javascript.layout_errors(path)

    assert result == [
        "forbidden: import",
        "forbidden: fetch(",
        "forbidden: require(",
        "forbidden: XMLHttpRequest",
        "forbidden: import",
        "forbidden: WebSocket",
    ]