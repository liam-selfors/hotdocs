# hotdocs-criterion: sha256:9bde1d37a7d632108c15a390b69e8aa954fb357ffbc8311d92b1ee230c9272f9
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


PAGE_HTML = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>AC-DRV-002</title>\n"
    "</head>\n"
    "<body>\n"
    "<button type=\"button\" id=\"add\">Add</button>\n"
    "<label for=\"filter\">Filter</label>\n"
    "<input id=\"filter\" type=\"text\">\n"
    "<ul id=\"items\">\n"
    "<li>alpha</li>\n"
    "<li>beta</li>\n"
    "</ul>\n"
    "<script>\n"
    "(function () {\n"
    "  var list = document.getElementById('items');\n"
    "  var add = document.getElementById('add');\n"
    "  var filter = document.getElementById('filter');\n"
    "  add.addEventListener('click', function () {\n"
    "    var li = document.createElement('li');\n"
    "    li.textContent = 'gamma';\n"
    "    list.appendChild(li);\n"
    "  });\n"
    "  filter.addEventListener('input', function () {\n"
    "    var needle = filter.value;\n"
    "    var items = list.querySelectorAll('li');\n"
    "    for (var i = 0; i < items.length; i++) {\n"
    "      var item = items[i];\n"
    "      if (item.textContent.indexOf(needle) === -1) {\n"
    "        item.style.display = 'none';\n"
    "      } else {\n"
    "        item.style.display = '';\n"
    "      }\n"
    "    }\n"
    "  });\n"
    "})();\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("browser provisioning failed: " + str(field(result, "reason")))
    return result


def _write_page(tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")
    return page_path


def test_find_reads_actions_and_console(provisioned, tmp_path):
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


def test_no_match_raises_browser_error(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        expected = 'no element matches role=button name="Remove"'
        with pytest.raises(driver_browser.BrowserError, match=re.escape(expected)) as info:
            page.find(role="button", name="Remove").click()
        assert str(info.value) == expected
    finally:
        session.close()


def test_find_with_two_selectors_raises_browser_error(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        expected = "find takes exactly one selector"
        with pytest.raises(driver_browser.BrowserError, match=re.escape(expected)) as info:
            page.find(css="li", role="button").count()
        assert str(info.value) == expected
    finally:
        session.close()