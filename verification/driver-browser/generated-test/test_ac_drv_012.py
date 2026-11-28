# hotdocs-criterion: sha256:b07b5a6db88707671bda52bd8f9d42bb083d762e00bf80fb98282041a54a76f0
import re
from pathlib import Path

import pytest

import driver_browser


PAGE = (
    "<!doctype html><html><head><style>\n"
    ":root { --c: #ff0000; }\n"
    "p { color: var(--c); margin-top: 1.5em; font-size: 10px; }\n"
    "@media (prefers-color-scheme: dark) { p { color: #00ff00; } }\n"
    "</style></head><body><p>x</p></body></html>\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _env_root():
    return Path.home() / ".cache" / "hotdocs-test"


@pytest.fixture(scope="session")
def provisioned():
    root = _env_root()
    root.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(root)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return root


def _write_page(tmp_path):
    path = tmp_path / "s.html"
    path.write_text(PAGE, encoding="utf-8")
    return path


def test_ac_drv_012_light_styles(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path)
        p = page.find(css="p")
        assert p.style("color") == "rgb(255, 0, 0)"
        assert p.style("margin-top") == "15px"
        assert page.find(css="html").style("--c") == "#ff0000"
    finally:
        session.close()


def test_ac_drv_012_dark_color_scheme(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        page = session.open(page_path, color_scheme="dark")
        assert page.find(css="p").style("color") == "rgb(0, 255, 0)"
    finally:
        session.close()


def test_ac_drv_012_invalid_color_scheme(provisioned, tmp_path):
    page_path = _write_page(tmp_path)
    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        with pytest.raises(
            driver_browser.BrowserError,
            match=re.escape("color_scheme is light or dark: blue"),
        ):
            session.open(page_path, color_scheme="blue")
    finally:
        session.close()