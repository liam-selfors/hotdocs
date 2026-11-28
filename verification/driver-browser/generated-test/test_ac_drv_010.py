# hotdocs-criterion: sha256:3127ece7ed4f33ba2964d25077b9116223dc5e23d37456dd0c3d5f2e8ec5dd31
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


@pytest.fixture
def session(provisioned, tmp_path):
    s = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        yield s
    finally:
        s.close()


def test_reference_outside_opened_directory_is_blocked(session, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
        b"\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    page_file = site / "page.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><img src=\"../outside.png\"></body></html>\n",
        encoding="utf-8",
    )

    page = session.open(page_file)

    blocked = page.blocked_requests()
    candidates = [
        [outside.as_uri()],
        [outside.resolve().as_uri()],
    ]
    assert blocked in candidates, blocked


def test_console_errors_and_no_blocked_requests(session, tmp_path):
    page_file = tmp_path / "console.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>c</title></head>\n"
        "<body><p>hello</p>\n"
        "<script>\n"
        "console.log(\"info\");\n"
        "console.error(\"bad\");\n"
        "</script>\n"
        "</body></html>\n",
        encoding="utf-8",
    )

    page = session.open(page_file)

    assert page.console_errors() == ["bad"]
    assert page.blocked_requests() == []


@pytest.mark.parametrize("url", ["http://example.com/", "ftp://127.0.0.1/x"])
def test_non_file_non_loopback_targets_are_refused(session, url):
    message = "only file paths and loopback URLs can be opened: " + url
    with pytest.raises(Exception, match="^" + re.escape(message) + "$") as excinfo:
        session.open(url)
    assert isinstance(excinfo.value, driver_browser.BrowserError)
    assert str(excinfo.value) == message