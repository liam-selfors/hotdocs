# hotdocs-criterion: sha256:62f82b7c061ca941db10cc57565ac760283632e849b6ccd03e4acc5424286c8d
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
        "model_call_error": None,
        "files": [{"path": "gen/foo/foo.py", "content": "x = 1\n"}],
    }
    verification = {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": {
                    "message": "m",
                    "actual": {"b", "a"},
                    "raw": b"x",
                },
            }
        ],
        "requirement_results": {"R-FOO-001": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "fail",
    }

    # Must not raise.
    provenance_tracker.write_attempt_record(
        component_id,
        generation,
        verification,
        "sha256:" + "0" * 64,
        repo_root,
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1, files

    data = json.loads(files[0].read_text(encoding="utf-8"))
    recorded_verification = data["verification"]
    assert recorded_verification is not None

    criteria = recorded_verification["criteria"]
    matching = [c for c in criteria if c.get("id") == "AC-FOO-001"]
    assert len(matching) == 1
    detail = matching[0]["failure_detail"]
    assert detail["message"] == "m"
    assert detail["actual"] == ["a", "b"]
    assert detail["raw"] == "x"