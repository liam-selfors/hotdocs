# hotdocs-criterion: sha256:7495dde2d2f605afeadd3738dff5e08a3b5ee3737a04d9afcd43cb50f9f94bd9
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

# A 1x1 transparent PNG.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return REPO_ROOT


def test_file_outside_opened_directory_is_blocked(provisioned, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(PNG_BYTES)
    page_file = site / "page.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><img src=\"../outside.png\" alt=\"x\"></body></html>\n",
        encoding="utf-8",
    )

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_file)
        blocked = page.blocked_requests()
        expected = {outside.as_uri(), outside.resolve().as_uri()}
        assert isinstance(blocked, list)
        assert len(blocked) == 1, blocked
        assert blocked[0] in expected, blocked
    finally:
        session.close()


def test_console_errors_and_no_blocked_requests_for_offline_page(provisioned, tmp_path):
    page_file = tmp_path / "console.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>c</title></head>\n"
        "<body><p>hello</p>\n"
        "<script>console.log(\"info\"); console.error(\"bad\");</script>\n"
        "</body></html>\n",
        encoding="utf-8",
    )

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_file)
        assert page.console_errors() == ["bad"]
        assert page.blocked_requests() == []
    finally:
        session.close()


@pytest.mark.parametrize("url", ["http://example.com/", "ftp://127.0.0.1/x"])
def test_non_loopback_and_non_http_urls_are_refused(provisioned, tmp_path, url):
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        expected = "only file paths and loopback URLs can be opened: " + url
        with pytest.raises(driver_browser.BrowserError, match=re.escape(expected)) as info:
            session.open(url)
        assert str(info.value) == expected
    finally:
        session.close()