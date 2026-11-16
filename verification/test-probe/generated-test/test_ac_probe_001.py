import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = "def test_a(:\n    pass\n"


def test_syntax_error_gives_single_finding_and_no_stub_run():
    report = test_probe.probe(SOURCE, {}, "slugify")

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


def test_syntax_error_report_to_dict_agrees():
    report = test_probe.probe(SOURCE, {}, "slugify")
    if isinstance(report, dict):
        data = report
    else:
        data = report.to_dict()

    assert data["ok"] is False
    assert len(data["findings"]) == 1
    only = data["findings"][0]
    assert only["kind"] == "syntax_error"
    assert only["severity"] == "error"
    assert only["line"] == 1
    assert data["tests_run"] == 0
    assert data["tests_reached"] == 0