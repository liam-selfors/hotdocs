# hotdocs-criterion: sha256:d2615273139b0f6b316c8923e05bc8cfb14a64247bbbf7293061efc9d5eb2be4
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
    "<html>\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>Keys</title>\n"
    "<style>\n"
    "body { margin: 0; padding: 10px; }\n"
    ".box { display: block; width: 200px; height: 40px; margin: 0 0 12px 0;"
    " background: #ddd; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<p id=\"out\">none</p>\n"
    "<div id=\"d\" class=\"box\">double</div>\n"
    "<div id=\"h\" class=\"box\">hover</div>\n"
    "<select id=\"s\"><option value=\"a\">a</option>"
    "<option value=\"b\">b</option></select>\n"
    "<div id=\"w\" class=\"box\">wheel</div>\n"
    "<div id=\"g\" class=\"box\">drag</div>\n"
    "<div id=\"m\" class=\"box\">modifier</div>\n"
    "<input type=\"checkbox\" id=\"k\">\n"
    "<script>\n"
    "var out = document.getElementById('out');\n"
    "function put(t) { out.textContent = t; }\n"
    "document.addEventListener('keydown', function (e) { put('key:' + e.key); });\n"
    "document.getElementById('d').addEventListener('dblclick', function () { put('dbl'); });\n"
    "document.getElementById('h').addEventListener('mouseenter', function () { put('hover'); });\n"
    "document.getElementById('s').addEventListener('change', function (e) {"
    " put('sel:' + e.target.value); });\n"
    "document.getElementById('w').addEventListener('wheel', function () { put('wheel'); });\n"
    "var dragging = false; var startX = 0;\n"
    "document.getElementById('g').addEventListener('mousedown', function (e) {"
    " dragging = true; startX = e.clientX; });\n"
    "document.addEventListener('mouseup', function (e) {"
    " if (dragging) { dragging = false; put('drag:' + Math.round(e.clientX - startX)); } });\n"
    "document.getElementById('m').addEventListener('click', function (e) {"
    " if (e.shiftKey) { put('shift'); } });\n"
    "document.getElementById('k').addEventListener('change', function (e) {"
    " put('chk:' + String(e.target.checked)); });\n"
    "window.addEventListener('resize', function () { put('size:' + window.innerWidth); });\n"
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
            (lambda: page.press("Escape"), "key:Escape"),
            (lambda: page.find(css="#d").dblclick(), "dbl"),
            (lambda: page.find(css="#h").hover(), "hover"),
            (lambda: page.find(css="#s").select("b"), "sel:b"),
            (lambda: page.find(css="#w").wheel(0, 50), "wheel"),
            (lambda: page.find(css="#g").drag_by(30, 0), "drag:30"),
            (lambda: page.find(css="#m").click(modifiers=["Shift"]), "shift"),
            (lambda: page.find(css="#k").check(), "chk:true"),
            (lambda: page.find(css="#k").uncheck(), "chk:false"),
            (lambda: page.set_size(500, 400), "size:500"),
        ]

        seen = []
        for action, expected in steps:
            action()
            seen.append(page.find(css="#out").text())
        assert seen == [expected for _, expected in steps]

        assert page.title() == "Keys"
        assert page.url().endswith("keys.html")
    finally:
        session.close()