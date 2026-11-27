# hotdocs-criterion: sha256:e205fdc79b3558d5791f34bee6c5ccde51c9b974368f39bab7ff43cf0bd1bbd8
import re
from pathlib import Path

import pytest

import driver_browser


ENV_ROOT = Path.home() / ".cache" / "hotdocs-test"

PAGE = (
    "<!doctype html><html><head><style>\n"
    ":root { --c: #ff0000; }\n"
    "p { color: var(--c); margin-top: 1.5em; font-size: 10px; }\n"
    "@media (prefers-color-scheme: dark) { p { color: #00ff00; } }\n"
    "</style></head><body><p>x</p></body></html>\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    result = driver_browser.provision(ENV_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def _write_page(tmp_path):
    path = tmp_path / "s.html"
    path.write_text(PAGE, encoding="utf-8")
    return path


def test_ac_drv_012_style_light(provisioned, tmp_path):
    path = _write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(path)
        p = page.find(css="p")
        assert p.style("color") == "rgb(255, 0, 0)"
        assert p.style("margin-top") == "15px"
        assert page.find(css="html").style("--c") == "#ff0000"
    finally:
        session.close()


def test_ac_drv_012_style_dark(provisioned, tmp_path):
    path = _write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        page = session.open(path, color_scheme="dark")
        assert page.find(css="p").style("color") == "rgb(0, 255, 0)"
    finally:
        session.close()


def test_ac_drv_012_both_in_one_session(provisioned, tmp_path):
    path = _write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        light = session.open(path)
        assert light.find(css="p").style("color") == "rgb(255, 0, 0)"
        assert light.find(css="p").style("margin-top") == "15px"
        assert light.find(css="html").style("--c") == "#ff0000"
        dark = session.open(path, color_scheme="dark")
        assert dark.find(css="p").style("color") == "rgb(0, 255, 0)"
    finally:
        session.close()


def test_ac_drv_012_bad_color_scheme(provisioned, tmp_path):
    path = _write_page(tmp_path)
    session = driver_browser.open_session(ENV_ROOT, tmp_path)
    try:
        with pytest.raises(
            Exception, match=re.escape("color_scheme is light or dark: blue")
        ) as excinfo:
            session.open(path, color_scheme="blue")
        assert isinstance(excinfo.value, driver_browser.BrowserError)
    finally:
        session.close()