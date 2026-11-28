# hotdocs-criterion: sha256:1d26e0de1b0bf7523fd64593fdddc8fedb8214e229bcac015511af1bf42343b7
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_syntax_error_gives_one_finding_and_returns_at_once():
    source = "def test_a(:\n    pass\n"
    report = test_probe.probe(source, {}, "slugify")

    assert field(report, "ok") is False

    findings = field(report, "findings")
    assert isinstance(findings, list)
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "syntax_error"
    assert field(finding, "severity") == "error"
    assert field(finding, "line") == 1

    assert field(report, "tests_run") == 0
    assert field(report, "tests_reached") == 0


def test_syntax_error_to_dict_agrees():
    source = "def test_a(:\n    pass\n"
    report = test_probe.probe(source, {}, "slugify")
    if isinstance(report, dict):
        data = report
    else:
        data = report.to_dict()

    assert data["ok"] is False
    assert len(data["findings"]) == 1
    finding = data["findings"][0]
    assert set(finding.keys()) == {"kind", "severity", "line", "message"}
    assert finding["kind"] == "syntax_error"
    assert finding["severity"] == "error"
    assert finding["line"] == 1
    assert data["tests_run"] == 0
    assert data["tests_reached"] == 0