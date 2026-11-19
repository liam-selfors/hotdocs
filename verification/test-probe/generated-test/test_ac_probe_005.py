# hotdocs-criterion: sha256:187b9cedcccf32fb90b00e4b6804c495079e1192e84f8b65a1f44ee10ef3506e
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


def test_ac_probe_005_classifies_five_tests():
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

    test_bugs = [f for f in findings if field(f, "kind") == "test_bug"]
    vacuous = [f for f in findings if field(f, "kind") == "vacuous"]
    assert len(test_bugs) == 1, findings
    assert len(vacuous) == 1, findings

    assert field(test_bugs[0], "message").startswith("test_missing: ")
    assert field(test_bugs[0], "severity") == "error"

    assert field(vacuous[0], "severity") == "warn"
    assert (
        field(vacuous[0], "message")
        == "test_constant passed without reaching the code under test"
    )

    assert field(report, "ok") is False


def test_ac_probe_005_timeout():
    source = (
        "import time\n"
        "\n"
        "\n"
        "def test_sleeps():\n"
        "    time.sleep(30)\n"
    )
    report = test_probe.probe(source, {}, "slugify", timeout=2)

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(findings[0], "severity") == "error"
    assert field(report, "ok") is False


def test_ac_probe_005_collection_error():
    source = (
        "raise RuntimeError(\"boom\")\n"
        "\n"
        "\n"
        "def test_after():\n"
        "    assert True\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(findings[0], "severity") == "error"
    assert field(report, "tests_run") == 0
    assert field(report, "ok") is False


def test_ac_probe_005_runtime_name_error():
    source = (
        "def test_x():\n"
        "    eval(\"undefined_q\")\n"
    )
    report = test_probe.probe(source, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")
    assert field(report, "ok") is False