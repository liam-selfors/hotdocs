# hotdocs-criterion: sha256:2e99368478bdf74bd2349f0addc1c19fd2c23f520ed87a7d717b646c3b4267e6
import time
from pathlib import Path

import pytest

import driver_browser


SHARED_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_drv_001_provision_twice_is_idempotent_and_fast():
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)

    first = driver_browser.provision(SHARED_ROOT)
    if not field(first, "ok"):
        pytest.fail("provision failed: " + str(field(first, "reason")))

    start = time.monotonic()
    second = driver_browser.provision(SHARED_ROOT)
    elapsed = time.monotonic() - start

    for report in (first, second):
        assert field(report, "ok") is True, field(report, "reason")
        assert field(report, "lockfile_sha256") is None

    first_versions = field(first, "versions")
    second_versions = field(second, "versions")
    assert first_versions == second_versions

    playwright_version = field(first_versions, "playwright")
    chromium_version = field(first_versions, "chromium")
    assert playwright_version == "1.64.1"
    assert isinstance(chromium_version, str)
    assert chromium_version.strip() != ""

    assert elapsed < 30, "second provision took " + repr(elapsed) + " seconds"