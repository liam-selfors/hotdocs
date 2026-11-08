import os
import shutil
import tempfile
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _to_dict(result):
    if isinstance(result, dict):
        return result
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return result


FAKE_CACHE_MANAGER_SRC = '''
class Miss:
    pass


class CacheKey:
    def __init__(self, spec_bundle_hash=None, gate_inputs_hash=None, gate_version=None, model_pin=None):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type=None, payload=None, stored_at=None):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    pass
'''


def _make_repo_root(suffix):
    repo_root = tempfile.mkdtemp(prefix="hotdocs_ac_secret_007_%s_" % suffix)
    cache_manager_dir = os.path.join(repo_root, "gen", "cache-manager")
    os.makedirs(cache_manager_dir, exist_ok=True)
    with open(os.path.join(cache_manager_dir, "cache_manager.py"), "w") as f:
        f.write(FAKE_CACHE_MANAGER_SRC)

    with open(os.path.join(repo_root, "README.md"), "w") as f:
        f.write("This is a plain readme file with no secret-like content inside it.\n")

    return repo_root


def _assert_single_result(result):
    assert result is not None
    assert not isinstance(result, (list, tuple, set))

    as_dict = _to_dict(result)
    assert isinstance(as_dict, dict)
    assert not isinstance(as_dict, (list, tuple, set))

    for field in (
        "scope",
        "flagged",
        "matches",
        "allowed",
        "unused_allowlist_entries",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    ):
        assert field in as_dict, "expected %r on the single SecretScanResult" % field

    scope = _get(result, "scope")
    assert scope == "full"

    flagged = _get(result, "flagged")
    assert isinstance(flagged, bool)

    matches = _get(result, "matches")
    assert isinstance(matches, list)


def test_full_scan_produces_exactly_one_secret_scan_result():
    repo_root = _make_repo_root("a")
    try:
        result = secret_scanner.scan(Path(repo_root))
        _assert_single_result(result)
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_any_full_scan_still_produces_exactly_one_result():
    repo_root_one = _make_repo_root("b1")
    repo_root_two = _make_repo_root("b2")
    try:
        result_one = secret_scanner.scan(Path(repo_root_one))
        result_two = secret_scanner.scan(Path(repo_root_two))

        _assert_single_result(result_one)
        _assert_single_result(result_two)

        assert result_one is not result_two
    finally:
        shutil.rmtree(repo_root_one, ignore_errors=True)
        shutil.rmtree(repo_root_two, ignore_errors=True)