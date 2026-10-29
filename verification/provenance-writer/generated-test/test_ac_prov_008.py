import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


def _truncate_to_seconds(dt):
    return dt.replace(microsecond=0)


def test_generated_at_reflects_own_write_time_not_upstream_internal_timestamp():
    repo_root = Path(tempfile.mkdtemp())

    internal_timestamp = "2000-01-01T00:00:00Z"

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        # An unrelated internal timestamp this component must not copy.
        "internal_timestamp": internal_timestamp,
    }

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    license_scan_result = {
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

    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
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
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }

    before = _truncate_to_seconds(datetime.now(timezone.utc))
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)
    after = _truncate_to_seconds(datetime.now(timezone.utc))

    manifest_paths = list(repo_root.rglob(".provenance.json"))
    assert len(manifest_paths) == 2

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text())

        generated_at = manifest["generated_at"]
        assert generated_at != internal_timestamp

        parsed = datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        assert before <= parsed <= after