import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "import os\n"
    "from slugify import slugify\n"
    "\n"
    "def test_a():\n"
    "    assert slugify(tmp_dir) == 'x'\n"
)


def test_ac_probe_002_undefined_name_is_only_finding():
    report = test_probe.probe(SOURCE, {}, "slugify")

    assert field(report, "ok") is False

    findings = field(report, "findings")
    assert isinstance(findings, list)
    assert len(findings) == 1, findings

    finding = findings[0]
    assert field(finding, "kind") == "undefined_name"
    assert field(finding, "severity") == "error"
    assert field(finding, "line") == 5
    assert field(finding, "message") == "undefined name 'tmp_dir'"


def test_ac_probe_002_to_dict_agrees():
    report = test_probe.probe(SOURCE, {}, "slugify")
    as_dict = report.to_dict()

    assert as_dict["ok"] is False
    assert as_dict["findings"] == [
        {
            "kind": "undefined_name",
            "severity": "error",
            "line": 5,
            "message": "undefined name 'tmp_dir'",
        }
    ]