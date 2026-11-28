# hotdocs-criterion: sha256:9e8310be444813e8b8d5c3d2cd17360ee9bfbb24a002372ba02aa833ae18eeef
from pathlib import Path

import pytest

import driver_browser


REPO_ROOT = Path.home() / ".cache" / "hotdocs-test"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def provisioned():
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    result = driver_browser.provision(REPO_ROOT)
    if not field(result, "ok"):
        pytest.fail("provision failed: " + str(field(result, "reason")))
    return result


def write_page(path, name):
    path.write_text(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\"><title>" + name + "</title></head>\n"
        "<body><p>" + name + "</p></body>\n"
        "</html>\n",
        encoding="utf-8",
    )


def listing(directory):
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir())


def test_ac_drv_013_close_saves_final_screenshots_and_second_close_is_noop(provisioned, tmp_path):
    a = tmp_path / "a.html"
    b = tmp_path / "b.html"
    write_page(a, "a")
    write_page(b, "b")

    screenshots = tmp_path / "screenshots"

    session = driver_browser.open_session(REPO_ROOT, tmp_path)
    closed = False
    try:
        session.open(a)
        session.open(b)

        session.close()
        closed = True

        names_after_first = listing(screenshots)
        assert names_after_first == ["final-1.png", "final-2.png"]

        for name in names_after_first:
            data = (screenshots / name).read_bytes()
            assert data[:8] == PNG_MAGIC, name

        contents_after_first = {
            name: (screenshots / name).read_bytes() for name in names_after_first
        }

        # The second close() raises nothing and adds no file.
        session.close()

        names_after_second = listing(screenshots)
        assert names_after_second == ["final-1.png", "final-2.png"]
        for name in names_after_second:
            data = (screenshots / name).read_bytes()
            assert data[:8] == PNG_MAGIC, name
            assert data == contents_after_first[name], name
    finally:
        if not closed:
            session.close()