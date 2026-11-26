# hotdocs-criterion: sha256:de47683241619f6b3e29aafe268e2cb3ea1155dcb9d69b9b987db2a7e72be255
import test_probe


TEST_SOURCE = (
    "def test_opens_page(browser):\n"
    "    browser.open(\"x.html\")\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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