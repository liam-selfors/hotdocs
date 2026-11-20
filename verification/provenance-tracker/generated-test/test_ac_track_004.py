# hotdocs-criterion: sha256:d1f65370f6102f9cd2e52e0cb3d0f460a782dfe5c9290a2e8200dbcdfcace098
import copy
import inspect
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "files": [
            {"path": "gen/foo/foo.py", "content": "def foo():\n    return 1\n"},
        ],
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "prompt_version": "v1",
        "model_call_error": None,
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
                "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:abc",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "fail",
    }


def test_ac_track_004_plain_values_and_no_gate_runner_dependency(tmp_path):
    repo_root = Path(tmp_path)
    generation_result = _generation_result()
    verification_report = _verification_report()
    expected_generation = copy.deepcopy(generation_result)
    expected_verification = copy.deepcopy(verification_report)

    record = provenance_tracker.write_attempt_record(
        "comp-foo", generation_result, verification_report, "sha256:abc", repo_root
    )

    generation = field(record, "generation")
    verification = field(record, "verification")
    assert json.loads(json.dumps(generation)) == expected_generation
    assert json.loads(json.dumps(verification)) == expected_verification
    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == "sha256:abc"

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1

    source = inspect.getsource(provenance_tracker)
    assert "component_gate_runner" not in source
    assert "ComponentPipelineResult" not in source