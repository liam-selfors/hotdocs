import json
from pathlib import Path

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _snapshot(root: Path):
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            snap[str(p.relative_to(root))] = (p.read_bytes(), st.st_mtime_ns)
    return snap


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}

MATCHING_HASH = "sha256:" + "a" * 64
MISMATCHED_HASH = "sha256:" + "b" * 64

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@3.1.0",
    "similarity_score": 0.0,
    "block_threshold": 0.70,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


@pytest.fixture
def repo_with_provenance(tmp_path):
    gen_dir = tmp_path / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    provenance_path = gen_dir / ".provenance.json"
    content = {
        "spec_bundle_hash": MATCHING_HASH,
        "gate_versions": GATE_VERSIONS,
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    provenance_path.write_text(json.dumps(content), encoding="utf-8")
    return tmp_path, provenance_path


def test_check_provenance_is_read_only_on_hit(repo_with_provenance):
    repo_root, provenance_path = repo_with_provenance

    before_bytes = provenance_path.read_bytes()
    before_mtime_ns = provenance_path.stat().st_mtime_ns
    before_snapshot = _snapshot(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", MATCHING_HASH, GATE_VERSIONS, repo_root
    )

    assert _get(result, "hit") is True

    after_bytes = provenance_path.read_bytes()
    after_mtime_ns = provenance_path.stat().st_mtime_ns
    after_snapshot = _snapshot(repo_root)

    assert after_bytes == before_bytes
    assert after_mtime_ns == before_mtime_ns
    assert after_snapshot == before_snapshot


def test_check_provenance_is_read_only_on_miss(repo_with_provenance):
    repo_root, provenance_path = repo_with_provenance

    before_bytes = provenance_path.read_bytes()
    before_mtime_ns = provenance_path.stat().st_mtime_ns
    before_snapshot = _snapshot(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", MISMATCHED_HASH, GATE_VERSIONS, repo_root
    )

    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None

    after_bytes = provenance_path.read_bytes()
    after_mtime_ns = provenance_path.stat().st_mtime_ns
    after_snapshot = _snapshot(repo_root)

    assert after_bytes == before_bytes
    assert after_mtime_ns == before_mtime_ns
    assert after_snapshot == before_snapshot


def test_check_provenance_is_read_only_across_repeated_hit_and_miss_calls(
    repo_with_provenance,
):
    repo_root, provenance_path = repo_with_provenance

    before_bytes = provenance_path.read_bytes()
    before_mtime_ns = provenance_path.stat().st_mtime_ns
    before_snapshot = _snapshot(repo_root)

    hit_result = provenance_checker.check_provenance(
        "comp-foo", MATCHING_HASH, GATE_VERSIONS, repo_root
    )
    miss_result = provenance_checker.check_provenance(
        "comp-foo", MISMATCHED_HASH, GATE_VERSIONS, repo_root
    )

    assert _get(hit_result, "hit") is True
    assert _get(miss_result, "hit") is False

    after_bytes = provenance_path.read_bytes()
    after_mtime_ns = provenance_path.stat().st_mtime_ns
    after_snapshot = _snapshot(repo_root)

    assert after_bytes == before_bytes
    assert after_mtime_ns == before_mtime_ns
    assert after_snapshot == before_snapshot