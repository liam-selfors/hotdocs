# hotdocs-criterion: sha256:102501314e1129c671f44c0ee9f4d414e8a0c00dd740b25b31e10cb71d35fe07
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KIND = "fake_signature_mismatch"

BUNDLE = {
    "dependency_interfaces": {
        "comp-bar": "bar_get(key: str, default: dict[str, str]) -> str\n"
        "bar_put(*, key: str) -> None"
    }
}

EXPECTED_MESSAGE = "bar_get takes 1 parameters; the interface of comp-bar gives 2"


def mismatches(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "kind") == KIND]


def def_line(source, prefix):
    for index, text in enumerate(source.split("\n"), start=1):
        if text.startswith(prefix):
            return index
    raise AssertionError("no line starting with " + repr(prefix))


TOP_LEVEL_DEFS = [
    "import slugify as target",
    "",
    "",
    "def bar_get(key):",
    "    return " + repr("v"),
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
]


def test_monkeypatch_setattr_installs_mismatched_fake_via_alias():
    lines = TOP_LEVEL_DEFS + [
        "def test_fakes(monkeypatch):",
        "    monkeypatch.setattr(target, " + repr("bar_get") + ", alias)",
        "    monkeypatch.setattr(target, " + repr("bar_put") + ", bar_put)",
        "    assert target.slugify(" + repr("x") + ") == " + repr("x"),
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1, found
    finding = found[0]
    assert field(finding, "line") == def_line(source, "def bar_get(")
    assert field(finding, "message") == EXPECTED_MESSAGE
    assert field(finding, "severity") == "error"


def test_setattr_and_attribute_assignment_install_fakes():
    lines = TOP_LEVEL_DEFS + [
        "def test_fakes(monkeypatch):",
        "    setattr(target, " + repr("bar_get") + ", alias)",
        "    target.bar_put = bar_put",
        "    monkeypatch.setattr(target, " + repr("other") + ", other)",
        "    assert target.slugify(" + repr("x") + ") == " + repr("x"),
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    found = mismatches(report)
    assert len(found) == 1, found
    finding = found[0]
    assert field(finding, "line") == def_line(source, "def bar_get(")
    assert field(finding, "message") == EXPECTED_MESSAGE
    assert field(finding, "severity") == "error"


def test_star_args_fake_satisfies_any_count():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get(*args):",
        "    return " + repr("v"),
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
        "    monkeypatch.setattr(target, " + repr("bar_get") + ", alias)",
        "    monkeypatch.setattr(target, " + repr("bar_put") + ", bar_put)",
        "    assert target.slugify(" + repr("x") + ") == " + repr("x"),
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert mismatches(report) == []


def test_uninstalled_helper_is_never_a_fake():
    lines = [
        "import slugify as target",
        "",
        "",
        "def bar_get():",
        "    return " + repr("k"),
        "",
        "",
        "def test_helper():",
        "    key = bar_get()",
        "    assert target.slugify(key) == key",
        "",
    ]
    source = "\n".join(lines)
    report = test_probe.probe(source, BUNDLE, "slugify")
    assert mismatches(report) == []


def test_fake_module_source_in_string_literal_is_checked():
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
        "    return " + repr("v"),  # 5
        "",  # 6
        "",  # 7
        "x = y = bar_get",  # 8
        "",  # 9
        'FAKE_SOURCE = """',  # 10
        "# fake module for comp-bar",  # 11
        "def bar_get(a, b):",  # 12
        "    return a",  # 13
        '"""',  # 14
        "",  # 15
        "",  # 16
        "def test_fake(monkeypatch):",  # 17
        "    monkeypatch.setattr(target, " + repr("bar_get") + ", bar_get)",
        "    assert FAKE_SOURCE",
        "    assert target.slugify(" + repr("x") + ") == " + repr("x"),
        "",
    ]
    source = "\n".join(lines)
    assert source.split("\n")[11] == "def bar_get(a, b):"
    report = test_probe.probe(source, bundle, "slugify")
    found = mismatches(report)
    assert len(found) == 1, found
    finding = found[0]
    assert field(finding, "line") == 12
    assert field(finding, "message") == (
        "bar_get takes 2 parameters; the interface of comp-bar gives 3"
    )