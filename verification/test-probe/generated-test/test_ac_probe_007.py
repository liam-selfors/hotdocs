import test_probe


SOURCE = (
    "import slugify\n"
    "import url_tools\n"
    "\n"
    "def test_a():\n"
    "    assert url_tools.join(slugify.slugify('A')) == 'a'\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def finding_field(finding, name):
    return finding[name] if isinstance(finding, dict) else getattr(finding, name)


def test_both_realizing_modules_resolve_and_stub_is_reached():
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])
    findings = list(field(report, "findings"))
    kinds = [finding_field(f, "kind") for f in findings]
    assert field(report, "ok") is True, findings
    assert "unknown_import" not in kinds, findings
    assert field(report, "tests_run") == 1, findings
    assert field(report, "tests_reached") == 1, findings


def test_name_outside_module_name_is_unknown_import():
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = list(field(report, "findings"))
    assert field(report, "ok") is False, findings
    unknown = [f for f in findings if finding_field(f, "kind") == "unknown_import"]
    assert len(unknown) == 1, findings
    only = unknown[0]
    assert finding_field(only, "line") == 2
    assert finding_field(only, "message") == "cannot import 'url_tools'"
    assert finding_field(only, "severity") == "error"