# hotdocs-criterion: sha256:c3e36059a20895d5cf155c19b51a438d6e94e84d1aa435d397231b541b63d648
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
    "  body { margin: 0; padding: 10px; font: 14px sans-serif; }\n"
    "  .box { display: block; width: 200px; height: 40px; margin: 0 0 14px 0;"
    " background: #ddd; }\n"
    "  #g { width: 120px; }\n"
    "  #out { min-height: 20px; margin: 0; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<p id=\"out\"></p>\n"
    "<div id=\"d\" class=\"box\">double</div>\n"
    "<div id=\"h\" class=\"box\">hover</div>\n"
    "<select id=\"s\"><option value=\"a\">a</option>"
    "<option value=\"b\">b</option></select>\n"
    "<div id=\"w\" class=\"box\" style=\"margin-top: 14px\">wheel</div>\n"
    "<div id=\"g\" class=\"box\">drag</div>\n"
    "<button id=\"m\" type=\"button\">modifier</button>\n"
    "<div style=\"margin-top: 14px\"><input id=\"k\" type=\"checkbox\"></div>\n"
    "<script>\n"
    "  var out = document.getElementById('out');\n"
    "  function write(text) { out.textContent = text; }\n"
    "  document.addEventListener('keydown', function (e) { write('key:' + e.key); });\n"
    "  document.getElementById('d').addEventListener('dblclick', function () { write('dbl'); });\n"
    "  document.getElementById('h').addEventListener('mouseenter', function () { write('hover'); });\n"
    "  document.getElementById('s').addEventListener('change', function (e) {"
    " write('sel:' + e.target.value); });\n"
    "  document.getElementById('w').addEventListener('wheel', function () { write('wheel'); });\n"
    "  var startX = null;\n"
    "  document.getElementById('g').addEventListener('mousedown', function (e) {"
    " startX = e.clientX; });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (startX === null) { return; }\n"
    "    var dx = Math.round(e.clientX - startX);\n"
    "    startX = null;\n"
    "    write('drag:' + dx);\n"
    "  });\n"
    "  document.getElementById('m').addEventListener('click', function (e) {"
    " if (e.shiftKey) { write('shift'); } });\n"
    "  document.getElementById('k').addEventListener('change', function (e) {"
    " write('chk:' + e.target.checked); });\n"
    "  window.addEventListener('resize', function () { write('size:' + window.innerWidth); });\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_007_input_actions_reach_page_handlers(provisioned, tmp_path):
    page_path = tmp_path / "keys.html"
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)

        steps = [
            ("press Escape", lambda: page.press("Escape"), "key:Escape"),
            ("dblclick #d", lambda: page.find(css="#d").dblclick(), "dbl"),
            ("hover #h", lambda: page.find(css="#h").hover(), "hover"),
            ("select b", lambda: page.find(css="#s").select("b"), "sel:b"),
            ("wheel #w", lambda: page.find(css="#w").wheel(0, 50), "wheel"),
            ("drag #g", lambda: page.find(css="#g").drag_by(30, 0), "drag:30"),
            (
                "shift-click #m",
                lambda: page.find(css="#m").click(modifiers=["Shift"]),
                "shift",
            ),
            ("check #k", lambda: page.find(css="#k").check(), "chk:true"),
            ("uncheck #k", lambda: page.find(css="#k").uncheck(), "chk:false"),
            ("set_size", lambda: page.set_size(500, 400), "size:500"),
        ]

        for label, action, expected in steps:
            action()
            got = page.find(css="#out").text()
            assert got == expected, label + ": expected " + repr(expected) + ", got " + repr(got)

        assert page.title() == "Keys"
        assert page.url().endswith("keys.html")
    finally:
        session.close()