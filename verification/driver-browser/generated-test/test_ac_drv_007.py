# hotdocs-criterion: sha256:32788bd33da45b8299b20e39f7e9145cc4d65095c35be49a3b671059b3f53626
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

PAGE = (
    "<!DOCTYPE html>\n"
    "<html>\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>Keys</title>\n"
    "<style>\n"
    "  body { margin: 0; padding: 8px; font-family: sans-serif; }\n"
    "  .box { display: block; width: 200px; height: 40px; margin: 6px 0;"
    " border: 1px solid #333; }\n"
    "  #out { min-height: 20px; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<p id=\"out\">start</p>\n"
    "<div id=\"d\" class=\"box\">double</div>\n"
    "<div id=\"h\" class=\"box\">hover</div>\n"
    "<select id=\"s\"><option value=\"a\">a</option>"
    "<option value=\"b\">b</option></select>\n"
    "<div id=\"w\" class=\"box\">wheel</div>\n"
    "<div id=\"g\" class=\"box\">drag</div>\n"
    "<button id=\"m\" type=\"button\">modifier</button>\n"
    "<input id=\"k\" type=\"checkbox\">\n"
    "<script>\n"
    "  var out = document.getElementById('out');\n"
    "  function show(t) { out.textContent = t; }\n"
    "  document.addEventListener('keydown', function (e) { show('key:' + e.key); });\n"
    "  document.getElementById('d').addEventListener('dblclick', function () { show('dbl'); });\n"
    "  document.getElementById('h').addEventListener('mouseenter', function () { show('hover'); });\n"
    "  document.getElementById('s').addEventListener('change', function (e) {"
    " show('sel:' + e.target.value); });\n"
    "  document.getElementById('w').addEventListener('wheel', function (e) {"
    " e.preventDefault(); show('wheel'); }, { passive: false });\n"
    "  var dragStart = null;\n"
    "  document.getElementById('g').addEventListener('mousedown', function (e) {"
    " dragStart = e.clientX; });\n"
    "  document.addEventListener('mouseup', function (e) {\n"
    "    if (dragStart !== null) {\n"
    "      show('drag:' + Math.round(e.clientX - dragStart));\n"
    "      dragStart = null;\n"
    "    }\n"
    "  });\n"
    "  document.getElementById('m').addEventListener('click', function (e) {"
    " if (e.shiftKey) { show('shift'); } });\n"
    "  document.getElementById('k').addEventListener('change', function (e) {"
    " show('chk:' + String(e.target.checked)); });\n"
    "  window.addEventListener('resize', function () { show('size:' + window.innerWidth); });\n"
    "</script>\n"
    "</body>\n"
    "</html>\n"
)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(REPO_ROOT)
    ok = result["ok"] if isinstance(result, dict) else getattr(result, "ok")
    if not ok:
        reason = result["reason"] if isinstance(result, dict) else getattr(result, "reason")
        pytest.fail(str(reason))
    return result


def test_ac_drv_007_actions_and_reads(provisioned, tmp_path):
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