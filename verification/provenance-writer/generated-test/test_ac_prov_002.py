# hotdocs-criterion: sha256:495b99fb1b620fcbb49a421f09e4df6f0cfde12b1a751d5263211f5888508c5b
import json
from pathlib import Path

import provenance_writer


def _walk_keys(value):
    """Yield every dict key found anywhere in a parsed JSON value."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "unreachable"},
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def test_ac_prov_002_fields_copied_and_no_sample_index(tmp_path):
    repo_root = Path(tmp_path)
    inputs = {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "model_call_error",
                "retry_feedback": ["R-FOO-002"],
                "error_category": "network",
                "failed_requirements": [],
                "transcript_sha256": None,
            }
        ],
        "gate_versions": {},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text)
        assert isinstance(manifest, dict)

        assert manifest["model_pin"] == "claude-sonnet-5"
        assert manifest["prompt_version"] == "v1"
        assert manifest["retry_feedback"] == ["R-FOO-002"]

        keys = set(_walk_keys(manifest))
        assert "sample_index" not in keys, "sample_index found in " + str(path)
        assert "sample_index" not in text