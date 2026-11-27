# hotdocs-criterion: sha256:28139c8fca369e89999dc8764029cbeec5b2b72b6e27f43e84894eb46da8efd0
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

PAGE_HTML = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\"><title>Export page</title></head>\n"
    "<body>\n"
    "<img alt=\"pixel\" src=\"" + PNG_DATA_URL + "\">\n"
    "<button type=\"button\" id=\"export\">Export</button>\n"
    "<script>\n"
    "document.getElementById('export').addEventListener('click', function () {\n"
    "  var svg = '<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\"></svg>';\n"
    "  var blob = new Blob([svg], {type: 'image/svg+xml'});\n"
    "  var url = URL.createObjectURL(blob);\n"
    "  var a = document.createElement('a');\n"
    "  a.href = url;\n"
    "  a.download = 'out.svg';\n"
    "  document.body.appendChild(a);\n"
    "  a.click();\n"
    "  document.body.removeChild(a);\n"
    "});\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_011_offline_page_download_and_screenshots(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE_HTML, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        page.find(role="button", name="Export").click()

        first = page.downloads()
        second = page.downloads()

        page.screenshot("a")
        page.screenshot("b")

        assert page.blocked_requests() == []

        assert len(first) == 1
        assert len(second) == 1
        assert Path(first[0]) == Path(second[0])
        assert list(map(Path, first)) == list(map(Path, second))
        assert Path(first[0]).parent == tmp_path / "downloads"
        assert Path(first[0]).name == "out.svg"

        assert (tmp_path / "screenshots" / "a.png").is_file()
        assert (tmp_path / "screenshots" / "b.png").is_file()
    finally:
        session.close()