# hotdocs-criterion: sha256:b8e9c2af2e859fa3bb44ce281a6d613ba631353b9e66e0227ac18065408919b9
import kind_css


def _write(path, lines):
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def test_forbid_css_reports_each_forbidden_occurrence_in_order(tmp_path):
    p = _write(
        tmp_path / "forbid.css",
        [
            "a {",
            "  background: url(x.png);",
            "  width: expression(1);",
            "}",
            "/* </style> */",
        ],
    )
    assert kind_css.layout_errors(p) == [
        "forbidden: url(",
        "forbidden: expression(",
        "forbidden: </style",
    ]


def test_quoted_url_is_not_forbidden(tmp_path):
    p = _write(tmp_path / "quoted.css", ['a { content: "url(x)"; }'])
    assert kind_css.layout_errors(p) == []


def test_structural_error_precedes_forbidden_messages(tmp_path):
    p = _write(tmp_path / "both.css", ["}", "a { background: URL(x); }"])
    assert kind_css.layout_errors(p) == [
        "parse error: line 1: unexpected }",
        "forbidden: url(",
    ]