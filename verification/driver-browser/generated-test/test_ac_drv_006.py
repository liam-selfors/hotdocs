# hotdocs-criterion: sha256:40d0303918a48603e7686f2dbef1f3e7f0c3fdfd5c0341b15f0c82c045caf824
import re
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


def _write_page(tmp_path):
    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><meta charset=\"utf-8\"><title>AC-DRV-006</title></head>\n"
        "<body>\n"
        "<input id=\"n\" value=\"7\">\n"
        "<a id=\"l\" href=\"x.html\" data-k=\"v\">Link</a>\n"
        "<input id=\"c\" type=\"checkbox\" checked>\n"
        "<div id=\"box\" style=\"position:absolute;left:10px;top:20px;"
        "width:30px;height:40px\"></div>\n"
        "<ul><li>one</li><li>two</li><li>three</li></ul>\n"
        "</body>\n"
        "</html>\n"
    )
    path = tmp_path / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def test_ac_drv_006_element_reads(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(page_path, width=400, height=300)

        assert page.find(css="#n").value() == "7"

        link = page.find(css="#l")
        assert link.attribute("data-k") == "v"
        assert link.attribute("missing") is None

        assert page.find(css="#c").checked() is True

        assert page.find(css="#box").box() == {
            "x": 10,
            "y": 20,
            "width": 30,
            "height": 40,
        }

        assert page.find(css="li").nth(1).text() == "two"

        assert page.find(css="ul").find(text="three").text() == "three"

        with pytest.raises(
            driver_browser.BrowserError,
            match="^" + re.escape("3 elements match css=li") + "$",
        ):
            page.find(css="li").text()
    finally:
        session.close()