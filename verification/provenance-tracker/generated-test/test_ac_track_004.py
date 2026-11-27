# hotdocs-criterion: sha256:ca1df589bc12aabf44dfce9fce640ba30989fd54106131624f11e1d7ad2db1d7
"""AC-TRACK-004: write_attempt_record takes plain-value generation/verification
inputs and provenance_tracker never depends on component-gate-runner's types."""

import copy
import inspect
import json

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "prompt_version": "v11",
        "files": [
            {"path": "gen/foo/foo.py", "content": "def foo():\n    return 1\n"},
        ],
        "model_call_error": None,
        "cache_hit": False,
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
        "drivers": [],
        "overall": "fail",
    }


def test_ac_track_004_plain_value_inputs_and_no_gate_runner_dependency(tmp_path):
    repo_root = tmp_path
    generation_result = _generation_result()
    verification_report = _verification_report()
    expected_generation = copy.deepcopy(generation_result)
    expected_verification = copy.deepcopy(verification_report)

    record = provenance_tracker.write_attempt_record(
        "comp-foo", generation_result, verification_report, "sha256:abc", repo_root
    )

    # The returned AttemptRecord carries generation/verification from the two dicts.
    generation = field(record, "generation")
    verification = field(record, "verification")
    assert json.loads(json.dumps(generation)) == expected_generation
    assert json.loads(json.dumps(verification)) == expected_verification
    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == "sha256:abc"

    # Exactly one file was written under .hotdocs/attempts/comp-foo/.
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1, files

    # The module source never references component-gate-runner or its result type.
    source = inspect.getsource(provenance_tracker)
    assert "component_gate_runner" not in source
    assert "ComponentPipelineResult" not in source