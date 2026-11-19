# hotdocs-criterion: sha256:05dc45b644e384ed9d6ae5ed1d843ef32726da26bfd76f84003db1a4ed5af55d
import os
import tempfile

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _temp_dir_names():
    root = tempfile.gettempdir()
    names = set()
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root, name)):
            names.add(name)
    return names


def test_clean_probe_ok_and_leaves_no_temp_directory():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_lowercases():\n"
        "    assert slugify.slugify(\"A\") == \"a\"\n"
    )
    before = _temp_dir_names()
    report = test_probe.probe(source, {}, "slugify")
    after = _temp_dir_names()

    assert field(report, "ok") is True
    assert field(report, "findings") == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1
    assert after - before == set()


def test_findings_ordered_by_check_and_to_dict_shape():
    source = (
        "import zz_no_such_module_hotdocs_qq\n"
        "\n"
        "def test_something():\n"
        "    assert undefined_thing_q == 1\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = field(report, "findings")
    kinds = [f["kind"] for f in findings]

    assert "undefined_name" in kinds
    assert "unknown_import" in kinds

    undefined = [
        i for i, f in enumerate(findings)
        if f["kind"] == "undefined_name" and f["line"] == 4
    ]
    unknown = [
        i for i, f in enumerate(findings)
        if f["kind"] == "unknown_import" and f["line"] == 1
    ]
    assert undefined, findings
    assert unknown, findings
    assert max(undefined) < min(unknown)

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    assert isinstance(as_dict["findings"], list)
    assert len(as_dict["findings"]) == len(findings)
    for entry in as_dict["findings"]:
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


def test_same_line_findings_ordered_by_message():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    assert zeta_q == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = field(report, "findings")
    undefined = [f for f in findings if f["kind"] == "undefined_name"]

    assert [f["line"] for f in undefined] == [5, 5]
    assert [f["message"] for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]