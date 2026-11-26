# hotdocs-criterion: sha256:8b40efda9c86713fec0cc31260fbb51222ccb3a927229590922ed063f21f86e8
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

TOP_LEVEL = [
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
    return [
        f for f in field(report, "findings")
        if field(f, "kind") == "fake_signature_mismatch"
    ]


def bar_get_line(lines):
    return lines.index("def bar_get(key):") + 1


def test_monkeypatch_installed_alias_mismatch():
    lines = TOP_LEVEL + [
        "def test_install(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    assert field(found[0], "line") == bar_get_line(lines)
    assert field(found[0], "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )


def test_setattr_and_attribute_assignment_installs():
    first_lines = TOP_LEVEL + [
        "def test_install(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "",
    ]
    first = mismatches(test_probe.probe("\n".join(first_lines), BUNDLE, "slugify"))

    lines = TOP_LEVEL + [
        "def test_install(monkeypatch):",
        "    setattr(target, 'bar_get', alias)",
        "    target.bar_put = bar_put",
        "    monkeypatch.setattr(target, 'other', other)",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    assert field(found[0], "line") == bar_get_line(lines)
    assert field(found[0], "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert len(first) == 1
    for key in ("kind", "severity", "line", "message"):
        assert field(found[0], key) == field(first[0], key)


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
        "def test_install(monkeypatch):",
        "    monkeypatch.setattr(target, 'bar_get', alias)",
        "    monkeypatch.setattr(target, 'bar_put', bar_put)",
        "",
    ]
    report = test_probe.probe("\n".join(lines), BUNDLE, "slugify")
    assert mismatches(report) == []


def test_uninstalled_helper_is_not_a_fake():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get():",
        "    return 'v'",
        "",
        "",
        "def test_helper():",
        "    assert bar_get() == 'v'",
        "    assert target is not None",
        "",
    ]
    report = test_probe.probe("\n".join(lines), BUNDLE, "slugify")
    assert mismatches(report) == []


def test_string_literal_fake_and_bracketed_interface():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": (
                "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"
            )
        }
    }
    lines = [
        "import slugify as target",          # 1
        "",                                  # 2
        "",                                  # 3
        "def bar_get(a, b, *, c):",          # 4
        "    return 'v'",                    # 5
        "",                                  # 6
        "",                                  # 7
        "x = y = bar_get",                   # 8
        "",                                  # 9
        'FAKE_SOURCE = """',                 # 10
        "# fake comp-bar module",            # 11
        "def bar_get(a, b):",                # 12
        "    return 'v'",                    # 13
        '"""',                               # 14
        "",                                  # 15
        "",                                  # 16
        "def test_install(monkeypatch):",    # 17
        "    monkeypatch.setattr(target, 'bar_get', bar_get)",
        "    assert FAKE_SOURCE",
        "",
    ]
    assert lines[11] == "def bar_get(a, b):"
    report = test_probe.probe("\n".join(lines), bundle, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    assert field(found[0], "line") == 12
    assert field(found[0], "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )