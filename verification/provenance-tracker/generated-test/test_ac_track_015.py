# hotdocs-criterion: sha256:9df7317124237a56459e0d8823e4ffe231d18cc9edee31ba0ba3234448076ee6
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_track_015_failure_detail_set_and_bytes_converted(tmp_path):
    repo_root = Path(tmp_path)
    component_id = "comp-foo"

    generation = {
        "component_id": component_id,
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "model_call_error": None,
        "files": [{"path": "gen/foo/foo.py", "content": "x = 1\n"}],
    }

    failing_criterion = {
        "id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "kind": "compiled",
        "result": "fail",
        "failure_origin": "implementation",
        "failure_detail": {"message": "m", "actual": {"b", "a"}, "raw": b"x"},
    }
    verification = {
        "component_id": component_id,
        "criteria": [failing_criterion],
        "requirement_results": {"R-FOO-001": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "fail",
    }

    spec_bundle_hash = "sha256:" + "0" * 64

    # Must not raise.
    provenance_tracker.write_attempt_record(
        component_id, generation, verification, spec_bundle_hash, repo_root
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1, files

    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert isinstance(record, dict)

    written_verification = record["verification"]
    assert isinstance(written_verification, dict)
    criteria = written_verification["criteria"]
    assert isinstance(criteria, list)
    matching = [c for c in criteria if c.get("id") == "AC-FOO-001"]
    assert len(matching) == 1
    detail = matching[0]["failure_detail"]

    assert detail["actual"] == ["a", "b"]
    assert detail["raw"] == "x"
    assert detail["message"] == "m"