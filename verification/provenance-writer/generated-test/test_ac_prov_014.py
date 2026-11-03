import json
import re
import shutil
import tempfile
from pathlib import Path

import provenance_writer


_GENERATED_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

# Fields whose value legitimately varies between two otherwise-identical
# calls (wall-clock timestamp, a run identifier not derivable from inputs).
_VOLATILE_MANIFEST_KEYS = {"generated_at", "verification_run_id"}


def _gen_manifest_path(repo_root, slug):
    return Path(repo_root) / "gen" / slug / ".provenance.json"


def _verification_manifest_path(repo_root, slug):
    return Path(repo_root) / "verification" / slug / ".provenance.json"


def _strip_volatile(manifest):
    return {k: v for k, v in manifest.items() if k not in _VOLATILE_MANIFEST_KEYS}


def _real_shaped_field_values():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3",
        },
    }


def test_dict_shaped_inputs_match_equivalent_instance_shaped_inputs():
    field_values = _real_shaped_field_values()

    repo_root_dict = tempfile.mkdtemp()
    repo_root_obj = tempfile.mkdtemp()
    try:
        inputs_dict = {"component_id": "comp-dict-foo", **field_values}
        inputs_obj = provenance_writer.ProvenanceInputs(
            component_id="comp-obj-foo", **field_values
        )

        provenance_writer.write_provenance(
            "comp-dict-foo", inputs_dict, Path(repo_root_dict)
        )
        provenance_writer.write_provenance(
            "comp-obj-foo", inputs_obj, Path(repo_root_obj)
        )

        dict_gen_path = _gen_manifest_path(repo_root_dict, "dict-foo")
        dict_verif_path = _verification_manifest_path(repo_root_dict, "dict-foo")
        obj_gen_path = _gen_manifest_path(repo_root_obj, "obj-foo")
        obj_verif_path = _verification_manifest_path(repo_root_obj, "obj-foo")

        assert dict_gen_path.is_file()
        assert dict_verif_path.is_file()
        assert obj_gen_path.is_file()
        assert obj_verif_path.is_file()

        manifest_from_dict = json.loads(dict_gen_path.read_text())
        manifest_from_dict_copy = json.loads(dict_verif_path.read_text())
        manifest_from_obj = json.loads(obj_gen_path.read_text())
        manifest_from_obj_copy = json.loads(obj_verif_path.read_text())

        assert _GENERATED_AT_RE.match(manifest_from_dict["generated_at"])
        assert _GENERATED_AT_RE.match(manifest_from_obj["generated_at"])

        # Each run's own gen/ manifest and its verification/ copy agree.
        assert _strip_volatile(manifest_from_dict) == _strip_volatile(
            manifest_from_dict_copy
        )
        assert _strip_volatile(manifest_from_obj) == _strip_volatile(
            manifest_from_obj_copy
        )

        # The dict-shaped run and the instance-shaped run, built from the
        # same field values, produce an identical manifest.
        assert _strip_volatile(manifest_from_dict) == _strip_volatile(manifest_from_obj)

        assert manifest_from_dict["provenance_hit"] is False
        assert manifest_from_dict["gate_versions"] == field_values["gate_versions"]
        assert manifest_from_dict["verification_report"] == field_values["verification_report"]
        assert manifest_from_dict["license_scan"] == field_values["license_scan_result"]
        assert manifest_from_dict["secret_scan"] == field_values["secret_scan_result"]
    finally:
        shutil.rmtree(repo_root_dict, ignore_errors=True)
        shutil.rmtree(repo_root_obj, ignore_errors=True)


def test_instance_shaped_inputs_write_without_raising():
    field_values = _real_shaped_field_values()
    repo_root = tempfile.mkdtemp()
    try:
        inputs_obj = provenance_writer.ProvenanceInputs(
            component_id="comp-bar", **field_values
        )

        provenance_writer.write_provenance("comp-bar", inputs_obj, Path(repo_root))

        gen_path = _gen_manifest_path(repo_root, "bar")
        verif_path = _verification_manifest_path(repo_root, "bar")
        assert gen_path.is_file()
        assert verif_path.is_file()

        manifest = json.loads(gen_path.read_text())
        assert _GENERATED_AT_RE.match(manifest["generated_at"])
        assert manifest["provenance_hit"] is False
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)