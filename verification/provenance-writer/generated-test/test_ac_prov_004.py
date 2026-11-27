# hotdocs-criterion: sha256:6934fe20bfca5d033dc8511e7df96c0c184f6220b39b92f301fbd76beeb78106
import json
from pathlib import Path

import provenance_writer


def _inputs(component_id):
    # Every gate's own result says "no cache hit", so a true provenance_hit
    # in the manifest can only come from the caller's own field.
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "boom"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.0-no-reference-corpus",
            "evaluated": False,
            "reason": "no-reference-corpus",
            "similarity_score": None,
            "block_threshold": None,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan_result": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "provenance_hit": True,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def test_ac_prov_004_provenance_hit_true_is_written(tmp_path):
    repo_root = Path(tmp_path)
    component_id = "comp-foo"

    provenance_writer.write_provenance(component_id, _inputs(component_id), repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "provenance_hit" in manifest
        assert manifest["provenance_hit"] is True