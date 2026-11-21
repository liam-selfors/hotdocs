# hotdocs-criterion: sha256:5026d96bd0c5b35a4f6b49b48040007aee9bfc1984ff7a5ab95d8e9f1a75dbee
import os
import tempfile

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _temp_dirs():
    base = tempfile.gettempdir()
    names = set()
    for name in os.listdir(base):
        if os.path.isdir(os.path.join(base, name)):
            names.add(name)
    return names


def test_reaching_test_is_ok_and_leaves_no_temp_directory():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_lowercases():\n"
        "    assert slugify.slugify(" + repr("A") + ") == " + repr("a") + "\n"
    )
    before = _temp_dirs()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dirs()

    assert field(report, "ok") is True
    assert field(report, "findings") == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1
    added = after - before
    assert added == set(), "probe left temporary directories: " + repr(sorted(added))


def test_findings_ordered_by_check_and_to_dict_shape():
    source = (
        "import zz_hotdocs_no_such_module_q\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    assert undefined_thing_q == 1\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = field(report, "findings")
    kinds = [field(f, "kind") for f in findings]

    assert "undefined_name" in kinds
    assert "unknown_import" in kinds
    undefined_index = kinds.index("undefined_name")
    unknown_index = kinds.index("unknown_import")
    assert undefined_index < unknown_index

    undefined = findings[undefined_index]
    unknown = findings[unknown_index]
    assert field(undefined, "line") == 5 or field(undefined, "line") == 4
    assert field(unknown, "line") == 1

    data = report.to_dict()
    assert isinstance(data, dict)
    assert isinstance(data["findings"], list)
    assert len(data["findings"]) == len(findings)
    for entry in data["findings"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


def test_same_line_undefined_names_ordered_by_message():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    assert zeta_q == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = field(report, "findings")
    undefined = [f for f in findings if field(f, "kind") == "undefined_name"]

    assert len(undefined) == 2
    for f in undefined:
        assert field(f, "line") == 5
    messages = [field(f, "message") for f in undefined]
    assert messages == ["undefined name 'alpha_q'", "undefined name 'zeta_q'"]
    assert field(report, "ok") is False