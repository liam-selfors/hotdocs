# hotdocs-criterion: sha256:4e08e6ea6e5d74f664eb53b8f4e3572b1ecc5ec3e40b2063be86c09935d6262f
import struct
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
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
    "body { height: 2000px; }\n"
    "#g { width: 100px; height: 60px; background: #ccc; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<div><button type=\"button\">Add</button> "
    "<button type=\"button\">Add more</button></div>\n"
    "<div><label for=\"q1\">Query</label> <input id=\"q1\" type=\"text\"></div>\n"
    "<div><label for=\"q2\">Query text</label> <input id=\"q2\" type=\"text\"></div>\n"
    "<ul><li>alpha</li><li>alphabet</li></ul>\n"
    "<div id=\"late\"></div>\n"
    "<script>\n"
    "setTimeout(function () {\n"
    "  var b = document.createElement('button');\n"
    "  b.type = 'button';\n"
    "  b.textContent = 'Late';\n"
    "  document.getElementById('late').appendChild(b);\n"
    "}, 1000);\n"
    "</script>\n"
    "<div id=\"g\"></div>\n"
    "<p id=\"out\"></p>\n"
    "<script>\n"
    "(function () {\n"
    "  var start = null;\n"
    "  document.getElementById('g').addEventListener('mousedown', function (e) {\n"
    "    start = { x: e.clientX, y: e.clientY };\n"
    "  });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (start === null) { return; }\n"
    "    var dx = Math.round(e.clientX - start.x);\n"
    "    var dy = Math.round(e.clientY - start.y);\n"
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
    width, height = struct.unpack(">II", data[16:24])
    return height


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