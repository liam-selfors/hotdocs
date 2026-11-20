# hotdocs-criterion: sha256:dbc31dd081a8dd8c3c6a7bd33016eb7e175dfd9411b2d05fa3d48c96915b5072
import kind_javascript


def test_ac_kjs_003_parse_error_then_forbidden(tmp_path):
    bad = tmp_path / "bad.js"
    bad.write_text("export function f(a {\n  return fetch(a);\n}\n", encoding="utf-8")
    result = kind_javascript.layout_errors(bad)
    assert result == [
        "parse error: SyntaxError: Unexpected token '{'",
        "forbidden: fetch(",
    ]


def test_ac_kjs_003_not_utf8(tmp_path):
    bad = tmp_path / "latin.js"
    bad.write_bytes(b"export const s = '\xff';\n")
    result = kind_javascript.layout_errors(bad)
    assert result == ["parse error: not UTF-8"]