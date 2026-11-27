# hotdocs-criterion: sha256:16c692277d5d5c4d11ca00cfe360b1ab8900d5425827d350797ac01cb9b9aa7b
import re
import time
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


PAGE_HTML = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>AC-DRV-003</title></head>\n"
    "<body>\n"
    "<button type=\"button\" id=\"warn\">Warn</button>\n"
    "<button type=\"button\" id=\"export\">Export</button>\n"
    "<script>\n"
    "document.getElementById('warn').addEventListener('click', function () {\n"
    "  alert('hi');\n"
    "});\n"
    "document.getElementById('export').addEventListener('click', function () {\n"
    "  var svg = '<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\"></svg>';\n"
    "  var blob = new Blob([svg], {type: 'image/svg+xml'});\n"
    "  var a = document.createElement('a');\n"
    "  a.href = URL.createObjectURL(blob);\n"
    "  a.download = 'out.svg';\n"
    "  document.body.appendChild(a);\n"
    "  a.click();\n"
    "});\n"
    "</script>\n"
    "<script>\n"
    "throw new Error('boom');\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def _wait_for(read, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    value = read()
    while not predicate(value) and time.monotonic() < deadline:
        time.sleep(0.1)
        value = read()
    return value


def test_ac_drv_003_errors_dialogs_downloads_screenshot_and_open_refusal(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)

        page.find(role="button", name="Warn").click()
        page.find(role="button", name="Export").click()

        assert page.console_errors() == ["Error: boom"]
        assert page.dialogs() == ["hi"]

        downloads = _wait_for(page.downloads, lambda d: len(d) >= 1)
        assert len(downloads) == 1
        download = Path(downloads[0])
        assert download.name == "out.svg"
        assert download.resolve().parent == (tmp_path / "downloads").resolve()
        assert download.is_file()

        shot = page.screenshot("home")
        assert Path(shot).resolve() == (tmp_path / "screenshots" / "home.png").resolve()
        with open(shot, "rb") as fh:
            assert fh.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE

        expected = "only file paths and loopback URLs can be opened: https://example.com/"
        with pytest.raises(driver_browser.BrowserError, match="^" + re.escape(expected) + "$") as excinfo:
            session.open("https://example.com/")
        assert str(excinfo.value) == expected
    finally:
        session.close()