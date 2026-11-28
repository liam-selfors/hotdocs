# hotdocs-criterion: sha256:364c44b04d754d77e212f9f6d1a046abc74477d0f42f206272cda6961a033a26
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


def test_clean_source_reaches_and_leaves_no_temp_dir():
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
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1
    assert after - before == set()


def test_findings_ordered_by_check_and_to_dict_shape():
    source = "import zz_no_such_module_q\n\ndef test_x():\n    assert undefined_q == 1\n"
    report = test_probe.probe(source, {}, "slugify")

    findings = list(field(report, "findings"))
    kinds = [f["kind"] for f in findings]
    assert "undefined_name" in kinds
    assert "unknown_import" in kinds
    undefined_index = kinds.index("undefined_name")
    unknown_index = kinds.index("unknown_import")
    assert unknown_index > undefined_index
    assert findings[undefined_index]["line"] == 4
    assert findings[unknown_index]["line"] == 1
    assert field(report, "ok") is False

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    entries = as_dict["findings"]
    assert isinstance(entries, list)
    assert len(entries) == len(findings)
    for entry in entries:
        assert set(entry.keys()) == {"kind", "severity", "line", "message"}


def test_same_line_findings_ordered_by_message():
    source = (
        "import slugify\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert zeta_q == alpha_q\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = list(field(report, "findings"))
    undefined = [f for f in findings if f["kind"] == "undefined_name"]
    assert [f["message"] for f in undefined] == [
        "undefined name 'alpha_q'",
        "undefined name 'zeta_q'",
    ]
    assert all(f["line"] == 5 for f in undefined)
    assert field(report, "ok") is False