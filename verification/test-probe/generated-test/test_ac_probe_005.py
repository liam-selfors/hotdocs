# hotdocs-criterion: sha256:0d7e2fcedbca73763a8398feb0e5b51e006d0d4a85691cff9a5b84f3b2022bd4
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _src(*lines):
    return "\n".join(lines) + "\n"


def _findings(report):
    return list(field(report, "findings"))


def test_five_tests_classified():
    source = _src(
        "import pytest",
        "from slugify import slugify",
        "",
        "",
        "def test_reach():",
        "    assert slugify(" + repr("A") + ") == " + repr("a"),
        "",
        "",
        "def test_guarded():",
        "    with pytest.raises(Exception):",
        "        slugify(" + repr("") + ")",
        "",
        "",
        "def test_missing(no_such_fixture):",
        "    assert no_such_fixture is not None",
        "",
        "",
        "def test_constant():",
        "    assert 1 == 1",
        "",
        "",
        "def test_wrong():",
        "    assert int(" + repr("x") + ") == 1",
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 5
    assert field(report, "tests_reached") == 2
    findings = _findings(report)
    assert len(findings) == 2, findings
    bugs = [f for f in findings if field(f, "kind") == "test_bug"]
    vac = [f for f in findings if field(f, "kind") == "vacuous"]
    assert len(bugs) == 1, findings
    assert len(vac) == 1, findings
    assert field(bugs[0], "message").startswith("test_missing: ")
    assert field(vac[0], "severity") == "warn"
    assert field(vac[0], "message") == (
        "test_constant passed without reaching the code under test")
    assert field(report, "ok") is False


def test_fixture_reaching_then_later_setup_assertion_error():
    source = _src(
        "import pytest",
        "from slugify import slugify",
        "",
        "",
        "@pytest.fixture",
        "def run():",
        "    return slugify(" + repr("A") + ")",
        "",
        "",
        "def test_one(run):",
        "    assert run == " + repr("a"),
        "",
        "",
        "def test_two(run):",
        "    assert run == " + repr("a"),
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 2
    assert field(report, "tests_reached") == 1
    assert _findings(report) == []
    assert field(report, "ok") is True


def test_setup_assertion_error_without_prior_reach_is_test_bug():
    source = _src(
        "import pytest",
        "",
        "",
        "@pytest.fixture",
        "def run():",
        "    raise AssertionError()",
        "",
        "",
        "def test_x(run):",
        "    assert run is None",
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message") == (
        'test_x: failed on setup with "AssertionError"')


def test_timeout_gives_probe_timeout():
    source = _src(
        "import time",
        "",
        "",
        "def test_sleep():",
        "    time.sleep(30)",
    )
    report = test_probe.probe(source, {}, "slugify", timeout=2)
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(report, "ok") is False


def test_module_body_raising_is_collection_error():
    source = _src(
        "raise RuntimeError(" + repr("boom") + ")",
        "",
        "",
        "def test_after():",
        "    assert 1 == 1",
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(report, "tests_run") == 0


def test_runtime_name_error_is_test_bug():
    source = _src(
        "def test_x():",
        "    eval(" + repr("undefined_q") + ")",
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")