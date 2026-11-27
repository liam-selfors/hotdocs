# hotdocs-criterion: sha256:f775f797a872ee8d566127d327900cc0d0051a9f4ae31d7569c11f033b32063e
import time
from pathlib import Path

import pytest

import driver_browser


SHARED_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(scope="session")
def shared_env():
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)
    report = driver_browser.provision(SHARED_ROOT)
    if not field(report, "ok"):
        pytest.fail("provision failed: " + str(field(report, "reason")))
    return SHARED_ROOT


def test_ac_drv_001_provision_twice_is_idempotent(shared_env):
    first = driver_browser.provision(shared_env)

    start = time.monotonic()
    second = driver_browser.provision(shared_env)
    elapsed = time.monotonic() - start

    assert field(first, "ok") is True, field(first, "reason")
    assert field(second, "ok") is True, field(second, "reason")

    assert field(first, "lockfile_sha256") is None
    assert field(second, "lockfile_sha256") is None

    first_versions = field(first, "versions")
    second_versions = field(second, "versions")
    assert first_versions == second_versions

    for versions in (first_versions, second_versions):
        assert field(versions, "playwright") == "1.64.1"
        chromium = field(versions, "chromium")
        assert isinstance(chromium, str)
        assert chromium != ""

    assert elapsed < 30, "second provision took " + repr(elapsed) + " seconds"