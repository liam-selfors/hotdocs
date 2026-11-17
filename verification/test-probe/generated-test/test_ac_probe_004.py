import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


def _mismatches(report):
    return [
        f for f in _findings(report)
        if field(f, "kind") == "fake_signature_mismatch"
    ]


BUNDLE_1 = {
    "dependency_interfaces": {
        "comp-bar": (
            "bar_get(key: str, default: dict[str, str]) -> str\n"
            "bar_put(*, key: str) -> None"
        )
    }
}


def test_one_mismatch_on_bar_get_def_line():
    lines = [
        "# fakes for comp-bar",
        "",
        "def bar_get(key):",
        "    return 'x'",
        "",
        "",
        "def bar_put(key):",
        "    return None",
        "",
        "",
        "def other(a, b, c):",
        "    return None",
        "",
        "",
        "alias = bar_get",
        "",
        "",
        "def test_nothing():",
        "    assert True",
        "",
    ]
    source = "\n".join(lines)
    bar_get_line = lines.index("def bar_get(key):") + 1

    report = test_probe.probe(source, BUNDLE_1, "slugify")

    mismatches = _mismatches(report)
    assert len(mismatches) == 1, _findings(report)
    finding = mismatches[0]
    assert field(finding, "line") == bar_get_line
    assert field(finding, "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert field(finding, "severity") == "error"


def test_star_args_fake_satisfies_any_count():
    lines = [
        "def bar_get(*args):",
        "    return 'x'",
        "",
        "",
        "def bar_put(key):",
        "    return None",
        "",
        "",
        "def test_nothing():",
        "    assert True",
        "",
    ]
    source = "\n".join(lines)

    report = test_probe.probe(source, BUNDLE_1, "slugify")

    assert _mismatches(report) == [], _findings(report)


def test_def_inside_string_literal_is_checked_with_its_source_line():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": (
                "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"
            )
        }
    }
    lines = [
        "def bar_get(a, b, *, c):",      # 1
        "    return 'x'",                # 2
        "",                              # 3
        "",                              # 4
        "x = y = bar_get",               # 5
        "",                              # 6
        "",                              # 7
        "def test_nothing():",           # 8
        "    assert True",               # 9
        'SNIPPET = """',                 # 10
        "# a fake inside a string",      # 11
        "def bar_get(a, b):",            # 12
        "    return 1",                  # 13
        '"""',                           # 14
        "",
    ]
    source = "\n".join(lines)
    assert source.split("\n")[9].startswith('SNIPPET = """')
    assert source.split("\n")[11] == "def bar_get(a, b):"

    report = test_probe.probe(source, bundle, "slugify")

    mismatches = _mismatches(report)
    assert len(mismatches) == 1, _findings(report)
    finding = mismatches[0]
    assert field(finding, "line") == 12
    assert field(finding, "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )
    assert field(finding, "severity") == "error"