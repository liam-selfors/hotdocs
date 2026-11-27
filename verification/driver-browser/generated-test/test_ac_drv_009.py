# hotdocs-criterion: sha256:0bd86b35c4eb33c308672cb7805444c79d5904a56de022088ef519c31a138fc8
import struct
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


PAGE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>AC-DRV-009</title>\n"
    "<style>\n"
    "html, body { margin: 0; padding: 0; }\n"
    "body { height: 2000px; font-size: 12px; }\n"
    "#g { width: 120px; height: 80px; background: #ccc; }\n"
    "ul { margin: 0; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<button type=\"button\">Add</button>\n"
    "<button type=\"button\">Add more</button>\n"
    "<div>\n"
    "<label for=\"q1\">Query</label> <input id=\"q1\" type=\"text\">\n"
    "</div>\n"
    "<div>\n"
    "<label for=\"q2\">Query text</label> <input id=\"q2\" type=\"text\">\n"
    "</div>\n"
    "<ul>\n"
    "<li>alpha</li>\n"
    "<li>alphabet</li>\n"
    "</ul>\n"
    "<div id=\"late\"></div>\n"
    "<div id=\"g\"></div>\n"
    "<p id=\"out\"></p>\n"
    "<script>\n"
    "window.addEventListener('load', function () {\n"
    "  setTimeout(function () {\n"
    "    var b = document.createElement('button');\n"
    "    b.type = 'button';\n"
    "    b.textContent = 'Late';\n"
    "    document.getElementById('late').appendChild(b);\n"
    "  }, 1000);\n"
    "});\n"
    "var start = null;\n"
    "document.getElementById('g').addEventListener('mousedown', function (e) {\n"
    "  start = [e.clientX, e.clientY];\n"
    "});\n"
    "document.addEventListener('mouseup', function (e) {\n"
    "  if (start === null) { return; }\n"
    "  var dx = Math.round(e.clientX - start[0]);\n"
    "  var dy = Math.round(e.clientY - start[1]);\n"
    "  start = null;\n"
    "  document.getElementById('out').textContent = 'drag:' + dx + ',' + dy;\n"
    "});\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def png_height(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG file"
    assert data[12:16] == b"IHDR", "first chunk is not IHDR"
    return struct.unpack(">I", data[20:24])[0]


def test_ac_drv_009(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path, width=400, height=300)

        page.find(role="button", name="Add").click()
        page.find(label="Query").fill("q")
        alpha_text = page.find(text="alpha").text()
        page.find(role="button", name="Late").click()
        page.find(css="#g").drag_by(0, 30)
        shot = page.screenshot("full")

        assert alpha_text == "alpha"
        assert page.find(css="#out").text() == "drag:0,30"

        shot_path = Path(shot)
        assert shot_path.is_file()
        assert png_height(shot_path) >= 2000
    finally:
        session.close()