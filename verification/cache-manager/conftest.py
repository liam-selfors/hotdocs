import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import cache_manager  # noqa: E402
from cache_manager import CacheKey, CachedResult  # noqa: E402


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return tmp_path


def make_key(**overrides) -> CacheKey:
    defaults = dict(
        spec_bundle_hash="sha256:aaa",
        gate_inputs_hash="sha256:bbb",
        gate_version="license_scanner@1.0.0",
        model_pin="claude-sonnet-5",
    )
    defaults.update(overrides)
    return CacheKey(**defaults)


def make_license_result(**overrides) -> CachedResult:
    payload = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@1.0.0",
        "similarity_score": 0.1,
        "blocked": False,
        "matches": [],
    }
    payload.update(overrides)
    return CachedResult(gate_type="license_scanner", payload=payload, stored_at=cache_manager.now_iso())
