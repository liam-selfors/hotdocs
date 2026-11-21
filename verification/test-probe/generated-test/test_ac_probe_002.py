# hotdocs-criterion: sha256:896f45228300dbb95afec603ebba0b4fa1138811287c76851e26014cbf2f1faf
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


def test_undefined_name_is_the_only_finding():
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


def test_unused_import_gives_no_finding():
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = field(report, "findings")
    kinds = [field(f, "kind") for f in findings]
    assert kinds == ["undefined_name"]
    messages = [field(f, "message") for f in findings]
    assert not any("os" in m and "imported" in m for m in messages)


def test_to_dict_agrees():
    report = test_probe.probe(SOURCE, {}, "slugify")
    if hasattr(report, "to_dict"):
        d = report.to_dict()
        assert d["ok"] is False
        assert d["findings"] == [
            {
                "kind": "undefined_name",
                "severity": "error",
                "line": 5,
                "message": "undefined name 'tmp_dir'",
            }
        ]