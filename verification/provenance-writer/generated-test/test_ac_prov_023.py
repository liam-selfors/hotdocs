# hotdocs-criterion: sha256:092a89ebbb9c4e95f0c70a15be2d85a5e88d3a0310b489b851485d85b15fa540
import json
import pathlib

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-004"


class S:
    __slots__ = ("x",)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _failure_detail(actual):
    return {
        "message": "m",
        "expected": "e",
        "actual": actual,
        "raw": b"x",
        "where": pathlib.Path("p"),
    }


def _inputs(actual):
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
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
                "failure_detail": _failure_detail(actual),
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-004": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "fail",
    }
    license_scan_result = {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _read_failure_detail(repo_root):
    path = repo_root / "verification" / SLUG / ".provenance.json"
    assert path.is_file(), "verification manifest not written at " + str(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    report = manifest["verification_report"]
    assert isinstance(report, dict)
    matches = [c for c in report["criteria"] if c.get("id") == CRITERION_ID]
    assert len(matches) == 1
    return matches[0]["failure_detail"]


def test_set_bytes_path_converted_in_failure_detail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(COMPONENT_ID, _inputs({"b", "a"}), repo_root)

    detail = _read_failure_detail(repo_root)
    assert detail["message"] == "m"
    assert detail["expected"] == "e"
    assert detail["actual"] == ["a", "b"]
    assert detail["raw"] == "x"
    assert detail["where"] == "p"


def test_slotted_object_actual_becomes_repr_string(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(S()), repo_root)

    detail = _read_failure_detail(repo_root)
    actual = detail["actual"]
    assert isinstance(actual, str)
    assert actual.startswith("<")