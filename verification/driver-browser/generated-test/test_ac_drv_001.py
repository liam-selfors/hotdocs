# hotdocs-criterion: sha256:31189414c7bc3bf178e1443ec6d4f5599cc2cc8f2397fafbac1dce1bbe3a2204
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
    return report


def test_ac_drv_001_provision_twice_is_idempotent(shared_env):
    first = driver_browser.provision(SHARED_ROOT)

    start = time.monotonic()
    second = driver_browser.provision(SHARED_ROOT)
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
        assert chromium.strip() != ""

    assert elapsed < 30, "second provision took " + repr(elapsed) + " seconds"