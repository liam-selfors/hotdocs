# hotdocs-criterion: sha256:b7dd217ab1c3bd06e69e155c6bb1dda988477809846e45bb73d7fc66a3b1612c
"""AC-CACHE-007 (covers R-CACHE-007).

Given a put call whose payload shape does not match the schema for the
cache_key's declared gate_version (e.g. a LintReport payload under a
license_scanner gate_version), when put is called, then it is rejected
with a schema-validation error and nothing is stored.
"""

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


def _key(gate_version="license_scanner@4.0.3+9f2c41ab07de", suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + (suffix * 64)[:64],
        gate_inputs_hash="sha256:" + ("b" * 64),
        gate_version=gate_version,
        model_pin="claude-sonnet-5",
    )


def _lint_report_payload():
    # A LintReport-shaped payload: none of license_scanner's required keys
    # beyond component_id (gate_version, similarity_score, blocked, matches
    # are all missing).
    return {
        "component_id": "comp-foo",
        "hard_failures": 0,
        "soft_failures": 1,
        "findings": [
            {"rule": "missing-heading", "path": "specs/x.md", "severity": "soft"}
        ],
    }


def _entry_count(repo_root):
    return field(cache_manager.stats(repo_root=repo_root), "entry_count")


def test_lint_report_payload_under_license_scanner_is_rejected_and_not_stored(repo_root):
    key = _key()
    result = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=_lint_report_payload(),
        stored_at=cache_manager.now_iso(),
    )

    assert _entry_count(repo_root) == 0

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    assert issubclass(cache_manager.SchemaValidationError, ValueError)

    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_payload_of_other_gate_type_under_license_scanner_key_is_rejected(repo_root):
    # A result whose gate_type does not match the key's gate_version gate type
    # (a well-formed llm_judge result under a license_scanner key).
    key = _key(suffix="c")
    result = cache_manager.CachedResult(
        gate_type="llm_judge",
        payload={"result": "pass", "rationale": "looks fine"},
        stored_at=cache_manager.now_iso(),
    )

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, result, repo_root=repo_root)

    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_rejection_is_specific_to_the_bad_payload(repo_root):
    # Control: a correctly-shaped license_scanner payload is accepted, so the
    # "nothing stored" observations above are meaningful.
    good_key = _key(suffix="d")
    good = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload={
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "similarity_score": 0.0,
            "blocked": False,
            "matches": [],
        },
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(good_key, good, repo_root=repo_root)
    assert not isinstance(cache_manager.get(good_key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 1

    bad_key = _key(suffix="e")
    bad = cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=_lint_report_payload(),
        stored_at=cache_manager.now_iso(),
    )
    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(bad_key, bad, repo_root=repo_root)

    assert isinstance(cache_manager.get(bad_key, repo_root=repo_root), cache_manager.Miss)
    assert _entry_count(repo_root) == 1