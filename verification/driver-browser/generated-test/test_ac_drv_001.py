# hotdocs-criterion: sha256:7a33cb13c1e374cc89132f221b6d479f37c4e87ea04f11415e9c6dbf093ae6c6
import time
from pathlib import Path

import driver_browser


SHARED_ROOT = Path.home() / ".cache" / "hotdocs-test"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_drv_001_provision_twice_is_idempotent_and_fast():
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)

    first = driver_browser.provision(SHARED_ROOT)
    assert field(first, "ok") is True, field(first, "reason")

    start = time.monotonic()
    second = driver_browser.provision(SHARED_ROOT)
    elapsed = time.monotonic() - start

    assert field(second, "ok") is True, field(second, "reason")

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