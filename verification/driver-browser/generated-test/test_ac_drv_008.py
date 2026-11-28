# hotdocs-criterion: sha256:1bfee92515c8f802c95961365b8000a83dd6a7c235c0c2dd92f2da60cd23f116
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    ok = result["ok"] if isinstance(result, dict) else getattr(result, "ok")
    if not ok:
        reason = result["reason"] if isinstance(result, dict) else getattr(result, "reason")
        pytest.fail("browser provision failed: " + str(reason))
    return result


PAGE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>Page</title></head>\n"
    "<body>\n"
    "<label for=\"q\">Query</label><input id=\"q\">\n"
    "<span data-testid=\"badge\">New</span>\n"
    "<h2>Title</h2>\n"
    "</body>\n"
    "</html>\n"
)


def test_open_relative_path_and_find_by_label_test_id_role(provisioned, tmp_path):
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


def test_open_missing_file_raises_browser_error(provisioned, tmp_path):
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        expected = "no such file: " + str(tmp_path / "missing.html")
        with pytest.raises(driver_browser.BrowserError, match="^" + re.escape(expected) + "$"):
            session.open("missing.html")
    finally:
        session.close()