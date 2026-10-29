import io
import json
import sys

import provenance_writer


def _valid_inputs_dict():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:abc123",
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "print('hi')"},
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
            "mutation_score": 0.92,
            "overall": "pass",
        },
        "license_scan_result": {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@3.1.0",
            "similarity_score": 0.1,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan_result": {
            "scope": "full",
            "gate_version": "secret_scanner@2.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "k-gram@1.0.0",
        },
    }


def test_main_writes_both_manifests_and_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs_dict())))

    argv = [
        "provenance",
        "write",
        "comp-foo",
        "--repo-root=" + str(tmp_path),
    ]

    result = provenance_writer.main(argv)

    assert result == 0
    assert (tmp_path / "gen" / "foo" / ".provenance.json").exists()
    assert (tmp_path / "verification" / "foo" / ".provenance.json").exists()


def test_main_returns_one_and_writes_nothing_on_missing_input_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs_dict())))

    def _raise(*args, **kwargs):
        raise provenance_writer.MissingInputError("secret_scan_result missing")

    monkeypatch.setattr(provenance_writer, "write_provenance", _raise)

    argv = [
        "provenance",
        "write",
        "comp-foo",
        "--repo-root=" + str(tmp_path),
    ]

    result = provenance_writer.main(argv)

    assert result == 1
    assert list(tmp_path.rglob(".provenance.json")) == []


def test_main_returns_two_when_component_id_missing(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    argv = ["provenance", "write"]

    result = provenance_writer.main(argv)

    assert result == 2


def test_main_returns_two_on_unrecognized_flag(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_valid_inputs_dict())))

    argv = ["provenance", "write", "comp-foo", "--bogus-flag"]

    result = provenance_writer.main(argv)

    assert result == 2


def test_main_returns_two_on_malformed_stdin_json(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))

    argv = ["provenance", "write", "comp-foo"]

    result = provenance_writer.main(argv)

    assert result == 2