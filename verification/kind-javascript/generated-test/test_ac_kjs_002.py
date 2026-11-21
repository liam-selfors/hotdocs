# hotdocs-criterion: sha256:eb83abfd9a97ff43cc1a10bee4a7c6445490aef4f0bdef31d747d4de12f32c85
import kind_javascript


FIRST_TEXT = (
    "// import x from 'y'; fetch(\n"
    "const s = \"require('fs') and new WebSocket(u)\";\n"
    "export function f(a) { return a + 1; }\n"
)

SECOND_TEXT = (
    "import x from './x.js';\n"
    "export function g(u) { fetch(u); require (u); return new XMLHttpRequest(); }\n"
    "export const h = () => import('./y.js') && new WebSocket('ws://a');\n"
)


def test_forbidden_words_inside_comment_and_string_are_not_reported(tmp_path):
    path = tmp_path / "app.js"
    path.write_text(FIRST_TEXT, encoding="utf-8")

    result = kind_javascript.layout_errors(path)

    assert result == []


def test_forbidden_tokens_reported_once_per_occurrence_in_text_order(tmp_path):
    first = tmp_path / "app.js"
    first.write_text(FIRST_TEXT, encoding="utf-8")
    assert kind_javascript.layout_errors(first) == []

    other_dir = tmp_path / "second"
    other_dir.mkdir()
    second = other_dir / "app.js"
    second.write_text(SECOND_TEXT, encoding="utf-8")

    result = kind_javascript.layout_errors(second)

    assert result == [
        "forbidden: import",
        "forbidden: fetch(",
        "forbidden: require(",
        "forbidden: XMLHttpRequest",
        "forbidden: import",
        "forbidden: WebSocket",
    ]