# hotdocs-criterion: sha256:ce0ff7fae57cbd6d2cd6ed44377bae40469627e4e3360486c2626dd9a74a0ec0
import json
import pathlib

import provenance_writer


class Slotted:
    __slots__ = ("x",)


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-002"


def _inputs(actual):
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
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": CRITERION_ID,
                "covers": "R-FOO-002",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": failure_detail,
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "fail",
    }
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"},
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


def _manifest_paths(repo_root):
    return [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]


def _criterion_detail(manifest):
    report = manifest["verification_report"]
    assert isinstance(report, dict)
    matches = [c for c in report["criteria"] if c.get("id") == CRITERION_ID]
    assert len(matches) == 1
    detail = matches[0]["failure_detail"]
    assert isinstance(detail, dict)
    return detail


def test_set_bytes_and_path_in_failure_detail_are_converted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(COMPONENT_ID, _inputs({"b", "a"}), repo_root)

    for path in _manifest_paths(repo_root):
        assert path.is_file(), path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        detail = _criterion_detail(manifest)
        assert detail["actual"] == ["a", "b"]
        assert detail["raw"] == "x"
        assert detail["where"] == "p"
        assert detail["message"] == "m"
        assert detail["expected"] == "e"


def test_slotted_object_in_failure_detail_becomes_repr_string(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(Slotted()), repo_root)

    for path in _manifest_paths(repo_root):
        assert path.is_file(), path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        detail = _criterion_detail(manifest)
        actual = detail["actual"]
        assert isinstance(actual, str)
        assert actual.startswith("<")