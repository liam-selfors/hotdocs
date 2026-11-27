# hotdocs-criterion: sha256:70a2f7f675da9a682d3cf562cddc549805a89daf269181a830947702b1ed8d21
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


PAGE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>AC-DRV-008</title></head>\n"
    "<body>\n"
    "<label for=\"q\">Query</label><input id=\"q\">\n"
    "<span data-testid=\"badge\">New</span>\n"
    "<h2>Title</h2>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_008_relative_open_and_selectors(provisioned, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "page.html").write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open("sub/page.html")

        page.find(label="Query").fill("abc")
        assert page.find(css="#q").value() == "abc"
        assert page.find(test_id="badge").text() == "New"
        assert page.find(role="heading").text() == "Title"
    finally:
        session.close()


def test_ac_drv_008_missing_file(provisioned, tmp_path):
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        expected = "no such file: " + str(tmp_path / "missing.html")
        with pytest.raises(driver_browser.BrowserError, match="^" + re.escape(expected) + "$"):
            session.open("missing.html")
    finally:
        session.close()