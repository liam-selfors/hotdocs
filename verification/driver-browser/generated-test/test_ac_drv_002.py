# hotdocs-criterion: sha256:ae995591bcddb340d57477dbdb2d8d885281e46f23bcab9417dd7d1f06b28731
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PAGE_HTML = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>AC-DRV-002</title></head>\n"
    "<body>\n"
    "<button type=\"button\" id=\"add\">Add</button>\n"
    "<label for=\"filter\">Filter</label>\n"
    "<input type=\"text\" id=\"filter\">\n"
    "<ul id=\"items\">\n"
    "<li>alpha</li>\n"
    "<li>beta</li>\n"
    "</ul>\n"
    "<script>\n"
    "document.getElementById('add').addEventListener('click', function () {\n"
    "  var li = document.createElement('li');\n"
    "  li.textContent = 'gamma';\n"
    "  document.getElementById('items').appendChild(li);\n"
    "});\n"
    "document.getElementById('filter').addEventListener('input', function (e) {\n"
    "  var v = e.target.value;\n"
    "  var items = document.querySelectorAll('#items li');\n"
    "  for (var i = 0; i < items.length; i++) {\n"
    "    items[i].hidden = items[i].textContent.indexOf(v) === -1;\n"
    "  }\n"
    "});\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


@pytest.fixture(scope="session")
def provisioned():
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def _write_page(tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")
    return page_path


def test_add_filter_and_reads(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
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


def test_click_missing_element_raises(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        with pytest.raises(
            driver_browser.BrowserError,
            match=re.escape('no element matches role=button name="Remove"'),
        ):
            page.find(role="button", name="Remove").click()
    finally:
        session.close()


def test_find_with_two_selectors_raises(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        with pytest.raises(
            driver_browser.BrowserError,
            match=re.escape("find takes exactly one selector"),
        ):
            page.find(css="li", role="button")
    finally:
        session.close()