# hotdocs-criterion: sha256:6995ae401acad17e293ef4fdbad1f1912d2ac94a8c1322c6c3f31c8cff164b27
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_asset_runner_call_reaches_code_under_test():
    source = (
        "def test_filter(asset_runner):\n"
        "    run = asset_runner('static/app.js')\n"
        "    assert run('filterNodes', [[], 'gen']) == []\n"
    )
    report = test_probe.probe(source, {}, "app")

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_asset_runner_lookup_only_is_vacuous():
    source = (
        "def test_lookup(asset_runner):\n"
        "    run = asset_runner('static/other.js')\n"
        "    assert callable(run)\n"
    )
    report = test_probe.probe(source, {}, "app")

    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 0

    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "vacuous"
    assert field(finding, "severity") == "warn"
    assert (
        field(finding, "message")
        == "test_lookup passed without reaching the code under test"
    )