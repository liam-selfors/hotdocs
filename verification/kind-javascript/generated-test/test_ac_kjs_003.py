# hotdocs-criterion: sha256:1ba6c29eecf0fe38044b376c845723082efabee204af6e27ad0aa6553d755c2c
from pathlib import Path

import kind_javascript


def test_ac_kjs_003_parse_error_then_forbidden(tmp_path):
    bad = tmp_path / "bad.js"
    bad.write_text("export function f(a {\n  return fetch(a);\n}\n", encoding="utf-8")

    result = kind_javascript.layout_errors(bad)

    assert result == [
        "parse error: SyntaxError: Unexpected token '{'",
        "forbidden: fetch(",
    ]


def test_ac_kjs_003_not_utf8_alone(tmp_path):
    bad = tmp_path / "notutf8.js"
    bad.write_bytes(b"export const s = '\xff';\n")

    result = kind_javascript.layout_errors(bad)

    assert result == ["parse error: not UTF-8"]