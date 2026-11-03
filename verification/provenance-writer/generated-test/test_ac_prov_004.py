import json
import tempfile
from pathlib import Path

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_inputs(fields):
    inputs_cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if inputs_cls is not None:
        return inputs_cls(**fields)
    return fields


def test_ac_prov_004_provenance_hit_true_propagates_to_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        generation_result = {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": "sealed-component",
            "retry_feedback": None,
        }

        license_scan_result = {
            "component_id": "comp-foo",
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

        fields = {
            "component_id": "comp-foo",
            "generation_result": generation_result,
            "verification_report": None,
            "license_scan_result": license_scan_result,
            "secret_scan_result": secret_scan_result,
            "provenance_hit": True,
            "attempts": 1,
            "gate_versions": {
                "compiler": "1.0.0",
                "license_scanner": "k-gram@1.0.0",
            },
        }

        inputs = _make_inputs(fields)

        provenance_writer.write_provenance("comp-foo", inputs, repo_root)

        gen_manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
        verification_manifest_path = (
            repo_root / "verification" / "foo" / ".provenance.json"
        )

        assert gen_manifest_path.is_file(), "gen manifest was not written"
        assert verification_manifest_path.is_file(), (
            "verification manifest was not written"
        )

        with open(gen_manifest_path) as f:
            gen_manifest = json.load(f)
        with open(verification_manifest_path) as f:
            verification_manifest = json.load(f)

        assert _get(gen_manifest, "provenance_hit") is True
        assert _get(verification_manifest, "provenance_hit") is True