import io
import json
import os
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
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {"foo.py": "def bar(x):\n    return x\n"},
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
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _run_main(argv, stdin_text, monkeypatch):
    stream = io.TextIOWrapper(io.BytesIO(stdin_text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stream)
    try:
        rc = provenance_writer.main(list(argv))
    except SystemExit as exc:
        rc = 0 if exc.code is None else exc.code
    return rc


def _manifest_paths(repo):
    return (
        repo / "gen" / "foo" / ".provenance.json",
        repo / "verification" / "foo" / ".provenance.json",
    )


def _all_files(root):
    found = []
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            found.append(os.path.join(dirpath, name))
    return found


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return root


def test_valid_inputs_equals_form_returns_0_and_writes_both(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(repo)],
        json.dumps(_valid_inputs()),
        monkeypatch,
    )
    assert rc == 0
    gen_path, ver_path = _manifest_paths(repo)
    assert gen_path.is_file()
    assert ver_path.is_file()


def test_missing_license_scan_result_returns_1_and_writes_nothing(repo, monkeypatch):
    doc = _valid_inputs()
    del doc["license_scan_result"]
    rc = _run_main(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(repo)],
        json.dumps(doc),
        monkeypatch,
    )
    assert rc == 1
    gen_path, ver_path = _manifest_paths(repo)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert _all_files(repo) == []


def test_missing_component_id_returns_2(repo, monkeypatch):
    rc = _run_main(["provenance", "write"], json.dumps(_valid_inputs()), monkeypatch)
    assert rc == 2


def test_bogus_flag_returns_2(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo", "--bogus-flag"],
        json.dumps(_valid_inputs()),
        monkeypatch,
    )
    assert rc == 2


def test_malformed_json_returns_2(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo"],
        '{"component_id": "comp-foo", "generation_result": {',
        monkeypatch,
    )
    assert rc == 2


def test_valid_inputs_space_form_returns_0_and_writes_both(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo", "--repo-root", str(repo)],
        json.dumps(_valid_inputs()),
        monkeypatch,
    )
    assert rc == 0
    gen_path, ver_path = _manifest_paths(repo)
    assert gen_path.is_file()
    assert ver_path.is_file()


def test_repo_root_without_value_returns_2(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo", "--repo-root"],
        json.dumps(_valid_inputs()),
        monkeypatch,
    )
    assert rc == 2


def test_second_positional_returns_2(repo, monkeypatch):
    rc = _run_main(
        ["provenance", "write", "comp-foo", "comp-bar"],
        json.dumps(_valid_inputs()),
        monkeypatch,
    )
    assert rc == 2