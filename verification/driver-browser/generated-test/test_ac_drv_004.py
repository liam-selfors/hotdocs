# hotdocs-criterion: sha256:83bf4557c4ee8b07e722bd2b11c04f44b16f14be31dc2e9fc75a898be50b8894
import functools
import http.server
import threading
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

# A 1x1 transparent PNG.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049"
    "454e44ae426082"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def test_remote_image_blocked_local_image_allowed(provisioned, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "pic.png").write_bytes(PNG_BYTES)
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Images</title></head>\n"
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


def test_loopback_page_sees_fixed_locale_and_time_zone(provisioned, tmp_path):
    site = tmp_path / "served"
    site.mkdir()
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Locale</title></head>\n"
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

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(site)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        session = driver_browser.open_session(REPO_ROOT, tmp_path)
        try:
            page = session.open("http://127.0.0.1:" + str(port) + "/")
            assert page.find(css="#lang").text() == "en-US"
            assert page.find(css="#tz").text() == "UTC"
            assert page.blocked_requests() == []
        finally:
            session.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)