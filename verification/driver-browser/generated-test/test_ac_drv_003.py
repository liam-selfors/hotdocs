# hotdocs-criterion: sha256:6a5beb47092846f6f1bd4cb1bde4219428ebf106274ce1c7dfe3a7c0ef61eceb
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
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


PAGE_HTML = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>AC-DRV-003</title></head>\n"
    "<body>\n"
    "<button id=\"warn\" type=\"button\">Warn</button>\n"
    "<button id=\"export\" type=\"button\">Export</button>\n"
    "<script>\n"
    "document.getElementById('warn').addEventListener('click', function () {\n"
    "  alert('hi');\n"
    "});\n"
    "document.getElementById('export').addEventListener('click', function () {\n"
    "  var svg = '<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"10\" height=\"10\"></svg>';\n"
    "  var blob = new Blob([svg], {type: 'image/svg+xml'});\n"
    "  var url = URL.createObjectURL(blob);\n"
    "  var a = document.createElement('a');\n"
    "  a.href = url;\n"
    "  a.download = 'out.svg';\n"
    "  document.body.appendChild(a);\n"
    "  a.click();\n"
    "  a.remove();\n"
    "});\n"
    "</script>\n"
    "<script>\n"
    "throw new Error('boom');\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_003(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)

        page.find(role="button", name="Warn").click()
        page.find(role="button", name="Export").click()

        # Allow the download to finish being saved, without asserting on timing.
        deadline = time.monotonic() + 10
        downloads = page.downloads()
        while not downloads and time.monotonic() < deadline:
            time.sleep(0.1)
            downloads = page.downloads()

        assert page.console_errors() == ["Error: boom"]
        assert page.dialogs() == ["hi"]

        assert isinstance(downloads, list)
        assert len(downloads) == 1
        downloaded = Path(downloads[0])
        assert downloaded.name == "out.svg"
        assert downloaded.resolve().parent == (tmp_path / "downloads").resolve()

        shot = page.screenshot("home")
        assert Path(shot) == tmp_path / "screenshots" / "home.png"
        assert Path(shot).is_file()
        assert Path(shot).read_bytes()[: len(PNG_SIGNATURE)] == PNG_SIGNATURE

        with pytest.raises(driver_browser.BrowserError) as excinfo:
            session.open("https://example.com/")
        assert str(excinfo.value) == (
            "only file paths and loopback URLs can be opened: https://example.com/"
        )
    finally:
        session.close()