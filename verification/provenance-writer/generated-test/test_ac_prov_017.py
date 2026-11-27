# hotdocs-criterion: sha256:aa71d145eb3d20f4f11a0d9a30263f9b128b19c622367dde407eb19e1266c9af
"""AC-PROV-017: ProvenanceInputs is a real, importable dataclass in
provenance_writer, constructible by keyword with every documented field,
and accepted by write_provenance, which writes a manifest without raising."""

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
    "attempt_history",
    "gate_versions",
    "spec_bundle_parts",
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _build_inputs():
    cls = provenance_writer.ProvenanceInputs
    return cls(
        component_id="comp-ac-prov-seventeen",
        generation_result={
            "component_id": "comp-ac-prov-seventeen",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "down"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        verification_report=None,
        license_scan_result={},
        secret_scan_result={},
        provenance_hit=False,
        attempts=1,
        attempt_history=[
            {
                "number": 1,
                "outcome": "model_call_error",
                "retry_feedback": [],
                "error_category": "network",
                "failed_requirements": [],
                "transcript_sha256": None,
            }
        ],
        gate_versions={"compiler": "1.0.0"},
        spec_bundle_parts={"spec": "sha256:" + "b" * 64,
                           "dependency_code": "sha256:" + "c" * 64},
    )


def test_provenance_inputs_is_real_dataclass_in_module():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = provenance_writer.ProvenanceInputs
    assert isinstance(cls, type)
    assert dataclasses.is_dataclass(cls)

    names = {f.name for f in dataclasses.fields(cls)}
    for name in DOCUMENTED_FIELDS:
        assert name in names, name

    inputs = _build_inputs()
    assert dataclasses.is_dataclass(inputs)
    assert isinstance(inputs, cls)
    assert field(inputs, "component_id") == "comp-ac-prov-seventeen"
    assert field(inputs, "attempts") == 1
    assert field(inputs, "provenance_hit") is False
    assert field(inputs, "verification_report") is None


def test_write_provenance_accepts_provenance_inputs_dataclass(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    result = provenance_writer.write_provenance(
        "comp-ac-prov-seventeen", inputs, repo_root
    )
    assert result is None

    gen_path = repo_root / "gen" / "ac-prov-seventeen" / ".provenance.json"
    ver_path = repo_root / "verification" / "ac-prov-seventeen" / ".provenance.json"
    assert gen_path.is_file()
    assert ver_path.is_file()
    assert gen_path.read_bytes() == ver_path.read_bytes()

    manifest = json.loads(gen_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    assert manifest["provenance_hit"] is False
    assert manifest["attempts"] == 1
    assert manifest["gate_versions"] == {"compiler": "1.0.0"}
    assert manifest["verification_report"] is None