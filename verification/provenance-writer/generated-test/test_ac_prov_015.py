# hotdocs-criterion: sha256:dc0c183eec8a8d817b693623a7bc36cb8b05a01b1251ff09c040269411fb3901
import io
import json
import sys
from pathlib import Path

import pytest

import provenance_writer


def _valid_doc():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
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
        },
        "verification_report": {
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
                    "adapter_sha256": "sha256:" + "1" * 64,
                    "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None,
                }
            ],
            "overall": "pass",
        },
        "license_scan_result": {
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
        "secret_scan_result": {
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
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def _manifest_paths(root):
    root = Path(root)
    return (
        root / "gen" / "foo" / ".provenance.json",
        root / "verification" / "foo" / ".provenance.json",
    )


def _nothing_written(root):
    return list(Path(root).iterdir()) == []


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def test_valid_equals_form_returns_0_and_writes_both(tmp_path, workdir, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root=" + str(root)])
    assert rc == 0
    gen_p, ver_p = _manifest_paths(root)
    assert gen_p.is_file()
    assert ver_p.is_file()
    assert _nothing_written(workdir)


def test_valid_space_form_returns_0_and_writes_both(tmp_path, workdir, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root", str(root)])
    assert rc == 0
    gen_p, ver_p = _manifest_paths(root)
    assert gen_p.is_file()
    assert ver_p.is_file()
    assert _nothing_written(workdir)


def test_missing_license_scan_result_returns_1_and_writes_nothing(tmp_path, workdir, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    doc = _valid_doc()
    del doc["license_scan_result"]
    _set_stdin(monkeypatch, json.dumps(doc))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root=" + str(root)])
    assert rc == 1
    gen_p, ver_p = _manifest_paths(root)
    assert not gen_p.exists()
    assert not ver_p.exists()
    assert _nothing_written(root)
    assert _nothing_written(workdir)


def test_missing_component_id_returns_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write"])
    assert rc == 2
    assert _nothing_written(workdir)


def test_bogus_flag_returns_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--bogus-flag"])
    assert rc == 2
    assert _nothing_written(workdir)


def test_malformed_json_returns_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, "{not valid json")
    rc = provenance_writer.main(["provenance", "write", "comp-foo"])
    assert rc == 2
    assert _nothing_written(workdir)


def test_repo_root_without_value_returns_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root"])
    assert rc == 2
    assert _nothing_written(workdir)


def test_second_positional_returns_2(workdir, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "comp-bar"])
    assert rc == 2
    assert _nothing_written(workdir)