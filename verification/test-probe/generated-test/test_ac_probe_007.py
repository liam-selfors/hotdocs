# hotdocs-criterion: sha256:75500ded4079e0934598351480012655bfcd8cbe8154b5b7aa1ecc2a4dfcfcc1
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


def test_both_realizing_modules_resolve_and_stub_run_reaches():
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])

    assert field(report, "ok") is True
    assert _unknown_imports(report) == []
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_single_module_name_reports_other_import_unknown():
    report = test_probe.probe(SOURCE, {}, "slugify")

    assert field(report, "ok") is False
    unknown = _unknown_imports(report)
    assert len(unknown) == 1
    finding = unknown[0]
    assert field(finding, "line") == 2
    assert field(finding, "message") == "cannot import 'url_tools'"
    assert field(finding, "severity") == "error"