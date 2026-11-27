# hotdocs-criterion: sha256:a3ddad037f6719fc4c696b4f02f30e5ee6734f1182624870265e78b6a8b16e6d
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def findings_of(report):
    return list(field(report, "findings"))


def test_mixed_suite_classification():
    source = (
        "import pytest\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        "def test_reach():\n"
        "    assert slugify(" + repr("A") + ") == " + repr("a") + "\n"
        "\n"
        "\n"
        "def test_guarded():\n"
        "    with pytest.raises(Exception):\n"
        "        slugify(" + repr("") + ")\n"
        "\n"
        "\n"
        "def test_missing(no_such_fixture):\n"
        "    pass\n"
        "\n"
        "\n"
        "def test_constant():\n"
        "    assert 1 == 1\n"
        "\n"
        "\n"
        "def test_wrong():\n"
        "    assert int(" + repr("x") + ") == 1\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 5
    assert field(report, "tests_reached") == 2
    findings = findings_of(report)
    assert len(findings) == 2, findings
    bugs = [f for f in findings if field(f, "kind") == "test_bug"]
    vacuous = [f for f in findings if field(f, "kind") == "vacuous"]
    assert len(bugs) == 1, findings
    assert len(vacuous) == 1, findings
    assert field(bugs[0], "message").startswith("test_missing: ")
    assert field(vacuous[0], "severity") == "warn"
    assert field(vacuous[0], "message") == (
        "test_constant passed without reaching the code under test"
    )
    assert field(report, "ok") is False


def test_fixture_reaching_stub_then_later_setup_assertion_error():
    source = (
        "import pytest\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def run():\n"
        "    return slugify(" + repr("A") + ")\n"
        "\n"
        "\n"
        "def test_one(run):\n"
        "    assert run == " + repr("a") + "\n"
        "\n"
        "\n"
        "def test_two(run):\n"
        "    assert run == " + repr("a") + "\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 2
    assert field(report, "tests_reached") == 1
    assert findings_of(report) == []
    assert field(report, "ok") is True


def test_setup_assertion_error_with_nothing_reached_before_is_test_bug():
    source = (
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def run():\n"
        "    raise AssertionError()\n"
        "\n"
        "\n"
        "def test_x(run):\n"
        "    assert run is None\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = findings_of(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message") == (
        'test_x: failed on setup with "AssertionError"'
    )


def test_timeout_gives_one_probe_timeout():
    source = (
        "import time\n"
        "\n"
        "\n"
        "def test_sleep():\n"
        "    time.sleep(30)\n"
    )
    report = test_probe.probe(source, {}, "slugify", timeout=2)
    findings = findings_of(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(report, "ok") is False


def test_module_body_error_gives_one_collection_error():
    source = (
        "raise RuntimeError(" + repr("boom") + ")\n"
        "\n"
        "\n"
        "def test_never():\n"
        "    assert True\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = findings_of(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(report, "tests_run") == 0


def test_runtime_name_error_is_test_bug():
    source = (
        "def test_x():\n"
        "    eval(" + repr("undefined_q") + ")\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = findings_of(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")