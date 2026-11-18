# hotdocs-criterion: sha256:40f6dd29a574a703458e9f46f8a5e928f5749faa3ffc8ac0510dc5e8eb229069
import dataclasses
import json
from pathlib import Path

import provenance_writer


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
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def f():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
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
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }


def _license_scan_result():
    return {
        "component_id": "comp-foo",
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
    cls = provenance_writer.ProvenanceInputs
    return cls(
        component_id="comp-foo",
        generation_result=_generation_result(),
        verification_report=_verification_report(),
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=1,
        gate_versions={
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    )


def test_provenance_inputs_is_a_real_dataclass_with_documented_fields():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = provenance_writer.ProvenanceInputs
    assert isinstance(cls, type)
    assert dataclasses.is_dataclass(cls)

    names = [f.name for f in dataclasses.fields(cls)]
    for name in DOCUMENTED_FIELDS:
        assert name in names, "missing documented field: " + name

    inputs = _build_inputs()
    assert dataclasses.is_dataclass(inputs)
    assert isinstance(inputs, cls)
    assert field(inputs, "component_id") == "comp-foo"
    assert field(inputs, "attempts") == 1
    assert field(inputs, "provenance_hit") is False
    assert field(inputs, "gate_versions")["compiler"] == "1.0.0"


def test_write_provenance_accepts_dataclass_inputs_and_writes_manifest(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_manifest = repo_root / "gen" / "foo" / ".provenance.json"
    ver_manifest = repo_root / "verification" / "foo" / ".provenance.json"
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()

    for path in (gen_manifest, ver_manifest):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)