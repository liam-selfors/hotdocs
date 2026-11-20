# hotdocs-criterion: sha256:1224a7c17b67164c9d2f6756de0911caa27c9b7ea2c034f00d1fc097752da77b
"""AC-CACHE-007: put rejects a payload whose shape does not match the schema
for the cache_key's declared gate_version, and stores nothing."""

import pytest

import cache_manager


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    # Force the local fallback store under this fresh repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _key(gate_version, suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + (suffix * 64)[:64],
        gate_inputs_hash="sha256:" + ("b" * 64),
        gate_version=gate_version,
        model_pin="claude-sonnet-5",
    )


def _lint_report_payload():
    # A LintReport-shaped payload: none of license_scanner's required keys.
    return {
        "hard_failures": 0,
        "soft_failures": 1,
        "findings": [
            {"rule": "L-001", "path": "specs/x.md", "message": "something"}
        ],
    }


def _entry_count(repo_root):
    return field(cache_manager.stats(repo_root=repo_root), "entry_count")


def test_lint_report_payload_under_license_scanner_gate_version_is_rejected(repo_root):
    key = _key("license_scanner@4.0.3+9f2c41ab07de")
    result = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=_lint_report_payload(),
        stored_at=cache_manager.now_iso(),
    )

    assert _entry_count(repo_root) == 0

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    # Nothing stored.
    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_schema_validation_error_is_a_value_error():
    assert issubclass(cache_manager.SchemaValidationError, ValueError)


def test_payload_missing_one_required_key_is_rejected(repo_root):
    key = _key("license_scanner@4.0.3+9f2c41ab07de", suffix="c")
    payload = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.0,
        "blocked": False,
        # "matches" deliberately missing
    }
    result = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_valid_payload_for_other_gate_type_under_license_scanner_key_is_rejected(repo_root):
    key = _key("license_scanner@4.0.3+9f2c41ab07de", suffix="d")
    # A well-formed llm_judge result, but the key declares license_scanner.
    result = cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": "pass", "rationale": "looks fine"},
        stored_at=cache_manager.now_iso(),
    )

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert isinstance(cache_manager.get(key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_control_matching_payload_is_stored(repo_root):
    # Positive control: confirms the "nothing stored" checks above are meaningful.
    key = _key("license_scanner@4.0.3+9f2c41ab07de", suffix="e")
    payload = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "similarity_score": 0.0,
        "blocked": False,
        "matches": [],
        "extra_key_is_permitted": True,
    }
    result = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )

    cache_manager.put(key, result, repo_root=repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert not isinstance(got, cache_manager.Miss)
    assert field(got, "gate_type") == "license_scanner"
    assert _entry_count(repo_root) == 1