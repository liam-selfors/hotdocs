# hotdocs-criterion: sha256:9ed06bcd9495c637d15833cc2290c257e11720d0c578ed1aed973d81cc2aa21a
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


def _unknown_imports(report):
    return [f for f in field(report, "findings") if field(f, "kind") == "unknown_import"]


def test_list_of_module_names_resolves_every_listed_import():
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])
    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert _unknown_imports(report) == [], findings
    assert field(report, "tests_run") == 1, findings
    assert field(report, "tests_reached") == 1, findings


def test_single_module_name_reports_the_other_import():
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = field(report, "findings")
    assert field(report, "ok") is False, findings
    unknown = _unknown_imports(report)
    assert len(unknown) == 1, findings
    assert field(unknown[0], "line") == 2
    assert field(unknown[0], "message") == "cannot import 'url_tools'"