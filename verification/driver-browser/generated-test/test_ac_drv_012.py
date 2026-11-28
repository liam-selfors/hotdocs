# hotdocs-criterion: sha256:494f7981673c165fab7b80abd5062df3d9be6dc306307921261157d87817c0d5
import re
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

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
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def write_page(tmp_path):
    path = tmp_path / "s.html"
    path.write_text(PAGE, encoding="utf-8")
    return path


def test_style_reads_computed_values_and_color_scheme(provisioned, tmp_path):
    page_path = write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        light = session.open(page_path)
        assert light.find(css="p").style("color") == "rgb(255, 0, 0)"
        assert light.find(css="p").style("margin-top") == "15px"
        assert light.find(css="html").style("--c") == "#ff0000"

        dark = session.open(page_path, color_scheme="dark")
        assert dark.find(css="p").style("color") == "rgb(0, 255, 0)"
    finally:
        session.close()


def test_invalid_color_scheme_raises(provisioned, tmp_path):
    page_path = write_page(tmp_path)
    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    try:
        with pytest.raises(
            driver_browser.BrowserError,
            match="^" + re.escape("color_scheme is light or dark: blue") + "$",
        ):
            session.open(page_path, color_scheme="blue")
    finally:
        session.close()