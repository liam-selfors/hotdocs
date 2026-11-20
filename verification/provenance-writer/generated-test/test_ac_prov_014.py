# hotdocs-criterion: sha256:1c6314948a3d5e1d40f57c83d5d61011192a017c1d796248467519a348d7a5fc
import json
import re
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _values():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"widget_maker.py": "def make():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-WIDGET-003"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "cd" * 32,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
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
    attempt_history = [
        {
            "number": 1,
            "outcome": "verification_failed",
            "retry_feedback": [],
            "error_category": None,
            "failed_requirements": ["R-WIDGET-003"],
            "transcript_sha256": None,
        },
        {
            "number": 2,
            "outcome": "passed",
            "retry_feedback": ["R-WIDGET-003"],
            "error_category": None,
            "failed_requirements": [],
            "transcript_sha256": None,
        },
    ]
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": attempt_history,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _read_manifest(repo_root):
    gen_path = Path(repo_root) / "gen" / SLUG / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file(), "manifest not written at " + str(gen_path)
    assert ver_path.is_file(), "manifest not written at " + str(ver_path)
    return json.loads(gen_path.read_text(encoding="utf-8"))


def _instance(values):
    return provenance_writer.ProvenanceInputs(**values)


def test_dict_inputs_write_same_manifest_as_instance_inputs(tmp_path):
    dict_root = tmp_path / "dict_root"
    inst_root = tmp_path / "inst_root"
    dict_root.mkdir()
    inst_root.mkdir()

    dict_inputs = _values()
    assert isinstance(dict_inputs, dict)
    assert not isinstance(dict_inputs, provenance_writer.ProvenanceInputs)

    provenance_writer.write_provenance(COMPONENT_ID, dict_inputs, dict_root)
    provenance_writer.write_provenance(COMPONENT_ID, _instance(_values()), inst_root)

    from_dict = _read_manifest(dict_root)
    from_inst = _read_manifest(inst_root)

    assert isinstance(from_dict, dict)
    assert isinstance(from_inst, dict)
    assert set(from_dict.keys()) == set(from_inst.keys())

    # generated_at is the current time, so it may differ by a second
    # between the two writes; every other field must be identical.
    for manifest in (from_dict, from_inst):
        assert "generated_at" in manifest
        assert isinstance(manifest["generated_at"], str)
        assert TIMESTAMP_RE.match(manifest["generated_at"])

    for key in from_inst:
        if key == "generated_at":
            continue
        assert from_dict[key] == from_inst[key], "field " + repr(key) + " differs"

    # Sanity: the dict-built manifest actually carries the input values.
    assert from_dict["provenance_hit"] is False
    assert from_dict["attempts"] == 2
    assert from_dict["gate_versions"] == {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}
    assert from_dict["model_pin"] == "claude-sonnet-5"
    assert from_dict["spec_bundle_hash"] == "sha256:" + "ab" * 32
    assert from_dict["license_scan"] == _values()["license_scan_result"]
    assert from_dict["secret_scan"] == _values()["secret_scan_result"]
    assert from_dict["verification_report"] == _values()["verification_report"]
    assert from_dict["assets"] == _values()["verification_report"]["assets"]


def test_instance_inputs_write_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    inputs = _instance(_values())
    assert not isinstance(inputs, dict)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifest = _read_manifest(repo_root)
    assert isinstance(manifest, dict)
    assert manifest["attempts"] == 2
    assert manifest["provenance_hit"] is False
    assert manifest["gate_versions"] == {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}