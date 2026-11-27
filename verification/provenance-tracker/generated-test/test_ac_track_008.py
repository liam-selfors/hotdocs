# hotdocs-criterion: sha256:3cc516d0b996c9e8e9ae74dff779b0286e18772811170f5627dfc3dc6a0caf23
"""AC-TRACK-008: last_requirement_failures returns the failing R-ids of the
most recent AttemptRecord with a non-null verification. It leaves out an R-id
whose non-pass covering criteria all have failure_origin "test" or
"environment"."""

from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v1",
        "files": [],
        "model_call_error": None,
    }


def _verification(requirement_results, criteria):
    overall = "pass" if all(v == "pass" for v in requirement_results.values()) else "fail"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _write(repo_root, verification):
    record = provenance_tracker.write_attempt_record(
        "comp-foo",
        _generation_result(),
        verification,
        "sha256:" + "0" * 64,
        repo_root,
    )
    assert field(record, "component_id") == "comp-foo"
    return record


def test_flat_requirement_results_failing_ids(tmp_path):
    repo_root = Path(tmp_path)
    verification = _verification(
        {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
             "result": "fail", "failure_origin": "implementation",
             "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
        ],
    )
    _write(repo_root, verification)

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert list(result) == ["R-FOO-002"]


def test_test_origin_failure_left_out(tmp_path):
    repo_root = Path(tmp_path)
    verification = _verification(
        {"R-FOO-001": "fail", "R-FOO-002": "fail"},
        [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "fail", "failure_origin": "test",
             "failure_detail": {"message": "m", "expected": None, "actual": None}},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
             "result": "fail", "failure_origin": "implementation",
             "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
        ],
    )
    _write(repo_root, verification)

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert list(result) == ["R-FOO-002"]


def test_pass_plus_environment_left_out_test_plus_absent_origin_kept(tmp_path):
    repo_root = Path(tmp_path)
    verification = _verification(
        {"R-FOO-001": "fail", "R-FOO-002": "fail"},
        [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "fail", "failure_origin": "environment",
             "failure_detail": {"message": "m", "expected": None, "actual": None}},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test",
             "result": "fail", "failure_origin": "test",
             "failure_detail": {"message": "m", "expected": None, "actual": None}},
            {"id": "AC-FOO-004", "covers": "R-FOO-002", "kind": "compiled",
             "result": "fail",
             "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
        ],
    )
    _write(repo_root, verification)

    result = provenance_tracker.last_requirement_failures("comp-foo", repo_root)

    assert list(result) == ["R-FOO-002"]