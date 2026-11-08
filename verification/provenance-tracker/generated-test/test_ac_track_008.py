import json
import tempfile
from pathlib import Path

import provenance_tracker


def test_last_requirement_failures_returns_failing_ids():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
        attempts_dir.mkdir(parents=True)

        attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
        record = {
            "attempt_id": attempt_id,
            "component_id": "comp-foo",
            "timestamp": "2026-10-25T14:32:01Z",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "generation": {
                "model_call_error": None,
                "file": {"path": "gen/foo/foo.py", "content": "x = 1\n"},
            },
            "verification": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {
                    "R-FOO-001": "pass",
                    "R-FOO-002": "fail",
                },
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "fail",
            },
        }

        record_path = attempts_dir / f"{attempt_id}.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")

        result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

        assert result == ["R-FOO-002"]