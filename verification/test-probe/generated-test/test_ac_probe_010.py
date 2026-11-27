# hotdocs-criterion: sha256:b7f128d19166ccdd3fab53e7005211ad5c0e4c4af9f4e8fa14f1d394ff7416e8
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TEST_SOURCE = (
    "def test_opens_page(browser):\n"
    "    browser.open(" + repr("x.html") + ")\n"
)


def test_declared_driver_fixture_reaches_code_under_test():
    report = test_probe.probe(TEST_SOURCE, {}, "slugify", drivers=["browser"])
    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert list(findings) == [], findings
    assert field(report, "tests_reached") == 1


def test_undeclared_driver_fixture_is_test_bug():
    report = test_probe.probe(TEST_SOURCE, {}, "slugify")
    findings = list(field(report, "findings"))
    assert field(report, "ok") is False, findings
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug", findings