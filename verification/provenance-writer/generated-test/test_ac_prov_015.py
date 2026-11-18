# hotdocs-criterion: sha256:fbc5f2598b45b4f57a30e0f89325ec878f2aae99faf8dcfa2f46ec58c0c31b35
import copy
import io
import json
import sys
from pathlib import Path

import pytest

import provenance_writer


def _generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
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
        "mutation_error": None,
        "overall": "pass",
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


def _valid_doc():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _run(argv, stdin_text, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    try:
        return provenance_writer.main(list(argv))
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code


def _gen_manifest(root):
    return Path(root) / "gen" / "foo" / ".provenance.json"


def _ver_manifest(root):
    return Path(root) / "verification" / "foo" / ".provenance.json"


def _any_manifest(root):
    return [p for p in Path(root).rglob("*") if p.name == ".provenance.json"]


def test_valid_equals_form_returns_0_and_writes_both(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    code = _run(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(repo)],
        json.dumps(_valid_doc()),
        monkeypatch,
    )
    assert code == 0
    assert _gen_manifest(repo).is_file()
    assert _ver_manifest(repo).is_file()
    json.loads(_gen_manifest(repo).read_text(encoding="utf-8"))
    json.loads(_ver_manifest(repo).read_text(encoding="utf-8"))
    assert _any_manifest(cwd) == []


def test_valid_space_form_returns_0_and_writes_both(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    code = _run(
        ["provenance", "write", "comp-foo", "--repo-root", str(repo)],
        json.dumps(_valid_doc()),
        monkeypatch,
    )
    assert code == 0
    assert _gen_manifest(repo).is_file()
    assert _ver_manifest(repo).is_file()
    assert _any_manifest(cwd) == []


def test_missing_license_scan_result_returns_1_and_writes_nothing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    doc = copy.deepcopy(_valid_doc())
    del doc["license_scan_result"]
    assert doc["generation_result"]["files"]
    assert doc["verification_report"] is not None
    code = _run(
        ["provenance", "write", "comp-foo", "--repo-root=" + str(repo)],
        json.dumps(doc),
        monkeypatch,
    )
    assert code == 1
    assert not _gen_manifest(repo).exists()
    assert not _ver_manifest(repo).exists()
    assert _any_manifest(repo) == []
    assert _any_manifest(cwd) == []


def test_no_component_id_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = _run(["provenance", "write"], json.dumps(_valid_doc()), monkeypatch)
    assert code == 2
    assert _any_manifest(tmp_path) == []


def test_bogus_flag_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = _run(
        ["provenance", "write", "comp-foo", "--bogus-flag"],
        json.dumps(_valid_doc()),
        monkeypatch,
    )
    assert code == 2
    assert _any_manifest(tmp_path) == []


def test_malformed_json_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = _run(
        ["provenance", "write", "comp-foo"],
        '{"component_id": "comp-foo", "generation_result": {',
        monkeypatch,
    )
    assert code == 2
    assert _any_manifest(tmp_path) == []


def test_repo_root_without_value_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = _run(
        ["provenance", "write", "comp-foo", "--repo-root"],
        json.dumps(_valid_doc()),
        monkeypatch,
    )
    assert code == 2
    assert _any_manifest(tmp_path) == []


def test_second_positional_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = _run(
        ["provenance", "write", "comp-foo", "comp-bar"],
        json.dumps(_valid_doc()),
        monkeypatch,
    )
    assert code == 2
    assert _any_manifest(tmp_path) == []