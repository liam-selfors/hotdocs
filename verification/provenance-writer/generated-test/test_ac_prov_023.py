# hotdocs-criterion: sha256:6aa62bfa790d7acc65747a412b515a6d58ab7faa4281a391b03f48160778a39b
import json
import pathlib

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-003"


class Slotted:
    __slots__ = ("x",)


def make_inputs(actual):
    failure_detail = {
        "message": "m",
        "expected": "e",
        "actual": actual,
        "raw": b"x",
        "where": pathlib.Path("p"),
    }
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            },
            {
                "id": CRITERION_ID,
                "covers": "R-FOO-003",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": failure_detail,
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-003": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "fail",
    }
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "1" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "X = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def read_manifest(repo_root):
    path = repo_root / "verification" / SLUG / ".provenance.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def failing_detail(manifest):
    report = manifest["verification_report"]
    assert report is not None
    matches = [c for c in report["criteria"] if c["id"] == CRITERION_ID]
    assert len(matches) == 1
    return matches[0]["failure_detail"]


def test_set_bytes_and_path_are_converted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs({"b", "a"})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    detail = failing_detail(read_manifest(repo_root))
    assert detail["actual"] == ["a", "b"]
    assert detail["raw"] == "x"
    assert detail["where"] == "p"
    assert detail["message"] == "m"
    assert detail["expected"] == "e"


def test_slotted_object_becomes_repr_string(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs(Slotted())

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    detail = failing_detail(read_manifest(repo_root))
    actual = detail["actual"]
    assert isinstance(actual, str)
    assert actual.startswith("<")