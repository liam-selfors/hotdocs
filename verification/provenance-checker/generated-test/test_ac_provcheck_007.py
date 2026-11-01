import json
import tempfile
from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_MATCHING_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}

_H_CORRECT = "sha256:" + "a" * 64
_H_WRONG = "sha256:" + "b" * 64

_VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "overall": "pass",
}

_LICENSE_SCAN = {
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

_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def _write_manifest(repo_root: Path, spec_bundle_hash: str) -> None:
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": dict(_MATCHING_GATE_VERSIONS),
        "verification_report": _VERIFICATION_REPORT,
        "license_scan": _LICENSE_SCAN,
        "secret_scan": _SECRET_SCAN,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


def test_check_provenance_uses_caller_supplied_hash_not_a_self_computed_one():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_manifest(repo_root, _H_CORRECT)

        # repo_root has no gen/spec-bundle-assembler (or any other dependency)
        # at all. If check_provenance ever computed its own spec_bundle_hash
        # itself -- the way current_provenance_key does, by calling
        # spec-bundle-assembler -- these calls would raise instead of
        # returning a result.

        hit_result = provenance_checker.check_provenance(
            "comp-foo", _H_CORRECT, dict(_MATCHING_GATE_VERSIONS), repo_root
        )
        assert _get(hit_result, "hit") is True
        assert _get(hit_result, "verification_report") is not None
        assert _get(hit_result, "license_scan") is not None
        assert _get(hit_result, "secret_scan") is not None

        miss_result = provenance_checker.check_provenance(
            "comp-foo", _H_WRONG, dict(_MATCHING_GATE_VERSIONS), repo_root
        )
        assert _get(miss_result, "hit") is False
        assert _get(miss_result, "verification_report") is None
        assert _get(miss_result, "license_scan") is None
        assert _get(miss_result, "secret_scan") is None

        # Nothing about the manifest or the environment changed between
        # these three calls -- only the caller-supplied hash did -- so
        # flipping back to a hit here shows the comparison is driven
        # exactly by that caller-supplied value, not by anything this
        # component might compute on its own.
        hit_again_result = provenance_checker.check_provenance(
            "comp-foo", _H_CORRECT, dict(_MATCHING_GATE_VERSIONS), repo_root
        )
        assert _get(hit_again_result, "hit") is True