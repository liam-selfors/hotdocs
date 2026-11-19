# hotdocs-criterion: sha256:a1c9c6977bc103100c233e2f8d464a65051f67fd5cec6b2281e2589f86a1d7d5
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_probe_001_syntax_error_gives_one_finding_and_no_run():
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