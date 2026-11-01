import json
import shutil
import tempfile
from pathlib import Path

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_gate_version_mismatch_is_miss_even_when_spec_bundle_hash_matches():
    repo_root = Path(tempfile.mkdtemp())
    try:
        spec_bundle_hash = "sha256:" + "a" * 64

        foo_dir = repo_root / "gen" / "foo"
        foo_dir.mkdir(parents=True)

        provenance = {
            "spec_bundle_hash": spec_bundle_hash,
            "gate_versions": {"license_scanner": "1.0.0"},
            "verification_report": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            },
            "license_scan": {
                "component_id": "comp-foo",
                "gate_version": "license_scanner@1.0.0",
                "similarity_score": 0.0,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
            "secret_scan": {
                "scope": "full",
                "gate_version": "secret_scanner@1.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        }
        (foo_dir / ".provenance.json").write_text(json.dumps(provenance))

        # Caller's current gate_versions disagrees with the manifest's
        # recorded gate_versions for "license_scanner", even though the
        # spec_bundle_hash itself matches exactly.
        result = provenance_checker.check_provenance(
            "comp-foo",
            spec_bundle_hash,
            {"license_scanner": "2.0.0"},
            repo_root,
        )

        assert _get(result, "hit") is False
        assert _get(result, "verification_report") is None
        assert _get(result, "license_scan") is None
        assert _get(result, "secret_scan") is None
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)