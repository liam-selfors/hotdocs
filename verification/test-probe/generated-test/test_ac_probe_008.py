# hotdocs-criterion: sha256:09275d2c92ad9144749756febb6fc773fc1e8e7b07894de08687c7fb14841024
import test_probe


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FIRST_SOURCE = (
    "def test_filter(asset_runner):\n"
    "    run = asset_runner('static/app.js')\n"
    "    assert run('filterNodes', [[], 'gen']) == []\n"
)

LOOKUP_SOURCE = (
    "def test_lookup(asset_runner):\n"
    "    run = asset_runner('static/other.js')\n"
    "    assert callable(run)\n"
)


def test_calling_declared_asset_reaches_code_under_test():
    report = test_probe.probe(FIRST_SOURCE, {}, "app")
    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_only_looking_up_asset_is_vacuous():
    report = test_probe.probe(LOOKUP_SOURCE, {}, "app")
    assert field(report, "ok") is True
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 0
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "vacuous"
    assert field(finding, "severity") == "warn"
    assert field(finding, "message") == (
        "test_lookup passed without reaching the code under test"
    )


def test_gen_prefixed_path_is_undeclared_test_bug():
    source = FIRST_SOURCE.replace("'static/app.js'", "'gen/app/static/app.js'")
    assert "'gen/app/static/app.js'" in source
    report = test_probe.probe(source, {}, "app")
    assert field(report, "ok") is False
    assert field(report, "tests_reached") == 0
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "test_bug"
    assert field(finding, "severity") == "error"
    message = field(finding, "message")
    assert message.startswith("test_filter: ")
    assert "HotdocsProbeUndeclaredAsset" in message
    assert "is not a declared asset path" in message


def test_path_missing_from_assets_list_is_test_bug():
    report = test_probe.probe(FIRST_SOURCE, {}, "app", assets=["static/other.js"])
    assert field(report, "ok") is False
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "kind") == "test_bug"
    assert "'static/app.js' is not a declared asset path" in field(finding, "message")


def test_path_in_assets_list_reaches_code_under_test():
    report = test_probe.probe(FIRST_SOURCE, {}, "app", assets=["static/app.js"])
    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []
    assert field(report, "tests_reached") == 1