# hotdocs-criterion: sha256:b271fb0dc761082d7cf4f0d1ba88cc313c3ff546c111d5ac513c297ad5affd8b
import pytest
from pathlib import Path

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
    "<html>\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>Keys</title>\n"
    "<style>\n"
    "html, body { margin: 0; padding: 0; }\n"
    "body { font-family: sans-serif; }\n"
    ".box { display: block; width: 200px; height: 40px; margin: 0 0 10px 0;"
    " background: #ddd; }\n"
    "#g { width: 300px; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<p id=\"out\">ready</p>\n"
    "<div id=\"d\" class=\"box\">double</div>\n"
    "<div id=\"h\" class=\"box\">hover</div>\n"
    "<select id=\"s\"><option value=\"a\">a</option>"
    "<option value=\"b\">b</option></select>\n"
    "<div id=\"w\" class=\"box\">wheel</div>\n"
    "<div id=\"g\" class=\"box\">drag</div>\n"
    "<button id=\"m\" class=\"box\" type=\"button\">modifier</button>\n"
    "<input id=\"k\" type=\"checkbox\">\n"
    "<script>\n"
    "(function () {\n"
    "  var out = document.getElementById('out');\n"
    "  function show(t) { out.textContent = t; }\n"
    "  document.addEventListener('keydown', function (e) { show('key:' + e.key); });\n"
    "  document.getElementById('d').addEventListener('dblclick', function () { show('dbl'); });\n"
    "  document.getElementById('h').addEventListener('mouseenter', function () { show('hover'); });\n"
    "  var s = document.getElementById('s');\n"
    "  s.addEventListener('change', function () { show('sel:' + s.value); });\n"
    "  document.getElementById('w').addEventListener('wheel', function (e) {\n"
    "    e.preventDefault(); show('wheel');\n"
    "  }, { passive: false });\n"
    "  var dragging = false; var startX = 0;\n"
    "  document.getElementById('g').addEventListener('mousedown', function (e) {\n"
    "    dragging = true; startX = e.clientX;\n"
    "  });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (dragging) { dragging = false; show('drag:' + Math.round(e.clientX - startX)); }\n"
    "  });\n"
    "  document.getElementById('m').addEventListener('click', function (e) {\n"
    "    if (e.shiftKey) { show('shift'); }\n"
    "  });\n"
    "  var k = document.getElementById('k');\n"
    "  k.addEventListener('change', function () { show('chk:' + String(k.checked)); });\n"
    "  window.addEventListener('resize', function () { show('size:' + window.innerWidth); });\n"
    "})();\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_007_input_actions_and_page_reads(provisioned, tmp_path):
    page_path = tmp_path / "keys.html"
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)

        def out():
            return page.find(css="#out").text()

        page.press("Escape")
        assert out() == "key:Escape"

        page.find(css="#d").dblclick()
        assert out() == "dbl"

        page.find(css="#h").hover()
        assert out() == "hover"

        page.find(css="#s").select("b")
        assert out() == "sel:b"

        page.find(css="#w").wheel(0, 50)
        assert out() == "wheel"

        page.find(css="#g").drag_by(30, 0)
        assert out() == "drag:30"

        page.find(css="#m").click(modifiers=["Shift"])
        assert out() == "shift"

        page.find(css="#k").check()
        assert out() == "chk:true"

        page.find(css="#k").uncheck()
        assert out() == "chk:false"

        page.set_size(500, 400)
        assert out() == "size:500"

        assert page.title() == "Keys"
        assert page.url().endswith("keys.html")
    finally:
        session.close()