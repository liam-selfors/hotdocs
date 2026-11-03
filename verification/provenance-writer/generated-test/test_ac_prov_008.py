import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_generated_at_is_own_write_time_not_upstream_internal_timestamp():
    unrelated_internal_timestamp = "2000-01-01T00:00:00Z"

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        # An unrelated internal timestamp carried by this upstream result —
        # provenance-writer MUST NOT copy this into its own generated_at.
        "generated_at": unrelated_internal_timestamp,
    }

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    inputs = {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3",
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        before = datetime.now(timezone.utc).replace(microsecond=0)
        provenance_writer.write_provenance("comp-foo", inputs, repo_root)
        after = datetime.now(timezone.utc).replace(microsecond=0)

        gen_manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
        verif_manifest_path = repo_root / "verification" / "foo" / ".provenance.json"

        assert gen_manifest_path.is_file()
        assert verif_manifest_path.is_file()

        for manifest_path in (gen_manifest_path, verif_manifest_path):
            manifest = json.loads(manifest_path.read_text())
            generated_at = _get(manifest, "generated_at")

            assert generated_at is not None
            assert generated_at != unrelated_internal_timestamp

            parsed = datetime.strptime(
                generated_at, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            assert before <= parsed <= after