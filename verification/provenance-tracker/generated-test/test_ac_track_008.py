import json
from pathlib import Path

import provenance_tracker


def _write_attempt(repo_root, component_id, attempt_id, timestamp, requirement_results):
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    attempts_dir.mkdir(parents=True, exist_ok=True)

    overall = "fail" if "fail" in requirement_results.values() else "pass"
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:" + attempt_id,
        "generation": {
            "model_call_error": None,
            "file": f"gen/{component_id}/placeholder.py",
        },
        "verification": {
            "component_id": component_id,
            "criteria": [
                {
                    "id": f"AC-{rid.split('-', 1)[1]}",
                    "covers": rid,
                    "kind": "compiled",
                    "result": result,
                }
                for rid, result in requirement_results.items()
            ],
            "requirement_results": requirement_results,
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": overall,
        },
    }

    path = attempts_dir / f"{attempt_id}.json"
    path.write_text(json.dumps(record))
    return path


def test_last_requirement_failures_returns_failing_rids_from_most_recent_attempt(tmp_path):
    repo_root = tmp_path
    component_id = "comp-foo"

    # An older attempt, which must NOT be the one consulted.
    _write_attempt(
        repo_root,
        component_id,
        attempt_id="2026-10-20T10:00:00Z-aaaaaa",
        timestamp="2026-10-20T10:00:00Z",
        requirement_results={"R-FOO-001": "fail"},
    )

    # The most recent attempt, matching the criterion's Given.
    _write_attempt(
        repo_root,
        component_id,
        attempt_id="2026-10-25T14:32:01Z-a1b2c3",
        timestamp="2026-10-25T14:32:01Z",
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "fail"},
    )

    result = provenance_tracker.last_requirement_failures(component_id, repo_root)

    assert result == ["R-FOO-002"]