import json
from pathlib import Path

import pytest

import provenance_writer


VALID_SOURCE_HASH = "sha256:" + ("ab01" * 16)


def valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_SOURCE_HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": {
            "overall": "pass",
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            ],
        },
    }


def assert_nothing_written(repo_root):
    assert list(Path(repo_root).rglob(".sealed-provenance.json")) == []


def call_and_expect_invalid(component_id, inputs, repo_root):
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    assert_nothing_written(repo_root)


def read_manifest(repo_root, source_path):
    manifest_path = Path(repo_root) / source_path.rstrip("/") / ".sealed-provenance.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_inputs_not_a_mapping_at_all(tmp_path):
    for i, bad in enumerate((None, ["a", "b"], "not-a-mapping")):
        repo_root = tmp_path / f"notmap_{i}"
        repo_root.mkdir()
        call_and_expect_invalid("comp-foo", bad, repo_root)


def test_missing_each_required_field(tmp_path):
    fields = [
        "component_id",
        "owners",
        "source_path",
        "source_hash",
        "verifier_version",
        "verification_report",
    ]
    for i, field in enumerate(fields):
        repo_root = tmp_path / f"missing_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        del inputs[field]
        call_and_expect_invalid("comp-foo", inputs, repo_root)


def test_component_id_invalid_values(tmp_path):
    for i, bad in enumerate((5, "Comp-foo", "foo")):
        repo_root = tmp_path / f"cid_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["component_id"] = bad
        call_and_expect_invalid(bad, inputs, repo_root)


def test_owners_invalid_values(tmp_path):
    bad_values = ("pipeline-team", [], [5], ["pipeline-team", ""], ["Pipeline"])
    for i, bad in enumerate(bad_values):
        repo_root = tmp_path / f"owners_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["owners"] = bad
        call_and_expect_invalid(inputs["component_id"], inputs, repo_root)


def test_source_path_invalid_values(tmp_path):
    bad_values = (5, "a b/", "../x/", "gen/foo/", "/abs/")
    for i, bad in enumerate(bad_values):
        repo_root = tmp_path / f"sp_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["source_path"] = bad
        call_and_expect_invalid(inputs["component_id"], inputs, repo_root)


def test_source_hash_invalid_values(tmp_path):
    bad_values = (
        5,
        "sha256:" + ("a" * 63),
        "sha256:" + ("A" * 64),
        "sha1:" + ("a" * 64),
    )
    for i, bad in enumerate(bad_values):
        repo_root = tmp_path / f"sh_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["source_hash"] = bad
        call_and_expect_invalid(inputs["component_id"], inputs, repo_root)


def test_verifier_version_invalid_values(tmp_path):
    bad_values = (5, "verifier-orchestrator@2", "other@2.0.0")
    for i, bad in enumerate(bad_values):
        repo_root = tmp_path / f"vv_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["verifier_version"] = bad
        call_and_expect_invalid(inputs["component_id"], inputs, repo_root)


def test_verification_report_invalid_values(tmp_path):
    bad_values = (
        None,
        ["not", "a", "mapping"],
        {"overall": "ok", "criteria": [{"result": "pass"}]},
        {"overall": 5, "criteria": [{"result": "pass"}]},
        {"overall": "pass", "criteria": "nope"},
        {"overall": "pass", "criteria": [{"id": "AC-X-001"}]},
        {"overall": "pass", "criteria": [{"result": "pass"}, {"result": "skipped"}]},
    )
    for i, bad in enumerate(bad_values):
        repo_root = tmp_path / f"vr_{i}"
        repo_root.mkdir()
        inputs = valid_inputs()
        inputs["verification_report"] = bad
        call_and_expect_invalid(inputs["component_id"], inputs, repo_root)


def test_report_fail_all_fail_is_written(tmp_path):
    repo_root = tmp_path / "fail_all"
    repo_root.mkdir()
    inputs = valid_inputs()
    inputs["verification_report"] = {
        "overall": "fail",
        "criteria": [{"result": "fail"}, {"result": "fail"}],
    }
    provenance_writer.write_sealed_provenance(inputs["component_id"], inputs, repo_root)
    manifest = read_manifest(repo_root, inputs["source_path"])
    assert manifest["characterization"]["overall"] == "fail"
    assert manifest["characterization"]["criteria_passed"] == 0
    assert manifest["characterization"]["criteria_total"] == 2


def test_report_fail_with_skipped_entries_is_written(tmp_path):
    repo_root = tmp_path / "fail_skipped"
    repo_root.mkdir()
    inputs = valid_inputs()
    inputs["verification_report"] = {
        "overall": "fail",
        "criteria": [
            {"result": "pass"},
            {"result": "skipped"},
            {"result": "fail"},
        ],
    }
    provenance_writer.write_sealed_provenance(inputs["component_id"], inputs, repo_root)
    manifest = read_manifest(repo_root, inputs["source_path"])
    assert manifest["characterization"]["overall"] == "fail"
    assert manifest["characterization"]["criteria_passed"] == 1
    assert manifest["characterization"]["criteria_total"] == 3


def test_source_path_no_trailing_slash_written_unchanged(tmp_path):
    repo_root = tmp_path / "no_slash"
    repo_root.mkdir()
    inputs = valid_inputs()
    inputs["source_path"] = "pipeline/foo"
    provenance_writer.write_sealed_provenance(inputs["component_id"], inputs, repo_root)
    manifest_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_path"] == "pipeline/foo"