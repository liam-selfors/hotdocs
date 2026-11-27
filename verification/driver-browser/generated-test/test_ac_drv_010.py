# hotdocs-criterion: sha256:4a48dc0305a3fd0644b65a0d06bafa4dbcc108f274baf2934b992c5798ef061d
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
    return REPO_ROOT


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_request_outside_opened_directory_is_blocked(provisioned, tmp_path):
    site = tmp_path / "site"
    _write(
        site / "page.html",
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><img src=\"../outside.png\"></body></html>\n",
    )
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n")

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(site / "page.html")
        expected = outside.resolve().as_uri()
        assert page.blocked_requests() == [expected]
    finally:
        session.close()


def test_console_errors_and_no_blocked_requests(provisioned, tmp_path):
    _write(
        tmp_path / "console.html",
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>c</title></head>\n"
        "<body><p>hello</p>\n"
        "<script>\n"
        "console.log(" + '"info"' + ");\n"
        "console.error(" + '"bad"' + ");\n"
        "</script>\n"
        "</body></html>\n",
    )

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(tmp_path / "console.html")
        assert page.console_errors() == ["bad"]
        assert page.blocked_requests() == []
    finally:
        session.close()


@pytest.mark.parametrize("url", ["http://example.com/", "ftp://127.0.0.1/x"])
def test_non_loopback_and_non_http_urls_are_refused(provisioned, tmp_path, url):
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        message = "only file paths and loopback URLs can be opened: " + url
        with pytest.raises(driver_browser.BrowserError, match=re.escape(message)) as info:
            session.open(url)
        assert str(info.value) == message
    finally:
        session.close()