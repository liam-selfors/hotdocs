import provenance_tracker


def test_last_requirement_failures_returns_failing_r_ids(tmp_path):
    repo_root = tmp_path

    # verification is non-null, so model_call_error must be null (AttemptRecord.md invariant)
    generation_result = {
        "model_call_error": None,
    }
    verification_report = {
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
        "mutation_score": 1.0,
        "overall": "fail",
    }
    spec_bundle_hash = "sha256:" + "a" * 64

    provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result,
        verification_report,
        spec_bundle_hash,
        repo_root,
    )

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert result == ["R-FOO-002"]