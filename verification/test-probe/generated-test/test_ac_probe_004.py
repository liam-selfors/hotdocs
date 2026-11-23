# hotdocs-criterion: sha256:6369f66f062599ef9629183b54f333517586a6f8b1425650ce8b88a437ce24e9
import test_probe


BUNDLE = {
    "dependency_interfaces": {
        "comp-bar": "bar_get(key: str, default: dict[str, str]) -> str\n"
        "bar_put(*, key: str) -> None"
    }
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def mismatches(report):
    return [
        f for f in field(report, "findings")
        if field(f, "kind") == "fake_signature_mismatch"
    ]


def defs_with(bar_get_def):
    # Lines 1..18; bar_get's def is always on line 4.
    return [
        "import slugify as target",          # 1
        "",                                  # 2
        "",                                  # 3
        bar_get_def,                         # 4
        "    return 'v'",                    # 5
        "",                                  # 6
        "",                                  # 7
        "def bar_put(key):",                 # 8
        "    return None",                   # 9
        "",                                  # 10
        "",                                  # 11
        "def other(a, b, c):",               # 12
        "    return a",                      # 13
        "",                                  # 14
        "",                                  # 15
        "alias = bar_get",                   # 16
        "",                                  # 17
        "",                                  # 18
    ]


def monkeypatch_install_source(bar_get_def):
    lines = defs_with(bar_get_def) + [
        "def test_fake(monkeypatch):",
        "    monkeypatch.setattr(target, " + repr("bar_get") + ", alias)",
        "    monkeypatch.setattr(target, " + repr("bar_put") + ", bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    return "\n".join(lines)


def other_install_source(bar_get_def):
    lines = defs_with(bar_get_def) + [
        "def test_fake(monkeypatch):",
        "    setattr(target, " + repr("bar_get") + ", alias)",
        "    target.bar_put = bar_put",
        "    monkeypatch.setattr(target, " + repr("other") + ", other)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    return "\n".join(lines)


EXPECTED_MESSAGE = "bar_get takes 1 parameters; the interface of comp-bar gives 2"


def assert_one_bar_get_mismatch(report):
    found = mismatches(report)
    assert len(found) == 1, field(report, "findings")
    assert field(found[0], "line") == 4
    assert field(found[0], "message") == EXPECTED_MESSAGE


def test_monkeypatch_installed_alias_mismatch():
    source = monkeypatch_install_source("def bar_get(key):")
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert_one_bar_get_mismatch(report)


def test_setattr_and_assignment_installed_mismatch():
    source = other_install_source("def bar_get(key):")
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert_one_bar_get_mismatch(report)


def test_star_args_fake_satisfies_any_count():
    source = monkeypatch_install_source("def bar_get(*args):")
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert mismatches(report) == []


def test_uninstalled_helper_is_never_a_fake():
    lines = [
        "def bar_get():",
        "    return 'v'",
        "",
        "",
        "def test_helper():",
        "    assert bar_get() == 'v'",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert mismatches(report) == []


def test_fake_module_in_string_literal_and_bracket_commas():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"
        }
    }
    lines = [
        "import slugify as target",                              # 1
        "",                                                      # 2
        "",                                                      # 3
        "def bar_get(a, b, *, c):",                              # 4
        "    return 'v'",                                        # 5
        "",                                                      # 6
        "",                                                      # 7
        "x = y = bar_get",                                       # 8
        "",                                                      # 9
        'FAKE = """',                                            # 10
        "# fake module",                                         # 11
        "def bar_get(a, b):",                                    # 12
        "    return 'v'",                                        # 13
        '"""',                                                   # 14
        "",                                                      # 15
        "",                                                      # 16
        "def test_fake(monkeypatch):",                           # 17
        "    monkeypatch.setattr(target, " + repr("bar_get") + ", bar_get)",
        "    assert FAKE",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, bundle, "slugify")
    found = mismatches(report)
    assert len(found) == 1, field(report, "findings")
    assert field(found[0], "line") == 12
    assert field(found[0], "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )