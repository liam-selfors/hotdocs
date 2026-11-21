# hotdocs-criterion: sha256:06d2c47c6402876cc8398af009d2492f2254d62c2c890d7cc2b77ebe8999454f
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


def _findings(report):
    return list(field(report, "findings"))


def test_both_module_names_resolve_imports_and_stub_run_reaches():
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])
    findings = _findings(report)
    assert field(report, "ok") is True, findings
    assert not [f for f in findings if field(f, "kind") == "unknown_import"], findings
    assert field(report, "tests_run") == 1, findings
    assert field(report, "tests_reached") == 1, findings


def test_single_module_name_reports_other_import_unknown():
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = _findings(report)
    assert field(report, "ok") is False, findings
    unknown = [f for f in findings if field(f, "kind") == "unknown_import"]
    assert len(unknown) == 1, findings
    finding = unknown[0]
    assert field(finding, "line") == 2
    assert field(finding, "message") == "cannot import 'url_tools'"
    assert field(finding, "severity") == "error"