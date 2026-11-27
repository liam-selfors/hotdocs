# hotdocs-criterion: sha256:0221ad4e4d1ab50e1c2e15f9c924f864c1e065049b39c282cc59dcee37d16fad
import re
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
    "<head><meta charset=\"utf-8\"><title>AC-DRV-006</title></head>\n"
    "<body>\n"
    "<input id=\"n\" value=\"7\">\n"
    "<a id=\"l\" href=\"x.html\" data-k=\"v\">Link</a>\n"
    "<input id=\"c\" type=\"checkbox\" checked>\n"
    "<div id=\"box\" style=\"position:absolute;left:10px;top:20px;width:30px;height:40px\"></div>\n"
    "<ul><li>one</li><li>two</li><li>three</li></ul>\n"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_006_element_reads(provisioned, tmp_path):
    page_path = tmp_path / "index.html"
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path, width=400, height=300)

        assert page.find(css="#n").value() == "7"

        link = page.find(css="#l")
        assert link.attribute("data-k") == "v"
        assert link.attribute("missing") is None

        assert page.find(css="#c").checked() is True

        box = page.find(css="#box").box()
        assert {
            "x": field(box, "x"),
            "y": field(box, "y"),
            "width": field(box, "width"),
            "height": field(box, "height"),
        } == {"x": 10, "y": 20, "width": 30, "height": 40}
        if isinstance(box, dict):
            assert box == {"x": 10, "y": 20, "width": 30, "height": 40}

        assert page.find(css="li").nth(1).text() == "two"

        assert page.find(css="ul").find(text="three").text() == "three"

        with pytest.raises(driver_browser.BrowserError, match=re.escape("3 elements match css=li")):
            page.find(css="li").text()
    finally:
        session.close()