# hotdocs-criterion: sha256:b263bb901afaa9d26c635b0e72698ffdb28d42bcf1acb575d58d0fc7e0c0dcf8
import dataclasses
import json

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
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _build_inputs():
    cls = provenance_writer.ProvenanceInputs
    return cls(
        component_id="comp-foo",
        generation_result={
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "environment", "message": "no model"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        verification_report=None,
        license_scan_result={
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
        },
        secret_scan_result={
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        provenance_hit=False,
        attempts=1,
        attempt_history=[
            {
                "number": 1,
                "outcome": "model_call_error",
                "retry_feedback": [],
                "error_category": "environment",
                "failed_requirements": [],
                "transcript_sha256": None,
            }
        ],
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def test_provenance_inputs_is_a_real_dataclass():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = provenance_writer.ProvenanceInputs
    assert isinstance(cls, type)
    assert dataclasses.is_dataclass(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    for name in DOCUMENTED_FIELDS:
        assert name in names, name


def test_construct_with_every_documented_field_by_keyword():
    inputs = _build_inputs()
    assert dataclasses.is_dataclass(inputs)
    assert isinstance(inputs, provenance_writer.ProvenanceInputs)
    assert field(inputs, "component_id") == "comp-foo"
    assert field(inputs, "attempts") == 1
    assert field(inputs, "provenance_hit") is False
    assert field(inputs, "verification_report") is None


def test_write_provenance_accepts_dataclass_instance(tmp_path):
    inputs = _build_inputs()
    result = provenance_writer.write_provenance("comp-foo", inputs, tmp_path)
    assert result is None

    gen_manifest = tmp_path / "gen" / "foo" / ".provenance.json"
    ver_manifest = tmp_path / "verification" / "foo" / ".provenance.json"
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()
    assert gen_bytes == ver_bytes

    doc = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(doc, dict)
    assert doc["attempts"] == 1
    assert doc["provenance_hit"] is False
    assert doc["gate_versions"] == {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}
    assert doc["verification_report"] is None