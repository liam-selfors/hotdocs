import io
import json
import sys

import pytest

import provenance_writer


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "print('hi')\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": {
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
            "overall": "pass",
        },
        "license_scan_result": {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.0",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.1,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan_result": {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0",
        },
    }


def _gen_manifest_path(repo_root):
    return repo_root / "gen" / "foo" / ".provenance.json"


def _verification_manifest_path(repo_root):
    return repo_root / "verification" / "foo" / ".provenance.json"


def test_valid_document_writes_both_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(
        ["provenance", "write", "comp-foo", f"--repo-root={tmp_path}"]
    )

    assert rc == 0
    assert _gen_manifest_path(tmp_path).exists()
    assert _verification_manifest_path(tmp_path).exists()


def test_missing_license_scan_result_returns_1_and_writes_nothing(tmp_path, monkeypatch):
    inputs = _valid_inputs()
    del inputs["license_scan_result"]
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(inputs)))

    rc = provenance_writer.main(
        ["provenance", "write", "comp-foo", f"--repo-root={tmp_path}"]
    )

    assert rc == 1
    assert not _gen_manifest_path(tmp_path).exists()
    assert not _verification_manifest_path(tmp_path).exists()


def test_missing_component_id_returns_2(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(["provenance", "write"])

    assert rc == 2


def test_unrecognized_flag_returns_2(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--bogus-flag"])

    assert rc == 2


def test_malformed_json_on_stdin_returns_2(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))

    rc = provenance_writer.main(["provenance", "write", "comp-foo"])

    assert rc == 2


def test_repo_root_as_separate_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(
        ["provenance", "write", "comp-foo", "--repo-root", str(tmp_path)]
    )

    assert rc == 0
    assert _gen_manifest_path(tmp_path).exists()
    assert _verification_manifest_path(tmp_path).exists()


def test_repo_root_with_no_value_returns_2(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root"])

    assert rc == 2


def test_second_positional_argument_returns_2(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs())))

    rc = provenance_writer.main(["provenance", "write", "comp-foo", "comp-bar"])

    assert rc == 2