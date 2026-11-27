# hotdocs-criterion: sha256:e61c180c2b715df65088873a259290b350a36c2f0f787ad8dc0ae69c4d542bd5
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


def test_file_outside_opened_directory_is_blocked(session, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    outside = tmp_path / "outside.png"
    # A minimal valid 1x1 PNG.
    outside.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c6360000002000154a24f5d00000000"
            "49454e44ae426082"
        )
    )
    page_file = site / "page.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><img src=\"../outside.png\" alt=\"x\"></body></html>\n",
        encoding="utf-8",
    )

    page = session.open(page_file)

    expected = outside.resolve().as_uri()
    assert list(page.blocked_requests()) == [expected]


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

    assert list(page.console_errors()) == ["bad"]
    assert list(page.blocked_requests()) == []


@pytest.mark.parametrize("url", ["http://example.com/", "ftp://127.0.0.1/x"])
def test_non_loopback_or_non_http_url_is_refused(session, url):
    message = "only file paths and loopback URLs can be opened: " + url
    with pytest.raises(Exception, match="^" + re.escape(message) + "$") as excinfo:
        session.open(url)
    assert isinstance(excinfo.value, driver_browser.BrowserError)
    assert str(excinfo.value) == message