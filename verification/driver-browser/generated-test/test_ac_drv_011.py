# hotdocs-criterion: sha256:adf42090e195502127f0f17c20839ca03bbb8a5c8feb6fd57c9382b4597c65bf
import time
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
    return ENV_ROOT


def _page_html():
    script = (
        "document.getElementById('export').addEventListener('click', function () {\n"
        "  var blob = new Blob(['<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>'],"
        " {type: 'image/svg+xml'});\n"
        "  var a = document.createElement('a');\n"
        "  a.href = URL.createObjectURL(blob);\n"
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
        "<img src=\"" + PNG_DATA_URL + "\" alt=\"pixel\">\n"
        "<button id=\"export\" type=\"button\">Export</button>\n"
        "<script>\n" + script + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def test_ac_drv_011_downloads_screenshots_and_no_blocked_requests(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(_page_html(), encoding="utf-8")

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        page.find(role="button", name="Export").click()

        # Give the download a moment to be saved, should it complete
        # asynchronously after the click returns.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if page.downloads():
                break
            time.sleep(0.1)

        first = page.downloads()
        second = page.downloads()

        page.screenshot("a")
        page.screenshot("b")

        assert page.blocked_requests() == []

        assert isinstance(first, list)
        assert isinstance(second, list)
        assert len(first) == 1, first
        assert len(second) == 1, second
        assert Path(first[0]) == Path(second[0])

        downloaded = Path(first[0])
        assert downloaded.name == "out.svg"
        assert downloaded.parent.resolve() == (tmp_path / "downloads").resolve()
        assert downloaded.is_file()

        assert (tmp_path / "screenshots" / "a.png").is_file()
        assert (tmp_path / "screenshots" / "b.png").is_file()
    finally:
        session.close()