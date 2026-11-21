# hotdocs-criterion: sha256:d095ab213db219618fcc6d4dcd57a089f08bd3417de0e5f152f498f14e933ae9
import kind_javascript


def test_parse_error_then_forbidden_fetch(tmp_path):
    bad = tmp_path / "bad.js"
    bad.write_text("export function f(a {\n  return fetch(a);\n}\n", encoding="utf-8")

    result = kind_javascript.layout_errors(bad)

    assert result == [
        "parse error: SyntaxError: Unexpected token '{'",
        "forbidden: fetch(",
    ]


def test_not_utf8_gives_only_not_utf8_message(tmp_path):
    bad = tmp_path / "notutf8.js"
    bad.write_bytes(b"export const s = '\xff';\n")

    result = kind_javascript.layout_errors(bad)

    assert result == ["parse error: not UTF-8"]