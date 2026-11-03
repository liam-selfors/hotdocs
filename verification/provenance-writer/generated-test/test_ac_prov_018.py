import hashlib
import json
import re

import provenance_writer


SOURCE_HASH = "sha256:" + hashlib.sha256(b"ac-prov-018-fixture").hexdigest()
WRITTEN_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

EXPECTED_KEY_ORDER = [
    "kind",
    "version",
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "characterization",
    "written_at",
]


class FakeCriterion:
    def __init__(self, result):
        self.result = result


def _all_pass_report():
    return {
        "overall": "pass",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "compiled", "result": "pass"},
        ],
    }


def test_sealed_provenance_all_pass_writes_manifest_only(tmp_path):
    inputs = provenance_writer.SealedProvenanceInputs(
        component_id="comp-foo",
        owners=["pipeline-team", "alice"],
        source_path="pipeline/foo/",
        source_hash=SOURCE_HASH,
        verifier_version="verifier-orchestrator@2.0.0",
        verification_report=_all_pass_report(),
    )

    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)

    manifest_path = tmp_path / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest_path.exists()

    text = manifest_path.read_text()
    data = json.loads(text)

    assert list(data.keys()) == EXPECTED_KEY_ORDER

    assert data["kind"] == "sealed-provenance"
    assert data["version"] == 1
    assert isinstance(data["version"], int) and not isinstance(data["version"], bool)

    assert data["component_id"] == "comp-foo"
    assert data["owners"] == ["pipeline-team", "alice"]
    assert data["source_path"] == "pipeline/foo/"
    assert data["source_hash"] == SOURCE_HASH
    assert data["verifier_version"] == "verifier-orchestrator@2.0.0"

    assert data["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert isinstance(data["characterization"]["criteria_passed"], int)
    assert not isinstance(data["characterization"]["criteria_passed"], bool)
    assert isinstance(data["characterization"]["criteria_total"], int)
    assert not isinstance(data["characterization"]["criteria_total"], bool)

    assert WRITTEN_AT_RE.match(data["written_at"])

    assert not (tmp_path / "gen").exists()
    assert not (tmp_path / "verification").exists()


def test_sealed_provenance_one_fail_characterization(tmp_path):
    report = {
        "overall": "fail",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "compiled", "result": "fail"},
        ],
    }
    inputs = provenance_writer.SealedProvenanceInputs(
        component_id="comp-foo",
        owners=["pipeline-team", "alice"],
        source_path="pipeline/foo/",
        source_hash=SOURCE_HASH,
        verifier_version="verifier-orchestrator@2.0.0",
        verification_report=report,
    )

    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)

    manifest_path = tmp_path / "pipeline" / "foo" / ".sealed-provenance.json"
    data = json.loads(manifest_path.read_text())

    assert data["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }


def test_sealed_provenance_dict_inputs_and_attribute_criteria(tmp_path):
    report = {
        "overall": "pass",
        "criteria": [
            FakeCriterion("pass"),
            FakeCriterion("pass"),
            FakeCriterion("pass"),
        ],
    }
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team", "alice"],
        "source_path": "pipeline/foo/",
        "source_hash": SOURCE_HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": report,
    }

    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)

    manifest_path = tmp_path / "pipeline" / "foo" / ".sealed-provenance.json"
    data = json.loads(manifest_path.read_text())

    assert list(data.keys()) == EXPECTED_KEY_ORDER
    assert data["kind"] == "sealed-provenance"
    assert data["version"] == 1
    assert data["component_id"] == "comp-foo"
    assert data["owners"] == ["pipeline-team", "alice"]
    assert data["source_path"] == "pipeline/foo/"
    assert data["source_hash"] == SOURCE_HASH
    assert data["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert data["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert WRITTEN_AT_RE.match(data["written_at"])

    assert not (tmp_path / "gen").exists()
    assert not (tmp_path / "verification").exists()