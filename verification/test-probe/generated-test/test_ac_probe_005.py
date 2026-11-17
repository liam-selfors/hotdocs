import textwrap

import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _findings(report):
    return list(field(report, "findings"))


SOURCE_MIXED = textwrap.dedent(
    '''
    import pytest
    from slugify import slugify


    def test_reach():
        assert slugify("A") == "a"


    def test_guarded():
        with pytest.raises(Exception):
            slugify("")


    def test_missing(no_such_fixture):
        assert no_such_fixture is not None


    def test_constant():
        assert 1 == 1


    def test_wrong():
        assert int("x") == 1
    '''
).lstrip()


SOURCE_SLEEP = textwrap.dedent(
    '''
    import time


    def test_sleeps():
        time.sleep(30)
        assert True
    '''
).lstrip()


SOURCE_COLLECTION_ERROR = textwrap.dedent(
    '''
    raise RuntimeError("boom")


    def test_after():
        assert True
    '''
).lstrip()


SOURCE_HIDDEN_NAME_ERROR = textwrap.dedent(
    '''
    from slugify import slugify


    def test_x():
        eval("undefined_q")
        assert slugify("A") == "a"
    '''
).lstrip()


def test_mixed_tests_are_classified():
    report = test_probe.probe(SOURCE_MIXED, {}, "slugify")

    assert field(report, "tests_run") == 5
    assert field(report, "tests_reached") == 2

    findings = _findings(report)
    assert len(findings) == 2, findings

    test_bugs = [f for f in findings if field(f, "kind") == "test_bug"]
    vacuous = [f for f in findings if field(f, "kind") == "vacuous"]
    assert len(test_bugs) == 1, findings
    assert len(vacuous) == 1, findings

    assert field(test_bugs[0], "message").startswith("test_missing: "), test_bugs[0]

    assert field(vacuous[0], "severity") == "warn"
    assert (
        field(vacuous[0], "message")
        == "test_constant passed without reaching the code under test"
    )

    assert field(report, "ok") is False


def test_long_running_test_times_out():
    report = test_probe.probe(SOURCE_SLEEP, {}, "slugify", timeout=2)

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "probe_timeout"
    assert field(report, "ok") is False


def test_module_body_error_is_collection_error():
    report = test_probe.probe(SOURCE_COLLECTION_ERROR, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "collection_error"
    assert field(report, "tests_run") == 0


def test_runtime_name_error_is_test_bug():
    report = test_probe.probe(SOURCE_HIDDEN_NAME_ERROR, {}, "slugify")

    findings = _findings(report)
    assert len(findings) == 1, findings
    assert field(findings[0], "kind") == "test_bug"
    assert field(findings[0], "message").startswith("test_x: NameError"), findings[0]