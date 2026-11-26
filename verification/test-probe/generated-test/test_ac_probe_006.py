# hotdocs-criterion: sha256:dd03da6917268b699be7818fe18f71cb96517723268ede69400b5c16dabf6404
import os
import tempfile

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _temp_dirs():
    root = tempfile.gettempdir()
    names = set()
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root, name)):
            names.add(name)
    return names


def test_clean_source_reaches_and_leaves_no_temp_dir():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_lower():\n"
        "    assert slugify.slugify(" + repr("A") + ") == " + repr("a") + "\n"
    )
    before = _temp_dirs()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dirs()

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1
    added = after - before
    assert added == set(), "probe left temporary directories: " + repr(sorted(added))


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

    assert "undefined_name" in kinds
    assert "unknown_import" in kinds
    undefined_index = kinds.index("undefined_name")
    unknown_index = kinds.index("unknown_import")
    assert undefined_index < unknown_index
    assert field(findings[undefined_index], "line") == 4
    assert field(findings[unknown_index], "line") == 1
    assert field(report, "ok") is False
    assert field(report, "tests_run") == 0
    assert field(report, "tests_reached") == 0

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    assert isinstance(as_dict["findings"], list)
    assert len(as_dict["findings"]) == len(findings)
    for entry in as_dict["findings"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


def test_same_check_same_line_ordered_by_message():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert zeta_q == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = list(field(report, "findings"))
    undefined = [f for f in findings if field(f, "kind") == "undefined_name"]

    assert len(undefined) == 2
    assert [field(f, "line") for f in undefined] == [5, 5]
    assert [field(f, "message") for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]
    assert field(report, "ok") is False