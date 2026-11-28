# hotdocs-criterion: sha256:687dea41f9fdd2682b39ac475826aefbcccc6f308960dfe66bfea2fd9d590f28
import base64
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"

PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(ENV_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def _page_html():
    script = (
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
    )
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\"><title>Export page</title></head>\n"
        "<body>\n"
        "<img alt=\"pixel\" src=\"" + PNG_DATA_URL + "\">\n"
        "<button id=\"export\" type=\"button\">Export</button>\n"
        "<script>\n" + script + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def test_ac_drv_011_offline_page_download_and_screenshots(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(_page_html(), encoding="utf-8")

    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        page.find(role="button", name="Export").click()

        first = page.downloads()
        second = page.downloads()

        page.screenshot("a")
        page.screenshot("b")

        assert page.blocked_requests() == []

        assert isinstance(first, list)
        assert isinstance(second, list)
        assert len(first) == 1
        assert len(second) == 1
        assert Path(first[0]) == Path(second[0])
        assert Path(first[0]).name == "out.svg"

        assert (tmp_path / "screenshots" / "a.png").is_file()
        assert (tmp_path / "screenshots" / "b.png").is_file()
    finally:
        session.close()