# hotdocs-criterion: sha256:5850498fad024581923be995997aed0bde502b2d422e8914fc05df2331d10c5d
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_probe_001_syntax_error_stops_probe():
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