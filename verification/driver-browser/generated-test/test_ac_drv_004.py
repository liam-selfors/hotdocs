# hotdocs-criterion: sha256:c0c3d9a2d250c3d3b18caab17a98cad6428e832d6dfd66c2645675fa84f19a15
import functools
import http.server
import struct
import threading
import zlib
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


def _png_bytes():
    def chunk(kind, data):
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_remote_image_is_blocked_and_local_image_is_not(provisioned, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "pic.png").write_bytes(_png_bytes())
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Images</title></head>\n"
        "<body>\n"
        "<img src=\"https://example.com/x.png\" alt=\"remote\">\n"
        "<img src=\"pic.png\" alt=\"local\">\n"
        "</body></html>\n"
    )
    (site / "index.html").write_text(html, encoding="utf-8")

    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(site / "index.html")
        assert page.blocked_requests() == ["https://example.com/x.png"]
    finally:
        session.close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def test_loopback_page_is_allowed_and_sees_fixed_locale_and_time_zone(
    provisioned, tmp_path
):
    site = tmp_path / "served"
    site.mkdir()
    html = (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>Locale</title>"
        "<link rel=\"icon\" href=\"data:,\"></head>\n"
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
        session = driver_browser.open_session(ENV_ROOT, tmp_path)
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
        thread.join(timeout=10)