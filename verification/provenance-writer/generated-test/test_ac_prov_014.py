# hotdocs-criterion: sha256:aebd82fe1fa04b1bd64ce95c3415bd585b65aebe441a5fd50dcf498bdb82b3ed
import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget"
SLUG = "widget"

# Fields that legitimately differ between two separate writes: the
# writer's own wall-clock time and any per-write run identifier.
VOLATILE_FIELDS = {"generated_at", "verification_run_id"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _values():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget.py": "def hello():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002",
             "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
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
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _make_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "gen" / SLUG).mkdir(parents=True, exist_ok=True)
    (root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)
    return root


def _read_manifests(repo_root):
    gen_path = repo_root / "gen" / SLUG / ".provenance.json"
    ver_path = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file(), "missing manifest at " + str(gen_path)
    assert ver_path.is_file(), "missing manifest at " + str(ver_path)
    gen_manifest = json.loads(gen_path.read_text(encoding="utf-8"))
    ver_manifest = json.loads(ver_path.read_text(encoding="utf-8"))
    assert isinstance(gen_manifest, dict)
    assert isinstance(ver_manifest, dict)
    return gen_manifest, ver_manifest


def _instance_from(values):
    return provenance_writer.ProvenanceInputs(**copy.deepcopy(values))


def _assert_equivalent(a, b):
    assert set(a.keys()) == set(b.keys())
    for key in a:
        if key in VOLATILE_FIELDS:
            assert type(a[key]) is type(b[key]), key
            continue
        assert a[key] == b[key], "field " + repr(key) + " differs"


def test_dict_inputs_write_manifest_identical_to_instance_inputs(tmp_path):
    values = _values()

    dict_root = _make_repo(tmp_path / "dict_repo")
    inst_root = _make_repo(tmp_path / "inst_repo")

    dict_inputs = copy.deepcopy(values)
    assert isinstance(dict_inputs, dict)
    assert not isinstance(dict_inputs, provenance_writer.ProvenanceInputs)

    instance_inputs = _instance_from(values)
    assert not isinstance(instance_inputs, dict)

    # Neither shape may raise.
    provenance_writer.write_provenance(COMPONENT_ID, dict_inputs, Path(dict_root))
    provenance_writer.write_provenance(COMPONENT_ID, instance_inputs, Path(inst_root))

    dict_gen, dict_ver = _read_manifests(dict_root)
    inst_gen, inst_ver = _read_manifests(inst_root)

    # Every field matches between the dict-written and instance-written manifests.
    _assert_equivalent(dict_gen, inst_gen)
    _assert_equivalent(dict_ver, inst_ver)

    # The dict path actually read the inputs' fields, not defaults.
    assert dict_gen.get("provenance_hit") is False
    assert dict_gen.get("gate_versions") == values["gate_versions"]
    assert dict_gen.get("model_pin") == values["generation_result"]["model"]
    assert dict_gen.get("spec_bundle_hash") == values["generation_result"]["spec_bundle_hash"]
    assert dict_gen.get("verification_report") is not None
    assert field(dict_gen["verification_report"], "overall") == "pass"
    assert dict_gen.get("license_scan") is not None
    assert dict_gen.get("secret_scan") is not None


def test_instance_inputs_write_manifest_without_raising(tmp_path):
    values = _values()
    repo_root = _make_repo(tmp_path / "repo")

    instance_inputs = _instance_from(values)
    assert not isinstance(instance_inputs, dict)

    provenance_writer.write_provenance(COMPONENT_ID, instance_inputs, Path(repo_root))

    gen_manifest, ver_manifest = _read_manifests(repo_root)
    assert gen_manifest.get("model_pin") == values["generation_result"]["model"]
    assert gen_manifest.get("gate_versions") == values["gate_versions"]
    _assert_equivalent(gen_manifest, ver_manifest)