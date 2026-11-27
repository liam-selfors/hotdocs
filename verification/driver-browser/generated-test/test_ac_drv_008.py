# hotdocs-criterion: sha256:5cd364b3c582eeaf250d4f3670a4351a62acaeb248b50b367a9562a2dbcb4581
import re
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(ENV_ROOT)
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


def test_ac_drv_008_relative_open_finders_and_missing_file(provisioned, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "page.html").write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open("sub/page.html")

        page.find(label="Query").fill("abc")
        assert page.find(css="#q").value() == "abc"
        assert page.find(test_id="badge").text() == "New"
        assert page.find(role="heading").text() == "Title"

        expected = "no such file: " + str(tmp_path / "missing.html")
        with pytest.raises(driver_browser.BrowserError) as excinfo:
            session.open("missing.html")
        assert str(excinfo.value) == expected
        assert re.search("^" + re.escape(expected) + "$", str(excinfo.value))
    finally:
        session.close()