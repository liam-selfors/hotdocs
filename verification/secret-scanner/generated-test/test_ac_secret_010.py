import os
import tempfile
import textwrap
from pathlib import Path

import secret_scanner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


_FAKE_CACHE_MANAGER_SOURCE = textwrap.dedent(
    """
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


    class Miss:
        pass


    def get(cache_key, *, repo_root=None):
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        return None
    """
)


def _write_fake_cache_manager(repo_root):
    cache_manager_dir = os.path.join(repo_root, "gen", "cache-manager")
    os.makedirs(cache_manager_dir, exist_ok=True)
    with open(
        os.path.join(cache_manager_dir, "cache_manager.py"), "w", encoding="utf-8"
    ) as f:
        f.write(_FAKE_CACHE_MANAGER_SOURCE)


def test_full_scan_flags_base64_and_hex_high_entropy_strings():
    with tempfile.TemporaryDirectory() as repo_root:
        _write_fake_cache_manager(repo_root)

        foo_dir = os.path.join(repo_root, "gen", "foo")
        os.makedirs(foo_dir, exist_ok=True)
        with open(os.path.join(foo_dir, "e.py"), "w", encoding="utf-8") as f:
            f.write('token = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r"\n')
            f.write('sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"\n')

        result = secret_scanner.scan(Path(repo_root))

        matches = _get(result, "matches")
        assert matches is not None
        assert len(matches) == 2

        first, second = matches[0], matches[1]

        assert _get(first, "rule_id") == "Base64 High Entropy String"
        assert _get(first, "risk_tier") == "low"
        assert _get(first, "file") == "gen/foo/e.py"
        assert _get(first, "line") == 1

        assert _get(second, "rule_id") == "Hex High Entropy String"
        assert _get(second, "risk_tier") == "low"
        assert _get(second, "file") == "gen/foo/e.py"
        assert _get(second, "line") == 2


def test_full_scan_misses_unquoted_high_entropy_token():
    with tempfile.TemporaryDirectory() as repo_root:
        _write_fake_cache_manager(repo_root)

        foo_dir = os.path.join(repo_root, "gen", "foo")
        os.makedirs(foo_dir, exist_ok=True)
        with open(os.path.join(foo_dir, "e.py"), "w", encoding="utf-8") as f:
            f.write("token = aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r\n")

        result = secret_scanner.scan(Path(repo_root))

        matches = _get(result, "matches")
        assert matches == []