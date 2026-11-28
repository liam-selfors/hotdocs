# hotdocs-criterion: sha256:07f1c8948e69894a6a687b326f13e8de7134c7d19c397385d5840fcaac278559
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


@pytest.fixture(scope="session")
def provisioned():
    report = driver_browser.provision(REPO_ROOT)
    ok = report["ok"] if isinstance(report, dict) else getattr(report, "ok")
    if not ok:
        reason = report["reason"] if isinstance(report, dict) else getattr(report, "reason")
        pytest.fail("browser provisioning failed: " + str(reason))
    return report


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


def test_relative_path_opens_and_selectors_work(provisioned, tmp_path, monkeypatch):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "page.html").write_text(PAGE, encoding="utf-8")

    # Make sure "relative" means relative to tmp_path, not the process cwd.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open("sub/page.html")
        page.find(label="Query").fill("abc")
        assert page.find(css="#q").value() == "abc"
        assert page.find(test_id="badge").text() == "New"
        assert page.find(role="heading").text() == "Title"
    finally:
        session.close()


def test_missing_file_raises_browser_error(provisioned, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    expected = str(tmp_path / "missing.html")
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        with pytest.raises(driver_browser.BrowserError) as excinfo:
            session.open("missing.html")
        assert str(excinfo.value) == "no such file: " + expected
        assert re.fullmatch(re.escape("no such file: " + expected), str(excinfo.value))
    finally:
        session.close()