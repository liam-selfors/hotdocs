# hotdocs-criterion: sha256:0d6053ff4c2389201b037dcb7a2c079b6234864bb2859d1e8ed768f943906949
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


def test_five_tests_classified():
    source = (
        "import pytest\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        "def test_reach():\n"
        "    assert slugify(\"A\") == \"a\"\n"
        "\n"
        "\n"
        "def test_guarded():\n"
        "    with pytest.raises(Exception):\n"
        "        slugify(\"\")\n"
        "\n"
        "\n"
        "def test_missing(no_such_fixture):\n"
        "    assert no_such_fixture\n"
        "\n"
        "\n"
        "def test_constant():\n"
        "    assert 1 == 1\n"
        "\n"
        "\n"
        "def test_wrong():\n"
        "    assert int(\"x\") == 1\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 5
    assert field(report, "tests_reached") == 2
    findings = _findings(report)
    assert len(findings) == 2, findings
    bugs = [f for f in findings if field(f, "kind") == "test_bug"]
    vacuous = [f for f in findings if field(f, "kind") == "vacuous"]
    assert len(bugs) == 1, findings
    assert len(vacuous) == 1, findings
    assert field(bugs[0], "message").startswith("test_missing: ")
    assert field(vacuous[0], "severity") == "warn"
    assert (
        field(vacuous[0], "message")
        == "test_constant passed without reaching the code under test"
    )
    assert field(report, "ok") is False


def test_fixture_reaching_stub_and_later_setup_error():
    source = (
        "import pytest\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def run():\n"
        "    return slugify(\"A\")\n"
        "\n"
        "\n"
        "def test_one(run):\n"
        "    assert run == \"a\"\n"
        "\n"
        "\n"
        "def test_two(run):\n"
        "    assert run == \"a\"\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    assert field(report, "tests_run") == 2
    assert field(report, "tests_reached") == 1
    assert _findings(report) == []
    assert field(report, "ok") is True


def test_setup_assertion_error_without_prior_reach_is_test_bug():
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
        "    assert run\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert (
        field(findings[0], "message")
        == 'test_x: failed on setup with "AssertionError"'
    )


def test_timeout_gives_probe_timeout():
    source = (
        "import time\n"
        "\n"
        "\n"
        "def test_sleep():\n"
        "    time.sleep(30)\n"
    )
    report = test_probe.probe(source, {}, "slugify", timeout=2)
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(report, "ok") is False


def test_module_body_raising_gives_collection_error():
    source = (
        "raise RuntimeError(\"boom\")\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert True\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(report, "tests_run") == 0


def test_runtime_name_error_is_test_bug():
    source = (
        "def test_x():\n"
        "    eval(\"undefined_q\")\n"
    )
    report = test_probe.probe(source, {}, "slugify")
    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")