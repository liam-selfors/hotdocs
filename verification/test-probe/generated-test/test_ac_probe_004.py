import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _mismatches(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "kind") == "fake_signature_mismatch"]


def _line_of(source, prefix):
    for index, text in enumerate(source.split("\n"), start=1):
        if text.startswith(prefix):
            return index
    raise AssertionError("prefix not found: " + prefix)


BUNDLE_ONE = {
    "dependency_interfaces": {
        "comp-bar": (
            "bar_get(key: str, default: dict[str, str]) -> str\n"
            "bar_put(*, key: str) -> None"
        )
    }
}


def test_ac_probe_004_single_mismatch_on_bar_get_def_line():
    source = "\n".join(
        [
            "# fixture test file",
            "",
            "",
            "def bar_get(key):",
            "    return 'v'",
            "",
            "",
            "def bar_put(key):",
            "    return None",
            "",
            "",
            "def other(a, b, c):",
            "    return a",
            "",
            "",
            "alias = bar_get",
            "",
            "",
            "def test_nothing():",
            "    assert True",
            "",
        ]
    )
    report = test_probe.probe(source, BUNDLE_ONE, "slugify")
    mismatches = _mismatches(report)
    assert len(mismatches) == 1, mismatches
    finding = mismatches[0]
    assert field(finding, "line") == _line_of(source, "def bar_get(")
    assert field(finding, "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert field(finding, "severity") == "error"


def test_ac_probe_004_star_args_fake_satisfies_any_count():
    source = "\n".join(
        [
            "# fixture test file",
            "",
            "",
            "def bar_get(*args):",
            "    return 'v'",
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
    )
    report = test_probe.probe(source, BUNDLE_ONE, "slugify")
    assert _mismatches(report) == []


def test_ac_probe_004_def_inside_string_literal_and_chained_alias():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": (
                "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"
            )
        }
    }
    lines = [
        "# fixture test file",          # 1
        "",                             # 2
        "",                             # 3
        "def bar_get(a, b, *, c):",     # 4
        "    return 'v'",               # 5
        "",                             # 6
        "",                             # 7
        "x = y = bar_get",              # 8
        "",                             # 9
        'SNIPPET = """',                # 10
        "import os",                    # 11
        "def bar_get(a, b):",           # 12
        "    return os.sep",            # 13
        '"""',                          # 14
        "",                             # 15
        "",                             # 16
        "def test_nothing():",          # 17
        "    assert SNIPPET",           # 18
        "",
    ]
    source = "\n".join(lines)
    assert source.split("\n")[9].startswith('SNIPPET = """')
    assert source.split("\n")[11] == "def bar_get(a, b):"

    report = test_probe.probe(source, bundle, "slugify")
    mismatches = _mismatches(report)
    assert len(mismatches) == 1, mismatches
    finding = mismatches[0]
    assert field(finding, "line") == 12
    assert field(finding, "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )