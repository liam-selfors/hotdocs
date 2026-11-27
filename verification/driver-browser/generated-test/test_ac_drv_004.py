# hotdocs-criterion: sha256:23254b5b34d7b40c2ae9b038cd52b8473078561de3a04184a3a01ddff694a5cd
import base64
import functools
import http.server
import threading
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def test_external_request_blocked_local_file_allowed(provisioned, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "pic.png").write_bytes(PNG_1X1)
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>imgs</title></head>\n"
        "<body>\n"
        "<img src=\"https://example.com/x.png\">\n"
        "<img src=\"pic.png\">\n"
        "</body></html>\n"
    )
    (site / "index.html").write_text(html, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(site / "index.html")
        assert page.blocked_requests() == ["https://example.com/x.png"]
    finally:
        session.close()


def test_loopback_page_not_blocked_and_fixed_locale_and_timezone(provisioned, tmp_path):
    site = tmp_path / "served"
    site.mkdir()
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>env</title></head>\n"
        "<body>\n"
        "<p id=\"lang\"></p>\n"
        "<p id=\"tz\"></p>\n"
        "<script>\n"
        "document.getElementById('lang').textContent = navigator.language;\n"
        "document.getElementById('tz').textContent = "
        "Intl.DateTimeFormat().resolvedOptions().timeZone;\n"
        "</script>\n"
        "</body></html>\n"
    )
    (site / "index.html").write_text(html, encoding="utf-8")

    handler = functools.partial(_QuietHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        session = driver_browser.open_session(REPO_ROOT, tmp_path)
        try:
            page = session.open("http://127.0.0.1:" + str(port) + "/")
            assert page.blocked_requests() == []
            assert page.find(text="en-US").visible() is True
            assert page.find(text="UTC").visible() is True
        finally:
            session.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)