# hotdocs-criterion: sha256:a89bab8ba5df04a7e1ed556f9bcc22922e0c798b72908db4c34b735c2c029590
import base64
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

# A 1x1 transparent PNG, so the outside file is a real image.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("browser provisioning failed: " + str(field(result, "reason")))
    return REPO_ROOT


def _session(repo_root, tmp_path):
    return driver_browser.open_session(repo_root, tmp_path)


def test_request_outside_opened_directory_is_blocked(provisioned, tmp_path):
    root = tmp_path.resolve()
    site = root / "site"
    site.mkdir()
    outside = root / "outside.png"
    outside.write_bytes(PNG_BYTES)
    page_file = site / "page.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><img src=\"../outside.png\" alt=\"outside\"></body></html>\n",
        encoding="utf-8",
    )

    session = _session(provisioned, tmp_path)
    try:
        page = session.open(page_file)
        assert page.blocked_requests() == [outside.as_uri()]
    finally:
        session.close()


def test_console_errors_and_no_blocked_requests_for_offline_page(provisioned, tmp_path):
    page_file = tmp_path.resolve() / "page.html"
    page_file.write_text(
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>t</title></head>\n"
        "<body><p>hello</p>\n"
        "<script>\n"
        "console.log(\"info\");\n"
        "console.error(\"bad\");\n"
        "</script>\n"
        "</body></html>\n",
        encoding="utf-8",
    )

    session = _session(provisioned, tmp_path)
    try:
        page = session.open(page_file)
        assert page.console_errors() == ["bad"]
        assert page.blocked_requests() == []
    finally:
        session.close()


@pytest.mark.parametrize("url", ["http://example.com/", "ftp://127.0.0.1/x"])
def test_non_loopback_or_non_http_url_cannot_be_opened(provisioned, tmp_path, url):
    expected = "only file paths and loopback URLs can be opened: " + url
    session = _session(provisioned, tmp_path)
    try:
        with pytest.raises(driver_browser.BrowserError, match=re.escape(expected)) as info:
            session.open(url)
        assert str(info.value) == expected
    finally:
        session.close()