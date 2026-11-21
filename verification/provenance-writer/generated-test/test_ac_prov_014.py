# hotdocs-criterion: sha256:c16ca7eb9600515a2bf99a71bd2650d86f911c12f38ce1da029d3c7de69f3853
"""AC-PROV-014: write_provenance accepts ProvenanceInputs as a plain dict or
as a ProvenanceInputs instance, reading every top-level field with dual
dict-or-attribute access (R-PROV-014)."""

import copy
import dataclasses
import json
import re
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _values():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SHA_A,
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
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "gpt-5", "seed": 0,
                                "prompt_version": "v1", "cache_hit": False}},
        ],
        "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {"kind": "python", "path": ".", "definition_sha256": None,
             "adapter_sha256": SHA_B, "versions": {"python": "3.12.4"},
             "lockfile_sha256": None},
            {"kind": "javascript", "path": "static/app.js",
             "definition_sha256": SHA_C, "adapter_sha256": SHA_B,
             "versions": {"node": "24.1.0"}, "lockfile_sha256": None},
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
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [
            {"number": 1, "outcome": "verification_failed",
             "retry_feedback": [], "error_category": None,
             "failed_requirements": ["R-WIDGET-003"],
             "transcript_sha256": None},
            {"number": 2, "outcome": "passed",
             "retry_feedback": ["R-WIDGET-003"], "error_category": None,
             "failed_requirements": [], "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0",
                          "license_scanner": "license_scanner@4.0.0-no-reference-corpus"},
    }


def _make_instance(values):
    cls = provenance_writer.ProvenanceInputs
    if dataclasses.is_dataclass(cls):
        names = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in values.items() if k in names}
    else:
        kwargs = dict(values)
    return cls(**kwargs)


def _read_manifest(repo_root):
    gen_path = repo_root / "gen" / SLUG / ".provenance.json"
    ver_path = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file(), "manifest missing at " + str(gen_path)
    assert ver_path.is_file(), "manifest missing at " + str(ver_path)
    gen_bytes = gen_path.read_bytes()
    assert gen_bytes == ver_path.read_bytes()
    manifest = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(manifest, dict)
    return manifest


TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def test_dict_inputs_write_same_manifest_as_instance(tmp_path):
    dict_root = tmp_path / "dict_root"
    inst_root = tmp_path / "inst_root"
    dict_root.mkdir()
    inst_root.mkdir()

    dict_inputs = copy.deepcopy(_values())
    assert isinstance(dict_inputs, dict)
    instance_inputs = _make_instance(copy.deepcopy(_values()))
    assert not isinstance(instance_inputs, dict)

    result = provenance_writer.write_provenance(COMPONENT_ID, dict_inputs, dict_root)
    assert result is None
    provenance_writer.write_provenance(COMPONENT_ID, instance_inputs, inst_root)

    from_dict = _read_manifest(dict_root)
    from_instance = _read_manifest(inst_root)

    # generated_at is the current wall-clock time; it may legitimately
    # differ between two calls, so check its shape and compare the rest.
    for manifest in (from_dict, from_instance):
        assert "generated_at" in manifest
        assert TIMESTAMP_RE.match(manifest["generated_at"])

    assert set(from_dict) == set(from_instance)
    for key in from_dict:
        if key == "generated_at":
            continue
        assert from_dict[key] == from_instance[key], key

    # The dict-shaped inputs' top-level fields were genuinely read.
    values = _values()
    assert from_dict["provenance_hit"] is False
    assert from_dict["attempts"] == 2
    assert from_dict["gate_versions"] == values["gate_versions"]
    assert from_dict["license_scan"] == values["license_scan_result"]
    assert from_dict["secret_scan"] == values["secret_scan_result"]
    assert from_dict["verification_report"] == values["verification_report"]
    assert from_dict["spec_bundle_hash"] == SHA_A
    assert from_dict["model_pin"] == "claude-sonnet-5"
    assert from_dict["assets"] == values["verification_report"]["assets"]


def test_instance_inputs_write_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    instance_inputs = _make_instance(copy.deepcopy(_values()))
    assert not isinstance(instance_inputs, dict)
    assert field(instance_inputs, "component_id") == COMPONENT_ID

    provenance_writer.write_provenance(COMPONENT_ID, instance_inputs, repo_root)

    manifest = _read_manifest(repo_root)
    assert manifest["attempts"] == 2
    assert manifest["provenance_hit"] is False
    assert manifest["gate_versions"] == _values()["gate_versions"]