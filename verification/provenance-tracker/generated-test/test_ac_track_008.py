import provenance_tracker


def test_last_requirement_failures_returns_failing_r_ids(tmp_path):
    repo_root = tmp_path

    generation_result = {"model_call_error": None}
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "boom", "expected": 1, "actual": 2},
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }

    provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result,
        verification_report,
        "sha256:" + "a" * 64,
        repo_root,
    )

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert result == ["R-FOO-002"]