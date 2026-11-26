# hotdocs-criterion: sha256:cf1883068ba88da000bce7aacc5a4eed91d748135c37ca10f2f728940f9ed471
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_probe_001_syntax_error_returns_single_finding():
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


def test_ac_probe_001_to_dict_agrees():
    source = "def test_a(:\n    pass\n"
    report = test_probe.probe(source, {}, "slugify")
    if isinstance(report, dict):
        data = report
    else:
        data = report.to_dict()
    assert data["ok"] is False
    assert len(data["findings"]) == 1
    assert data["findings"][0]["kind"] == "syntax_error"
    assert data["findings"][0]["severity"] == "error"
    assert data["findings"][0]["line"] == 1
    assert data["tests_run"] == 0
    assert data["tests_reached"] == 0