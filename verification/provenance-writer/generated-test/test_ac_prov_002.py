# hotdocs-criterion: sha256:50925742fb525683ac5afae511e26f3ee5482fc4cc66d1b5ed7062bf286a23bd
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


def _contains_text(text, needle):
    return needle in text


def test_ac_prov_002_generation_fields_copied_and_no_sample_index(tmp_path):
    repo_root = Path(tmp_path)
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
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
    inputs = {
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

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + repr(str(path))
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text)
        assert isinstance(manifest, dict)
        assert field(manifest, "model_pin") == "claude-sonnet-5"
        assert field(manifest, "prompt_version") == "v1"
        assert field(manifest, "retry_feedback") == ["R-FOO-002"]
        assert field(manifest, "spec_bundle_hash") == "sha256:" + "0" * 64
        assert not _contains_key(manifest, "sample_index"), (
            "sample_index field present in " + repr(str(path))
        )
        assert not _contains_text(text, '"sample_index"')