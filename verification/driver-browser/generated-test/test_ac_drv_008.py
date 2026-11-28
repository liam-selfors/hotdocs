# hotdocs-criterion: sha256:62d286151d9a2592f2a12e076ab79fd26f7f236c07981eec7e8ad1a6fd907407
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


PAGE_HTML = (
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


def test_relative_open_and_selectors(provisioned, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "page.html").write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open("sub/page.html")
        page.find(label="Query").fill("abc")
        assert page.find(css="#q").value() == "abc"
        assert page.find(test_id="badge").text() == "New"
        assert page.find(role="heading").text() == "Title"
    finally:
        session.close()


def test_open_missing_file_raises(provisioned, tmp_path):
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        candidates = {str(tmp_path / "missing.html"), str((tmp_path / "missing.html").resolve())}
        pattern = "^no such file: (" + "|".join(re.escape(c) for c in sorted(candidates)) + ")$"
        with pytest.raises(driver_browser.BrowserError, match=pattern):
            session.open("missing.html")
    finally:
        session.close()