# hotdocs-criterion: sha256:df28d539535ac4a6a4a9a635bc38f81c10c46c011f0ba0e2d4d6a34966da1a29
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


def test_classifies_each_testcase_of_the_stub_run():
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
        "    assert no_such_fixture is not None\n"
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


def test_timeout_gives_one_probe_timeout_finding():
    source = (
        "import time\n"
        "\n"
        "\n"
        "def test_slow():\n"
        "    time.sleep(30)\n"
    )
    report = test_probe.probe(source, {}, "slugify", timeout=2)

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(report, "ok") is False


def test_module_level_error_gives_one_collection_error():
    source = (
        "raise RuntimeError(\"boom\")\n"
        "\n"
        "\n"
        "def test_a():\n"
        "    assert True\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(report, "tests_run") == 0


def test_runtime_name_error_is_test_bug():
    source = (
        "from slugify import slugify\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    eval(\"undefined_q\")\n"
        "    assert slugify(\"A\") == \"a\"\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")