"""AC-PROV-015 (covers R-PROV-015): the `provenance write` CLI's exit codes
and its effect on the filesystem."""

import copy
import io
import json
import sys

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def _valid_document():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "def bar(x):\n    return x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": {
            "component_id": COMPONENT_ID,
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
            "component_id": COMPONENT_ID,
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
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _set_stdin(monkeypatch, text):
    stream = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stream)


def _run(argv):
    try:
        rc = provenance_writer.main(list(argv))
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code
    return rc


def _manifest_paths(repo_root):
    return (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    )


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return repo, cwd


def _files_under(root):
    return [p for p in root.rglob("*") if p.is_file()]


def test_valid_document_with_repo_root_equals_form_returns_0_and_writes_both(dirs, monkeypatch):
    repo, _ = dirs
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write", COMPONENT_ID, f"--repo-root={repo}"])
    assert rc == 0
    gen_manifest, ver_manifest = _manifest_paths(repo)
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()


def test_missing_license_scan_result_returns_1_and_writes_nothing(dirs, monkeypatch):
    repo, cwd = dirs
    doc = copy.deepcopy(_valid_document())
    del doc["license_scan_result"]
    _set_stdin(monkeypatch, json.dumps(doc))
    rc = _run(["provenance", "write", COMPONENT_ID, f"--repo-root={repo}"])
    assert rc == 1
    gen_manifest, ver_manifest = _manifest_paths(repo)
    assert not gen_manifest.exists()
    assert not ver_manifest.exists()
    assert _files_under(repo) == []
    assert _files_under(cwd) == []


def test_missing_component_id_returns_2(dirs, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write"])
    assert rc == 2


def test_unrecognized_flag_returns_2(dirs, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write", COMPONENT_ID, "--bogus-flag"])
    assert rc == 2


def test_malformed_json_on_stdin_returns_2(dirs, monkeypatch):
    _set_stdin(monkeypatch, "{not valid json")
    rc = _run(["provenance", "write", COMPONENT_ID])
    assert rc == 2


def test_valid_document_with_repo_root_space_form_returns_0_and_writes_both(dirs, monkeypatch):
    repo, _ = dirs
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write", COMPONENT_ID, "--repo-root", str(repo)])
    assert rc == 0
    gen_manifest, ver_manifest = _manifest_paths(repo)
    assert gen_manifest.is_file()
    assert ver_manifest.is_file()


def test_repo_root_with_no_value_returns_2(dirs, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write", COMPONENT_ID, "--repo-root"])
    assert rc == 2


def test_second_positional_argument_returns_2(dirs, monkeypatch):
    _set_stdin(monkeypatch, json.dumps(_valid_document()))
    rc = _run(["provenance", "write", COMPONENT_ID, "comp-bar"])
    assert rc == 2