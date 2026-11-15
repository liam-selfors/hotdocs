import provenance_tracker

from pathlib import Path


def _generation_result():
    # A successful generation: no model_call_error, so verification is non-null.
    return {
        "component_id": "comp-foo",
        "model_call_error": None,
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "files": [
            {"path": "gen/foo/foo.py", "content": "def f():\n    return 1\n"}
        ],
    }


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "result.foo equals 5 failed",
                    "expected": 5,
                    "actual": 3,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }


def test_last_requirement_failures_returns_exactly_failing_rids(tmp_path):
    repo_root = Path(tmp_path)

    # Given comp-foo's most recent AttemptRecord with a non-null verification
    # whose requirement_results is {"R-FOO-001": "pass", "R-FOO-002": "fail"},
    # written via this component's own write_attempt_record.
    provenance_tracker.write_attempt_record(
        "comp-foo",
        _generation_result(),
        _verification_report(),
        "sha256:" + "ab" * 32,
        repo_root,
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts"
    assert attempts_dir.is_dir()

    # When last_requirement_failures("comp-foo", repo_root) is called
    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    # Then it returns exactly ["R-FOO-002"]
    assert isinstance(result, list)
    assert result == ["R-FOO-002"]