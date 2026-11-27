# hotdocs-criterion: sha256:cfd4cd9bbbebb018d2922a5cafc2b142b780d97fcff8ee6379de4af6e82ec91b
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
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>AC-DRV-003</title>\n"
    "</head>\n"
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


def _wait_for_downloads(page, timeout=10.0):
    deadline = time.monotonic() + timeout
    downloads = page.downloads()
    while not downloads and time.monotonic() < deadline:
        time.sleep(0.1)
        downloads = page.downloads()
    return downloads


def test_ac_drv_003(provisioned, tmp_path):
    index = tmp_path / "index.html"
    index.write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(index)

        page.find(role="button", name="Warn").click()
        page.find(role="button", name="Export").click()

        assert page.console_errors() == ["Error: boom"]
        assert page.dialogs() == ["hi"]

        downloads = _wait_for_downloads(page)
        assert isinstance(downloads, list)
        assert len(downloads) == 1
        download = Path(downloads[0])
        assert download.name == "out.svg"
        assert download.resolve().parent == (tmp_path / "downloads").resolve()

        shot = page.screenshot("home")
        assert Path(shot).resolve() == (tmp_path / "screenshots" / "home.png").resolve()
        assert Path(shot).is_file()
        with open(shot, "rb") as handle:
            assert handle.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE

        with pytest.raises(driver_browser.BrowserError) as excinfo:
            session.open("https://example.com/")
        assert str(excinfo.value) == (
            "only file paths and loopback URLs can be opened: https://example.com/"
        )
    finally:
        session.close()