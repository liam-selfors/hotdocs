# hotdocs-criterion: sha256:fb0ab8ab21469585397b804ff651a8be43e387c5f223620b42520189e5c33862
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
        pytest.fail(str(field(result, "reason")))
    return result


PAGE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>Keys</title>\n"
    "<style>\n"
    "html, body { margin: 0; padding: 0; overflow: hidden; }\n"
    ".box { display: block; width: 200px; height: 30px; margin: 4px 0 4px 10px;"
    " background: #ddd; border: 0; padding: 0; }\n"
    "#k { display: block; width: 20px; height: 20px; margin: 4px 0 4px 10px; }\n"
    "#out { margin: 4px 0 4px 10px; height: 30px; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<div id=\"d\" class=\"box\">double</div>\n"
    "<div id=\"h\" class=\"box\">hover</div>\n"
    "<select id=\"s\" class=\"box\">"
    "<option value=\"a\">a</option>"
    "<option value=\"b\">b</option>"
    "</select>\n"
    "<div id=\"w\" class=\"box\">wheel</div>\n"
    "<div id=\"g\" class=\"box\">drag</div>\n"
    "<div id=\"m\" class=\"box\">modifier</div>\n"
    "<input type=\"checkbox\" id=\"k\">\n"
    "<p id=\"out\">none</p>\n"
    "<script>\n"
    "(function () {\n"
    "  var out = document.getElementById('out');\n"
    "  function show(text) { out.textContent = text; }\n"
    "  document.addEventListener('keydown', function (e) { show('key:' + e.key); });\n"
    "  document.getElementById('d').addEventListener('dblclick', function () { show('dbl'); });\n"
    "  document.getElementById('h').addEventListener('mouseenter', function () { show('hover'); });\n"
    "  var sel = document.getElementById('s');\n"
    "  sel.addEventListener('change', function () { show('sel:' + sel.value); });\n"
    "  document.getElementById('w').addEventListener('wheel', function () { show('wheel'); });\n"
    "  var dragging = false;\n"
    "  var startX = 0;\n"
    "  document.getElementById('g').addEventListener('mousedown', function (e) {\n"
    "    dragging = true;\n"
    "    startX = e.clientX;\n"
    "  });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (dragging) {\n"
    "      dragging = false;\n"
    "      show('drag:' + Math.round(e.clientX - startX));\n"
    "    }\n"
    "  });\n"
    "  document.getElementById('m').addEventListener('click', function (e) {\n"
    "    if (e.shiftKey) { show('shift'); }\n"
    "  });\n"
    "  var chk = document.getElementById('k');\n"
    "  chk.addEventListener('change', function () { show('chk:' + chk.checked); });\n"
    "  window.addEventListener('resize', function () { show('size:' + window.innerWidth); });\n"
    "})();\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_007_input_actions_reach_page_handlers(provisioned, tmp_path):
    page_file = tmp_path / "keys.html"
    page_file.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_file)

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