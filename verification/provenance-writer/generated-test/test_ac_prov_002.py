# hotdocs-criterion: sha256:4cd1ae49fb2d3e1db8385d1757ca8131b58adf1e37609eedac7ba9d514ae29c8
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _contains_key(value, key):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == key:
                return True
            if _contains_key(v, key):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _inputs():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        # An extra field that must never be written into the manifest.
        "sample_index": 3,
    }
    return {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def test_ac_prov_002_fields_copied_from_generation_result_and_no_sample_index(tmp_path):
    repo_root = Path(tmp_path)

    result = provenance_writer.write_provenance("comp-foo", _inputs(), repo_root)
    assert result is None

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)

        assert field(manifest, "model_pin") == "claude-sonnet-5"
        assert field(manifest, "prompt_version") == "v1"
        assert field(manifest, "retry_feedback") == ["R-FOO-002"]
        assert field(manifest, "spec_bundle_hash") == "sha256:" + "a" * 64

        assert not _contains_key(manifest, "sample_index"), (
            "sample_index must not appear anywhere in " + str(path)
        )