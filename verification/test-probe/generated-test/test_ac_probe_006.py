# hotdocs-criterion: sha256:0680d6f94acfd180a1d43f11881937f36b41a7c5b78fd0b1d6bf31cdc887cef2
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


def test_clean_source_ok_and_temp_dir_removed():
    source = (
        "from slugify import slugify\n"
        "\n"
        "\n"
        "def test_a():\n"
        "    assert slugify(" + repr("A") + ") == " + repr("a") + "\n"
    )
    before = _temp_dirs()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dirs()

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1

    added = after - before
    assert added == set(), "probe left directories in the temp dir: " + repr(sorted(added))


def test_findings_ordered_by_check_and_to_dict_shape():
    source = (
        "import zz_no_such_module_q\n"
        "\n"
        "def test_x():\n"
        "    assert undefined_q == 1\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = list(field(report, "findings"))
    kinds = [field(f, "kind") for f in findings]
    assert "undefined_name" in kinds, repr(findings)
    assert "unknown_import" in kinds, repr(findings)
    undefined_index = kinds.index("undefined_name")
    unknown_index = kinds.index("unknown_import")
    assert undefined_index < unknown_index, repr(findings)

    undefined = findings[undefined_index]
    unknown = findings[unknown_index]
    assert field(undefined, "line") == 4
    assert field(unknown, "line") == 1
    assert field(report, "ok") is False

    data = report.to_dict()
    assert isinstance(data, dict)
    assert isinstance(data["findings"], list)
    assert len(data["findings"]) == len(findings)
    for entry in data["findings"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}
    dict_kinds = [entry["kind"] for entry in data["findings"]]
    assert dict_kinds.index("undefined_name") < dict_kinds.index("unknown_import")


def test_same_line_undefined_names_ordered_by_message():
    source = (
        "# probe ordering\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert zeta_q == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = list(field(report, "findings"))
    undefined = [f for f in findings if field(f, "kind") == "undefined_name"]
    assert len(undefined) == 2, repr(findings)
    assert [field(f, "line") for f in undefined] == [5, 5]
    assert [field(f, "message") for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]
    assert field(report, "ok") is False