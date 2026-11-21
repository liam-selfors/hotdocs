# hotdocs-criterion: sha256:5a92a7e6edfb5d585348685697a1f5637347b2500f888085613eda8dc868e8ba
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
)


def _build_inputs():
    cls = provenance_writer.ProvenanceInputs
    return cls(
        component_id="comp-foo",
        generation_result={"files": {}},
        verification_report=None,
        license_scan_result={},
        secret_scan_result={},
        provenance_hit=False,
        attempts=1,
        attempt_history=[],
        gate_versions={},
    )


def test_provenance_inputs_is_real_dataclass_constructible_by_keyword():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = getattr(provenance_writer, "ProvenanceInputs")
    assert isinstance(cls, type)
    assert dataclasses.is_dataclass(cls)

    field_names = {f.name for f in dataclasses.fields(cls)}
    for name in DOCUMENTED_FIELDS:
        assert name in field_names, "missing documented field: " + repr(name)

    inputs = _build_inputs()
    assert dataclasses.is_dataclass(inputs)
    assert isinstance(inputs, cls)
    assert inputs.component_id == "comp-foo"
    assert inputs.attempts == 1
    assert inputs.provenance_hit is False
    assert inputs.verification_report is None


def test_write_provenance_accepts_dataclass_inputs_and_writes_manifest(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    result = provenance_writer.write_provenance("comp-foo", inputs, repo_root)
    assert result is None

    gen_manifest = repo_root / "gen" / "foo" / ".provenance.json"
    ver_manifest = repo_root / "verification" / "foo" / ".provenance.json"
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()
    assert gen_bytes == ver_bytes

    manifest = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(manifest, dict)
    assert manifest.get("provenance_hit") is False
    assert manifest.get("attempts") == 1
    assert manifest.get("gate_versions") == {}
    assert manifest.get("verification_report") is None