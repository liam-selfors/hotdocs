# hotdocs-criterion: sha256:fa7952f8920fb46d4a164f6445535bd6504fab6786cb7486916574c214e0644a
import re
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
        pytest.fail(str(field(result, "reason")))
    return result


PAGE = (
    "<!DOCTYPE html>\n"
    "<html>\n"
    "<head><meta charset=\"utf-8\"><title>v</title></head>\n"
    "<body>"
    "<svg width=\"100\" height=\"100\"><line class=\"v\" x1=\"50\" y1=\"10\" "
    "x2=\"50\" y2=\"90\" style=\"stroke: rgb(1, 2, 3)\"></line></svg>"
    "</body>\n"
    "</html>\n"
)


def test_ac_drv_014(provisioned, tmp_path):
    page_path = tmp_path / "v.html"
    page_path.write_text(PAGE, encoding="utf-8")

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        page = session.open(page_path)
        line = page.find(css="line.v")

        assert line.attribute("x1") == "50"
        assert line.style("stroke") == "rgb(1, 2, 3)"

        with pytest.raises(Exception, match=re.escape("no element matches css=line.v")) as excinfo:
            page.find(css="line.v").text()
        assert isinstance(excinfo.value, driver_browser.BrowserError)
        assert str(excinfo.value) == "no element matches css=line.v"
    finally:
        session.close()