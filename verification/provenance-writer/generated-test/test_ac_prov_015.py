# hotdocs-criterion: sha256:c61e60a71e250b5f6ed1474d9e7d2d51cd82542a7b7f38f43152a6b2dcf07de9
import io
import json
import sys

import pytest

import provenance_writer


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }


def _generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "1" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
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


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "passed",
                "retry_feedback": [],
                "error_category": None,
                "failed_requirements": [],
                "transcript_sha256": None,
            }
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _set_stdin(monkeypatch, text):
    stream = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stream)


def _manifest_paths(root):
    return (
        root / "gen" / "foo" / ".provenance.json",
        root / "verification" / "foo" / ".provenance.json",
    )


def _all_files(root):
    return sorted(p for p in root.rglob("*") if p.is_file())


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_valid_document_with_equals_repo_root_exits_0_and_writes_both(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(workdir)]
    )
    assert code == 0
    gen_path, ver_path = _manifest_paths(workdir)
    assert gen_path.is_file()
    assert ver_path.is_file()


def test_valid_document_with_space_repo_root_exits_0_and_writes_both(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(
        ["provenance", "write", "comp-foo", "--repo-root", str(workdir)]
    )
    assert code == 0
    gen_path, ver_path = _manifest_paths(workdir)
    assert gen_path.is_file()
    assert ver_path.is_file()


def test_missing_license_scan_result_exits_1_and_writes_nothing(workdir, monkeypatch):
    doc = _valid_inputs()
    del doc["license_scan_result"]
    _set_stdin(monkeypatch, json.dumps(doc))
    code = provenance_writer.main(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(workdir)]
    )
    assert code == 1
    gen_path, ver_path = _manifest_paths(workdir)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert _all_files(workdir) == []


def test_no_component_id_exits_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(["provenance", "write"])
    assert code == 2
    assert _all_files(workdir) == []


def test_bogus_flag_exits_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(["provenance", "write", "comp-foo", "--bogus-flag"])
    assert code == 2
    assert _all_files(workdir) == []


def test_malformed_json_exits_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, "{ this is not json")
    code = provenance_writer.main(["provenance", "write", "comp-foo"])
    assert code == 2
    assert _all_files(workdir) == []


def test_repo_root_without_value_exits_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root"])
    assert code == 2
    assert _all_files(workdir) == []


def test_second_positional_exits_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_inputs()))
    code = provenance_writer.main(["provenance", "write", "comp-foo", "comp-bar"])
    assert code == 2
    assert _all_files(workdir) == []