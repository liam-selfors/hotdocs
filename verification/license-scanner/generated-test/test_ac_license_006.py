import textwrap
from pathlib import Path

import pytest

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fake_cache_manager(repo_root: Path) -> None:
    gen_dir = repo_root / "gen" / "cache-manager"
    gen_dir.mkdir(parents=True, exist_ok=True)
    module_path = gen_dir / "cache_manager.py"
    module_path.write_text(
        textwrap.dedent(
            """
            import dataclasses


            @dataclasses.dataclass
            class CacheKey:
                spec_bundle_hash: str
                gate_inputs_hash: str
                gate_version: str
                model_pin: str


            @dataclasses.dataclass
            class CachedResult:
                gate_type: str
                payload: object
                stored_at: str


            def get(cache_key, *, repo_root=None):
                return CachedResult(
                    gate_type="license_scanner", payload=None, stored_at=None
                )


            def put(cache_key, result, *, repo_root=None):
                return None
            """
        )
    )


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    _write_fake_cache_manager(tmp_path)
    return tmp_path


_RESULT_FIELDS = [
    "component_id",
    "gate_version",
    "evaluated",
    "reason",
    "similarity_score",
    "block_threshold",
    "blocked",
    "matches",
    "notified",
    "notification_delivery_error",
    "cache_hit",
]


def _assert_is_single_license_scan_result(result, expected_component_id):
    assert not isinstance(result, (list, tuple, set, dict)) or isinstance(result, dict)
    # A LicenseScanResult may be returned as a dict or as an object; either
    # way it must be ONE such thing, not a collection of several results.
    assert not isinstance(result, (list, tuple, set))

    sentinel = object()
    for field in _RESULT_FIELDS:
        assert _get(result, field, sentinel) is not sentinel, (
            f"LicenseScanResult is missing field {field!r}"
        )

    assert _get(result, "component_id") == expected_component_id
    assert isinstance(_get(result, "matches"), list)
    assert isinstance(_get(result, "evaluated"), bool)
    assert isinstance(_get(result, "blocked"), bool)
    assert isinstance(_get(result, "notified"), bool)
    assert isinstance(_get(result, "cache_hit"), bool)


def test_scan_produces_exactly_one_result_for_the_component(repo_root):
    result = license_scanner.scan("comp-alpha", repo_root)

    _assert_is_single_license_scan_result(result, "comp-alpha")

    # With no reference corpus configured, this is the deterministic
    # not-evaluated outcome -- confirming the single object returned is a
    # genuine, computed LicenseScanResult rather than an arbitrary stub.
    assert _get(result, "evaluated") is False
    assert _get(result, "reason") == "no-reference-corpus"
    assert _get(result, "matches") == []
    assert _get(result, "blocked") is False


def test_each_distinct_component_gets_its_own_single_result(repo_root):
    result_a = license_scanner.scan("comp-alpha", repo_root)
    result_b = license_scanner.scan("comp-beta", repo_root)

    _assert_is_single_license_scan_result(result_a, "comp-alpha")
    _assert_is_single_license_scan_result(result_b, "comp-beta")

    assert _get(result_a, "component_id") != _get(result_b, "component_id")


def test_repeated_scans_of_the_same_component_each_yield_a_single_result(repo_root):
    first = license_scanner.scan("comp-gamma", repo_root)
    second = license_scanner.scan("comp-gamma", repo_root)

    _assert_is_single_license_scan_result(first, "comp-gamma")
    _assert_is_single_license_scan_result(second, "comp-gamma")