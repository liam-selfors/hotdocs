# hotdocs-criterion: sha256:2c499e354b26e1caad149cbb95de43c88e560b93e3a262213b2219c2f36a6e5c
import inspect
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "files": [
            {"path": "gen/foo/foo.py", "content": "def foo():\n    return 1\n"}
        ],
        "model_call_error": None,
        "retry_feedback": [],
    }


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "generated-test",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 5, "actual": 3},
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "overall": "fail",
    }


def test_write_attempt_record_takes_plain_values_and_has_no_gate_runner_dependency(tmp_path):
    repo_root = Path(tmp_path)
    generation_result = _generation_result()
    verification_report = _verification_report()
    expected_generation = _generation_result()
    expected_verification = _verification_report()

    record = provenance_tracker.write_attempt_record(
        "comp-foo", generation_result, verification_report, "sha256:abc", repo_root
    )

    generation = field(record, "generation")
    verification = field(record, "verification")
    assert generation == expected_generation
    assert verification == expected_verification
    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == "sha256:abc"

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1, files

    source = inspect.getsource(provenance_tracker)
    assert "component_gate_runner" not in source
    assert "ComponentPipelineResult" not in source