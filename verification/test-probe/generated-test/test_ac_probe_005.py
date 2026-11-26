# hotdocs-criterion: sha256:18e18131470557210c1e9a449a641c208d8ee7eb277ccf0c16e84903dde3c151
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE_FIVE = (
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

SOURCE_SHARED_FIXTURE = (
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

SOURCE_ASSERTION_FIXTURE = (
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

SOURCE_SLEEP = (
    "import time\n"
    "\n"
    "\n"
    "def test_sleep():\n"
    "    time.sleep(30)\n"
)

SOURCE_MODULE_RAISES = (
    "raise RuntimeError(\"boom\")\n"
    "\n"
    "\n"
    "def test_x():\n"
    "    assert True\n"
)

SOURCE_EVAL_NAME_ERROR = (
    "def test_x():\n"
    "    value = eval(\"undefined_q\")\n"
    "    assert value == 1\n"
)


def kinds(report):
    return [field(f, "kind") for f in field(report, "findings")]


def test_five_tests_classified():
    report = test_probe.probe(SOURCE_FIVE, {}, "slugify")
    assert field(report, "tests_run") == 5
    assert field(report, "tests_reached") == 2
    findings = list(field(report, "findings"))
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


def test_shared_fixture_reaching_stub_no_findings():
    report = test_probe.probe(SOURCE_SHARED_FIXTURE, {}, "slugify")
    assert field(report, "tests_run") == 2
    assert field(report, "tests_reached") == 1
    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True


def test_assertion_setup_without_prior_reach_is_test_bug():
    report = test_probe.probe(SOURCE_ASSERTION_FIXTURE, {}, "slugify")
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message") == (
        'test_x: failed on setup with "AssertionError"'
    )


def test_timeout_gives_probe_timeout():
    report = test_probe.probe(SOURCE_SLEEP, {}, "slugify", timeout=2)
    assert kinds(report) == ["probe_timeout"]
    assert field(report, "ok") is False


def test_module_body_raising_gives_collection_error():
    report = test_probe.probe(SOURCE_MODULE_RAISES, {}, "slugify")
    assert kinds(report) == ["collection_error"]
    assert field(report, "tests_run") == 0


def test_eval_name_error_is_test_bug():
    report = test_probe.probe(SOURCE_EVAL_NAME_ERROR, {}, "slugify")
    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError")