# hotdocs-criterion: sha256:068e51fcc439b4d1abe00c43efe9b9747e65dcfd8a11991f303b4b6a7ce7b119
import json
import pathlib
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-004"


class Slotted:
    __slots__ = ("x",)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
                "covers": "R-FOO-004",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": failure_detail,
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-004": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
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


def read_manifests(repo_root):
    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), "manifest missing at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def failing_detail(manifest):
    report = field(manifest, "verification_report")
    assert report is not None
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1
    return field(matches[0], "failure_detail")


def test_set_bytes_path_are_converted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs({"b", "a"})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in read_manifests(repo_root):
        detail = failing_detail(manifest)
        assert detail["message"] == "m"
        assert detail["expected"] == "e"
        assert detail["actual"] == ["a", "b"]
        assert detail["raw"] == "x"
        assert detail["where"] == "p"


def test_slotted_actual_becomes_repr_string(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs(Slotted())

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in read_manifests(repo_root):
        detail = failing_detail(manifest)
        actual = detail["actual"]
        assert isinstance(actual, str)
        assert actual.startswith("<")