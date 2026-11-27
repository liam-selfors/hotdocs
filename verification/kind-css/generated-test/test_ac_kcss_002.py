# hotdocs-criterion: sha256:4debde49d5aaaad7c5af25f11ac78a09a1b15a97fba9c012686b355eb3d07e48
import pytest

import kind_css


CASES = [
    ("ok.css", ["a {", "  color: red;", "}"], []),
    (
        "close.css",
        ["a { color: red; }", "}"],
        ["parse error: line 2: unexpected }"],
    ),
    (
        "open.css",
        ["a {", "  color: red;"],
        ["parse error: line 1: unclosed {"],
    ),
    (
        "colon.css",
        ["a {", "  color red;", "}"],
        ["parse error: line 2: expected :"],
    ),
    (
        "import.css",
        ['@import "x.css";'],
        ["parse error: line 1: at-rule @import is not allowed"],
    ),
    (
        "font.css",
        ["@font-face {", "}"],
        ["parse error: line 1: at-rule @font-face is not allowed"],
    ),
    (
        "media.css",
        ["@media (x) {", "  @media (y) {", "  }", "}"],
        ["parse error: line 2: @media inside @media"],
    ),
    (
        "nest.css",
        ["a {", "  b { color: red; }", "}"],
        ["parse error: line 2: unexpected {"],
    ),
    ("semi.css", ["a;"], ["parse error: line 1: unexpected ;"]),
]


@pytest.mark.parametrize(
    "name,lines,expected", CASES, ids=[c[0] for c in CASES]
)
def test_layout_errors_table(tmp_path, name, lines, expected):
    path = tmp_path / name
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    result = kind_css.layout_errors(path)
    assert result == expected


def test_layout_errors_all_files_each_own_path(tmp_path):
    paths = {}
    for name, lines, _expected in CASES:
        path = tmp_path / name
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        paths[name] = path
    bad = tmp_path / "bad.css"
    bad.write_bytes(b"a { color: \xff; }\n")
    for name, _lines, expected in CASES:
        assert kind_css.layout_errors(paths[name]) == expected
    assert kind_css.layout_errors(bad) == ["parse error: not UTF-8"]


def test_layout_errors_not_utf8(tmp_path):
    bad = tmp_path / "bad.css"
    bad.write_bytes(b"a { color: \xff; }\n")
    assert kind_css.layout_errors(bad) == ["parse error: not UTF-8"]