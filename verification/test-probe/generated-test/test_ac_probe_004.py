# hotdocs-criterion: sha256:b0f8eb3a741022186a881a319c05a5a9b83d041f5869b2028910035bc4ee9e1b
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "dependency_interfaces": {
        "comp-bar": (
            "bar_get(key: str, default: dict[str, str]) -> str\n"
            "bar_put(*, key: str) -> None"
        )
    }
}

HEADER = [
    "import slugify as target",
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
    "    return None",
    "",
    "",
    "alias = bar_get",
    "",
    "",
]


def mismatches(report):
    findings = field(report, "findings")
    return [
        f for f in findings if field(f, "kind") == "fake_signature_mismatch"
    ]


def bar_get_def_line(lines):
    return lines.index("def bar_get(key):") + 1


def test_monkeypatch_installed_fake_arity_mismatch_is_reported():
    lines = HEADER + [
        "def test_fake(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    finding = found[0]
    assert field(finding, "line") == bar_get_def_line(lines)
    assert field(finding, "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )


def test_other_install_forms_give_the_same_single_finding():
    lines1 = HEADER + [
        "def test_fake(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    lines2 = HEADER + [
        "def test_fake(monkeypatch):",
        "    setattr(target, 'bar_get', alias)",
        "    target.bar_put = bar_put",
        "    monkeypatch.setattr(target, 'other', other)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    report1 = test_probe.probe("\n".join(lines1), BUNDLE, "slugify")
    report2 = test_probe.probe("\n".join(lines2), BUNDLE, "slugify")
    found1 = mismatches(report1)
    found2 = mismatches(report2)
    assert len(found2) == 1
    finding = found2[0]
    assert field(finding, "line") == bar_get_def_line(lines2)
    assert field(finding, "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert len(found1) == 1
    for name in ("kind", "severity", "line", "message"):
        assert field(found1[0], name) == field(finding, name)


def test_star_args_fake_satisfies_any_count():
    lines = [
        "import slugify as target",
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
        "def other(a, b, c):",
        "    return None",
        "",
        "",
        "alias = bar_get",
        "",
        "",
        "def test_fake(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    report = test_probe.probe("\n".join(lines), BUNDLE, "slugify")
    assert mismatches(report) == []


def test_uninstalled_helper_is_never_a_fake():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get():",
        "    return 'k'",
        "",
        "",
        "def test_helper():",
        "    key = bar_get()",
        "    assert target.bar_get(key, {}) is not None",
        "",
    ]
    report = test_probe.probe("\n".join(lines), BUNDLE, "slugify")
    assert mismatches(report) == []


def test_fake_module_source_in_string_literal_is_checked():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": (
                "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str)"
                " -> str"
            )
        }
    }
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get(a, b, *, c):",
        "    return 'v'",
        "",
        "",
        "x = y = bar_get",
        "",
        'FAKE = """',
        "# fake comp-bar module",
        "def bar_get(a, b):",
        "    return 'v'",
        '"""',
        "",
        "",
        "def test_fake(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', bar_get)",
        "    assert FAKE",
        "",
    ]
    assert lines[9].startswith('FAKE = """')
    assert lines[11] == "def bar_get(a, b):"
    report = test_probe.probe("\n".join(lines), bundle, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    finding = found[0]
    assert field(finding, "line") == 12
    assert field(finding, "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )