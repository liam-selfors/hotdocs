# hotdocs-criterion: sha256:f09c30b1f823ca100ed041fdc355679f23ec946989592713944fd90c3ce6e051
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def mismatches(report):
    return [
        f for f in field(report, "findings")
        if field(f, "kind") == "fake_signature_mismatch"
    ]


def line_of(lines, text):
    return lines.index(text) + 1


BUNDLE = {
    "dependency_interfaces": {
        "comp-bar": (
            "bar_get(key: str, default: dict[str, str]) -> str\n"
            "bar_put(*, key: str) -> None"
        )
    }
}


def test_alias_installed_fake_with_wrong_arity_gives_one_mismatch():
    lines = [
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
        "    return a",
        "",
        "",
        "alias = bar_get",
        "",
        "",
        "def test_fakes(monkeypatch):",
        "    monkeypatch.setattr(target, \"bar_get\", alias)",
        "    monkeypatch.setattr(target, \"bar_put\", bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    assert field(found[0], "line") == line_of(lines, "def bar_get(key):")
    assert field(found[0], "message") == (
        "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert field(found[0], "severity") == "error"


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
        "alias = bar_get",
        "",
        "",
        "def test_fakes(monkeypatch):",
        "    monkeypatch.setattr(target, \"bar_get\", alias)",
        "    monkeypatch.setattr(target, \"bar_put\", bar_put)",
        "    assert target.bar_get('k') == 'v'",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert mismatches(report) == []


def test_uninstalled_helper_is_never_a_fake():
    lines = [
        "import slugify",
        "",
        "",
        "def bar_get():",
        "    return 'v'",
        "",
        "",
        "def test_helper():",
        "    assert bar_get() == 'v'",
        "    assert slugify is not None",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
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
        "FAKE_SOURCE = \"\"\"",
        "# fake comp-bar module",
        "def bar_get(a, b):",
        "    return 'v'",
        "\"\"\"",
        "",
        "",
        "def test_install(monkeypatch):",
        "    monkeypatch.setattr(target, \"bar_get\", bar_get)",
        "    assert target.bar_get(1, 2, c='z') == 'v'",
        "",
    ]
    assert lines[9].startswith("FAKE_SOURCE = \"\"\"")
    assert lines[11] == "def bar_get(a, b):"
    source = "\n".join(lines)
    report = test_probe.probe(source, bundle, "slugify")
    found = mismatches(report)
    assert len(found) == 1
    assert field(found[0], "line") == 12
    assert field(found[0], "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )