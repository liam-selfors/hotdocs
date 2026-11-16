"""AC-PROV-014 (Covers: R-PROV-014).

`write_provenance` must read every top-level field of `inputs` with dual
dict-or-attribute access: a plain dict-shaped ProvenanceInputs writes a
manifest identical in every field to the one written from an equivalent
`ProvenanceInputs` instance, and an instance writes without raising.

Manifests are read from their exact paths, never by a glob: they are
hidden files (`.provenance.json`) that a glob such as `*.provenance.json`
would never match.
"""

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-dualshape"
SLUG = "prov-dualshape"

# Fields whose value may legitimately vary between two separate writes
# (a wall-clock write time, or a per-run identifier the writer may mint).
VOLATILE_FIELDS = ("generated_at", "verification_run_id")

TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _inputs_dict():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"prov_dualshape.py": "def compute_total(x):\n    return x + 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-PROV-DUALSHAPE-003"],
    }
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-PROV-DUALSHAPE-001", "covers": "R-PROV-DUALSHAPE-001",
             "kind": "compiled", "result": "pass"},
            {"id": "AC-PROV-DUALSHAPE-002", "covers": "R-PROV-DUALSHAPE-002",
             "kind": "llm-judge", "result": "skipped", "rationale": None},
            {"id": "AC-PROV-DUALSHAPE-003", "covers": "R-PROV-DUALSHAPE-003",
             "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "gpt-5", "seed": 0,
                                "prompt_version": "v1", "cache_hit": False}},
        ],
        "requirement_results": {
            "R-PROV-DUALSHAPE-001": "pass",
            "R-PROV-DUALSHAPE-002": "fail",
            "R-PROV-DUALSHAPE-003": "pass",
        },
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.12,
        "block_threshold": 0.70,
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
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "verifier": "verifier-orchestrator@2.0.0",
        },
    }


def _instance_from(values):
    cls = provenance_writer.ProvenanceInputs
    inst = cls(**copy.deepcopy(values))
    assert not isinstance(inst, dict), "ProvenanceInputs instance must not be a dict"
    return inst


def _manifest_paths(repo_root):
    return [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]


def _read_manifests(repo_root):
    manifests = []
    for path in _manifest_paths(repo_root):
        assert path.is_file(), f"manifest not written at exact path {path}"
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def _check_volatile(a, b, before, after):
    for key in VOLATILE_FIELDS:
        assert (key in a) == (key in b), f"{key!r} present in only one manifest"
        if key not in a:
            continue
        va, vb = a[key], b[key]
        assert type(va) is type(vb), f"{key!r} differs in shape: {va!r} vs {vb!r}"
    if "generated_at" in a and a["generated_at"] is not None:
        for value in (a["generated_at"], b["generated_at"]):
            assert isinstance(value, str) and TIMESTAMP_RE.match(value), value
            ts = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            assert before <= ts <= after, f"generated_at {value} outside [{before}, {after}]"


def _strip_volatile(manifest):
    return {k: v for k, v in manifest.items() if k not in VOLATILE_FIELDS}


def test_dict_shaped_inputs_write_manifest_identical_to_instance(tmp_path):
    values = _inputs_dict()
    assert isinstance(values, dict)

    dict_root = tmp_path / "dict-root"
    inst_root = tmp_path / "instance-root"
    dict_root.mkdir()
    inst_root.mkdir()

    before = datetime.now(timezone.utc).replace(microsecond=0)
    # Plain dict, not a ProvenanceInputs instance: must not raise.
    result = provenance_writer.write_provenance(
        COMPONENT_ID, copy.deepcopy(values), dict_root
    )
    assert result is None
    provenance_writer.write_provenance(COMPONENT_ID, _instance_from(values), inst_root)
    after = datetime.now(timezone.utc).replace(microsecond=0)

    dict_manifests = _read_manifests(dict_root)
    inst_manifests = _read_manifests(inst_root)

    for dict_manifest, inst_manifest in zip(dict_manifests, inst_manifests):
        assert isinstance(dict_manifest, dict)
        assert set(dict_manifest) == set(inst_manifest)
        _check_volatile(dict_manifest, inst_manifest, before, after)
        if dict_manifest.get("generated_at") == inst_manifest.get("generated_at") and \
                dict_manifest.get("verification_run_id") == inst_manifest.get("verification_run_id"):
            assert dict_manifest == inst_manifest
        else:
            assert _strip_volatile(dict_manifest) == _strip_volatile(inst_manifest)

    # The dict-shaped inputs' values really were read (not silently defaulted).
    m = dict_manifests[0]
    assert field(m, "provenance_hit") is False
    assert field(m, "gate_versions") == values["gate_versions"]
    assert field(m, "verification_report") == values["verification_report"]
    assert field(m, "license_scan") == values["license_scan_result"]
    assert field(m, "secret_scan") == values["secret_scan_result"]
    assert field(m, "model_pin") == values["generation_result"]["model"]


def test_instance_inputs_write_manifest_without_raising(tmp_path):
    values = _inputs_dict()
    inst = _instance_from(values)

    before = datetime.now(timezone.utc).replace(microsecond=0)
    result = provenance_writer.write_provenance(COMPONENT_ID, inst, tmp_path)
    after = datetime.now(timezone.utc).replace(microsecond=0)
    assert result is None

    manifests = _read_manifests(tmp_path)
    for manifest in manifests:
        assert isinstance(manifest, dict)
        assert field(manifest, "gate_versions") == values["gate_versions"]
        assert field(manifest, "provenance_hit") is False
        assert field(manifest, "verification_report") == values["verification_report"]
        generated_at = manifest.get("generated_at")
        if generated_at is not None:
            assert TIMESTAMP_RE.match(generated_at), generated_at
            ts = datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            assert before <= ts <= after