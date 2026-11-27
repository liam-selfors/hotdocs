# hotdocs-criterion: sha256:614223445512dab35de76268dc9a9aed28aa67bb780b92a9a6b71d39448351c1
import time
from pathlib import Path

import pytest

import driver_browser


SHARED_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_drv_001_provision_twice_is_idempotent_and_reports_versions():
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)

    first = driver_browser.provision(SHARED_ROOT)
    if field(first, "ok") is not True:
        pytest.fail("first provision failed: " + repr(field(first, "reason")))

    started = time.monotonic()
    second = driver_browser.provision(SHARED_ROOT)
    elapsed = time.monotonic() - started
    if field(second, "ok") is not True:
        pytest.fail("second provision failed: " + repr(field(second, "reason")))

    assert field(first, "ok") is True
    assert field(second, "ok") is True

    assert field(first, "lockfile_sha256") is None
    assert field(second, "lockfile_sha256") is None

    first_versions = field(first, "versions")
    second_versions = field(second, "versions")
    assert first_versions == second_versions

    for versions in (first_versions, second_versions):
        assert versions["playwright"] == "1.64.1"
        chromium = versions["chromium"]
        assert isinstance(chromium, str)
        assert chromium.strip() != ""

    assert elapsed < 30, "second provision took " + repr(elapsed) + " seconds"