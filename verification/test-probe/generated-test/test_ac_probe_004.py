# hotdocs-criterion: sha256:07868c51ba1e7ec234a3edc7149143c2746972bd17d164933c256ffde907f7f8
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
        f
        for f in field(report, "findings")
        if field(f, "kind") == "fake_signature_mismatch"
    ]


def test_alias_installed_fake_with_wrong_arity_is_flagged():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get(key):",
        '    return "v"',
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
        "def test_install(monkeypatch):",
        '    monkeypatch.setattr(target, "bar_get", alias)',
        '    monkeypatch.setattr(target, "bar_put", bar_put)',
        "",
    ]
    source = "\n".join(lines)
    def_line = lines.index("def bar_get(key):") + 1

    report = test_probe.probe(source, BUNDLE, "slugify")

    found = mismatches(report)
    assert len(found) == 1, found
    assert field(found[0], "line") == def_line
    assert (
        field(found[0], "message")
        == "bar_get takes 1 parameters; the interface of comp-bar gives 2"
    )
    assert field(found[0], "severity") == "error"


def test_star_args_fake_satisfies_any_count():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get(*args):",
        '    return "v"',
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
        "def test_install(monkeypatch):",
        '    monkeypatch.setattr(target, "bar_get", alias)',
        '    monkeypatch.setattr(target, "bar_put", bar_put)',
        "",
    ]
    source = "\n".join(lines)

    report = test_probe.probe(source, BUNDLE, "slugify")

    assert mismatches(report) == []


def test_uninstalled_helper_is_not_a_fake():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get():",
        '    return "v"',
        "",
        "",
        "def test_helper():",
        '    assert bar_get() == "v"',
        "    assert target is not None",
        "",
    ]
    source = "\n".join(lines)

    report = test_probe.probe(source, BUNDLE, "slugify")

    assert mismatches(report) == []


def test_fake_module_in_string_literal_is_checked_at_its_line():
    bundle = {
        "dependency_interfaces": {
            "comp-bar": "bar_get(a: int, /, b: dict[str, tuple[int, int]], *, c: str) -> str"
        }
    }
    lines = [
        "import slugify as target",  # 1
        "",  # 2
        "",  # 3
        "def bar_get(a, b, *, c):",  # 4
        '    return "v"',  # 5
        "",  # 6
        "",  # 7
        "x = y = bar_get",  # 8
        "",  # 9
        'FAKE = """',  # 10
        "# fake module",  # 11
        "def bar_get(a, b):",  # 12
        '    return "v"',  # 13
        '"""',  # 14
        "",  # 15
        "",  # 16
        "def test_fake(monkeypatch):",  # 17
        '    monkeypatch.setattr(target, "bar_get", bar_get)',  # 18
        "    assert FAKE",  # 19
        "",
    ]
    source = "\n".join(lines)
    assert source.split("\n")[9].startswith('FAKE = """')
    assert source.split("\n")[11] == "def bar_get(a, b):"

    report = test_probe.probe(source, bundle, "slugify")

    found = mismatches(report)
    assert len(found) == 1, found
    assert field(found[0], "line") == 12
    assert (
        field(found[0], "message")
        == "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )