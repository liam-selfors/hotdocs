import dataclasses
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"

DOCUMENTED_FIELDS = (
    "component_id",
    "generation_result",
    "verification_report",
    "license_scan_result",
    "secret_scan_result",
    "provenance_hit",
    "attempts",
    "gate_versions",
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "def bar(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
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
        "mutation_score": 0.92,
        "overall": "pass",
    }


def _license_scan_result():
    return {
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


def _secret_scan_result():
    return {
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


def _build_inputs():
    cls = getattr(provenance_writer, "ProvenanceInputs")
    return cls(
        component_id=COMPONENT_ID,
        generation_result=_generation_result(),
        verification_report=_verification_report(),
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=2,
        gate_versions={
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    )


def test_provenance_inputs_is_a_real_dataclass_constructible_by_keyword():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = provenance_writer.ProvenanceInputs
    assert isinstance(cls, type)
    assert dataclasses.is_dataclass(cls)

    names = {f.name for f in dataclasses.fields(cls)}
    for name in DOCUMENTED_FIELDS:
        assert name in names, f"ProvenanceInputs lacks documented field {name!r}"

    inputs = _build_inputs()
    assert isinstance(inputs, cls)
    assert dataclasses.is_dataclass(inputs)
    assert field(inputs, "component_id") == COMPONENT_ID
    assert field(inputs, "attempts") == 2
    assert field(inputs, "provenance_hit") is False


def test_write_provenance_accepts_dataclass_inputs_and_writes_manifest(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    # Must not raise.
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    candidates = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    written = [p for p in candidates if p.is_file()]
    assert written, (
        "write_provenance wrote no manifest at either "
        f"{candidates[0]} or {candidates[1]}"
    )
    for path in written:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)