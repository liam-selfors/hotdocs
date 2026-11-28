# hotdocs-criterion: sha256:a4652125c94207c3f51bf9caf0ea8029f441451730b52aa1455b32b8bc71b908
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    ENV_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(ENV_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return ENV_ROOT


PAGE = (
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
    "  var svg = '<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"10\" height=\"10\"></svg>';\n"
    "  var blob = new Blob([svg], {type: 'image/svg+xml'});\n"
    "  var a = document.createElement('a');\n"
    "  a.href = URL.createObjectURL(blob);\n"
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
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        page.find(role="button", name="Warn").click()
        page.find(role="button", name="Export").click()

        assert page.console_errors() == ["Error: boom"]
        assert page.dialogs() == ["hi"]

        downloads = page.downloads()
        assert isinstance(downloads, list)
        assert len(downloads) == 1
        download = Path(downloads[0])
        assert download.name == "out.svg"
        downloads_dir = (tmp_path / "downloads").resolve()
        assert download.resolve().parent == downloads_dir
        assert download.resolve().is_file()

        shot = page.screenshot("home")
        assert isinstance(shot, Path)
        expected = tmp_path / "screenshots" / "home.png"
        assert shot.resolve() == expected.resolve()
        assert expected.is_file()
        with open(expected, "rb") as fh:
            assert fh.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE

        with pytest.raises(driver_browser.BrowserError) as excinfo:
            session.open("https://example.com/")
        assert str(excinfo.value) == (
            "only file paths and loopback URLs can be opened: https://example.com/"
        )
    finally:
        session.close()