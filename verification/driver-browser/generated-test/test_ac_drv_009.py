# hotdocs-criterion: sha256:7721b7d9fc4131dc23f8ca358755e1dfeacff1facaaf433ea01a58e05ee085c1
import struct
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


PAGE = (
    "<!DOCTYPE html>\n"
    "<html>\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>AC-DRV-009</title>\n"
    "<style>\n"
    "html, body { margin: 0; padding: 0; }\n"
    "body { height: 2000px; }\n"
    "#g { width: 120px; height: 80px; background: #ccc; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<div id=\"g\">drag me</div>\n"
    "<p id=\"out\"></p>\n"
    "<button type=\"button\">Add</button>\n"
    "<button type=\"button\">Add more</button>\n"
    "<label for=\"q1\">Query</label><input id=\"q1\" type=\"text\">\n"
    "<label for=\"q2\">Query text</label><input id=\"q2\" type=\"text\">\n"
    "<ul>\n"
    "<li>alpha</li>\n"
    "<li>alphabet</li>\n"
    "</ul>\n"
    "<div id=\"late\"></div>\n"
    "<script>\n"
    "setTimeout(function () {\n"
    "  var b = document.createElement('button');\n"
    "  b.type = 'button';\n"
    "  b.textContent = 'Late';\n"
    "  document.getElementById('late').appendChild(b);\n"
    "}, 1000);\n"
    "(function () {\n"
    "  var g = document.getElementById('g');\n"
    "  var start = null;\n"
    "  g.addEventListener('mousedown', function (e) {\n"
    "    start = [e.clientX, e.clientY];\n"
    "  });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (start === null) { return; }\n"
    "    var dx = Math.round(e.clientX - start[0]);\n"
    "    var dy = Math.round(e.clientY - start[1]);\n"
    "    start = null;\n"
    "    document.getElementById('out').textContent = 'drag:' + dx + ',' + dy;\n"
    "  });\n"
    "})();\n"
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

    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(page_path, width=400, height=300)

        page.find(role="button", name="Add").click()
        page.find(label="Query").fill("q")
        page.find(text="alpha").text()
        page.find(role="button", name="Late").click()
        page.find(css="#g").drag_by(0, 30)
        shot = page.screenshot("full")

        assert page.find(css="#out").text() == "drag:0,30"

        shot_path = Path(shot)
        assert shot_path.is_file()
        assert png_height(shot_path) >= 2000
    finally:
        session.close()