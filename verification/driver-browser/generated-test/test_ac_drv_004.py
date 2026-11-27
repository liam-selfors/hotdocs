# hotdocs-criterion: sha256:2c3562273b1fc94db19806b7625c5e7648e0fe54741115533106bac4807ec914
import base64
import functools
import http.server
import threading
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"

# A valid 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(ENV_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


@pytest.fixture
def session(provisioned, tmp_path):
    s = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        yield s
    finally:
        s.close()


def test_external_image_blocked_local_image_allowed(session, tmp_path):
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

    page = session.open(site / "index.html")

    assert page.blocked_requests() == ["https://example.com/x.png"]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def test_loopback_page_not_blocked_and_shows_fixed_locale_and_timezone(session, tmp_path):
    served = tmp_path / "served"
    served.mkdir()
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
    (served / "index.html").write_text(html, encoding="utf-8")

    handler = functools.partial(_QuietHandler, directory=str(served))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        page = session.open("http://127.0.0.1:" + str(port) + "/")

        assert page.blocked_requests() == []
        assert page.find(text="en-US").text() == "en-US"
        assert page.find(text="UTC").text() == "UTC"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)