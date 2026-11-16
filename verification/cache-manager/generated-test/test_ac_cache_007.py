"""AC-CACHE-007 (Covers: R-CACHE-007).

Given a put call whose payload shape does not match the schema for the
cache_key's declared gate_version (e.g. a LintReport payload under a
license_scanner gate_version)
When put is called
Then it is rejected with a schema-validation error and nothing is stored.
"""

import cache_manager

import pytest


GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    # Force the local fallback store under this fresh repo_root.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _key(suffix="a"):
    return cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + (suffix * 64)[:64],
        gate_inputs_hash="sha256:" + (suffix * 64)[:64][::-1],
        gate_version=GATE_VERSION,
        model_pin="claude-sonnet-5",
    )


def _result(payload):
    return cache_manager.CachedResult(
        gate_type="license_scanner",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )


def _entry_count(repo_root):
    return field(cache_manager.stats(repo_root=repo_root), "entry_count")


# A LintReport-shaped payload: none of license_scanner's required keys
# (component_id, gate_version, similarity_score, blocked, matches).
LINT_REPORT_PAYLOAD = {
    "hard_failures": 1,
    "soft_failures": 0,
    "findings": [
        {
            "rule": "R-LINT-001",
            "path": "specs/components/foo/component.md",
            "severity": "hard",
            "message": "missing frontmatter field: owners",
        }
    ],
}

# Nearly license_scanner-shaped, but missing one required key ("matches").
PARTIAL_LICENSE_PAYLOAD = {
    "component_id": "comp-foo",
    "gate_version": GATE_VERSION,
    "similarity_score": 0.01,
    "blocked": False,
}


@pytest.mark.parametrize(
    "payload",
    [LINT_REPORT_PAYLOAD, PARTIAL_LICENSE_PAYLOAD],
    ids=["lint-report-shaped", "license-missing-matches"],
)
def test_put_rejects_mismatched_payload_and_stores_nothing(repo_root, payload):
    key = _key("a")
    assert _entry_count(repo_root) == 0

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(key, _result(payload), repo_root=repo_root)

    # SchemaValidationError is documented as a ValueError subclass.
    assert issubclass(cache_manager.SchemaValidationError, ValueError)

    # Nothing stored: the key is still a miss and the store is empty.
    got = cache_manager.get(key, repo_root=repo_root)
    assert isinstance(got, cache_manager.Miss)
    assert _entry_count(repo_root) == 0


def test_valid_payload_control_is_stored_but_invalid_one_is_not(repo_root):
    """Control: the same store does accept a correctly shaped payload, so the
    'nothing stored' assertions above are meaningful, and a rejected put
    alongside it adds no entry."""
    good_key = _key("b")
    bad_key = _key("c")
    good_payload = {
        "component_id": "comp-foo",
        "gate_version": GATE_VERSION,
        "similarity_score": 0.0,
        "blocked": False,
        "matches": [],
    }

    cache_manager.put(good_key, _result(good_payload), repo_root=repo_root)
    assert _entry_count(repo_root) == 1
    hit = cache_manager.get(good_key, repo_root=repo_root)
    assert not isinstance(hit, cache_manager.Miss)
    assert field(hit, "gate_type") == "license_scanner"

    with pytest.raises(cache_manager.SchemaValidationError):
        cache_manager.put(
            bad_key, _result(LINT_REPORT_PAYLOAD), repo_root=repo_root
        )

    assert isinstance(
        cache_manager.get(bad_key, repo_root=repo_root), cache_manager.Miss
    )
    assert _entry_count(repo_root) == 1