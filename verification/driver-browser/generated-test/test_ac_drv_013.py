# hotdocs-criterion: sha256:1fd7076c913d914799a69bdb1f8f5dc3cd5a5b41aaec94dd3569a8a617648fa8
from pathlib import Path

import pytest

import driver_browser


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _repo_root():
    return Path.home() / ".cache" / "hotdocs-test"


@pytest.fixture(scope="session")
def provisioned():
    repo_root = _repo_root()
    repo_root.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(repo_root)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return repo_root


def _page_source(name):
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\"><title>" + name + "</title></head>\n"
        "<body><p>" + name + "</p></body>\n"
        "</html>\n"
    )


def _listing(directory):
    if not directory.is_dir():
        return {}
    return {
        p.name: p.read_bytes()
        for p in sorted(directory.iterdir())
    }


def test_ac_drv_013_close_saves_final_screenshots_and_second_close_is_noop(
    provisioned, tmp_path
):
    (tmp_path / "a.html").write_text(_page_source("a"), encoding="utf-8")
    (tmp_path / "b.html").write_text(_page_source("b"), encoding="utf-8")

    screenshots = tmp_path / "screenshots"

    session = driver_browser.open_session(provisioned, tmp_path)
    try:
        session.open(tmp_path / "a.html")
        session.open(tmp_path / "b.html")

        session.close()

        assert screenshots.is_dir()
        names = sorted(p.name for p in screenshots.iterdir())
        assert names == ["final-1.png", "final-2.png"]
        for name in names:
            with open(screenshots / name, "rb") as handle:
                assert handle.read(8) == PNG_MAGIC

        before = _listing(screenshots)

        session.close()

        after = _listing(screenshots)
        assert sorted(after) == ["final-1.png", "final-2.png"]
        assert sorted(after) == sorted(before)
    finally:
        session.close()