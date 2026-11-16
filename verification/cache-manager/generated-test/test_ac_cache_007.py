import dataclasses
import os
from pathlib import Path

import pytest

import cache_manager


SPEC_HASH = "sha256:" + "a" * 64
INPUTS_HASH = "sha256:" + "b" * 64
LICENSE_GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


@dataclasses.dataclass
class _FallbackCacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class _FallbackCachedResult:
    gate_type: str
    payload: dict
    stored_at: str


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_key(gate_version=LICENSE_GATE_VERSION, inputs_hash=INPUTS_HASH):
    cls = getattr(cache_manager, "CacheKey", None) or _FallbackCacheKey
    return cls(
        spec_bundle_hash=SPEC_HASH,
        gate_inputs_hash=inputs_hash,
        gate_version=gate_version,
        model_pin=MODEL_PIN,
    )


def _make_result(gate_type, payload):
    cls = getattr(cache_manager, "CachedResult", None) or _FallbackCachedResult
    return cls(gate_type=gate_type, payload=payload, stored_at=cache_manager.now_iso())


def _valid_license_payload():
    return {
        "component_id": "comp-example",
        "gate_version": LICENSE_GATE_VERSION,
        "similarity_score": 0.12,
        "blocked": False,
        "matches": [],
    }


def _lint_report_payload():
    # A LintReport-shaped payload: none of license_scanner's required keys.
    return {
        "findings": [
            {
                "rule": "R-LINT-001",
                "severity": "hard-fail",
                "path": "specs/components/example/component.md",
                "message": "missing frontmatter field: owners",
            }
        ],
        "hard_fail_count": 1,
        "passed": False,
    }


def _valid_compiler_payload():
    return {
        "outputs": [],
        "gate_version": "compiler@1.0.0",
        "summary": "ok",
    }


def _entry_count(repo_root):
    s = cache_manager.stats(repo_root=repo_root)
    return _field(s, "entry_count")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_schema_validation_error_is_value_error():
    assert issubclass(cache_manager.SchemaValidationError, ValueError)


def test_positive_control_valid_payload_is_stored(repo_root):
    # Sanity check that the local store actually works, so the "nothing
    # stored" assertions in the rejection tests below are meaningful.
    key = _make_key()
    assert _entry_count(repo_root) == 0
    cache_manager.put(key, _make_result("license_scanner", _valid_license_payload()), repo_root=repo_root)
    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert _field(got, "gate_type") == "license_scanner"
    assert _field(got, "payload") == _valid_license_payload()
    assert _entry_count(repo_root) == 1


def test_lint_report_payload_under_license_scanner_is_rejected_and_not_stored(repo_root):
    key = _make_key()
    result = _make_result("license_scanner", _lint_report_payload())

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)
    assert got == cache_manager.Miss()
    assert _entry_count(repo_root) == 0


@pytest.mark.parametrize(
    "missing_key",
    ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
)
def test_license_scanner_payload_missing_required_key_is_rejected(repo_root, missing_key):
    key = _make_key()
    payload = _valid_license_payload()
    del payload[missing_key]
    result = _make_result("license_scanner", payload)

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_empty_payload_under_license_scanner_is_rejected(repo_root):
    key = _make_key()
    result = _make_result("license_scanner", {})

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_compiler_shaped_payload_under_license_scanner_gate_type_is_rejected(repo_root):
    key = _make_key()
    result = _make_result("license_scanner", _valid_compiler_payload())

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_result_gate_type_mismatching_key_gate_type_is_rejected(repo_root):
    # A self-consistent compiler result put under a license_scanner key.
    key = _make_key()
    result = _make_result("compiler", _valid_compiler_payload())

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_extra_keys_are_permitted(repo_root):
    # Shallow key-presence check: extra keys must not cause rejection.
    key = _make_key(inputs_hash="sha256:" + "c" * 64)
    payload = _valid_license_payload()
    payload["extra_field"] = "ignored"
    cache_manager.put(key, _make_result("license_scanner", payload), repo_root=repo_root)
    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert _field(got, "gate_type") == "license_scanner"


def test_rejected_put_does_not_overwrite_existing_entry(repo_root):
    key = _make_key()
    good = _make_result("license_scanner", _valid_license_payload())
    cache_manager.put(key, good, repo_root=repo_root)
    assert _entry_count(repo_root) == 1

    bad = _make_result("license_scanner", _lint_report_payload())
    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, bad, repo_root=repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert _field(got, "gate_type") == "license_scanner"
    assert _field(got, "payload") == _valid_license_payload()
    assert _entry_count(repo_root) == 1