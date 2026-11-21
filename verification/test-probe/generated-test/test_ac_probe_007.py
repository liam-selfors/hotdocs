# hotdocs-criterion: sha256:6e06364473e66e4720e9586c98f7e8242f4525d73ce91dba96c8dd0e6ab4d559
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


def test_list_module_name_resolves_every_name():
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])
    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert not [f for f in findings if field(f, "kind") == "unknown_import"], findings
    assert field(report, "tests_run") == 1, findings
    assert field(report, "tests_reached") == 1, findings


def test_string_module_name_reports_other_import():
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = field(report, "findings")
    assert field(report, "ok") is False, findings
    unknown = [f for f in findings if field(f, "kind") == "unknown_import"]
    assert len(unknown) == 1, findings
    assert field(unknown[0], "line") == 2
    assert field(unknown[0], "message") == "cannot import 'url_tools'"