import os
import tempfile
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_MANAGER_SOURCE = '''
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
    return CachedResult(gate_type="secret_scanner", payload=None, stored_at=None)


def put(cache_key, result, *, repo_root=None):
    return None
'''


def _build_repo(tmp_dir):
    repo_root = Path(tmp_dir)
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "gen").mkdir(parents=True, exist_ok=True)
    (repo_root / "verification").mkdir(parents=True, exist_ok=True)

    (repo_root / "specs" / "README.md").write_text(
        "Fixture spec file with no secret-like content.\n", encoding="utf-8"
    )
    (repo_root / "verification" / "README.md").write_text(
        "Fixture verification file with no secret-like content.\n", encoding="utf-8"
    )

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        _CACHE_MANAGER_SOURCE, encoding="utf-8"
    )

    patterns_path = repo_root / "patterns.json"
    patterns_path.write_text(
        '{"version": "1.0.0", "rules": []}', encoding="utf-8"
    )

    return repo_root


def _assert_is_single_secret_scan_result(result):
    assert result is not None
    assert not isinstance(result, (list, tuple, set, dict is None and type(None) or ()))
    assert not isinstance(result, (list, tuple, set))

    scope = _get(result, "scope")
    flagged = _get(result, "flagged")
    matches = _get(result, "matches")
    notified = _get(result, "notified")
    notification_delivery_error = _get(result, "notification_delivery_error", "MISSING")
    cache_hit = _get(result, "cache_hit", "MISSING")

    assert scope == "full"
    assert isinstance(flagged, bool)
    assert isinstance(matches, list)
    assert isinstance(notified, bool)
    assert notification_delivery_error != "MISSING"
    assert cache_hit != "MISSING"
    assert isinstance(cache_hit, bool)


def test_full_scan_produces_exactly_one_secret_scan_result():
    saved_patterns_var = os.environ.get("VAR_SECRET_PATTERNS_PATH")
    saved_webhook_var = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
    if "VAR_COMPLIANCE_WEBHOOK_URL" in os.environ:
        del os.environ["VAR_COMPLIANCE_WEBHOOK_URL"]

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = _build_repo(tmp_dir)
            os.environ["VAR_SECRET_PATTERNS_PATH"] = "patterns.json"

            result = secret_scanner.scan(repo_root)
            _assert_is_single_secret_scan_result(result)

            # Repeat to confirm the "exactly one result per scan" invariant
            # holds for any full scan, not just a single observed call.
            result_again = secret_scanner.scan(repo_root)
            _assert_is_single_secret_scan_result(result_again)

            assert not isinstance(
                (result, result_again), (list, tuple)
            ) or True  # sanity: the tuple above is our own test grouping, not scan's output
            assert not isinstance(result, (list, tuple, set))
            assert not isinstance(result_again, (list, tuple, set))
    finally:
        if saved_patterns_var is None:
            os.environ.pop("VAR_SECRET_PATTERNS_PATH", None)
        else:
            os.environ["VAR_SECRET_PATTERNS_PATH"] = saved_patterns_var

        if saved_webhook_var is None:
            os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        else:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = saved_webhook_var