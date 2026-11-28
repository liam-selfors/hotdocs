# hotdocs-criterion: sha256:04d5a682501a8a4963efe2b3b8a78189d7107206c3cf4a56ce43e64aab7abd9f
"""AC-PROV-014: write_provenance accepts ProvenanceInputs as a plain dict or as
a ProvenanceInputs instance, reading every top-level field with dual
dict-or-attribute access (R-PROV-014)."""

import copy
import json
import re

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _values():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
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
            {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002", "kind": "llm-judge",
             "result": "skipped", "rationale": None},
        ],
        "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "skipped"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "b" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "drivers": [],
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
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [
            {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
             "error_category": None, "failed_requirements": ["R-WIDGET-003"],
             "transcript_sha256": None},
            {"number": 2, "outcome": "passed", "retry_feedback": ["R-WIDGET-003"],
             "error_category": None, "failed_requirements": [],
             "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
        "spec_bundle_parts": {"spec": "sha256:" + "c" * 64,
                              "dependency_code": "sha256:" + "d" * 64},
    }


def _instance(values):
    return provenance_writer.ProvenanceInputs(**copy.deepcopy(values))


def _read_manifests(repo_root):
    # Exact paths: .provenance.json is a hidden file, never globbed.
    gen_path = repo_root / "gen" / SLUG / ".provenance.json"
    ver_path = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file(), "missing " + str(gen_path)
    assert ver_path.is_file(), "missing " + str(ver_path)
    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes
    return json.loads(gen_bytes.decode("utf-8"))


TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def test_dict_inputs_write_same_manifest_as_instance(tmp_path):
    values = _values()

    dict_root = tmp_path / "dict_root"
    dict_root.mkdir()
    inst_root = tmp_path / "inst_root"
    inst_root.mkdir()

    dict_inputs = copy.deepcopy(values)
    assert isinstance(dict_inputs, dict)
    assert not isinstance(dict_inputs, provenance_writer.ProvenanceInputs)

    provenance_writer.write_provenance(COMPONENT_ID, dict_inputs, dict_root)
    provenance_writer.write_provenance(COMPONENT_ID, _instance(values), inst_root)

    from_dict = _read_manifests(dict_root)
    from_inst = _read_manifests(inst_root)

    assert isinstance(from_dict, dict)
    assert set(from_dict.keys()) == set(from_inst.keys())

    # generated_at is the wall clock at write time; both must be well formed,
    # every other field must be identical.
    assert TIMESTAMP_RE.match(from_dict["generated_at"])
    assert TIMESTAMP_RE.match(from_inst["generated_at"])
    for key in from_inst:
        if key == "generated_at":
            continue
        assert from_dict[key] == from_inst[key], "field differs: " + key

    # The dict-shaped inputs' top-level fields were actually read.
    assert from_dict["license_scan"] == values["license_scan_result"]
    assert from_dict["secret_scan"] == values["secret_scan_result"]
    assert from_dict["verification_report"] == values["verification_report"]
    assert from_dict["gate_versions"] == values["gate_versions"]
    assert from_dict["provenance_hit"] is False
    assert from_dict["attempts"] == 2
    assert from_dict["spec_bundle_hash"] == values["generation_result"]["spec_bundle_hash"]
    assert from_dict["model_pin"] == "claude-sonnet-5"
    assert from_dict["verification_run_id"] == SLUG + "-attempt-2"


def test_instance_inputs_write_manifest(tmp_path):
    values = _values()
    inputs = _instance(values)
    assert not isinstance(inputs, dict)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    manifest = _read_manifests(tmp_path)
    assert manifest["license_scan"] == values["license_scan_result"]
    assert manifest["secret_scan"] == values["secret_scan_result"]
    assert manifest["verification_report"] == values["verification_report"]
    assert manifest["gate_versions"] == values["gate_versions"]
    assert manifest["provenance_hit"] is False
    assert manifest["attempts"] == 2
    assert TIMESTAMP_RE.match(manifest["generated_at"])