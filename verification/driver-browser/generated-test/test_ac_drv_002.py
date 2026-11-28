# hotdocs-criterion: sha256:60f4d9028e5cf1a40269c4d3fda0987fda6399db2443cdb835c8ecb66d7a093d
import re
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    ENV_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(ENV_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


PAGE_HTML = (
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
    "    var item = items[i];\n"
    "    item.style.display = item.textContent.indexOf(q) === -1 ? 'none' : '';\n"
    "  }\n"
    "});\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def write_page(tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")
    return page_path


def test_ac_drv_002_find_actions_and_reads(provisioned, tmp_path):
    page_path = write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
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
    page_path = write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        expected = "no element matches role=button name=\"Remove\""
        with pytest.raises(Exception, match=re.escape(expected)) as excinfo:
            page.find(role="button", name="Remove").click()
        assert isinstance(excinfo.value, driver_browser.BrowserError)
        assert str(excinfo.value) == expected
    finally:
        session.close()


def test_ac_drv_002_two_selectors_raises(provisioned, tmp_path):
    page_path = write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        expected = "find takes exactly one selector"
        with pytest.raises(Exception, match=re.escape(expected)) as excinfo:
            element = page.find(css="li", role="button")
            element.count()
        assert isinstance(excinfo.value, driver_browser.BrowserError)
        assert str(excinfo.value) == expected
    finally:
        session.close()