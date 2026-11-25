# hotdocs-criterion: sha256:649f48e0d7b199731dee446f4f5b8f94af590a5daf4c7a37c1cb4d9ec642734d
import inspect
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_track_004_plain_values_no_gate_runner_dependency(tmp_path):
    repo_root = Path(tmp_path)

    generation_result = {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v11",
        "files": [{"path": "foo.py", "content": "X = 1\n"}],
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
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "mutation_error": None,
        "assets": [],
        "overall": "fail",
    }

    record = provenance_tracker.write_attempt_record(
        "comp-foo", generation_result, verification_report, "sha256:abc", repo_root
    )

    generation = field(record, "generation")
    verification = field(record, "verification")
    assert generation is not None
    assert verification is not None

    for key, expected in generation_result.items():
        assert field(generation, key) == expected, key
    for key, expected in verification_report.items():
        assert field(verification, key) == expected, key

    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == "sha256:abc"

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.rglob("*") if p.is_file()]
    assert len(files) == 1, files

    source = inspect.getsource(provenance_tracker)
    assert "component_gate_runner" not in source
    assert "ComponentPipelineResult" not in source