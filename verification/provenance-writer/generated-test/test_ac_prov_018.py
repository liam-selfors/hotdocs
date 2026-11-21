# hotdocs-criterion: sha256:344d64e28cb32878d523e55ebd02d4c4eeb119252712cccf8f1ab6df9908d21e
import json
import types
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


SOURCE_HASH = "sha256:" + "0123456789abcdef" * 4
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
COMPONENT_ID = "comp-foo"

EXPECTED_KEYS = [
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


def _criteria_dicts(results):
    entries = []
    for i, result in enumerate(results, start=1):
        entries.append(
            {
                "id": "AC-FOO-00" + str(i),
                "covers": "R-FOO-00" + str(i),
                "kind": "compiled",
                "result": result,
            }
        )
    return entries


def _criteria_objects(results):
    return [types.SimpleNamespace(**entry) for entry in _criteria_dicts(results)]


def _report(criteria, overall):
    return {
        "component_id": COMPONENT_ID,
        "criteria": criteria,
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def _fields(report):
    return {
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": SOURCE_HASH,
        "verifier_version": VERIFIER_VERSION,
        "verification_report": report,
    }


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _no_files_under(path):
    if not path.exists():
        return True
    return not any(p.is_file() for p in path.rglob("*"))


def _write_and_read(inputs, repo_root):
    before = _now()
    provenance_writer.write_sealed_provenance(COMPONENT_ID, inputs, repo_root)
    after = _now()
    manifest_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    written = datetime.strptime(manifest["written_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    assert before <= written <= after
    assert _no_files_under(repo_root / "gen")
    assert _no_files_under(repo_root / "verification")
    return manifest


def _assert_common(manifest):
    assert list(manifest.keys()) == EXPECTED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1
    assert type(manifest["version"]) is int
    assert manifest["component_id"] == COMPONENT_ID
    assert manifest["owners"] == OWNERS
    assert manifest["source_path"] == SOURCE_PATH
    assert manifest["source_hash"] == SOURCE_HASH
    assert manifest["verifier_version"] == VERIFIER_VERSION


def test_pass_report_writes_sealed_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report(_criteria_dicts(["pass", "pass", "pass"]), "pass")
    inputs = provenance_writer.SealedProvenanceInputs(**_fields(report))
    manifest = _write_and_read(inputs, repo_root)
    _assert_common(manifest)
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert list(manifest["characterization"].keys()) == [
        "overall",
        "criteria_passed",
        "criteria_total",
    ]


def test_fail_report_characterization(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report(_criteria_dicts(["pass", "fail", "pass"]), "fail")
    inputs = provenance_writer.SealedProvenanceInputs(**_fields(report))
    manifest = _write_and_read(inputs, repo_root)
    _assert_common(manifest)
    assert manifest["characterization"] == {
        "overall": "fail",
        "criteria_passed": 2,
        "criteria_total": 3,
    }


def test_dict_inputs_and_attribute_criteria_write_same_manifest(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    report_a = _report(_criteria_dicts(["pass", "pass", "pass"]), "pass")
    inputs_a = provenance_writer.SealedProvenanceInputs(**_fields(report_a))
    manifest_a = _write_and_read(inputs_a, repo_a)

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir()
    report_b = _report(_criteria_objects(["pass", "pass", "pass"]), "pass")
    inputs_b = _fields(report_b)
    manifest_b = _write_and_read(inputs_b, repo_b)

    _assert_common(manifest_b)
    assert manifest_b["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    a = {k: v for k, v in manifest_a.items() if k != "written_at"}
    b = {k: v for k, v in manifest_b.items() if k != "written_at"}
    assert a == b
    assert list(manifest_a.keys()) == list(manifest_b.keys())