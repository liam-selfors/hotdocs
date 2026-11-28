# hotdocs-criterion: sha256:4d2a2fff985ba063dcabb61650e7d594c1f215a2853dd6615cb393b32591feeb
import re
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"


PAGE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>AC-DRV-002</title></head>\n"
    "<body>\n"
    "<button type=\"button\" id=\"add\">Add</button>\n"
    "<label for=\"filter\">Filter</label>\n"
    "<input id=\"filter\" type=\"text\">\n"
    "<ul id=\"items\">\n"
    "<li>alpha</li>\n"
    "<li>beta</li>\n"
    "</ul>\n"
    "<script>\n"
    "var list = document.getElementById('items');\n"
    "var filter = document.getElementById('filter');\n"
    "document.getElementById('add').addEventListener('click', function () {\n"
    "  var li = document.createElement('li');\n"
    "  li.textContent = 'gamma';\n"
    "  list.appendChild(li);\n"
    "});\n"
    "filter.addEventListener('input', function () {\n"
    "  var q = filter.value;\n"
    "  var items = list.querySelectorAll('li');\n"
    "  for (var i = 0; i < items.length; i++) {\n"
    "    var it = items[i];\n"
    "    it.style.display = it.textContent.indexOf(q) === -1 ? 'none' : '';\n"
    "  }\n"
    "});\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(ENV_ROOT)
    ok = result["ok"] if isinstance(result, dict) else getattr(result, "ok")
    if not ok:
        reason = result["reason"] if isinstance(result, dict) else getattr(result, "reason")
        pytest.fail("provision failed: " + str(reason))
    return ENV_ROOT


def _write_page(tmp_path):
    path = tmp_path / "index.html"
    path.write_text(PAGE, encoding="utf-8")
    return path


def test_ac_drv_002_find_reads_and_actions(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        page.find(role="button", name="Add").click()
        page.find(label="Filter").fill("al")

        assert page.find(css="li").count() == 3
        assert page.find(css="li").texts() == ["alpha", "beta", "gamma"]
        assert page.find(text="alpha").visible() is True
        assert page.find(text="beta").visible() is False
        assert page.console_errors() == []
    finally:
        session.close()


def test_ac_drv_002_no_match_raises(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        expected = "no element matches role=button name=\"Remove\""
        with pytest.raises(driver_browser.BrowserError, match="^" + re.escape(expected) + "$"):
            page.find(role="button", name="Remove").click()
    finally:
        session.close()


def test_ac_drv_002_two_selectors_raise(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        expected = "find takes exactly one selector"
        with pytest.raises(driver_browser.BrowserError, match="^" + re.escape(expected) + "$"):
            page.find(css="li", role="listitem")
    finally:
        session.close()