# hotdocs-criterion: sha256:43b5f2179bcadfb5f1866765e3101df243ffc90841d2f8e9a4645388cfc860b8
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


REACHING_SOURCE = (
    "def test_filter(asset_runner):\n"
    "    run = asset_runner('static/app.js')\n"
    "    assert run('filterNodes', [[], 'gen']) == []\n"
)

NON_REACHING_SOURCE = (
    "def test_lookup(asset_runner):\n"
    "    run = asset_runner('static/other.js')\n"
    "    assert callable(run)\n"
)


def test_calling_asset_runner_callable_reaches_code_under_test():
    report = test_probe.probe(REACHING_SOURCE, {}, "app")
    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert list(findings) == [], findings
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_only_taking_asset_runner_is_vacuous():
    report = test_probe.probe(NON_REACHING_SOURCE, {}, "app")
    findings = list(field(report, "findings"))
    assert field(report, "ok") is True, findings
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 0
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "kind") == "vacuous"
    assert field(finding, "severity") == "warn"
    assert field(finding, "message") == (
        "test_lookup passed without reaching the code under test"
    )