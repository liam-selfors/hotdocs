# hotdocs-criterion: sha256:15bdf9eba64013b2c5dabd62e07a3482639deffd062052ca8d4bf8ec8183f0a5
import importlib.util

import test_probe

import pytest


SOURCE = (
    "import slugify\n"
    "import url_tools\n"
    "\n"
    "def test_a():\n"
    "    assert url_tools.join(slugify.slugify('A')) == 'a'\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _require_url_tools_absent():
    if importlib.util.find_spec("url_tools") is not None:
        pytest.skip("url_tools is importable in this environment")


def test_both_names_in_module_name_resolve_and_reach():
    _require_url_tools_absent()
    report = test_probe.probe(SOURCE, {}, ["slugify", "url_tools"])
    findings = field(report, "findings")
    assert field(report, "ok") is True, findings
    assert not [f for f in findings if field(f, "kind") == "unknown_import"], findings
    assert field(report, "tests_run") == 1
    assert field(report, "tests_reached") == 1


def test_missing_name_reports_one_unknown_import():
    _require_url_tools_absent()
    report = test_probe.probe(SOURCE, {}, "slugify")
    findings = field(report, "findings")
    assert field(report, "ok") is False, findings
    unknown = [f for f in findings if field(f, "kind") == "unknown_import"]
    assert len(unknown) == 1, findings
    assert field(unknown[0], "line") == 2
    assert field(unknown[0], "message") == "cannot import 'url_tools'"